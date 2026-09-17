# Copyright 2026 Cisco Systems, Inc. and its affiliates
# SPDX-License-Identifier: Apache-2.0

import threading

import pytest

from aidefense.runtime.event_stream import (
    StreamDirection,
    StrandsEventAdapter,
    agentcore_events,
)


@pytest.mark.asyncio
async def test_strands_text_and_tool_events_become_canonical_messages():
    events = [
        {"messageStart": {"role": "assistant"}},
        {
            "contentBlockDelta": {
                "contentBlockIndex": 0,
                "delta": {"text": "hello"},
            }
        },
        {
            "contentBlockStart": {
                "contentBlockIndex": 1,
                "start": {"toolUse": {"toolUseId": "call-1", "name": "lookup"}},
            }
        },
        {
            "contentBlockDelta": {
                "contentBlockIndex": 1,
                "delta": {"toolUse": {"input": '{"q":"safe"}'}},
            }
        },
        {"contentBlockStop": {"contentBlockIndex": 1}},
    ]
    adapter = StrandsEventAdapter(
        message_id="message-1", direction=StreamDirection.RESPONSE
    )

    converted = [item async for item in adapter.adapt(events)]

    assert converted[1].message.content.text == "hello"
    call = converted[-1].message.tool_calls[0]
    assert (call.id_, call.function.name, call.function.arguments_json) == (
        "call-1",
        "lookup",
        '{"q":"safe"}',
    )
    assert all(item.message_id == "message-1" for item in converted)


@pytest.mark.asyncio
async def test_strands_data_chunks_are_supported_without_strands_dependency():
    adapter = StrandsEventAdapter(message_id="message-1")
    converted = [
        item async for item in adapter.adapt([{"data": "one"}, {"data": "two"}])
    ]
    assert [item.message.content.text for item in converted] == ["one", "two"]


@pytest.mark.asyncio
async def test_agentcore_chunk_bytes_are_unwrapped():
    response = {"response": [{"chunk": {"bytes": b'{"data":"hello"}'}}]}
    assert [item async for item in agentcore_events(response)] == [{"data": "hello"}]


@pytest.mark.asyncio
async def test_agentcore_result_message_is_unwrapped_and_canonicalized():
    body = b'{"result":{"role":"assistant","content":[{"text":"hello"}]}}'

    events = [item async for item in agentcore_events(body)]
    converted = [
        item
        async for item in StrandsEventAdapter(
            message_id="message-1", direction=StreamDirection.RESPONSE
        ).adapt(events)
    ]

    assert events == [{"role": "assistant", "content": [{"text": "hello"}]}]
    assert converted[0].message.content.text == "hello"


@pytest.mark.asyncio
async def test_agentcore_sse_response_is_yielded_as_stream_events():
    class StreamingBody:
        def __init__(self):
            self.reader_threads = []
            self.closed = False

        def iter_lines(self, chunk_size):
            self.reader_threads.append(threading.get_ident())
            assert chunk_size == 1024
            yield b"event: message"
            yield b'data: {"data":"hello "}'
            yield b"data: {'data': 'hello ', 'agent': <Agent object>}"
            yield b"data: \"{'data': 'hello ', 'agent': <Agent object>}\""
            yield b""
            yield b'data: {"data":"world"}'
            yield b"data: plain text"
            yield b"data: [DONE]"

        def close(self):
            self.closed = True

    body = StreamingBody()

    response = {
        "contentType": "text/event-stream; charset=utf-8",
        "response": body,
    }

    assert [item async for item in agentcore_events(response)] == [
        {"data": "hello "},
        {"data": "world"},
        "plain text",
    ]
    assert body.reader_threads
    assert all(thread_id != threading.get_ident() for thread_id in body.reader_threads)
    assert body.closed is True


def test_adapter_emits_pydantic_runtime_messages():
    converted = StrandsEventAdapter(message_id="message-1").convert({"data": "hello"})

    assert converted.message.model_dump()["content"]["text"] == "hello"
