# Copyright 2026 Cisco Systems, Inc. and its affiliates
# SPDX-License-Identifier: Apache-2.0

"""High-level, fail-closed bidirectional gRPC inspection client."""

from __future__ import annotations

import asyncio
import inspect
import logging
import math
import time
import uuid
from dataclasses import dataclass, replace
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)

import grpc  # type: ignore[import-untyped]
from google.protobuf.json_format import (  # type: ignore[import-untyped]
    MessageToDict,
    ParseDict,
)

from aidefense.pydantic.runtime.ai_defense.inspection.v1 import (
    inspection_pydantic as runtime_chat,
)
from aidefense.pydantic.runtime.ai_defense.inspection_grpc.v1 import (
    inspection_grpc_pydantic as runtime_stream,
)
from aidefense.pydantic.runtime.ai_defense.inspection_grpc.v1 import (
    inspection_grpc_pb2 as stream_api,
)
from aidefense.runtime.models import InspectionConfig

from ._grpc import InspectionServiceStub
from .adapters import EventStreamAdapter, StrandsEventAdapter, agentcore_events
from .exceptions import (
    EventStreamError,
    StreamCancelledError,
    StreamBackpressureError,
    StreamConfigurationError,
    StreamConnectionError,
    StreamProtocolError,
    StreamTimeoutError,
    UnsafeContentError,
)
from .models import (
    CanonicalMessage,
    EventStreamConfig,
    SourceRange,
    StreamContext,
    StreamDecision,
    StreamDirection,
    StreamEvent,
    StreamInspectionResult,
)
from .observability import ReasonCode, StreamObserver


API_KEY_HEADER = "x-cisco-ai-defense-api-key"
REQUEST_ID_HEADER = "x-aidefense-request-id"
_END = object()
_ACK = object()
_SENT = object()


def _action_name(action: str) -> str:
    """Normalize generated enum strings such as ``Action.Block``."""

    return action.rsplit(".", 1)[-1].lower()


def _with_redacted_text(application_event: Any, text: str) -> Optional[Any]:
    """Preserve a common vendor event shape while replacing only its text."""

    if isinstance(application_event, bytes):
        return text.encode("utf-8")
    if isinstance(application_event, str):
        return text
    if not isinstance(application_event, dict):
        return None

    updated = dict(application_event)
    wrapped = updated.get("event")
    if isinstance(wrapped, dict):
        redacted_wrapped = _with_redacted_text(wrapped, text)
        if redacted_wrapped is None:
            return None
        updated["event"] = redacted_wrapped
        return updated

    delta_event = updated.get("contentBlockDelta")
    if isinstance(delta_event, dict):
        updated_delta_event = dict(delta_event)
        delta = updated_delta_event.get("delta")
        if isinstance(delta, dict) and isinstance(delta.get("text"), str):
            updated_delta = dict(delta)
            updated_delta["text"] = text
            updated_delta_event["delta"] = updated_delta
            updated["contentBlockDelta"] = updated_delta_event
            return updated

    for key in ("data", "text", "result", "response", "completion", "content"):
        if isinstance(updated.get(key), str):
            updated[key] = text
            return updated
    return None


@dataclass
class _DirectionBarrier:
    """Hold a later direction until all earlier-direction frames are safe."""

    direction: StreamDirection
    released: asyncio.Event


@dataclass
class _Batch:
    events: List[StreamEvent]
    token_count: int

    @property
    def semantic_event(self) -> StreamEvent:
        return next(event for event in self.events if event.message is not None)

    @property
    def direction(self) -> StreamDirection:
        return self.semantic_event.direction

    @property
    def message_id(self) -> str:
        return self.semantic_event.message_id

    @property
    def has_content(self) -> bool:
        return any(event.message is not None for event in self.events)

    @property
    def direction_barrier(self) -> Optional[_DirectionBarrier]:
        if len(self.events) != 1:
            return None
        candidate = self.events[0].application_event
        return candidate if isinstance(candidate, _DirectionBarrier) else None


@dataclass
class _Pending:
    sequence: int
    application_events: List[Any]
    ranges: Tuple[SourceRange, ...]
    direction: StreamDirection


def _token_count(message: Optional[CanonicalMessage]) -> int:
    if message is None:
        return 0
    size = len(message.content.text or "") if message.content is not None else 0
    size += sum(
        len(call.function.name) + len(call.function.arguments_json)
        for call in message.tool_calls
        if call.function is not None
    )
    return max(1, math.ceil(size / 4)) if size else max(1, len(message.tool_calls))


def _overlap_identity(message: CanonicalMessage) -> Tuple[Any, ...]:
    """Keep overlap within one compatible role/tool message identity."""

    tool_calls = tuple(
        (
            call.id_,
            call.type_,
            call.function.name if call.function is not None else "",
            call.function.arguments_json if call.function is not None else "",
        )
        for call in message.tool_calls
    )
    function_call = (
        (
            message.function_call.name,
            message.function_call.arguments,
        )
        if message.function_call is not None
        else None
    )
    return (
        message.role,
        message.tool_call_id,
        message.name,
        tool_calls,
        function_call,
    )


def _prompt_messages(
    prompt: Union[str, Sequence[CanonicalMessage], Sequence[Dict[str, Any]]],
) -> Tuple[CanonicalMessage, ...]:
    """Normalize a string or canonical conversation without logging its content."""

    if isinstance(prompt, str):
        if not prompt:
            raise StreamProtocolError("AgentCore prompt must be a non-empty string")
        return (
            CanonicalMessage(
                role=runtime_chat.Role.user,
                content=runtime_chat.MessageContent(text=prompt),
            ),
        )
    if not isinstance(prompt, Sequence) or isinstance(prompt, (bytes, bytearray)):
        raise StreamProtocolError(
            "AgentCore prompt must be a string or canonical message sequence"
        )
    if not prompt:
        raise StreamProtocolError("AgentCore conversation must not be empty")

    messages = []
    for value in prompt:
        try:
            if isinstance(value, CanonicalMessage):
                message = value.model_copy(deep=True)
            elif isinstance(value, dict):
                data = dict(value)
                if isinstance(data.get("content"), str):
                    data["content"] = {"text": data["content"]}
                message = CanonicalMessage.model_validate(data)
            else:
                raise TypeError
        except (TypeError, ValueError) as exc:
            raise StreamProtocolError(
                "AgentCore conversation contains an invalid canonical message"
            ) from exc
        if message.role in (None, runtime_chat.Role.invalid_role):
            raise StreamProtocolError(
                "AgentCore conversation messages must have a valid role"
            )
        messages.append(message)

    if messages[-1].role != runtime_chat.Role.user:
        raise StreamProtocolError(
            "AgentCore prompt conversation must end with a user message"
        )
    return tuple(messages)


def _boundary(batch: _Batch, event: StreamEvent) -> bool:
    if not batch.has_content:
        return False
    return (
        batch.direction is not event.direction or batch.message_id != event.message_id
    )


async def _batches(
    events: AsyncIterator[StreamEvent], config: EventStreamConfig
) -> AsyncIterator[_Batch]:
    """Batch an arbitrary async source without cancelling its __anext__ calls."""

    queue: asyncio.Queue = asyncio.Queue(maxsize=config.input_queue_size)
    producer_error: List[BaseException] = []
    producer_done = asyncio.Event()

    async def produce() -> None:
        try:
            async for event in events:
                message = event.message
                limit = config.token_limit - config.overlap_tokens
                if message is not None and _token_count(message) > limit:
                    text = (
                        message.content.text
                        if message.content is not None
                        and message.content.text is not None
                        else ""
                    )
                    if message.tool_calls or not text:
                        raise StreamProtocolError(
                            "one structured event exceeds token_limit and cannot be split safely"
                        )
                    width = limit * 4
                    pieces = [
                        text[index : index + width]
                        for index in range(0, len(text), width)
                    ]
                    for index, piece in enumerate(pieces):
                        await queue.put(
                            replace(
                                event,
                                application_event=(
                                    event.application_event
                                    if index == len(pieces) - 1
                                    else None
                                ),
                                message=message.model_copy(
                                    update={
                                        "content": runtime_chat.MessageContent(
                                            text=piece
                                        )
                                    }
                                ),
                            )
                        )
                else:
                    await queue.put(event)
        except Exception as exc:
            producer_error.append(exc)
        finally:
            producer_done.set()
            try:
                queue.put_nowait(_END)
            except asyncio.QueueFull:
                # The consumer sees producer_done after draining the queue.
                pass

    producer = asyncio.create_task(produce(), name="aidefense-stream-input")
    current: Optional[_Batch] = None
    batch_deadline: Optional[float] = None
    try:
        while True:
            if producer_done.is_set() and queue.empty():
                if current is not None:
                    yield current
                if producer_error:
                    raise producer_error[0]
                break
            if (
                current is not None
                and current.has_content
                and batch_deadline is not None
                and time.monotonic() >= batch_deadline
            ):
                yield current
                current = None
                batch_deadline = None
                continue
            try:
                timeout = (
                    max(0.0, batch_deadline - time.monotonic())
                    if batch_deadline is not None
                    else None
                )
                if timeout is None:
                    item = await queue.get()
                else:
                    item = await asyncio.wait_for(queue.get(), timeout=timeout)
            except asyncio.TimeoutError:
                if current is not None and current.has_content:
                    yield current
                    current = None
                    batch_deadline = None
                continue

            if item is _END:
                if current is not None:
                    yield current
                if producer_error:
                    raise producer_error[0]
                break

            event = item
            if isinstance(event.application_event, _DirectionBarrier):
                if current is not None:
                    yield current
                    current = None
                    batch_deadline = None
                yield _Batch([event], 0)
                continue
            tokens = _token_count(event.message)
            if current is None:
                current = _Batch([event], tokens)
                batch_deadline = time.monotonic() + config.batch_interval
                continue
            if len(current.events) >= config.input_queue_size:
                if not current.has_content:
                    raise StreamBackpressureError(
                        "too many framework control events without inspectable content"
                    )
                yield current
                current = _Batch([event], tokens)
                batch_deadline = time.monotonic() + config.batch_interval
                continue
            # Preserve a complete request-side conversation in one frame when
            # limits permit, but never coalesce separate streamed response
            # events. Each response chunk receives its own server decision and
            # is released independently.
            separate_response_event = (
                current.has_content
                and current.direction is StreamDirection.RESPONSE
                and event.message is not None
            )
            if (
                separate_response_event
                or _boundary(current, event)
                or (
                    current.has_content
                    and event.message is not None
                    and current.token_count + tokens
                    > config.token_limit - config.overlap_tokens
                )
            ):
                yield current
                current = _Batch([event], tokens)
                batch_deadline = time.monotonic() + config.batch_interval
            else:
                current.events.append(event)
                current.token_count += tokens
    finally:
        if not producer.done():
            producer.cancel()
        await asyncio.gather(producer, return_exceptions=True)


class EventStreamClient:
    """Inspect Strands/AgentCore streams and only yield acknowledged-safe events."""

    def __init__(
        self,
        config: EventStreamConfig,
        *,
        observer: Optional[StreamObserver] = None,
        on_decision: Optional[Callable[[StreamInspectionResult], Any]] = None,
        channel_factory: Optional[Callable[..., Any]] = None,
        stub_factory: Callable[[Any], Any] = InspectionServiceStub,
    ) -> None:
        self.observer = observer or StreamObserver()
        # Revalidation is intentional: mutated/fake dataclasses cannot defer an
        # invalid setting until after a network write.
        try:
            config.validate()
        except StreamConfigurationError:
            self.observer.event(ReasonCode.CONFIGURATION_INVALID, level=logging.ERROR)
            raise
        self.config = config
        self._on_decision = on_decision
        self._channel_factory = channel_factory
        self._stub_factory = stub_factory

    @classmethod
    def from_env(
        cls,
        *,
        observer: Optional[StreamObserver] = None,
        on_decision: Optional[Callable[[StreamInspectionResult], Any]] = None,
        **overrides: Any,
    ) -> "EventStreamClient":
        """Build a client from secure runtime environment configuration."""

        resolved_observer = observer or StreamObserver()
        try:
            config = EventStreamConfig.from_env(**overrides)
        except StreamConfigurationError:
            resolved_observer.event(
                ReasonCode.CONFIGURATION_INVALID, level=logging.ERROR
            )
            raise
        return cls(
            config,
            observer=resolved_observer,
            on_decision=on_decision,
        )

    async def inspect_strands(
        self,
        events: Any,
        *,
        context: StreamContext,
        direction: StreamDirection = StreamDirection.RESPONSE,
        message_id: Optional[str] = None,
        source: str = "strands",
        inspection_config: Optional[InspectionConfig] = None,
    ) -> AsyncIterator[Any]:
        """Yield original Strands events only after AI Defense allows them."""

        identifier = message_id or str(uuid.uuid4())
        adapter = StrandsEventAdapter(
            message_id=identifier,
            direction=direction,
            source=source,
            max_tool_argument_chars=(
                self.config.token_limit - self.config.overlap_tokens
            )
            * 4,
        )
        async for event in self.inspect(
            events,
            adapter=adapter,
            context=context,
            inspection_config=inspection_config,
        ):
            yield event

    async def inspect(
        self,
        events: Any,
        *,
        adapter: EventStreamAdapter,
        context: StreamContext,
        source: Optional[str] = None,
        inspection_config: Optional[InspectionConfig] = None,
    ) -> AsyncIterator[Any]:
        """Inspect any vendor/framework stream through an adapter."""

        resolved_source = source or adapter.source
        async for event in self.inspect_events(
            adapter.adapt(events),
            context=context,
            source=resolved_source,
            inspection_config=inspection_config,
        ):
            yield event

    async def inspect_agentcore(
        self,
        prompt: Union[
            str,
            Sequence[CanonicalMessage],
            Sequence[Dict[str, Any]],
        ],
        response: Any,
        *,
        context: StreamContext,
        message_id: Optional[str] = None,
        source: str = "strands-agentcore",
        inspection_config: Optional[InspectionConfig] = None,
    ) -> AsyncIterator[Any]:
        """Inspect a prompt before lazily invoking or consuming its AgentCore response.

        ``prompt`` may be text or the complete canonical conversation through
        its latest user message. Conversation messages are sent in one request
        event whenever configured limits permit. ``response`` may be an
        invocation result, awaitable, or zero-argument callable. Use a callable
        to ensure the model is not invoked until the complete prompt has been
        acknowledged as safe.
        """

        prompt_messages = _prompt_messages(prompt)
        identifier = message_id or str(uuid.uuid4())
        adapter = StrandsEventAdapter(
            message_id=identifier,
            direction=StreamDirection.RESPONSE,
            source=source,
            max_tool_argument_chars=(
                self.config.token_limit - self.config.overlap_tokens
            )
            * 4,
        )

        async def conversation() -> AsyncIterator[StreamEvent]:
            prompt_barrier = _DirectionBarrier(
                direction=StreamDirection.REQUEST,
                released=asyncio.Event(),
            )
            for message in prompt_messages:
                yield StreamEvent(
                    application_event=None,
                    message=message,
                    direction=StreamDirection.REQUEST,
                    message_id=identifier,
                )
            yield StreamEvent(
                application_event=prompt_barrier,
                message=None,
                direction=StreamDirection.REQUEST,
                message_id=identifier,
            )
            # Do not invoke or consume the model response until every prompt
            # frame has received a safe acknowledgement.
            await prompt_barrier.released.wait()
            async for item in adapter.adapt(agentcore_events(response)):
                yield item

        async for event in self.inspect_events(
            conversation(),
            context=context,
            source=source,
            inspection_config=inspection_config,
        ):
            yield event

    async def inspect_events(
        self,
        events: AsyncIterator[StreamEvent],
        *,
        context: StreamContext,
        source: str,
        inspection_config: Optional[InspectionConfig] = None,
    ) -> AsyncIterator[Any]:
        """Inspect canonical events; application events remain locally buffered."""

        context.validate()
        if not source.strip():
            raise StreamProtocolError("source must not be empty")

        channel = self._open_channel()
        call: Optional[Any] = None
        tasks: List[asyncio.Task] = []
        output: asyncio.Queue = asyncio.Queue(maxsize=self.config.input_queue_size)
        pending: Dict[int, _Pending] = {}
        direction_barriers: List[_DirectionBarrier] = []
        pending_lock = asyncio.Lock()
        capacity = asyncio.Semaphore(self.config.max_pending_batches)
        sequence_lock = asyncio.Lock()
        next_sequence = 0
        offsets: Dict[Tuple[str, StreamDirection], int] = {}
        overlap: Dict[Tuple[str, StreamDirection], Tuple[Tuple[Any, ...], str]] = {}
        terminal = asyncio.Event()
        half_close_started = asyncio.Event()
        started = time.monotonic()
        outcome = "failure"
        active_stream_counted = False
        # A Block acknowledgement is a server-owned terminal condition. Once
        # it arrives the orchestrator closes the RPC, so cleanup must not race
        # it by issuing a client cancellation.
        server_blocked = False
        stream_correlation_id = uuid.uuid4().hex

        def observed(**attributes: Any) -> Dict[str, Any]:
            return {
                "stream_correlation_id": stream_correlation_id,
                **attributes,
            }

        async def sequence() -> int:
            nonlocal next_sequence
            async with sequence_lock:
                next_sequence += 1
                return next_sequence

        try:
            stub = self._stub_factory(channel)
            metadata = [
                (API_KEY_HEADER, self.config.api_key),
                (REQUEST_ID_HEADER, context.request_id),
                *self.config.metadata,
            ]
            call = stub.InspectEventStream(
                metadata=metadata, timeout=self.config.absolute_timeout
            )
            await call.write(self._start_frame(context, inspection_config))
            self.observer.active_streams(1)
            active_stream_counted = True
            self.observer.event(ReasonCode.STREAM_STARTED, attributes=observed())

            async def writer() -> None:
                sent_events = 0
                sent_bytes = 0
                previous: Optional[_Batch] = None
                leading_controls: List[StreamEvent] = []
                try:
                    async for batch in _batches(events, self.config):
                        barrier = batch.direction_barrier
                        if barrier is not None:
                            if previous is None:
                                raise StreamProtocolError(
                                    "direction barrier has no preceding content"
                                )
                            event_count, byte_count = await send(
                                previous,
                                False,
                                sent_bytes,
                                direction_barrier=barrier,
                            )
                            sent_events += event_count
                            sent_bytes += byte_count
                            previous = None
                            continue
                        if not batch.has_content:
                            if previous is not None:
                                previous.events.extend(batch.events)
                            else:
                                leading_controls.extend(batch.events)
                            continue
                        if leading_controls:
                            batch.events[:0] = leading_controls
                            leading_controls = []
                        if previous is not None:
                            event_count, byte_count = await send(
                                previous, False, sent_bytes
                            )
                            sent_events += event_count
                            sent_bytes += byte_count
                        previous = batch
                    if previous is None:
                        raise StreamProtocolError(
                            "stream contained no inspectable content"
                        )
                    event_count, byte_count = await send(previous, True, sent_bytes)
                    sent_events += event_count
                    sent_bytes += byte_count
                    half_close_started.set()
                    await call.done_writing()
                except Exception as exc:
                    if not terminal.is_set():
                        await output.put(self._map_error(exc))
                    terminal.set()
                    call.cancel()

            async def send(
                batch: _Batch,
                is_final: bool,
                already_sent_bytes: int,
                *,
                direction_barrier: Optional[_DirectionBarrier] = None,
            ) -> Tuple[int, int]:
                if capacity.locked():
                    self.observer.event(
                        ReasonCode.BACKPRESSURE_WAIT, attributes=observed()
                    )
                await capacity.acquire()
                seq = await sequence()
                if seq > self.config.max_stream_events:
                    capacity.release()
                    raise StreamProtocolError("stream exceeds the server event limit")
                proto_event, retained, ranges = self._event_frame(
                    batch, seq, source, is_final, offsets, overlap
                )
                frame = stream_api.InspectStreamRequest(
                    events=stream_api.InspectStreamEvents(events=[proto_event])
                )
                frame_bytes = frame.ByteSize()
                if already_sent_bytes + frame_bytes > self.config.max_stream_bytes:
                    capacity.release()
                    raise StreamProtocolError(
                        "stream exceeds the server retention limit"
                    )
                try:
                    # Keep the acknowledgement reader behind this lock until
                    # write() returns. Otherwise a very fast acknowledgement
                    # could release capacity before a failed write cleans up.
                    async with pending_lock:
                        pending[seq] = _Pending(seq, retained, ranges, batch.direction)
                        if direction_barrier is not None:
                            direction_barriers.append(direction_barrier)
                        with self.observer.span(
                            "aidefense.stream.send",
                            observed(sequence=seq, direction=batch.direction.value),
                        ):
                            await call.write(frame)
                except BaseException:
                    async with pending_lock:
                        pending.pop(seq, None)
                        if direction_barrier is not None:
                            try:
                                direction_barriers.remove(direction_barrier)
                            except ValueError:
                                pass
                    capacity.release()
                    raise
                self.observer.event(
                    ReasonCode.BATCH_SENT,
                    attributes=observed(sequence=seq, direction=batch.direction.value),
                )
                # Wake the consumer so idle_timeout starts when a frame is
                # actually awaiting acknowledgement, not while an upstream
                # model is still producing its next chunk.
                await output.put(_SENT)
                return 1, frame_bytes

            async def reader() -> None:
                nonlocal server_blocked
                try:
                    async for result in call:
                        runtime_result = runtime_stream.InspectionResult.model_validate(
                            MessageToDict(
                                result,
                                preserving_proto_field_name=True,
                            )
                        )
                        through = tuple(runtime_result.through_sequences)
                        if not through:
                            raise StreamProtocolError(
                                "server acknowledgement has no through_sequences"
                            )
                        ack = max(through)
                        if runtime_result.inspect_response is None:
                            raise StreamProtocolError(
                                "server acknowledgement has no inspect_response"
                            )
                        decision = self._decision(runtime_result.inspect_response)
                        async with pending_lock:
                            if ack > next_sequence:
                                raise StreamProtocolError(
                                    "server acknowledged a sequence that was not sent"
                                )
                            ready_keys = sorted(key for key in pending if key <= ack)
                            if not ready_keys:
                                raise StreamProtocolError(
                                    "server acknowledgement did not advance the stream"
                                )
                            ready = [pending.pop(key) for key in ready_keys]
                        for _ in ready:
                            capacity.release()
                        inspection_result = StreamInspectionResult(
                            decision=decision,
                            through_sequences=tuple(item.sequence for item in ready),
                            directions=tuple(item.direction for item in ready),
                        )
                        if self._on_decision is not None:
                            callback_result = self._on_decision(inspection_result)
                            if inspect.isawaitable(callback_result):
                                await callback_result
                        with self.observer.span(
                            "aidefense.stream.acknowledgement",
                            observed(through_sequence=ack),
                        ):
                            self.observer.event(
                                ReasonCode.ACK_RECEIVED,
                                attributes=observed(through_sequence=ack),
                            )
                        action = _action_name(decision.action)
                        if action == "block" or (
                            not decision.is_safe and action not in {"allow", "redact"}
                        ):
                            with self.observer.span(
                                "aidefense.stream.block",
                                observed(through_sequence=ack),
                            ):
                                self.observer.event(
                                    ReasonCode.DECISION_BLOCK,
                                    level=logging.WARNING,
                                    attributes=observed(through_sequence=ack),
                                )
                            server_blocked = True
                            raise UnsafeContentError(
                                "AI Defense blocked streamed content before release",
                                decision=decision,
                                sequences=inspection_result.through_sequences,
                                directions=inspection_result.directions,
                            )
                        async with pending_lock:
                            for barrier in tuple(direction_barriers):
                                if any(
                                    item.direction is barrier.direction
                                    for item in pending.values()
                                ):
                                    continue
                                direction_barriers.remove(barrier)
                                barrier.released.set()
                        with self.observer.span(
                            "aidefense.stream.decision",
                            observed(
                                through_sequence=ack,
                                is_safe=decision.is_safe,
                                action=decision.action,
                            ),
                        ):
                            self.observer.event(
                                ReasonCode.DECISION_ALLOW,
                                attributes=observed(through_sequence=ack),
                            )
                        await output.put(_ACK)
                        for item in ready:
                            for application_event in item.application_events:
                                if application_event is not None:
                                    if action == "redact":
                                        if decision.redacted_content:
                                            redacted_event = _with_redacted_text(
                                                application_event,
                                                decision.redacted_content,
                                            )
                                            if redacted_event is not None:
                                                await output.put(redacted_event)
                                    else:
                                        # Monitor policies report a violation
                                        # but intentionally allow the original
                                        # application event to continue.
                                        await output.put(application_event)
                    async with pending_lock:
                        if not half_close_started.is_set() and not terminal.is_set():
                            raise StreamProtocolError(
                                "server closed before the client half-closed"
                            )
                        if pending and not terminal.is_set():
                            raise StreamProtocolError(
                                "stream closed with unacknowledged content"
                            )
                    if not terminal.is_set():
                        await output.put(_END)
                    terminal.set()
                except Exception as exc:
                    if not terminal.is_set():
                        await output.put(self._map_error(exc))
                    terminal.set()
                    if not server_blocked:
                        call.cancel()

            tasks = [
                asyncio.create_task(writer(), name="aidefense-stream-writer"),
                asyncio.create_task(reader(), name="aidefense-stream-reader"),
            ]

            deadline = started + self.config.absolute_timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise StreamTimeoutError("event stream absolute timeout expired")
                async with pending_lock:
                    waiting_for_ack = bool(pending)
                wait_timeout = (
                    min(self.config.idle_timeout, remaining)
                    if waiting_for_ack
                    else remaining
                )
                try:
                    item = await asyncio.wait_for(output.get(), timeout=wait_timeout)
                except asyncio.TimeoutError as exc:
                    if not waiting_for_ack:
                        raise StreamTimeoutError(
                            "event stream absolute timeout expired",
                            cause=exc,
                        ) from exc
                    raise StreamTimeoutError(
                        "event stream frame was not acknowledged before idle timeout",
                        cause=exc,
                    ) from exc
                if item is _END:
                    outcome = "completed"
                    break
                if item is _ACK or item is _SENT:
                    continue
                if isinstance(item, BaseException):
                    raise item
                yield item
        except asyncio.CancelledError as exc:
            outcome = "cancelled"
            with self.observer.span("aidefense.stream.cancellation", observed()):
                self.observer.event(
                    ReasonCode.STREAM_CANCELLED,
                    level=logging.WARNING,
                    attributes=observed(),
                )
            # Preserve asyncio cancellation semantics for structured-concurrency
            # callers. Remote gRPC cancellation is mapped to StreamCancelledError.
            raise
        except UnsafeContentError:
            outcome = "blocked"
            raise
        except StreamTimeoutError:
            outcome = "timeout"
            with self.observer.span("aidefense.stream.timeout", observed()):
                self.observer.event(
                    ReasonCode.STREAM_TIMEOUT,
                    level=logging.ERROR,
                    attributes=observed(),
                )
            raise
        except EventStreamError:
            self.observer.event(
                ReasonCode.STREAM_FAILED,
                level=logging.ERROR,
                attributes=observed(),
            )
            raise
        except Exception as exc:
            self.observer.event(
                ReasonCode.STREAM_FAILED,
                level=logging.ERROR,
                attributes=observed(),
            )
            raise self._map_error(exc) from exc
        finally:
            terminal.set()
            if call is not None and not server_blocked:
                call.cancel()
            for task in tasks:
                if not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            close = getattr(channel, "close", None)
            if close is not None:
                result = close()
                if hasattr(result, "__await__"):
                    await result
            if active_stream_counted:
                self.observer.active_streams(-1)
            self.observer.latency(time.monotonic() - started, outcome)
            if outcome == "completed":
                self.observer.event(ReasonCode.STREAM_COMPLETED, attributes=observed())

    def _open_channel(self) -> Any:
        if self._channel_factory is not None:
            return self._channel_factory(self.config)
        options = (
            ("grpc.max_send_message_length", self.config.max_stream_bytes),
            ("grpc.max_receive_message_length", self.config.max_stream_bytes),
        )
        if self.config.use_tls:
            credentials = grpc.ssl_channel_credentials(
                root_certificates=self.config.root_certificates
            )
            return grpc.aio.secure_channel(
                self.config.endpoint, credentials, options=options
            )
        return grpc.aio.insecure_channel(self.config.endpoint, options=options)

    @staticmethod
    def _start_frame(
        context: StreamContext, config: Optional[InspectionConfig]
    ) -> stream_api.InspectStreamRequest:
        start = runtime_stream.InspectStreamStart(
            context=runtime_stream.InspectionContext(
                session_id=context.session_id,
                request_id=context.request_id,
                conversation_id=context.conversation_id,
                actor_id=context.actor_id,
            )
        )
        if config is not None:
            start.inspection_config = _inspection_config(config)
        model = runtime_stream.InspectStreamRequest(start=start)
        return _to_wire(model, stream_api.InspectStreamRequest())

    def _event_frame(
        self,
        batch: _Batch,
        sequence: int,
        source: str,
        is_final: bool,
        offsets: Dict[Tuple[str, StreamDirection], int],
        overlap: Dict[Tuple[str, StreamDirection], Tuple[Tuple[Any, ...], str]],
    ) -> Tuple[Any, List[Any], Tuple[SourceRange, ...]]:
        key = (batch.message_id, batch.direction)
        offset = offsets.get(key, 0)
        messages: List[CanonicalMessage] = []
        ranges = []
        retained = []
        previous_identity, prefix = overlap.get(key, ((), ""))
        prefix_used = False
        overlap_identity: Tuple[Any, ...] = ()
        overlap_text = ""

        for event in batch.events:
            retained.append(event.application_event)
            message = event.message
            if message is None:
                continue
            content = (
                message.content.text
                if message.content is not None and message.content.text is not None
                else ""
            )
            identity = _overlap_identity(message)
            if content:
                source_range = SourceRange(offset, offset + len(content))
                ranges.append(source_range)
                offset = source_range.end
                if prefix and not prefix_used and identity == previous_identity:
                    content = prefix + content
                prefix_used = True
                if identity == overlap_identity:
                    overlap_text += content
                else:
                    overlap_identity = identity
                    overlap_text = content
            elif identity != overlap_identity:
                overlap_identity = identity
                overlap_text = ""
            messages.append(
                message.model_copy(
                    update={"content": runtime_chat.MessageContent(text=content)}
                )
            )

        if not messages:
            raise StreamProtocolError("batch contained no canonical messages")
        offsets[key] = offset
        if self.config.overlap_tokens:
            char_limit = self.config.overlap_tokens * 4
            overlap[key] = (overlap_identity, overlap_text[-char_limit:])
        else:
            overlap[key] = ((), "")

        direction = (
            runtime_stream.Direction.DIRECTION_REQUEST
            if batch.direction is StreamDirection.REQUEST
            else runtime_stream.Direction.DIRECTION_RESPONSE
        )
        runtime_event = runtime_stream.InspectionEvent(
            message_id=batch.message_id,
            sequence=sequence,
            source=source,
            direction=direction,
            is_final=is_final,
            conversation=runtime_stream.ConversationPayload(messages=messages),
        )
        return (
            _to_wire(runtime_event, stream_api.InspectionEvent()),
            retained,
            tuple(ranges),
        )

    @staticmethod
    def _decision(response: runtime_chat.InspectResponse) -> StreamDecision:
        return StreamDecision(
            is_safe=response.is_safe,
            action=str(response.action or runtime_chat.Action.ActionUnspecified),
            event_id=response.event_id,
            classifications=tuple(str(value) for value in response.classifications),
            rules=tuple(rule.rule_name for rule in response.rules),
            redacted_content=response.redacted_content,
        )

    @staticmethod
    def _map_error(exc: BaseException) -> EventStreamError:
        if isinstance(exc, EventStreamError):
            return exc
        if isinstance(exc, asyncio.CancelledError):
            return StreamCancelledError("event stream was cancelled", cause=exc)
        if isinstance(exc, asyncio.TimeoutError):
            return StreamTimeoutError("event stream timed out", cause=exc)
        if isinstance(exc, grpc.aio.AioRpcError):
            code = exc.code()
            details = " ".join((exc.details() or "").split())
            if len(details) > 512:
                details = f"{details[:509]}..."
            if code == grpc.StatusCode.CANCELLED:
                return StreamCancelledError(
                    "server cancelled the event stream", cause=exc
                )
            if code == grpc.StatusCode.DEADLINE_EXCEEDED:
                return StreamTimeoutError("server deadline expired", cause=exc)
            if code in (
                grpc.StatusCode.INVALID_ARGUMENT,
                grpc.StatusCode.FAILED_PRECONDITION,
            ):
                message = f"event stream request was rejected with {code.name}"
                if details:
                    message = f"{message}: {details}"
                return StreamProtocolError(message, cause=exc)
            if code == grpc.StatusCode.RESOURCE_EXHAUSTED:
                message = "event stream exceeded a server capacity limit"
                if details:
                    message = f"{message}: {details}"
                return StreamBackpressureError(message, cause=exc)
            if code in (
                grpc.StatusCode.UNAUTHENTICATED,
                grpc.StatusCode.PERMISSION_DENIED,
            ):
                message = f"event stream authorization failed with {code.name}"
                if details:
                    message = f"{message}: {details}"
                return StreamConnectionError(message, cause=exc)
            message = f"event stream RPC failed with status {code.name}"
            if details:
                message = f"{message}: {details}"
            return StreamConnectionError(message, cause=exc)
        return StreamConnectionError("event stream connection failed", cause=exc)


def _inspection_config(config: InspectionConfig) -> runtime_chat.Config:
    proto = runtime_chat.Config(
        integration_tenant_id=config.integration_tenant_id or "",
        integration_type=config.integration_type or "",
    )
    for rule in config.enabled_rules or []:
        proto.enabled_rules.append(
            runtime_chat.RuleObject(
                rule_name=rule.rule_name.value if rule.rule_name is not None else "",
                rule_id=rule.rule_id or 0,
                entity_types=rule.entity_types or [],
                classification=(
                    runtime_chat.ClassificationTypes(rule.classification.value)
                    if rule.classification is not None
                    else runtime_chat.ClassificationTypes.NONE_VIOLATION
                ),
            )
        )
    return proto


def _to_wire(model: Any, message: Any) -> Any:
    """Convert a validated public Pydantic runtime model to a private protobuf."""

    return ParseDict(model.model_dump(mode="json"), message)
