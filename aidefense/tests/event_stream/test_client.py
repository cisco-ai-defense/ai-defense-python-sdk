# Copyright 2026 Cisco Systems, Inc. and its affiliates
# SPDX-License-Identifier: Apache-2.0

import asyncio
from concurrent.futures import ThreadPoolExecutor
import gc
import logging
import threading
from types import SimpleNamespace
import weakref

import grpc
import pytest

from aidefense.config import Config
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
    ReasonCode,
    StreamBackpressureError,
    StreamConfigurationError,
    StreamConnectionError,
    StreamContext,
    StreamDirection,
    StreamEvent,
    StreamProtocolError,
    StreamSourceError,
    StreamTimeoutError,
    StreamObserver,
    StrandsBedrockAdapter,
    UnsafeContentError,
)


_UNSET = object()


class FakeChannel:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


class FakeCall:
    END = object()

    def __init__(
        self,
        *,
        decision=None,
        acknowledgement_gate=None,
        unsafe_action=inspect_api.Block,
        redacted_content="",
        batch_responses=False,
        response_batches=None,
    ):
        self.writes = []
        self.cancelled = False
        self.queue = asyncio.Queue()
        self.decision = decision or (lambda event: True)
        self.acknowledgement_gate = acknowledgement_gate
        self.unsafe_action = unsafe_action
        self.redacted_content = redacted_content
        self.batch_responses = batch_responses
        self.response_batches = response_batches
        self.response_sequences = []

    async def write(self, frame):
        self.writes.append(frame)
        if not frame.HasField("events"):
            return
        event = frame.events.events[0]
        if self.batch_responses and event.direction == stream_api.DIRECTION_RESPONSE:
            self.response_sequences.append(event.sequence)
            if not event.is_final:
                return
            # One server result can explicitly acknowledge several
            # individually sent events.
            batches = self.response_batches or [self.response_sequences]
        else:
            batches = [[event.sequence]]
        safe = self.decision(event)
        for sequences in batches:
            await self.queue.put(
                stream_api.InspectionResult(
                    through_sequences=sequences,
                    inspect_response=inspect_api.InspectResponse(
                        is_safe=safe,
                        action=inspect_api.Allow if safe else self.unsafe_action,
                        redacted_content="" if safe else self.redacted_content,
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


class FlowControlledCall(FakeCall):
    """Simulate a write that completes only after its acknowledgement is handled."""

    def __init__(self):
        super().__init__()
        self.acknowledgement_processed = asyncio.Event()

    async def write(self, frame):
        await super().write(frame)
        if frame.HasField("events") and frame.events.events[0].sequence == 1:
            await self.acknowledgement_processed.wait()


class MalformedResultCall(FakeCall):
    async def write(self, frame):
        self.writes.append(frame)
        if frame.HasField("events"):
            await self.queue.put(object())


def harness(*, config=None, call=None, on_decision=None, observer=None):
    channel = FakeChannel()
    call = call or FakeCall()
    stub = SimpleNamespace(InspectEventStream=lambda **_: call)
    client = EventStreamClient(
        config
        or EventStreamConfig(
            endpoint="localhost:443",
            api_key="secret",
            idle_timeout=1,
            absolute_timeout=2,
        ),
        observer=observer,
        on_decision=on_decision,
        channel_factory=lambda _: channel,
        stub_factory=lambda _: stub,
    )
    return client, call, channel


@pytest.mark.asyncio
async def test_debug_logs_cover_stream_lifecycle_without_content(caplog):
    logger = logging.getLogger("aidefense-test-stream-lifecycle")
    logger.setLevel(logging.DEBUG)
    client, _, _ = harness(observer=StreamObserver(logger=logger))

    with caplog.at_level(logging.DEBUG, logger=logger.name):
        assert await collect(
            client.inspect(
                invocation("private-response-marker"),
                context=context(),
                source="vendor",
            )
        ) == [{"data": "private-response-marker"}]

    for reason in (
        ReasonCode.STREAM_STARTED,
        ReasonCode.EVENT_SENT,
        ReasonCode.CHANNEL_OPENING,
        ReasonCode.CHANNEL_READY,
        ReasonCode.WORKERS_STARTED,
        ReasonCode.REQUEST_GATE_WAIT,
        ReasonCode.REQUEST_GATE_OPEN,
        ReasonCode.RESULT_PARSED,
        ReasonCode.ACK_RECEIVED,
        ReasonCode.DECISION_ALLOW,
        ReasonCode.EVENTS_RELEASED,
        ReasonCode.CLEANUP_STARTED,
        ReasonCode.CLEANUP_COMPLETED,
        ReasonCode.STREAM_COMPLETED,
    ):
        assert reason.value in caplog.text
    assert "private-response-marker" not in caplog.text


@pytest.mark.asyncio
async def test_routine_success_logs_are_debug_only_but_metrics_are_preserved(caplog):
    logger = logging.getLogger("aidefense-test-stream-info")
    logger.setLevel(logging.INFO)
    metric_events = []
    metrics = SimpleNamespace(
        record=lambda reason, attributes: metric_events.append((reason, attributes)),
        active_streams=lambda _delta: None,
        latency=lambda _seconds, _outcome: None,
    )
    client, _, _ = harness(observer=StreamObserver(logger=logger, metrics=metrics))

    with caplog.at_level(logging.INFO, logger=logger.name):
        await collect(
            client.inspect(
                invocation("response"),
                context=context(),
                source="vendor",
            )
        )

    metric_reasons = [reason for reason, _ in metric_events]
    for reason in (
        ReasonCode.STREAM_STARTED,
        ReasonCode.EVENT_SENT,
        ReasonCode.ACK_RECEIVED,
        ReasonCode.DECISION_ALLOW,
        ReasonCode.STREAM_COMPLETED,
    ):
        assert reason.value not in caplog.text
        assert reason.value in metric_reasons


def test_client_accepts_chat_inspect_style_api_key_and_config():
    Config._instances = {}
    try:
        runtime_config = Config(
            runtime_base_url="https://inspect.example",
            timeout=1800,
        )

        client = EventStreamClient(api_key="secret", config=runtime_config)

        assert client.config.api_key == "secret"
        assert client.config.endpoint == "inspect.example:443"
        assert client.config.tls is True
        assert client.config.idle_timeout == 30
        assert client.config.absolute_timeout == 1800
    finally:
        Config._instances = {}


def test_chat_inspect_style_custom_http_url_disables_tls():
    Config._instances = {}
    try:
        client = EventStreamClient(
            api_key="secret",
            config=Config(runtime_base_url="http://localhost:50051", timeout=60),
        )

        assert client.config.endpoint == "localhost:50051"
        assert client.config.tls is False
    finally:
        Config._instances = {}


def context():
    return StreamContext(
        session_id="session",
        request_id="request",
        conversation_id="conversation",
    )


def test_event_frame_serializes_all_server_required_fields():
    """Guard against emitting an envelope whose nested event has default fields."""

    wire = EventStreamClient._event_frame(
        event("prompt", StreamDirection.REQUEST, message_id="message-1"),
        sequence=1,
        source="strands-agentcore",
        is_final=False,
    )
    round_trip = stream_api.InspectionEvent.FromString(wire.SerializeToString())

    assert round_trip.message_id == "message-1"
    assert round_trip.sequence == 1
    assert round_trip.source == "strands-agentcore"
    assert round_trip.direction == stream_api.DIRECTION_REQUEST
    assert round_trip.WhichOneof("payload") == "conversation"
    assert len(round_trip.conversation.messages) == 1


def event(text, direction, *, application_event=_UNSET, message_id="message-1"):
    role = "user" if direction is StreamDirection.REQUEST else "assistant"
    return StreamEvent(
        application_event=(
            {"data": text} if application_event is _UNSET else application_event
        ),
        messages=(CanonicalMessage(role=role, content={"text": text}),),
        direction=direction,
        message_id=message_id,
    )


def invocation(*responses):
    return [
        event("safe prompt", StreamDirection.REQUEST, application_event=None),
        *[event(value, StreamDirection.RESPONSE) for value in responses],
    ]


@pytest.mark.asyncio
async def test_each_input_event_is_one_grpc_event_without_content_batching():
    decisions = []
    client, call, channel = harness(on_decision=decisions.append)

    released = await collect(
        client.inspect(
            invocation("hello ", "world"),
            context=context(),
            source="vendor",
        )
    )

    frames = [frame for frame in call.writes if frame.HasField("events")]
    events = [frame.events.events[0] for frame in frames]
    assert all(len(frame.events.events) == 1 for frame in frames)
    assert [item.sequence for item in events] == [1, 2, 3]
    assert [item.conversation.messages[0].content.text for item in events] == [
        "safe prompt",
        "hello ",
        "world",
    ]
    assert [item.is_final for item in events] == [False, False, True]
    assert released == [{"data": "hello "}, {"data": "world"}]
    assert [result.through_sequences for result in decisions] == [(1,), (2,), (3,)]
    assert channel.closed is True


@pytest.mark.asyncio
async def test_one_client_and_adapter_support_concurrent_api_calls():
    channels = []

    def channel_factory(_config):
        channel = FakeChannel()
        channel.call = FakeCall()
        channels.append(channel)
        return channel

    client = EventStreamClient(
        EventStreamConfig(
            endpoint="localhost:443",
            api_key="secret",
            idle_timeout=1,
            absolute_timeout=2,
        ),
        channel_factory=channel_factory,
        stub_factory=lambda channel: SimpleNamespace(
            InspectEventStream=lambda **_: channel.call
        ),
    )
    adapter = StrandsBedrockAdapter()

    async def invoke(name):
        return await collect(
            client.inspect(
                lambda: [{"data": name}],
                request=f"prompt {name}",
                adapter=adapter,
                context=StreamContext(
                    session_id=f"session-{name}",
                    request_id=f"request-{name}",
                    conversation_id=f"conversation-{name}",
                ),
            )
        )

    first, second = await asyncio.gather(invoke("first"), invoke("second"))

    assert first == [{"data": "first"}]
    assert second == [{"data": "second"}]
    assert len(channels) == 2
    assert all(channel.closed for channel in channels)
    message_ids = {
        frame.events.events[0].message_id
        for channel in channels
        for frame in channel.call.writes
        if frame.HasField("events")
    }
    assert len(message_ids) == 2


@pytest.mark.asyncio
async def test_flow_controlled_write_does_not_deadlock_acknowledgement_reader():
    call = FlowControlledCall()

    def acknowledgement_processed(_result):
        call.acknowledgement_processed.set()

    client, _, _ = harness(call=call, on_decision=acknowledgement_processed)

    assert await asyncio.wait_for(
        collect(
            client.inspect(invocation("response"), context=context(), source="vendor")
        ),
        timeout=0.5,
    ) == [{"data": "response"}]


def test_one_client_and_adapter_support_calls_from_multiple_threads():
    channels = []
    channels_lock = threading.Lock()

    def channel_factory(_config):
        channel = FakeChannel()
        channel.call = FakeCall()
        with channels_lock:
            channels.append(channel)
        return channel

    client = EventStreamClient(
        EventStreamConfig(
            endpoint="localhost:443",
            api_key="secret",
            idle_timeout=1,
            absolute_timeout=2,
        ),
        channel_factory=channel_factory,
        stub_factory=lambda channel: SimpleNamespace(
            InspectEventStream=lambda **_: channel.call
        ),
    )
    adapter = StrandsBedrockAdapter()

    def invoke(index):
        async def run():
            return await collect(
                client.inspect(
                    lambda: [{"data": f"answer-{index}"}],
                    request=f"prompt-{index}",
                    adapter=adapter,
                    context=StreamContext(
                        session_id=f"session-{index}",
                        request_id=f"request-{index}",
                        conversation_id=f"conversation-{index}",
                    ),
                )
            )

        return asyncio.run(run())

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(invoke, range(32)))

    assert results == [[{"data": f"answer-{index}"}] for index in range(32)]
    assert len(channels) == 32
    assert all(channel.closed for channel in channels)


@pytest.mark.asyncio
async def test_completed_sessions_release_channels_and_worker_tasks():
    channel_refs = []

    def channel_factory(_config):
        channel = FakeChannel()
        channel.call = FakeCall()
        channel_refs.append(weakref.ref(channel))
        return channel

    client = EventStreamClient(
        EventStreamConfig(
            endpoint="localhost:443",
            api_key="secret",
            idle_timeout=1,
            absolute_timeout=2,
        ),
        channel_factory=channel_factory,
        stub_factory=lambda channel: SimpleNamespace(
            InspectEventStream=lambda **_: channel.call
        ),
    )
    adapter = StrandsBedrockAdapter()

    for index in range(100):
        assert await collect(
            client.inspect(
                lambda: [{"data": f"answer-{index}"}],
                request=f"prompt-{index}",
                adapter=adapter,
                context=StreamContext(
                    session_id=f"session-{index}",
                    request_id=f"request-{index}",
                    conversation_id=f"conversation-{index}",
                ),
            )
        ) == [{"data": f"answer-{index}"}]

    await asyncio.sleep(0)
    gc.collect()

    assert all(reference() is None for reference in channel_refs)
    assert not [
        task
        for task in asyncio.all_tasks()
        if task is not asyncio.current_task()
        and task.get_name().startswith("aidefense-stream-")
        and not task.done()
    ]


@pytest.mark.asyncio
async def test_high_level_adapter_api_accepts_dict_conversation_without_protobufs():
    client, call, _ = harness()

    released = await collect(
        client.inspect(
            [{"data": "answer"}],
            request=[
                {"role": "system", "content": "Be concise."},
                {"role": "user", "content": "Explain ML."},
            ],
            adapter=StrandsBedrockAdapter(),
            context=context(),
        )
    )

    request_event = next(
        frame.events.events[0]
        for frame in call.writes
        if frame.HasField("events")
        and frame.events.events[0].direction == stream_api.DIRECTION_REQUEST
    )
    assert released == [{"data": "answer"}]
    assert [message.role for message in request_event.conversation.messages] == [
        inspect_api.system,
        inspect_api.user,
    ]


@pytest.mark.asyncio
async def test_one_server_result_releases_all_covered_sequences_in_order():
    decisions = []
    call = FakeCall(batch_responses=True)
    client, call, _ = harness(call=call, on_decision=decisions.append)

    released = await collect(
        client.inspect(
            invocation("one", "two", "three"),
            context=context(),
            source="vendor",
        )
    )

    assert released == [{"data": "one"}, {"data": "two"}, {"data": "three"}]
    assert [result.through_sequences for result in decisions] == [
        (1,),
        (2, 3, 4),
    ]
    assert decisions[-1].directions == (
        StreamDirection.RESPONSE,
        StreamDirection.RESPONSE,
        StreamDirection.RESPONSE,
    )


@pytest.mark.asyncio
async def test_sparse_bulk_acknowledgements_release_only_listed_sequences_in_order():
    decisions = []
    call = FakeCall(
        batch_responses=True,
        response_batches=[[2, 4], [3]],
    )
    client, _, _ = harness(call=call, on_decision=decisions.append)

    released = await collect(
        client.inspect(
            invocation("one", "two", "three"),
            context=context(),
            source="vendor",
        )
    )

    assert released == [{"data": "one"}, {"data": "two"}, {"data": "three"}]
    assert [result.through_sequences for result in decisions] == [
        (1,),
        (2, 4),
        (3,),
    ]


@pytest.mark.asyncio
async def test_response_is_not_sent_until_all_request_events_are_acknowledged():
    gate = asyncio.Event()
    call = FakeCall(acknowledgement_gate=gate)
    client, call, _ = harness(call=call)
    task = asyncio.create_task(
        collect(
            client.inspect(invocation("response"), context=context(), source="vendor")
        )
    )

    await asyncio.sleep(0.02)
    sent = [frame.events.events[0] for frame in call.writes if frame.HasField("events")]
    assert [item.direction for item in sent] == [stream_api.DIRECTION_REQUEST]

    gate.set()
    assert await task == [{"data": "response"}]


@pytest.mark.asyncio
async def test_complete_prompt_conversation_is_caller_owned_and_inspected_once():
    decisions = []
    client, call, _ = harness(on_decision=decisions.append)
    prompt = StreamEvent(
        application_event=None,
        messages=(
            CanonicalMessage(role="system", content={"text": "Be concise."}),
            CanonicalMessage(role="user", content={"text": "Explain ML."}),
        ),
        direction=StreamDirection.REQUEST,
        message_id="message-1",
    )

    async def events():
        yield prompt
        assert decisions[0].directions == (StreamDirection.REQUEST,)
        yield event("response", StreamDirection.RESPONSE)

    assert await collect(
        client.inspect(events(), context=context(), source="vendor")
    ) == [{"data": "response"}]
    request = next(
        frame.events.events[0]
        for frame in call.writes
        if frame.HasField("events")
        and frame.events.events[0].direction == stream_api.DIRECTION_REQUEST
    )
    assert [message.role for message in request.conversation.messages] == [
        inspect_api.system,
        inspect_api.user,
    ]


@pytest.mark.asyncio
async def test_blocked_prompt_does_not_pull_or_invoke_response_source():
    call = FakeCall(decision=lambda _event: False)
    client, _, _ = harness(call=call)
    response_started = False

    async def events():
        nonlocal response_started
        yield event("unsafe prompt", StreamDirection.REQUEST, application_event=None)
        response_started = True
        yield event("must not run", StreamDirection.RESPONSE)

    with pytest.raises(UnsafeContentError):
        await collect(client.inspect(events(), context=context(), source="vendor"))

    assert response_started is False


@pytest.mark.asyncio
async def test_high_level_adapter_does_not_call_model_when_prompt_is_blocked():
    call = FakeCall(decision=lambda _event: False)
    client, _, _ = harness(call=call)
    invoked = False

    def response():
        nonlocal invoked
        invoked = True
        return [{"data": "must not run"}]

    with pytest.raises(UnsafeContentError):
        await collect(
            client.inspect(
                response,
                request="unsafe prompt",
                adapter=StrandsBedrockAdapter(),
                context=context(),
            )
        )

    assert invoked is False


@pytest.mark.asyncio
async def test_high_level_adapter_reports_provider_failure_as_source_error():
    client, call, channel = harness()
    provider_error = RuntimeError("bedrock unavailable")

    async def response():
        raise provider_error
        yield  # pragma: no cover - keeps this an async generator

    with pytest.raises(
        StreamSourceError, match="strands-bedrock event source failed"
    ) as error:
        await collect(
            client.inspect(
                response,
                request="safe prompt",
                adapter=StrandsBedrockAdapter(),
                context=context(),
            )
        )

    assert error.value.reason_code == "SOURCE_FAILURE"
    assert error.value.cause is provider_error
    assert call.cancelled is True
    assert channel.closed is True


@pytest.mark.asyncio
async def test_bounded_pending_events_apply_backpressure():
    gate = asyncio.Event()
    call = FakeCall(acknowledgement_gate=gate)
    config = EventStreamConfig(
        endpoint="localhost:443",
        api_key="secret",
        idle_timeout=1,
        absolute_timeout=2,
        max_pending_events=1,
    )
    client, call, _ = harness(config=config, call=call)
    task = asyncio.create_task(
        collect(
            client.inspect(invocation("one", "two"), context=context(), source="vendor")
        )
    )

    await asyncio.sleep(0.02)
    assert len([frame for frame in call.writes if frame.HasField("events")]) == 1
    gate.set()
    assert await task == [{"data": "one"}, {"data": "two"}]


@pytest.mark.asyncio
async def test_unsafe_response_is_not_released():
    call = FakeCall(
        decision=lambda item: item.direction == stream_api.DIRECTION_REQUEST
    )
    client, call, _ = harness(call=call)
    released = []

    with pytest.raises(UnsafeContentError) as error:
        async for item in client.inspect(
            invocation("unsafe"), context=context(), source="vendor"
        ):
            released.append(item)

    assert released == []
    assert error.value.directions == (StreamDirection.RESPONSE,)
    assert call.cancelled is False


@pytest.mark.asyncio
async def test_monitor_violation_releases_original_content():
    call = FakeCall(
        decision=lambda item: item.direction == stream_api.DIRECTION_REQUEST,
        unsafe_action=inspect_api.Allow,
    )
    client, _, _ = harness(call=call)

    assert await collect(
        client.inspect(invocation("monitored"), context=context(), source="vendor")
    ) == [{"data": "monitored"}]


@pytest.mark.asyncio
async def test_batched_redaction_is_emitted_once_not_duplicated_per_sequence():
    call = FakeCall(
        decision=lambda item: item.direction == stream_api.DIRECTION_REQUEST,
        unsafe_action=inspect_api.Redact,
        redacted_content="[REDACTED]",
        batch_responses=True,
    )
    client, _, _ = harness(call=call)

    released = await collect(
        client.inspect(
            invocation("secret one", "secret two"),
            context=context(),
            source="vendor",
        )
    )

    assert released == [{"data": "[REDACTED]"}]


@pytest.mark.asyncio
async def test_idle_timeout_cancels_call_and_closes_channel():
    gate = asyncio.Event()
    call = FakeCall(acknowledgement_gate=gate)
    config = EventStreamConfig(
        endpoint="localhost:443",
        api_key="secret",
        idle_timeout=0.02,
        absolute_timeout=1,
    )
    client, call, channel = harness(config=config, call=call)

    with pytest.raises(StreamTimeoutError):
        await collect(
            client.inspect(invocation("response"), context=context(), source="vendor")
        )

    assert call.cancelled is True
    assert channel.closed is True


@pytest.mark.asyncio
async def test_cancellation_closes_source_call_and_channel_without_orphan_tasks():
    gate = asyncio.Event()
    source_closed = asyncio.Event()
    call = FakeCall(acknowledgement_gate=gate)
    client, call, channel = harness(call=call)

    async def events():
        try:
            yield event("prompt", StreamDirection.REQUEST, application_event=None)
            while True:
                yield event("chunk", StreamDirection.RESPONSE)
                await asyncio.sleep(0.01)
        finally:
            source_closed.set()

    task = asyncio.create_task(
        collect(client.inspect(events(), context=context(), source="vendor"))
    )
    await asyncio.sleep(0.03)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.wait_for(source_closed.wait(), timeout=0.2)
    assert call.cancelled is True
    assert channel.closed is True


@pytest.mark.asyncio
async def test_explicit_generator_close_releases_source_call_and_channel():
    source_closed = asyncio.Event()
    client, call, channel = harness()

    async def events():
        try:
            yield event("prompt", StreamDirection.REQUEST, application_event=None)
            while True:
                yield event("chunk", StreamDirection.RESPONSE)
                await asyncio.sleep(0)
        finally:
            source_closed.set()

    stream = client.inspect(events(), context=context(), source="vendor")
    assert await stream.__anext__() == {"data": "chunk"}
    await stream.aclose()

    await asyncio.wait_for(source_closed.wait(), timeout=0.2)
    assert call.cancelled is True
    assert channel.closed is True


@pytest.mark.asyncio
async def test_channel_factory_failure_is_a_typed_connection_error():
    def fail_channel(_config):
        raise RuntimeError("TLS setup failed")

    client = EventStreamClient(
        EventStreamConfig(endpoint="localhost:443", api_key="secret"),
        channel_factory=fail_channel,
    )

    with pytest.raises(StreamConnectionError, match="connection failed"):
        await collect(
            client.inspect(invocation("response"), context=context(), source="vendor")
        )


@pytest.mark.asyncio
async def test_hanging_channel_cleanup_is_bounded_and_observable(monkeypatch):
    from aidefense.runtime.event_stream import _session as session_module

    class Metrics:
        def __init__(self):
            self.events = []

        def record(self, reason, attributes):
            self.events.append((reason, attributes))

    class HangingChannel(FakeChannel):
        async def close(self):
            await asyncio.Event().wait()

    channel = HangingChannel()
    call = FakeCall()
    stub = SimpleNamespace(InspectEventStream=lambda **_: call)
    metrics = Metrics()
    client = EventStreamClient(
        EventStreamConfig(
            endpoint="localhost:443",
            api_key="secret",
            idle_timeout=1,
            absolute_timeout=2,
        ),
        observer=StreamObserver(metrics=metrics),
        channel_factory=lambda _: channel,
        stub_factory=lambda _: stub,
    )
    monkeypatch.setattr(session_module, "_CLEANUP_TIMEOUT_SECONDS", 0.01)

    assert await asyncio.wait_for(
        collect(
            client.inspect(invocation("response"), context=context(), source="vendor")
        ),
        timeout=0.2,
    ) == [{"data": "response"}]
    assert any(
        reason == ReasonCode.CLEANUP_FAILED.value for reason, _ in metrics.events
    )


@pytest.mark.asyncio
async def test_stream_requires_request_and_response_content():
    client, _, _ = harness()

    with pytest.raises(StreamProtocolError, match="response content"):
        await collect(
            client.inspect(
                [event("prompt", StreamDirection.REQUEST, application_event=None)],
                context=context(),
                source="vendor",
            )
        )


def test_tls_configuration_is_validated():
    with pytest.raises(StreamConfigurationError, match="configured together"):
        EventStreamConfig(
            endpoint="localhost:443",
            api_key="secret",
            client_certificate=b"certificate",
        )
    with pytest.raises(StreamConfigurationError, match="non-empty PEM bytes"):
        EventStreamConfig(
            endpoint="localhost:443",
            api_key="secret",
            root_certificates=b"",
        )
    with pytest.raises(StreamConfigurationError, match="require tls=True"):
        EventStreamConfig(
            endpoint="localhost:443",
            api_key="secret",
            tls=False,
            root_certificates=b"root",
        )


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"endpoint": None}, "endpoint must not be empty"),
        ({"api_key": None}, "api_key is required"),
        ({"tls": "true"}, "tls must be a boolean"),
        ({"idle_timeout": float("nan")}, "timeouts must be finite"),
        ({"max_pending_events": 1.5}, "stream limits must be integers"),
        ({"metadata": [("x-test", "value")]}, "metadata must be a tuple"),
        ({"metadata": (("missing-value",),)}, "key/value string pairs"),
    ],
)
def test_invalid_runtime_configuration_raises_typed_error(override, message):
    values = {"endpoint": "localhost:443", "api_key": "secret", **override}

    with pytest.raises(StreamConfigurationError, match=message):
        EventStreamConfig(**values)


def test_tls_channel_supports_custom_ca_and_server_name(monkeypatch):
    credentials = object()
    secure_channel = object()
    captured = {}

    def fake_credentials(**kwargs):
        captured["credentials"] = kwargs
        return credentials

    def fake_secure_channel(endpoint, supplied, *, options):
        captured["channel"] = (endpoint, supplied, options)
        return secure_channel

    monkeypatch.setattr(grpc, "ssl_channel_credentials", fake_credentials)
    monkeypatch.setattr(grpc.aio, "secure_channel", fake_secure_channel)
    client = EventStreamClient(
        EventStreamConfig(
            endpoint="inspect.example:443",
            api_key="secret",
            root_certificates=b"root",
            tls_server_name="inspect.internal",
        )
    )

    assert client._open_channel() is secure_channel
    assert captured["credentials"] == {
        "root_certificates": b"root",
        "private_key": None,
        "certificate_chain": None,
    }
    assert ("grpc.ssl_target_name_override", "inspect.internal") in captured["channel"][
        2
    ]


def test_tls_channel_supports_optional_enterprise_mtls(monkeypatch):
    credentials = object()
    captured = {}

    def fake_credentials(**kwargs):
        captured.update(kwargs)
        return credentials

    monkeypatch.setattr(grpc, "ssl_channel_credentials", fake_credentials)
    monkeypatch.setattr(grpc.aio, "secure_channel", lambda *_args, **_kwargs: object())
    client = EventStreamClient(
        EventStreamConfig(
            endpoint="private.inspect.example:443",
            api_key="secret",
            root_certificates=b"enterprise-ca-bundle",
            client_certificate=b"client-certificate-chain",
            client_private_key=b"client-private-key",
        )
    )

    client._open_channel()

    assert captured == {
        "root_certificates": b"enterprise-ca-bundle",
        "private_key": b"client-private-key",
        "certificate_chain": b"client-certificate-chain",
    }


@pytest.mark.asyncio
async def test_malformed_server_result_is_a_protocol_failure():
    client, _, _ = harness(call=MalformedResultCall())

    with pytest.raises(StreamProtocolError, match="malformed inspection result"):
        await collect(
            client.inspect(invocation("response"), context=context(), source="vendor")
        )


def test_tls_can_be_disabled_from_environment(monkeypatch):
    monkeypatch.setenv("AI_DEFENSE_EVENT_STREAM_ENDPOINT", "localhost:50051")
    monkeypatch.setenv("AI_DEFENSE_EVENT_STREAM_API_KEY", "top-secret")
    monkeypatch.setenv("AI_DEFENSE_EVENT_STREAM_TLS", "false")

    config = EventStreamConfig.from_env()

    assert config.tls is False
    assert "top-secret" not in repr(config)


@pytest.mark.parametrize(
    ("code", "expected_type", "detail"),
    [
        (grpc.StatusCode.INVALID_ARGUMENT, StreamProtocolError, "no policy"),
        (
            grpc.StatusCode.RESOURCE_EXHAUSTED,
            StreamBackpressureError,
            "retained limit",
        ),
        (
            grpc.StatusCode.PERMISSION_DENIED,
            StreamConnectionError,
            "not authorized",
        ),
    ],
)
def test_grpc_status_preserves_category_and_server_detail(code, expected_type, detail):
    rpc_error = grpc.aio.AioRpcError(code, (), (), details=detail)

    mapped = EventStreamClient._map_error(rpc_error)

    assert isinstance(mapped, expected_type)
    assert detail in str(mapped)


async def collect(iterator):
    return [item async for item in iterator]
