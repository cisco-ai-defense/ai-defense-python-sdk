# Copyright 2026 Cisco Systems, Inc. and its affiliates
# SPDX-License-Identifier: Apache-2.0

import asyncio
from types import SimpleNamespace

import grpc
import pytest

from aidefense.pydantic.runtime.ai_defense.inspection.v1 import (
    inspection_pb2 as inspect_api,
)
from aidefense.pydantic.runtime.ai_defense.inspection_grpc.v1 import (
    inspection_grpc_pb2 as stream_api,
)
from aidefense.runtime.event_stream import (
    CanonicalMessage,
    EventStreamClient,
    EventStreamConfig,
    StreamConfigurationError,
    StreamBackpressureError,
    StreamConnectionError,
    StreamContext,
    StreamDirection,
    StreamEvent,
    StreamProtocolError,
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

    def __init__(
        self,
        decision=None,
        acknowledgement_gate=None,
        unsafe_action=inspect_api.Block,
        redacted_content=None,
    ):
        self.writes = []
        self.cancelled = False
        self.queue = asyncio.Queue()
        self.decision = decision or (lambda event: True)
        self.acknowledgement_gate = acknowledgement_gate
        self.unsafe_action = unsafe_action
        self.redacted_content = redacted_content

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
                        action=inspect_api.Allow if safe else self.unsafe_action,
                        redacted_content=(
                            "" if safe else (self.redacted_content or "")
                        ),
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


def harness(*, config=None, call=None, on_decision=None):
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
        on_decision=on_decision,
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
    decisions = []
    client, call, channel = harness(on_decision=decisions.append)
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
    assert [result.directions for result in decisions] == [
        (StreamDirection.REQUEST,),
        (StreamDirection.RESPONSE,),
        (StreamDirection.RESPONSE,),
    ]
    assert [result.through_sequences for result in decisions] == [
        (1,),
        (2,),
        (3,),
    ]
    response_events = [
        event for event in events if event.direction == stream_api.DIRECTION_RESPONSE
    ]
    assert len(response_events) == 2
    assert [
        event.conversation.messages[0].content.text for event in response_events
    ] == ["hello ", "hello world"]
    assert events[-1].is_final is True
    assert channel.closed is True


@pytest.mark.asyncio
async def test_agentcore_response_is_invoked_only_after_safe_prompt_acknowledgement():
    decisions = []
    client, _, _ = harness(on_decision=decisions.append)
    prompt = "p" * 120  # Split across multiple request frames.

    async def invoke_response():
        assert len(decisions) == 3
        assert all(
            result.directions == (StreamDirection.REQUEST,) for result in decisions
        )
        return [{"data": "safe response"}]

    released = [
        item
        async for item in client.inspect_agentcore(
            prompt,
            invoke_response,
            context=context(),
            message_id="message-1",
        )
    ]

    assert released == [{"data": "safe response"}]


@pytest.mark.asyncio
async def test_agentcore_generation_wait_does_not_consume_ack_idle_timeout():
    config = EventStreamConfig(
        endpoint="localhost:443",
        api_key="secret",
        idle_timeout=0.02,
        absolute_timeout=1,
        batch_interval=0.005,
        token_limit=16,
        overlap_tokens=0,
    )
    client, _, _ = harness(config=config)

    async def delayed_response():
        await asyncio.sleep(0.06)
        return [{"data": "first streamed response"}]

    released = await _collect(
        client.inspect_agentcore(
            "safe prompt",
            delayed_response,
            context=context(),
            message_id="message-1",
        )
    )

    assert released == [{"data": "first streamed response"}]


@pytest.mark.asyncio
async def test_agentcore_conversation_is_one_prompt_event_and_one_decision():
    decisions = []
    client, call, _ = harness(on_decision=decisions.append)
    conversation = [
        {"role": "system", "content": "Be concise."},
        {"role": "user", "content": "What is ML?"},
        {"role": "assistant", "content": "Learn data."},
        {"role": "user", "content": "Give an example."},
    ]

    released = [
        item
        async for item in client.inspect_agentcore(
            conversation,
            lambda: [{"data": "Spam filtering."}],
            context=context(),
            message_id="message-1",
        )
    ]

    events = [
        frame.events.events[0] for frame in call.writes if frame.HasField("events")
    ]
    request_events = [
        event for event in events if event.direction == stream_api.DIRECTION_REQUEST
    ]
    assert len(request_events) == 1
    assert [message.role for message in request_events[0].conversation.messages] == [
        inspect_api.system,
        inspect_api.user,
        inspect_api.assistant,
        inspect_api.user,
    ]
    assert [
        message.content.text for message in request_events[0].conversation.messages
    ] == [
        "Be concise.",
        "What is ML?",
        "Learn data.",
        "Give an example.",
    ]
    assert [result.directions for result in decisions] == [
        (StreamDirection.REQUEST,),
        (StreamDirection.RESPONSE,),
    ]
    assert released == [{"data": "Spam filtering."}]


@pytest.mark.asyncio
async def test_split_prompt_conversation_does_not_overlap_across_roles():
    client, call, _ = harness()
    conversation = [
        {"role": "assistant", "content": "a" * 48},
        {"role": "user", "content": "latest user message"},
    ]

    await _collect(
        client.inspect_agentcore(
            conversation,
            lambda: [{"data": "response"}],
            context=context(),
            message_id="message-1",
        )
    )

    request_events = [
        frame.events.events[0]
        for frame in call.writes
        if frame.HasField("events")
        and frame.events.events[0].direction == stream_api.DIRECTION_REQUEST
    ]
    assert len(request_events) == 2
    assert request_events[1].conversation.messages[0].role == inspect_api.user
    assert (
        request_events[1].conversation.messages[0].content.text == "latest user message"
    )


@pytest.mark.asyncio
async def test_agentcore_conversation_must_end_with_user_before_opening_stream():
    client, call, channel = harness()

    with pytest.raises(StreamProtocolError, match="end with a user message"):
        await _collect(
            client.inspect_agentcore(
                [
                    {"role": "user", "content": "question"},
                    {"role": "assistant", "content": "answer"},
                ],
                lambda: [{"data": "must not run"}],
                context=context(),
            )
        )

    assert call.writes == []
    assert channel.closed is False


@pytest.mark.asyncio
async def test_unsafe_prompt_does_not_invoke_agentcore_response():
    call = FakeCall(decision=lambda event: False)
    client, _, _ = harness(call=call)
    invoked = False

    async def invoke_response():
        nonlocal invoked
        invoked = True
        return [{"data": "must not be generated"}]

    with pytest.raises(UnsafeContentError) as error:
        await _collect(
            client.inspect_agentcore(
                "unsafe prompt",
                invoke_response,
                context=context(),
                message_id="message-1",
            )
        )

    assert error.value.directions == (StreamDirection.REQUEST,)
    assert invoked is False


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
    assert error.value.directions == (StreamDirection.RESPONSE,)
    assert call.cancelled is False


@pytest.mark.asyncio
async def test_unsafe_unspecified_action_fails_closed():
    call = FakeCall(
        decision=lambda event: event.direction == stream_api.DIRECTION_REQUEST,
        unsafe_action=inspect_api.ActionUnspecified,
    )
    client, _, _ = harness(call=call)

    with pytest.raises(UnsafeContentError):
        await _collect(
            client.inspect_agentcore(
                "safe prompt",
                [{"data": "unsafe output"}],
                context=context(),
                message_id="message-1",
            )
        )


@pytest.mark.asyncio
async def test_monitor_violation_releases_content_and_continues():
    call = FakeCall(
        decision=lambda event: event.direction == stream_api.DIRECTION_REQUEST,
        unsafe_action=inspect_api.Allow,
    )
    client, _, _ = harness(call=call)
    chunks = [{"data": "monitored one"}, {"data": "monitored two"}]

    released = await _collect(
        client.inspect_agentcore(
            "safe prompt",
            chunks,
            context=context(),
            message_id="message-1",
        )
    )

    assert released == chunks


@pytest.mark.asyncio
async def test_redact_violation_releases_only_redacted_content_and_continues():
    call = FakeCall(
        decision=lambda event: event.direction == stream_api.DIRECTION_REQUEST,
        unsafe_action=inspect_api.Redact,
        redacted_content="[REDACTED]",
    )
    client, _, _ = harness(call=call)

    released = await _collect(
        client.inspect_agentcore(
            "safe prompt",
            [{"data": "secret one"}, {"data": "secret two"}],
            context=context(),
            message_id="message-1",
        )
    )

    assert released == [
        {"data": "[REDACTED]"},
        {"data": "[REDACTED]"},
    ]


@pytest.mark.asyncio
async def test_redact_without_replacement_drops_chunk_but_keeps_stream_open():
    decisions = iter([True, False, True])
    call = FakeCall(
        decision=lambda _event: next(decisions),
        unsafe_action=inspect_api.Redact,
    )
    client, _, _ = harness(call=call)

    released = await _collect(
        client.inspect_agentcore(
            "safe prompt",
            [{"data": "drop me"}, {"data": "safe next chunk"}],
            context=context(),
            message_id="message-1",
        )
    )

    assert released == [{"data": "safe next chunk"}]


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


@pytest.mark.parametrize(
    ("code", "expected_type", "detail"),
    [
        (
            grpc.StatusCode.INVALID_ARGUMENT,
            StreamProtocolError,
            "connection has no policy",
        ),
        (
            grpc.StatusCode.FAILED_PRECONDITION,
            StreamProtocolError,
            "event received after final event",
        ),
        (
            grpc.StatusCode.RESOURCE_EXHAUSTED,
            StreamBackpressureError,
            "retained content limit exceeded",
        ),
        (
            grpc.StatusCode.PERMISSION_DENIED,
            StreamConnectionError,
            "connection key is not authorized",
        ),
    ],
)
def test_grpc_status_preserves_failure_category_and_server_detail(
    code, expected_type, detail
):
    rpc_error = grpc.aio.AioRpcError(code, (), (), details=detail)

    mapped = EventStreamClient._map_error(rpc_error)

    assert isinstance(mapped, expected_type)
    assert detail in str(mapped)


async def _collect(iterator):
    return [item async for item in iterator]
