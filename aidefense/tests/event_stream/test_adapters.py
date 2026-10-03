# Copyright 2026 Cisco Systems, Inc. and its affiliates
# SPDX-License-Identifier: Apache-2.0

import asyncio
import threading

import pytest

from aidefense.runtime.event_stream import (
    StreamDirection,
    StrandsAgentCoreAdapter,
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

    assert converted[0].messages[0].content.text == "hello"
    call = converted[-1].messages[0].tool_calls[0]
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
    assert [item.messages[0].content.text for item in converted] == ["one", "two"]


@pytest.mark.asyncio
async def test_strands_raw_and_typed_text_pair_is_emitted_once():
    raw = {
        "event": {
            "contentBlockDelta": {
                "contentBlockIndex": 0,
                "delta": {"text": "Delhi."},
            }
        }
    }
    typed = {"data": "Delhi.", "delta": {"text": "Delhi."}}

    converted = [
        item
        async for item in StrandsEventAdapter().adapt(
            [raw, typed], message_id="message-1"
        )
    ]

    assert [item.messages[0].content.text for item in converted] == ["Delhi."]
    assert converted[0].application_event is typed


@pytest.mark.asyncio
async def test_strands_wrapped_raw_text_without_typed_pair_is_preserved():
    raw = {
        "event": {
            "contentBlockDelta": {
                "contentBlockIndex": 0,
                "delta": {"text": "raw-only"},
            }
        }
    }

    converted = [
        item
        async for item in StrandsEventAdapter().adapt([raw], message_id="message-1")
    ]

    assert [item.messages[0].content.text for item in converted] == ["raw-only"]
    assert converted[0].application_event is raw


@pytest.mark.asyncio
async def test_strands_different_adjacent_text_events_are_not_deduplicated():
    raw = {
        "event": {
            "contentBlockDelta": {
                "contentBlockIndex": 0,
                "delta": {"text": "one"},
            }
        }
    }
    typed = {"data": "two", "delta": {"text": "two"}}

    converted = [
        item
        async for item in StrandsEventAdapter().adapt(
            [raw, typed], message_id="message-1"
        )
    ]

    assert [item.messages[0].content.text for item in converted] == ["one", "two"]


@pytest.mark.asyncio
async def test_adapter_is_reusable_across_concurrent_invocations():
    adapter = StrandsEventAdapter()

    async def convert(message_id, text):
        return [
            item
            async for item in adapter.adapt([{"data": text}], message_id=message_id)
        ]

    first, second = await asyncio.gather(
        convert("message-1", "one"),
        convert("message-2", "two"),
    )

    assert first[0].message_id == "message-1"
    assert first[0].messages[0].content.text == "one"
    assert second[0].message_id == "message-2"
    assert second[0].messages[0].content.text == "two"


@pytest.mark.asyncio
async def test_strands_source_is_created_consumed_and_closed_in_one_task():
    consumer_task = asyncio.current_task()
    source_tasks = []
    closed = asyncio.Event()

    class Source:
        def __init__(self):
            self.sent = False

        def __aiter__(self):
            return self

        async def __anext__(self):
            source_tasks.append(asyncio.current_task())
            if not self.sent:
                self.sent = True
                return {"data": "one"}
            await asyncio.Event().wait()

        async def aclose(self):
            source_tasks.append(asyncio.current_task())
            closed.set()

    def events():
        source_tasks.append(asyncio.current_task())
        return Source()

    stream = StrandsEventAdapter().adapt(events, message_id="message-1")
    converted = await stream.__anext__()
    await stream.aclose()

    assert converted.messages[0].content.text == "one"
    assert closed.is_set()
    assert source_tasks
    assert all(task is source_tasks[0] for task in source_tasks)
    assert source_tasks[0] is not consumer_task


@pytest.mark.asyncio
async def test_strands_agentcore_adapter_accepts_runtime_response_directly():
    adapter = StrandsAgentCoreAdapter()
    response = {"response": [{"chunk": {"bytes": b'{"data":"hello"}'}}]}

    converted = [item async for item in adapter.adapt(response, message_id="message-1")]

    assert converted[0].application_event == {"data": "hello"}
    assert converted[0].messages[0].content.text == "hello"


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
    assert converted[0].messages[0].content.text == "hello"


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

    assert converted.messages[0].model_dump()["content"]["text"] == "hello"
