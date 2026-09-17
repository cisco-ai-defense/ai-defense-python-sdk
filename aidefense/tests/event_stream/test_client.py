# Copyright 2026 Cisco Systems, Inc. and its affiliates
# SPDX-License-Identifier: Apache-2.0

import asyncio
from types import SimpleNamespace

import pytest

from aidefense.runtime.event_stream._generated.ai_defense.inspection.v1 import (
    inspection_pb2 as inspect_api,
)
from aidefense.runtime.event_stream._generated.ai_defense.inspection_grpc.v1 import (
    inspection_grpc_pb2 as stream_api,
)
from aidefense.runtime.event_stream import (
    CanonicalMessage,
    EventStreamClient,
    EventStreamConfig,
    StreamConfigurationError,
    StreamContext,
    StreamDirection,
    StreamEvent,
    StreamTimeoutError,
    UnsafeContentError,
)


class FakeChannel:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


class FakeCall:
    END = object()

    def __init__(self, decision=None, acknowledgement_gate=None):
        self.writes = []
        self.cancelled = False
        self.queue = asyncio.Queue()
        self.decision = decision or (lambda event: True)
        self.acknowledgement_gate = acknowledgement_gate

    async def write(self, frame):
        self.writes.append(frame)
        if frame.HasField("events"):
            event = frame.events.events[-1]
            safe = self.decision(event)
            await self.queue.put(
                stream_api.InspectionResult(
                    through_sequences=[event.sequence],
                    inspect_response=inspect_api.InspectResponse(
                        is_safe=safe,
                        action=inspect_api.Allow if safe else inspect_api.Block,
                        rules=(
                            []
                            if safe
                            else [inspect_api.RuleObject(rule_name="test-rule")]
                        ),
                    ),
                )
            )

    async def done_writing(self):
        await self.queue.put(self.END)

    def cancel(self):
        self.cancelled = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        value = await self.queue.get()
        if value is self.END:
            raise StopAsyncIteration
        if self.acknowledgement_gate is not None:
            await self.acknowledgement_gate.wait()
        return value


def harness(*, config=None, call=None):
    channel = FakeChannel()
    call = call or FakeCall()
    stub = SimpleNamespace(InspectEventStream=lambda **_: call)
    client = EventStreamClient(
        config
        or EventStreamConfig(
            endpoint="localhost:443",
            api_key="secret",
            batch_interval=0.01,
            token_limit=16,
            overlap_tokens=2,
        ),
        channel_factory=lambda _: channel,
        stub_factory=lambda _: stub,
    )
    return client, call, channel


def context():
    return StreamContext(
        session_id="session",
        request_id="request",
        conversation_id="conversation",
    )


@pytest.mark.asyncio
async def test_safe_agentcore_chunks_are_released_after_acknowledgement():
    client, call, channel = harness()
    chunks = [{"data": "hello "}, {"data": "world"}]

    released = [
        item
        async for item in client.inspect_agentcore(
            "safe prompt", chunks, context=context(), message_id="message-1"
        )
    ]

    assert released == chunks
    event_frames = [frame for frame in call.writes if frame.HasField("events")]
    events = [frame.events.events[0] for frame in event_frames]
    assert [event.sequence for event in events] == list(range(1, len(events) + 1))
    assert {event.message_id for event in events} == {"message-1"}
    assert {event.direction for event in events} == {
        stream_api.DIRECTION_REQUEST,
        stream_api.DIRECTION_RESPONSE,
    }
    assert events[-1].is_final is True
    assert channel.closed is True


@pytest.mark.asyncio
async def test_unsafe_response_is_never_released():
    call = FakeCall(
        decision=lambda event: event.direction == stream_api.DIRECTION_REQUEST
    )
    client, call, _ = harness(call=call)
    released = []

    with pytest.raises(UnsafeContentError) as error:
        async for item in client.inspect_agentcore(
            "safe prompt",
            [{"data": "unsafe output"}],
            context=context(),
            message_id="message-1",
        ):
            released.append(item)

    assert released == []
    assert error.value.decision.is_safe is False
    assert call.cancelled is True


@pytest.mark.asyncio
async def test_overlap_is_inspected_but_not_duplicated_in_application_output():
    client, call, _ = harness()

    async def delayed_chunks():
        yield {"data": "abcdefgh"}
        await asyncio.sleep(0.03)
        yield {"data": "ijklmnop"}

    released = [
        item
        async for item in client.inspect_strands(
            delayed_chunks(), context=context(), message_id="message-1"
        )
    ]

    response_events = [
        frame.events.events[0]
        for frame in call.writes
        if frame.HasField("events")
        and frame.events.events[0].direction == stream_api.DIRECTION_RESPONSE
    ]
    assert released == [{"data": "abcdefgh"}, {"data": "ijklmnop"}]
    assert response_events[0].conversation.messages[0].content.text == "abcdefgh"
    assert (
        response_events[1].conversation.messages[0].content.text == "abcdefghijklmnop"
    )


@pytest.mark.asyncio
async def test_bounded_pending_batches_apply_backpressure():
    gate = asyncio.Event()
    call = FakeCall(acknowledgement_gate=gate)
    config = EventStreamConfig(
        endpoint="localhost:443",
        api_key="secret",
        batch_interval=0.005,
        token_limit=4,
        overlap_tokens=0,
        max_pending_batches=1,
    )
    client, call, _ = harness(config=config, call=call)

    async def chunks():
        yield {"data": "a" * 16}
        await asyncio.sleep(0.02)
        yield {"data": "b" * 16}

    task = asyncio.create_task(
        _collect(client.inspect_strands(chunks(), context=context()))
    )
    await asyncio.sleep(0.03)
    assert len([frame for frame in call.writes if frame.HasField("events")]) == 1
    gate.set()
    assert await task == [{"data": "a" * 16}, {"data": "b" * 16}]


@pytest.mark.asyncio
async def test_idle_timeout_cancels_and_closes_stream():
    gate = asyncio.Event()
    call = FakeCall(acknowledgement_gate=gate)
    config = EventStreamConfig(
        endpoint="localhost:443",
        api_key="secret",
        idle_timeout=0.02,
        absolute_timeout=1,
        batch_interval=0.005,
        token_limit=16,
        overlap_tokens=0,
    )
    client, call, channel = harness(config=config, call=call)

    with pytest.raises(StreamTimeoutError):
        await _collect(client.inspect_strands([{"data": "content"}], context=context()))

    assert call.cancelled is True
    assert channel.closed is True


@pytest.mark.asyncio
async def test_framework_adapter_uses_generic_transport_pipeline():
    class VendorAdapter:
        source = "custom-vendor"

        async def adapt(self, events):
            for event in events:
                yield StreamEvent(
                    application_event=event,
                    message=CanonicalMessage(
                        role="assistant",
                        content={"text": event["token"]},
                    ),
                    direction=StreamDirection.RESPONSE,
                    message_id="vendor-message",
                )

    client, call, _ = harness()
    native = [{"token": "one"}, {"token": "two"}]
    released = [
        item
        async for item in client.inspect(
            native, adapter=VendorAdapter(), context=context()
        )
    ]

    assert released == native
    event = next(frame for frame in call.writes if frame.HasField("events"))
    assert event.events.events[0].source == "custom-vendor"


@pytest.mark.asyncio
async def test_trailing_framework_control_event_is_released_after_decision():
    client, _, _ = harness()

    async def events():
        yield {"data": "safe text"}
        await asyncio.sleep(0.02)
        yield {"messageStop": {"stopReason": "end_turn"}}

    released = [
        item async for item in client.inspect_strands(events(), context=context())
    ]

    assert released == [
        {"data": "safe text"},
        {"messageStop": {"stopReason": "end_turn"}},
    ]


@pytest.mark.asyncio
async def test_cancellation_closes_source_rpc_and_channel_without_orphan_tasks():
    gate = asyncio.Event()
    source_closed = asyncio.Event()
    call = FakeCall(acknowledgement_gate=gate)
    client, call, channel = harness(call=call)

    async def events():
        try:
            while True:
                yield {"data": "safe text"}
                await asyncio.sleep(0.02)
        finally:
            source_closed.set()

    task = asyncio.create_task(
        _collect(client.inspect_strands(events(), context=context()))
    )
    await asyncio.sleep(0.04)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.wait_for(source_closed.wait(), timeout=0.2)
    assert call.cancelled is True
    assert channel.closed is True


def test_invalid_configuration_fails_without_opening_connection():
    with pytest.raises(StreamConfigurationError):
        EventStreamConfig(
            endpoint="localhost:443",
            api_key="",
            token_limit=8,
            overlap_tokens=8,
        )


def test_api_key_is_not_exposed_by_repr(monkeypatch):
    monkeypatch.setenv("AI_DEFENSE_EVENT_STREAM_ENDPOINT", "localhost:443")
    monkeypatch.setenv("AI_DEFENSE_EVENT_STREAM_API_KEY", "top-secret")
    config = EventStreamConfig.from_env()
    assert "top-secret" not in repr(config)


async def _collect(iterator):
    return [item async for item in iterator]
