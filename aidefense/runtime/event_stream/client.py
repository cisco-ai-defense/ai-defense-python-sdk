# Copyright 2026 Cisco Systems, Inc. and its affiliates
# SPDX-License-Identifier: Apache-2.0

"""High-level, fail-closed bidirectional gRPC inspection client."""

from __future__ import annotations

import asyncio
import logging
import math
import time
import uuid
from dataclasses import dataclass, replace
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Tuple

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
from aidefense.runtime.event_stream._generated.ai_defense.inspection_grpc.v1 import (
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
)
from .observability import ReasonCode, StreamObserver


API_KEY_HEADER = "x-cisco-ai-defense-api-key"
REQUEST_ID_HEADER = "x-aidefense-request-id"
_END = object()
_ACK = object()


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


@dataclass
class _Pending:
    sequence: int
    application_events: List[Any]
    ranges: Tuple[SourceRange, ...]


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
            if _boundary(current, event) or (
                current.has_content
                and event.message is not None
                and current.token_count + tokens
                > config.token_limit - config.overlap_tokens
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
        self._channel_factory = channel_factory
        self._stub_factory = stub_factory

    @classmethod
    def from_env(
        cls,
        *,
        observer: Optional[StreamObserver] = None,
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
        return cls(config, observer=resolved_observer)

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
        prompt: str,
        response: Any,
        *,
        context: StreamContext,
        message_id: Optional[str] = None,
        source: str = "strands-agentcore",
        inspection_config: Optional[InspectionConfig] = None,
    ) -> AsyncIterator[Any]:
        """Inspect one AgentCore invocation (prompt and streamed response)."""

        if not isinstance(prompt, str) or not prompt:
            raise StreamProtocolError("AgentCore prompt must be a non-empty string")
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
            yield StreamEvent(
                application_event=None,
                message=CanonicalMessage(
                    role=runtime_chat.Role.user,
                    content=runtime_chat.MessageContent(text=prompt),
                ),
                direction=StreamDirection.REQUEST,
                message_id=identifier,
            )
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
        pending_lock = asyncio.Lock()
        capacity = asyncio.Semaphore(self.config.max_pending_batches)
        sequence_lock = asyncio.Lock()
        next_sequence = 0
        offsets: Dict[Tuple[str, StreamDirection], int] = {}
        overlap: Dict[Tuple[str, StreamDirection], str] = {}
        terminal = asyncio.Event()
        half_close_started = asyncio.Event()
        started = time.monotonic()
        outcome = "failure"
        active_stream_counted = False
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
                batch: _Batch, is_final: bool, already_sent_bytes: int
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
                        pending[seq] = _Pending(seq, retained, ranges)
                        with self.observer.span(
                            "aidefense.stream.send",
                            observed(sequence=seq, direction=batch.direction.value),
                        ):
                            await call.write(frame)
                except BaseException:
                    async with pending_lock:
                        pending.pop(seq, None)
                    capacity.release()
                    raise
                self.observer.event(
                    ReasonCode.BATCH_SENT,
                    attributes=observed(sequence=seq, direction=batch.direction.value),
                )
                return 1, frame_bytes

            async def reader() -> None:
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
                        with self.observer.span(
                            "aidefense.stream.acknowledgement",
                            observed(through_sequence=ack),
                        ):
                            self.observer.event(
                                ReasonCode.ACK_RECEIVED,
                                attributes=observed(through_sequence=ack),
                            )
                        if not decision.is_safe:
                            with self.observer.span(
                                "aidefense.stream.block",
                                observed(through_sequence=ack),
                            ):
                                self.observer.event(
                                    ReasonCode.DECISION_BLOCK,
                                    level=logging.WARNING,
                                    attributes=observed(through_sequence=ack),
                                )
                            raise UnsafeContentError(
                                "AI Defense blocked streamed content before release",
                                decision=decision,
                                sequences=tuple(item.sequence for item in ready),
                            )
                        with self.observer.span(
                            "aidefense.stream.decision",
                            observed(through_sequence=ack, is_safe=True),
                        ):
                            self.observer.event(
                                ReasonCode.DECISION_ALLOW,
                                attributes=observed(through_sequence=ack),
                            )
                        await output.put(_ACK)
                        for item in ready:
                            for application_event in item.application_events:
                                if application_event is not None:
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
                try:
                    item = await asyncio.wait_for(
                        output.get(), timeout=min(self.config.idle_timeout, remaining)
                    )
                except asyncio.TimeoutError as exc:
                    raise StreamTimeoutError(
                        "event stream produced no acknowledgement before idle timeout",
                        cause=exc,
                    ) from exc
                if item is _END:
                    outcome = "completed"
                    break
                if item is _ACK:
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
            if call is not None:
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
        overlap: Dict[Tuple[str, StreamDirection], str],
    ) -> Tuple[Any, List[Any], Tuple[SourceRange, ...]]:
        key = (batch.message_id, batch.direction)
        offset = offsets.get(key, 0)
        messages: List[CanonicalMessage] = []
        ranges = []
        canonical_new_text = ""
        retained = []
        prefix = overlap.get(key, "")
        prefix_used = False

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
            if content:
                source_range = SourceRange(offset, offset + len(content))
                ranges.append(source_range)
                offset = source_range.end
                canonical_new_text += content
                if prefix and not prefix_used:
                    content = prefix + content
                    prefix_used = True
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
            overlap[key] = (prefix + canonical_new_text)[-char_limit:]
        else:
            overlap[key] = ""

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
            if code == grpc.StatusCode.CANCELLED:
                return StreamCancelledError(
                    "server cancelled the event stream", cause=exc
                )
            if code == grpc.StatusCode.DEADLINE_EXCEEDED:
                return StreamTimeoutError("server deadline expired", cause=exc)
            return StreamConnectionError(
                f"event stream RPC failed with status {code.name}", cause=exc
            )
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
