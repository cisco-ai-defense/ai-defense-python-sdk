# Copyright 2026 Cisco Systems, Inc. and its affiliates
# SPDX-License-Identifier: Apache-2.0

"""Small, fail-closed bidirectional gRPC inspection client."""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
import uuid
from dataclasses import dataclass
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
    inspection_grpc_pb2 as stream_api,
)
from aidefense.pydantic.runtime.ai_defense.inspection_grpc.v1 import (
    inspection_grpc_pydantic as runtime_stream,
)
from aidefense.runtime.models import InspectionConfig

from ._grpc import InspectionServiceStub
from .adapters import EventStreamAdapter, as_async_iterable
from .exceptions import (
    EventStreamError,
    StreamBackpressureError,
    StreamCancelledError,
    StreamConfigurationError,
    StreamConnectionError,
    StreamProtocolError,
    StreamTimeoutError,
    UnsafeContentError,
)
from .models import (
    CanonicalMessage,
    EventStreamConfig,
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

RequestContent = Union[
    str,
    Sequence[CanonicalMessage],
    Sequence[Dict[str, Any]],
]


def _action_name(action: str) -> str:
    return action.rsplit(".", 1)[-1].lower()


def _with_redacted_text(application_event: Any, text: str) -> Optional[Any]:
    """Replace text in common vendor event shapes without mutating the input."""

    if isinstance(application_event, bytes):
        return text.encode("utf-8")
    if isinstance(application_event, str):
        return text
    if not isinstance(application_event, dict):
        return None

    updated = dict(application_event)
    wrapped = updated.get("event")
    if isinstance(wrapped, dict):
        redacted = _with_redacted_text(wrapped, text)
        if redacted is None:
            return None
        updated["event"] = redacted
        return updated

    block_delta = updated.get("contentBlockDelta")
    if isinstance(block_delta, dict):
        updated_block = dict(block_delta)
        delta = updated_block.get("delta")
        if isinstance(delta, dict) and isinstance(delta.get("text"), str):
            updated_delta = dict(delta)
            updated_delta["text"] = text
            updated_block["delta"] = updated_delta
            updated["contentBlockDelta"] = updated_block
            return updated

    for key in ("data", "text", "result", "response", "completion", "content"):
        if isinstance(updated.get(key), str):
            updated[key] = text
            return updated
    return None


def _request_messages(request: RequestContent) -> Tuple[CanonicalMessage, ...]:
    """Normalize SDK input without requiring protobuf construction."""

    if isinstance(request, str):
        if not request:
            raise StreamProtocolError("request must not be empty")
        return (
            CanonicalMessage(
                role=runtime_chat.Role.user,
                content=runtime_chat.MessageContent(text=request),
            ),
        )
    if not isinstance(request, Sequence) or isinstance(request, (bytes, bytearray)):
        raise StreamProtocolError(
            "request must be text or a sequence of canonical messages"
        )
    if not request:
        raise StreamProtocolError("request conversation must not be empty")

    messages = []
    for value in request:
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
                "request contains an invalid canonical message"
            ) from exc
        if message.role in (None, runtime_chat.Role.invalid_role):
            raise StreamProtocolError("request messages must have a valid role")
        messages.append(message)
    return tuple(messages)


@dataclass
class _Pending:
    sequence: int
    application_event: Any
    direction: StreamDirection
    sent_at: float


@dataclass
class _Approved:
    """Application values approved for one sequence, possibly intentionally empty."""

    outputs: Tuple[Any, ...]


class EventStreamClient:
    """Send canonical events and release application events after inspection.

    The SDK sends exactly one ``InspectionEvent`` per input ``StreamEvent``.
    It does not group content, split tokens, or create overlap. The service may
    acknowledge a set of sent events in one result; exactly those local events
    are decided, while application content is still released in sequence order.
    """

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

    async def inspect(
        self,
        events: Any,
        *,
        context: StreamContext,
        source: Optional[str] = None,
        request: Optional[RequestContent] = None,
        adapter: Optional[EventStreamAdapter] = None,
        message_id: Optional[str] = None,
        inspection_config: Optional[InspectionConfig] = None,
    ) -> AsyncIterator[Any]:
        """Inspect native adapter events or caller-created ``StreamEvent`` values.

        With ``adapter``, ``request`` becomes one request event and native
        response events are converted lazily after that request is safe.
        Without ``adapter``, ``events`` must contain the canonical request and
        response sequence. One response event is retained only to mark the
        actual final event; content is never grouped.
        """

        context.validate()
        if adapter is not None:
            if request is None:
                raise StreamProtocolError(
                    "request is required when an adapter is provided"
                )
            request_messages = _request_messages(request)
            identifier = message_id or str(uuid.uuid4())
            resolved_source = source or adapter.source
            native_events = events

            async def canonical_events() -> AsyncIterator[StreamEvent]:
                yield StreamEvent(
                    application_event=None,
                    messages=request_messages,
                    direction=StreamDirection.REQUEST,
                    message_id=identifier,
                )
                async for converted in adapter.adapt(
                    native_events,
                    message_id=identifier,
                    direction=StreamDirection.RESPONSE,
                ):
                    yield converted

            events = canonical_events()
        else:
            if request is not None or message_id is not None:
                raise StreamProtocolError("request and message_id require an adapter")
            resolved_source = source or ""
        if not resolved_source.strip():
            raise StreamProtocolError("source must not be empty")

        channel = self._open_channel()
        call: Optional[Any] = None
        tasks: List[asyncio.Task] = []
        output: asyncio.Queue = asyncio.Queue(
            maxsize=max(4, self.config.max_pending_events)
        )
        pending: Dict[int, _Pending] = {}
        approved: Dict[int, _Approved] = {}
        pending_lock = asyncio.Lock()
        capacity = asyncio.Semaphore(self.config.max_pending_events)
        request_drained = asyncio.Event()
        request_drained.set()
        terminal = asyncio.Event()
        half_close_started = asyncio.Event()
        started = time.monotonic()
        outcome = "failure"
        active_stream_counted = False
        server_blocked = False
        stream_correlation_id = uuid.uuid4().hex
        sent_sequence = 0
        sent_bytes = 0

        def observed(**attributes: Any) -> Dict[str, Any]:
            return {"stream_correlation_id": stream_correlation_id, **attributes}

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

            async def send(event: StreamEvent, *, is_final: bool) -> None:
                nonlocal sent_sequence, sent_bytes
                if capacity.locked():
                    self.observer.event(
                        ReasonCode.BACKPRESSURE_WAIT, attributes=observed()
                    )
                await capacity.acquire()
                if terminal.is_set():
                    capacity.release()
                    return

                sequence = sent_sequence + 1
                if sequence > self.config.max_stream_events:
                    capacity.release()
                    raise StreamProtocolError("stream exceeds the server event limit")
                proto_event = self._event_frame(
                    event, sequence, resolved_source, is_final
                )
                frame = stream_api.InspectStreamRequest(
                    events=stream_api.InspectStreamEvents(events=[proto_event])
                )
                frame_bytes = frame.ByteSize()
                if sent_bytes + frame_bytes > self.config.max_stream_bytes:
                    capacity.release()
                    raise StreamProtocolError(
                        "stream exceeds the server retention limit"
                    )

                try:
                    async with pending_lock:
                        pending[sequence] = _Pending(
                            sequence=sequence,
                            application_event=event.application_event,
                            direction=event.direction,
                            sent_at=time.monotonic(),
                        )
                        if event.direction is StreamDirection.REQUEST:
                            request_drained.clear()
                        with self.observer.span(
                            "aidefense.stream.send",
                            observed(
                                sequence=sequence,
                                direction=event.direction.value,
                            ),
                        ):
                            await call.write(frame)
                        sent_sequence = sequence
                        sent_bytes += frame_bytes
                except BaseException:
                    async with pending_lock:
                        pending.pop(sequence, None)
                        if not any(
                            item.direction is StreamDirection.REQUEST
                            for item in pending.values()
                        ):
                            request_drained.set()
                    capacity.release()
                    raise

                self.observer.event(
                    ReasonCode.EVENT_SENT,
                    attributes=observed(
                        sequence=sequence, direction=event.direction.value
                    ),
                )
                await output.put(_SENT)

            async def writer() -> None:
                buffered_response: Optional[StreamEvent] = None
                saw_request = False
                saw_response = False
                try:
                    async for event in as_async_iterable(events):
                        self._validate_event(event)
                        if terminal.is_set():
                            return
                        if event.direction is StreamDirection.REQUEST:
                            if saw_response:
                                raise StreamProtocolError(
                                    "request content cannot follow response content"
                                )
                            saw_request = True
                            await send(event, is_final=False)
                            # Pulling the next item may invoke the model. Wait
                            # until this caller-owned prompt event is approved.
                            await request_drained.wait()
                            if terminal.is_set():
                                return
                            continue

                        if not saw_request:
                            raise StreamProtocolError(
                                "response content requires preceding request content"
                            )
                        if not saw_response:
                            # Keep prompt and completion decisions separate even
                            # when the service batches acknowledgements internally.
                            await request_drained.wait()
                            if terminal.is_set():
                                return
                            saw_response = True
                        if buffered_response is not None:
                            await send(buffered_response, is_final=False)
                        buffered_response = event

                    if not saw_request:
                        raise StreamProtocolError(
                            "stream contained no inspectable request content"
                        )
                    if buffered_response is None:
                        raise StreamProtocolError(
                            "stream contained no inspectable response content"
                        )
                    await send(buffered_response, is_final=True)
                    if terminal.is_set():
                        return
                    half_close_started.set()
                    await call.done_writing()
                except Exception as exc:
                    if not terminal.is_set():
                        await output.put(self._map_error(exc))
                    terminal.set()
                    call.cancel()

            async def reader() -> None:
                nonlocal server_blocked
                next_release_sequence = 1
                try:
                    async for result in call:
                        runtime_result = runtime_stream.InspectionResult.model_validate(
                            MessageToDict(result, preserving_proto_field_name=True)
                        )
                        through = tuple(
                            int(sequence)
                            for sequence in runtime_result.through_sequences
                        )
                        if not through:
                            raise StreamProtocolError(
                                "server acknowledgement has no through_sequences"
                            )
                        if len(set(through)) != len(through):
                            raise StreamProtocolError(
                                "server acknowledgement contains duplicate sequences"
                            )
                        highest_sequence = max(through)
                        if runtime_result.inspect_response is None:
                            raise StreamProtocolError(
                                "server acknowledgement has no inspect_response"
                            )
                        decision = self._decision(runtime_result.inspect_response)

                        async with pending_lock:
                            if any(sequence > sent_sequence for sequence in through):
                                raise StreamProtocolError(
                                    "server acknowledged a sequence that was not sent"
                                )
                            ready_keys = sorted(through)
                            missing = [
                                sequence
                                for sequence in ready_keys
                                if sequence not in pending
                            ]
                            if missing:
                                raise StreamProtocolError(
                                    "server acknowledged a sequence that is not pending"
                                )
                            ready = [pending.pop(key) for key in ready_keys]
                        for _ in ready:
                            capacity.release()

                        inspection_result = StreamInspectionResult(
                            decision=decision,
                            through_sequences=tuple(ready_keys),
                            directions=tuple(item.direction for item in ready),
                        )
                        if self._on_decision is not None:
                            callback_result = self._on_decision(inspection_result)
                            if inspect.isawaitable(callback_result):
                                await callback_result

                        with self.observer.span(
                            "aidefense.stream.acknowledgement",
                            observed(
                                through_sequence=highest_sequence,
                                sequence_count=len(ready_keys),
                            ),
                        ):
                            self.observer.event(
                                ReasonCode.ACK_RECEIVED,
                                attributes=observed(
                                    through_sequence=highest_sequence,
                                    sequence_count=len(ready_keys),
                                ),
                            )

                        action = _action_name(decision.action)
                        if action == "block" or (
                            not decision.is_safe and action not in {"allow", "redact"}
                        ):
                            with self.observer.span(
                                "aidefense.stream.block",
                                observed(through_sequence=highest_sequence),
                            ):
                                self.observer.event(
                                    ReasonCode.DECISION_BLOCK,
                                    level=logging.WARNING,
                                    attributes=observed(
                                        through_sequence=highest_sequence
                                    ),
                                )
                            server_blocked = True
                            raise UnsafeContentError(
                                "AI Defense blocked streamed content before release",
                                decision=decision,
                                sequences=inspection_result.through_sequences,
                                directions=inspection_result.directions,
                            )

                        async with pending_lock:
                            if not any(
                                item.direction is StreamDirection.REQUEST
                                for item in pending.values()
                            ):
                                # Acknowledgement alone is insufficient: only
                                # an allowed prompt may unblock model output.
                                request_drained.set()

                        with self.observer.span(
                            "aidefense.stream.decision",
                            observed(
                                through_sequence=highest_sequence,
                                is_safe=decision.is_safe,
                                action=decision.action,
                            ),
                        ):
                            self.observer.event(
                                ReasonCode.DECISION_ALLOW,
                                attributes=observed(through_sequence=highest_sequence),
                            )
                        await output.put(_ACK)
                        if action == "redact":
                            for item in ready:
                                approved[item.sequence] = _Approved(outputs=())
                            if decision.redacted_content:
                                # A batched decision contains one replacement,
                                # so attach it once to the latest acknowledged
                                # shape. Earlier sequence gaps still prevent it
                                # from being emitted out of application order.
                                originals = [
                                    item.application_event
                                    for item in ready
                                    if item.application_event is not None
                                ]
                                if originals:
                                    redacted = _with_redacted_text(
                                        originals[-1], decision.redacted_content
                                    )
                                    if redacted is not None:
                                        approved[ready[-1].sequence] = _Approved(
                                            outputs=(redacted,)
                                        )
                        else:
                            for item in ready:
                                outputs = (
                                    ()
                                    if item.application_event is None
                                    else (item.application_event,)
                                )
                                approved[item.sequence] = _Approved(outputs=outputs)

                        # Acknowledgement IDs are an explicit set, not a
                        # cumulative max watermark. Hold a later approved item
                        # until every earlier sequence has also been decided so
                        # sparse or out-of-order bulk responses cannot reorder
                        # model chunks in the application.
                        while next_release_sequence in approved:
                            released = approved.pop(next_release_sequence)
                            next_release_sequence += 1
                            for application_event in released.outputs:
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
                        if approved and not terminal.is_set():
                            raise StreamProtocolError(
                                "stream closed before acknowledged content could be released"
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
                now = time.monotonic()
                remaining = deadline - now
                if remaining <= 0:
                    raise StreamTimeoutError("event stream absolute timeout expired")
                async with pending_lock:
                    oldest = min(
                        (item.sent_at for item in pending.values()), default=None
                    )
                if oldest is None:
                    wait_timeout = remaining
                else:
                    idle_remaining = self.config.idle_timeout - (now - oldest)
                    if idle_remaining <= 0:
                        raise StreamTimeoutError(
                            "event stream frame was not acknowledged before idle timeout"
                        )
                    wait_timeout = min(idle_remaining, remaining)
                try:
                    item = await asyncio.wait_for(output.get(), timeout=wait_timeout)
                except asyncio.TimeoutError as exc:
                    if oldest is None:
                        raise StreamTimeoutError(
                            "event stream absolute timeout expired", cause=exc
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
        except asyncio.CancelledError:
            outcome = "cancelled"
            with self.observer.span("aidefense.stream.cancellation", observed()):
                self.observer.event(
                    ReasonCode.STREAM_CANCELLED,
                    level=logging.WARNING,
                    attributes=observed(),
                )
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
                if inspect.isawaitable(result):
                    await result
            if active_stream_counted:
                self.observer.active_streams(-1)
            self.observer.latency(time.monotonic() - started, outcome)
            if outcome == "completed":
                self.observer.event(ReasonCode.STREAM_COMPLETED, attributes=observed())

    @staticmethod
    def _validate_event(event: Any) -> None:
        if not isinstance(event, StreamEvent):
            raise StreamProtocolError("inspect accepts only StreamEvent values")
        if not event.messages:
            raise StreamProtocolError("StreamEvent.messages must not be empty")
        if not event.message_id.strip():
            raise StreamProtocolError("StreamEvent.message_id must not be empty")
        if not isinstance(event.direction, StreamDirection):
            raise StreamProtocolError("StreamEvent.direction is invalid")

    def _open_channel(self) -> Any:
        if self._channel_factory is not None:
            return self._channel_factory(self.config)
        options: List[Tuple[str, Any]] = [
            ("grpc.max_send_message_length", self.config.max_stream_bytes),
            ("grpc.max_receive_message_length", self.config.max_stream_bytes),
        ]
        if self.config.tls_server_name:
            options.extend(
                [
                    ("grpc.ssl_target_name_override", self.config.tls_server_name),
                    ("grpc.default_authority", self.config.tls_server_name),
                ]
            )
        if self.config.tls:
            credentials = grpc.ssl_channel_credentials(
                root_certificates=self.config.root_certificates,
                private_key=self.config.client_private_key,
                certificate_chain=self.config.client_certificate,
            )
            return grpc.aio.secure_channel(
                self.config.endpoint, credentials, options=tuple(options)
            )
        return grpc.aio.insecure_channel(self.config.endpoint, options=tuple(options))

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
        return _to_wire(
            runtime_stream.InspectStreamRequest(start=start),
            stream_api.InspectStreamRequest(),
        )

    @staticmethod
    def _event_frame(
        event: StreamEvent,
        sequence: int,
        source: str,
        is_final: bool,
    ) -> Any:
        direction = (
            runtime_stream.Direction.DIRECTION_REQUEST
            if event.direction is StreamDirection.REQUEST
            else runtime_stream.Direction.DIRECTION_RESPONSE
        )
        runtime_event = runtime_stream.InspectionEvent(
            message_id=event.message_id,
            sequence=sequence,
            source=source,
            direction=direction,
            is_final=is_final,
            conversation=runtime_stream.ConversationPayload(
                messages=list(event.messages)
            ),
        )
        return _to_wire(runtime_event, stream_api.InspectionEvent())

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
    """Convert a validated public Pydantic runtime model to private protobuf."""

    return ParseDict(model.model_dump(mode="json"), message)
