# Copyright 2026 Cisco Systems, Inc. and its affiliates
# SPDX-License-Identifier: Apache-2.0

"""Per-invocation state machine for bidirectional stream inspection."""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence, Tuple

from google.protobuf.json_format import MessageToDict  # type: ignore[import-untyped]

from aidefense.pydantic.runtime.ai_defense.inspection_grpc.v1 import (
    inspection_grpc_pb2 as stream_api,
)
from aidefense.pydantic.runtime.ai_defense.inspection_grpc.v1 import (
    inspection_grpc_pydantic as runtime_stream,
)
from aidefense.runtime.models import InspectionConfig

from .adapters import as_async_iterable
from .exceptions import (
    EventStreamError,
    StreamConnectionError,
    StreamProtocolError,
    StreamTimeoutError,
    UnsafeContentError,
)
from .models import (
    StreamContext,
    StreamDecision,
    StreamDirection,
    StreamEvent,
    StreamInspectionResult,
)
from .observability import ReasonCode


API_KEY_HEADER = "x-cisco-ai-defense-api-key"
REQUEST_ID_HEADER = "x-aidefense-request-id"
_END = object()
_ACK = object()
_SENT = object()
_CLEANUP_TIMEOUT_SECONDS = 5.0


@dataclass
class _Pending:
    """Caller content retained until the server decides its exact sequence."""

    sequence: int
    application_event: Any
    direction: StreamDirection
    sent_at: float


@dataclass
class _Approved:
    """Approved values waiting for all earlier sequences to become releasable."""

    outputs: Tuple[Any, ...]


def _consume_task_result(task: "asyncio.Future[Any]") -> None:
    """Retrieve a detached cleanup task's result without raising in the loop."""

    try:
        task.exception()
    except (asyncio.CancelledError, Exception):
        pass


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


class _StreamSession:
    """One isolated gRPC call and its bounded asynchronous state.

    Keeping lifecycle state here makes EventStreamClient safe to reuse: every
    inspect() call gets its own channel, sequence counter, queues, locks, tasks,
    and retained application events. The writer owns sequence assignment; the
    reader owns acknowledgement validation and ordered release. They coordinate
    only through bounded structures so a slow server applies backpressure.
    """

    def __init__(
        self,
        *,
        client: Any,
        events: Any,
        context: StreamContext,
        source: str,
        inspection_config: Optional[InspectionConfig],
    ) -> None:
        self.events = events
        self.context = context
        self.source = source
        self.inspection_config = inspection_config

        # The public client owns only reusable configuration and stateless
        # helpers. Everything below is private to this one inspect() call.
        self.config = client.config
        self.observer = client.observer
        self.on_decision = client._on_decision
        self.stub_factory = client._stub_factory
        self.open_channel = client._open_channel
        self.start_frame = client._start_frame
        self.event_frame = client._event_frame
        self.validate_event = client._validate_event
        self.parse_decision = client._decision
        self.map_error = client._map_error

        self.channel: Optional[Any] = None
        self.call: Optional[Any] = None
        self.tasks: List[asyncio.Task] = []
        # This queue is the only path from background workers to run(). Marker
        # objects wake deadline handling without exposing protocol frames to the
        # application. Its bound prevents a slow consumer from growing memory.
        self.output: asyncio.Queue = asyncio.Queue(
            maxsize=max(4, self.config.max_pending_events)
        )
        # pending is sent-but-undecided content. approved is decided content
        # waiting for an earlier sequence. Both collections are bounded.
        self.pending: Dict[int, _Pending] = {}
        self.approved: Dict[int, _Approved] = {}
        self.pending_lock = asyncio.Lock()
        # BoundedSemaphore turns any future token-accounting regression into a
        # controlled stream failure instead of silently disabling backpressure.
        self.capacity = asyncio.BoundedSemaphore(self.config.max_pending_events)
        # Prompt events have no application output, but they still must receive
        # an allow/monitor/redact decision before an adapter may invoke a model.
        self.request_drained = asyncio.Event()
        self.request_drained.set()
        self.terminal = asyncio.Event()
        self.half_close_started = asyncio.Event()

        self.started = time.monotonic()
        self.outcome = "failure"
        self.active_stream_counted = False
        self.server_blocked = False
        self.call_cancelled = False
        self.channel_closed = False
        self.correlation_id = uuid.uuid4().hex
        self.sent_sequence = 0
        self.sent_bytes = 0
        self.next_release_sequence = 1

    def observed(self, **attributes: Any) -> Dict[str, Any]:
        """Return bounded telemetry attributes without customer identifiers."""

        return {"stream_correlation_id": self.correlation_id, **attributes}

    def require_call(self) -> Any:
        if self.call is None:
            raise StreamConnectionError("event stream call was not created")
        return self.call

    async def run(self) -> AsyncIterator[Any]:
        """Open the RPC, run workers, and yield only server-approved content."""

        try:
            await self.open()
            # Append each worker immediately so cleanup still owns the first
            # task if creating the second task unexpectedly fails.
            self.tasks.append(
                asyncio.create_task(self.write_events(), name="aidefense-stream-writer")
            )
            self.tasks.append(
                asyncio.create_task(self.read_results(), name="aidefense-stream-reader")
            )
            self.observer.debug(
                ReasonCode.WORKERS_STARTED,
                attributes=self.observed(worker_count=len(self.tasks)),
            )

            while True:
                item = await self.next_output()
                if item is _END:
                    self.outcome = "completed"
                    break
                if item is _ACK or item is _SENT:
                    continue
                if isinstance(item, BaseException):
                    raise item
                yield item
        except asyncio.CancelledError:
            self.outcome = "cancelled"
            with self.observer.span("aidefense.stream.cancellation", self.observed()):
                self.observer.event(
                    ReasonCode.STREAM_CANCELLED,
                    level=logging.WARNING,
                    attributes=self.observed(),
                )
            raise
        except UnsafeContentError:
            self.outcome = "blocked"
            raise
        except StreamTimeoutError:
            self.outcome = "timeout"
            with self.observer.span("aidefense.stream.timeout", self.observed()):
                self.observer.event(
                    ReasonCode.STREAM_TIMEOUT,
                    level=logging.ERROR,
                    attributes=self.observed(),
                )
            raise
        except EventStreamError as exc:
            self.observer.event(
                ReasonCode.STREAM_FAILED,
                level=logging.ERROR,
                attributes=self.observed(error_reason=exc.reason_code),
            )
            raise
        except Exception as exc:
            mapped = self.map_error(exc)
            self.observer.event(
                ReasonCode.STREAM_FAILED,
                level=logging.ERROR,
                attributes=self.observed(error_reason=mapped.reason_code),
            )
            raise mapped from exc
        finally:
            await self.cleanup()

    async def open(self) -> None:
        """Create the channel and send the protocol-required start frame."""

        # Channel construction is inside run()'s typed failure boundary so DNS,
        # TLS, credential, and custom factory failures become SDK exceptions.
        self.observer.debug(
            ReasonCode.CHANNEL_OPENING,
            attributes=self.observed(
                tls_mode=self.client_tls_mode(),
                absolute_timeout_seconds=self.config.absolute_timeout,
            ),
        )
        self.channel = self.open_channel()
        self.observer.debug(
            ReasonCode.CHANNEL_READY,
            attributes=self.observed(tls_mode=self.client_tls_mode()),
        )
        stub = self.stub_factory(self.channel)
        metadata = [
            (API_KEY_HEADER, self.config.api_key),
            (REQUEST_ID_HEADER, self.context.request_id),
            *self.config.metadata,
        ]
        self.call = stub.InspectEventStream(
            metadata=metadata, timeout=self.config.absolute_timeout
        )

        # Context/config must be the first frame and are deliberately not logged.
        await self.require_call().write(
            self.start_frame(self.context, self.inspection_config)
        )
        self.observer.debug(ReasonCode.START_FRAME_SENT, attributes=self.observed())
        self.observer.active_streams(1)
        self.active_stream_counted = True
        self.observer.event(ReasonCode.STREAM_STARTED, attributes=self.observed())

    async def send(self, event: StreamEvent, *, is_final: bool) -> None:
        """Reserve capacity, retain content, then write one canonical event.

        Retention is committed before the network write so an immediate server
        result is valid. The state lock is released before awaiting gRPC flow
        control; otherwise the reader could deadlock waiting for the same lock.
        """

        if self.capacity.locked():
            self.observer.event(
                ReasonCode.BACKPRESSURE_WAIT,
                attributes=self.observed(
                    pending_count=len(self.pending),
                    max_pending_events=self.config.max_pending_events,
                ),
            )
        await self.capacity.acquire()
        if self.terminal.is_set():
            self.capacity.release()
            return

        sequence = self.sent_sequence + 1
        if sequence > self.config.max_stream_events:
            self.capacity.release()
            raise StreamProtocolError("stream exceeds the server event limit")

        proto_event = self.event_frame(event, sequence, self.source, is_final)
        frame = stream_api.InspectStreamRequest(
            events=stream_api.InspectStreamEvents(events=[proto_event])
        )
        frame_bytes = frame.ByteSize()
        if self.sent_bytes + frame_bytes > self.config.max_stream_bytes:
            self.capacity.release()
            raise StreamProtocolError("stream exceeds the server retention limit")

        try:
            # Commit retained state before writing so a fast acknowledgement is
            # valid, but never hold this lock across network flow control. The
            # reader needs the same lock to consume the acknowledgement that may
            # allow an awaiting write to complete.
            async with self.pending_lock:
                self.pending[sequence] = _Pending(
                    sequence=sequence,
                    application_event=event.application_event,
                    direction=event.direction,
                    sent_at=time.monotonic(),
                )
                if event.direction is StreamDirection.REQUEST:
                    self.request_drained.clear()
                self.sent_sequence = sequence
                self.sent_bytes += frame_bytes

            with self.observer.span(
                "aidefense.stream.send",
                self.observed(
                    sequence=sequence,
                    direction=event.direction.value,
                ),
            ):
                await self.require_call().write(frame)
        except BaseException:
            async with self.pending_lock:
                removed = self.pending.pop(sequence, None)
                if not self.has_pending_request():
                    self.request_drained.set()
            # If the reader already consumed this sequence it also returned the
            # capacity token. Avoid over-releasing the bounded semaphore.
            if removed is not None:
                self.capacity.release()
            raise

        self.observer.event(
            ReasonCode.EVENT_SENT,
            attributes=self.observed(
                sequence=sequence, direction=event.direction.value
            ),
        )
        await self.output.put(_SENT)

    async def write_events(self) -> None:
        """Gate prompts, stream responses, mark the final event, and half-close."""

        # One response event is retained solely to mark is_final accurately.
        # No response chunks are grouped or accumulated.
        buffered_response: Optional[StreamEvent] = None
        saw_request = False
        saw_response = False
        try:
            async for event in as_async_iterable(self.events):
                self.validate_event(event)
                if self.terminal.is_set():
                    return

                if event.direction is StreamDirection.REQUEST:
                    if saw_response:
                        raise StreamProtocolError(
                            "request content cannot follow response content"
                        )
                    saw_request = True
                    await self.send(event, is_final=False)
                    # Do not pull the response source (which may invoke the
                    # model) until all request content is allowed.
                    self.observer.debug(
                        ReasonCode.REQUEST_GATE_WAIT,
                        attributes=self.observed(
                            through_sequence=self.sent_sequence,
                            pending_count=len(self.pending),
                        ),
                    )
                    await self.request_drained.wait()
                    if self.terminal.is_set():
                        return
                    self.observer.debug(
                        ReasonCode.REQUEST_GATE_OPEN,
                        attributes=self.observed(
                            through_sequence=self.sent_sequence,
                        ),
                    )
                    continue

                if not saw_request:
                    raise StreamProtocolError(
                        "response content requires preceding request content"
                    )
                if not saw_response:
                    await self.request_drained.wait()
                    if self.terminal.is_set():
                        return
                    saw_response = True
                if buffered_response is not None:
                    await self.send(buffered_response, is_final=False)
                buffered_response = event

            self.observer.debug(
                ReasonCode.SOURCE_EXHAUSTED,
                attributes=self.observed(
                    saw_request=saw_request,
                    saw_response=saw_response,
                ),
            )
            if not saw_request:
                raise StreamProtocolError(
                    "stream contained no inspectable request content"
                )
            if buffered_response is None:
                raise StreamProtocolError(
                    "stream contained no inspectable response content"
                )

            await self.send(buffered_response, is_final=True)
            if self.terminal.is_set():
                return
            self.half_close_started.set()
            await self.require_call().done_writing()
            self.observer.debug(
                ReasonCode.STREAM_HALF_CLOSED,
                attributes=self.observed(sent_sequence=self.sent_sequence),
            )
        except Exception as exc:
            await self.fail_worker(exc, cancel=True)

    async def read_results(self) -> None:
        """Validate server results and apply every explicit sequence decision."""

        try:
            async for wire_result in self.require_call():
                await self.handle_result(wire_result)
            await self.validate_server_close()
            if not self.terminal.is_set():
                # Claim the terminal outcome before awaiting queue capacity so
                # a concurrent worker cannot enqueue a second terminal result.
                self.terminal.set()
                await self.output.put(_END)
        except Exception as exc:
            await self.fail_worker(exc, cancel=not self.server_blocked)

    async def handle_result(self, wire_result: Any) -> None:
        """Validate one result and apply its explicit sequence set atomically.

        ``through_sequences`` contains concrete event sequence IDs; it does not
        mean every lower sequence is acknowledged. Sparse safe results remain
        buffered until a contiguous prefix can be released in application order.
        """

        try:
            runtime_result = runtime_stream.InspectionResult.model_validate(
                MessageToDict(wire_result, preserving_proto_field_name=True)
            )
        except Exception as exc:
            raise StreamProtocolError(
                "server returned a malformed inspection result", cause=exc
            ) from exc
        through = tuple(int(sequence) for sequence in runtime_result.through_sequences)
        if not through:
            raise StreamProtocolError("server acknowledgement has no through_sequences")
        if len(set(through)) != len(through):
            raise StreamProtocolError(
                "server acknowledgement contains duplicate sequences"
            )
        if runtime_result.inspect_response is None:
            raise StreamProtocolError("server acknowledgement has no inspect_response")

        highest_sequence = max(through)
        decision = self.parse_decision(runtime_result.inspect_response)
        self.observer.debug(
            ReasonCode.RESULT_PARSED,
            attributes=self.observed(
                through_sequence=highest_sequence,
                sequence_count=len(through),
                action=_action_name(decision.action),
                is_safe=decision.is_safe,
            ),
        )
        ready = await self.take_pending(through)
        result = StreamInspectionResult(
            decision=decision,
            through_sequences=tuple(item.sequence for item in ready),
            directions=tuple(item.direction for item in ready),
        )

        await self.notify_decision(result)
        self.record_acknowledgement(highest_sequence, len(ready))
        action = _action_name(decision.action)
        if action == "block" or (
            not decision.is_safe and action not in {"allow", "redact"}
        ):
            self.record_block(highest_sequence, action, decision)
            self.server_blocked = True
            raise UnsafeContentError(
                "AI Defense blocked streamed content before release",
                decision=decision,
                sequences=result.through_sequences,
                directions=result.directions,
            )

        async with self.pending_lock:
            if not self.has_pending_request():
                self.request_drained.set()

        self.record_allow(highest_sequence, action, decision)
        await self.output.put(_ACK)
        self.approve(ready, action, decision)
        await self.release_approved()

    async def take_pending(self, through: Tuple[int, ...]) -> List[_Pending]:
        """Remove acknowledged events and return capacity to the writer.

        Validation and removal share one lock, preventing duplicate or unknown
        acknowledgements from partially mutating retained stream state.
        """

        async with self.pending_lock:
            if any(sequence > self.sent_sequence for sequence in through):
                raise StreamProtocolError(
                    "server acknowledged a sequence that was not sent"
                )
            ready_keys = sorted(through)
            missing = [
                sequence for sequence in ready_keys if sequence not in self.pending
            ]
            if missing:
                raise StreamProtocolError(
                    "server acknowledged a sequence that is not pending"
                )
            ready = [self.pending.pop(sequence) for sequence in ready_keys]

        for _ in ready:
            self.capacity.release()
        return ready

    async def notify_decision(self, result: StreamInspectionResult) -> None:
        if self.on_decision is None:
            return
        callback_result = self.on_decision(result)
        if inspect.isawaitable(callback_result):
            await callback_result

    def record_acknowledgement(self, sequence: int, count: int) -> None:
        attributes = self.observed(
            through_sequence=sequence,
            sequence_count=count,
        )
        with self.observer.span("aidefense.stream.acknowledgement", attributes):
            self.observer.event(ReasonCode.ACK_RECEIVED, attributes=attributes)

    def record_block(
        self, sequence: int, action: str, decision: StreamDecision
    ) -> None:
        with self.observer.span(
            "aidefense.stream.block",
            self.observed(through_sequence=sequence),
        ):
            self.observer.event(
                ReasonCode.DECISION_BLOCK,
                level=logging.WARNING,
                attributes=self.observed(
                    through_sequence=sequence,
                    action=action,
                    is_safe=decision.is_safe,
                ),
            )

    def record_allow(
        self, sequence: int, action: str, decision: StreamDecision
    ) -> None:
        attributes = self.observed(
            through_sequence=sequence,
            action=action,
            is_safe=decision.is_safe,
        )
        with self.observer.span("aidefense.stream.decision", attributes):
            self.observer.event(ReasonCode.DECISION_ALLOW, attributes=attributes)

    def approve(
        self,
        ready: Sequence[_Pending],
        action: str,
        decision: StreamDecision,
    ) -> None:
        """Store safe output while preserving sparse acknowledgement ordering."""

        if action != "redact":
            for item in ready:
                outputs = (
                    () if item.application_event is None else (item.application_event,)
                )
                self.approved[item.sequence] = _Approved(outputs=outputs)
            return

        for item in ready:
            self.approved[item.sequence] = _Approved(outputs=())
        if not decision.redacted_content:
            return

        originals = [
            item.application_event
            for item in ready
            if item.application_event is not None
        ]
        if not originals:
            return
        redacted = _with_redacted_text(originals[-1], decision.redacted_content)
        if redacted is not None:
            # A batched result has one replacement, so emit it once on the
            # latest acknowledged event rather than once per sequence.
            self.approved[ready[-1].sequence] = _Approved(outputs=(redacted,))

    async def release_approved(self) -> None:
        """Release only a contiguous prefix, even for sparse bulk responses."""

        released_sequences = 0
        released_outputs = 0
        while self.next_release_sequence in self.approved:
            released = self.approved.pop(self.next_release_sequence)
            self.next_release_sequence += 1
            released_sequences += 1
            for application_event in released.outputs:
                await self.output.put(application_event)
                released_outputs += 1
        if released_sequences:
            self.observer.debug(
                ReasonCode.EVENTS_RELEASED,
                attributes=self.observed(
                    sequence_count=released_sequences,
                    output_count=released_outputs,
                    next_release_sequence=self.next_release_sequence,
                ),
            )

    async def validate_server_close(self) -> None:
        async with self.pending_lock:
            if not self.half_close_started.is_set() and not self.terminal.is_set():
                raise StreamProtocolError("server closed before the client half-closed")
            if self.pending and not self.terminal.is_set():
                raise StreamProtocolError("stream closed with unacknowledged content")
            if self.approved and not self.terminal.is_set():
                raise StreamProtocolError(
                    "stream closed before acknowledged content could be released"
                )

    def has_pending_request(self) -> bool:
        return any(
            item.direction is StreamDirection.REQUEST for item in self.pending.values()
        )

    async def fail_worker(self, exc: Exception, *, cancel: bool) -> None:
        # Check-and-set has no await and therefore acts as the terminal outcome
        # arbitration point for workers on this event loop.
        if self.terminal.is_set():
            return
        self.terminal.set()
        mapped = self.map_error(exc)
        current = asyncio.current_task()
        self.observer.debug(
            ReasonCode.WORKER_FAILED,
            attributes=self.observed(
                worker_name=current.get_name() if current is not None else "unknown",
                error_reason=mapped.reason_code,
                cancel_rpc=cancel,
            ),
        )
        await self.output.put(mapped)
        if cancel:
            await self.cancel_call()

    async def next_output(self) -> Any:
        """Wait for output under both the absolute and oldest-frame deadlines."""

        now = time.monotonic()
        remaining = self.started + self.config.absolute_timeout - now
        if remaining <= 0:
            raise StreamTimeoutError("event stream absolute timeout expired")

        async with self.pending_lock:
            oldest = min((item.sent_at for item in self.pending.values()), default=None)
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
            return await asyncio.wait_for(self.output.get(), timeout=wait_timeout)
        except asyncio.TimeoutError as exc:
            if oldest is None:
                raise StreamTimeoutError(
                    "event stream absolute timeout expired", cause=exc
                ) from exc
            raise StreamTimeoutError(
                "event stream frame was not acknowledged before idle timeout",
                cause=exc,
            ) from exc

    async def cancel_call(self) -> None:
        """Cancel the RPC once without allowing cleanup to mask its result."""

        if self.call is None or self.call_cancelled:
            return
        # There is no await before this assignment, so concurrent worker cleanup
        # cannot invoke cancel twice.
        self.call_cancelled = True
        try:
            result = self.call.cancel()
            if inspect.isawaitable(result):
                await self.await_cleanup(result, "call_cancel")
        except Exception:
            self.record_cleanup_failure("call_cancel")

    async def close_channel(self) -> None:
        """Bound channel cleanup so a broken transport cannot hang the caller."""

        if self.channel is None or self.channel_closed:
            return
        self.channel_closed = True
        try:
            close = getattr(self.channel, "close", None)
            if close is None:
                return
            result = close()
            if inspect.isawaitable(result):
                await self.await_cleanup(result, "channel_close")
        except Exception:
            self.record_cleanup_failure("channel_close")

    async def await_cleanup(self, awaitable: Any, stage: str) -> None:
        """Wait for cleanup without trusting cancellation to be cooperative."""

        cleanup_task = asyncio.ensure_future(awaitable)
        done, pending = await asyncio.wait(
            {cleanup_task}, timeout=_CLEANUP_TIMEOUT_SECONDS
        )
        if done:
            # Propagate now so the caller can record the failed cleanup stage.
            cleanup_task.result()
            return

        self.record_cleanup_failure(stage)
        cleanup_task.cancel()
        # A third-party coroutine can suppress cancellation. Detach it after
        # retrieving any eventual exception so SDK shutdown remains bounded.
        cleanup_task.add_done_callback(_consume_task_result)

    def record_cleanup_failure(self, stage: str) -> None:
        self.observer.event(
            ReasonCode.CLEANUP_FAILED,
            level=logging.WARNING,
            attributes=self.observed(cleanup_stage=stage),
        )

    async def cleanup(self) -> None:
        """Release workers, transport, queues, and retained customer content.

        Cleanup executes from ``run``'s ``finally`` on every terminal path. All
        application-owned awaitables are bounded because a vendor iterator or
        custom channel may ignore cancellation.
        """

        self.terminal.set()
        self.observer.debug(
            ReasonCode.CLEANUP_STARTED,
            attributes=self.observed(
                outcome=self.outcome,
                task_count=len(self.tasks),
                pending_count=len(self.pending),
                approved_count=len(self.approved),
            ),
        )
        if self.call is not None and not self.server_blocked:
            await self.cancel_call()
        for task in self.tasks:
            if not task.done():
                task.cancel()
        if self.tasks:
            done, pending = await asyncio.wait(
                self.tasks, timeout=_CLEANUP_TIMEOUT_SECONDS
            )
            for task in done:
                _consume_task_result(task)
            if pending:
                self.record_cleanup_failure("worker_shutdown")
                for task in pending:
                    task.cancel()
                    task.add_done_callback(_consume_task_result)
        await self.close_channel()

        if self.active_stream_counted:
            self.observer.active_streams(-1)
        self.observer.latency(time.monotonic() - self.started, self.outcome)
        if self.outcome == "completed":
            self.observer.event(ReasonCode.STREAM_COMPLETED, attributes=self.observed())

        self.observer.debug(
            ReasonCode.CLEANUP_COMPLETED,
            attributes=self.observed(outcome=self.outcome),
        )

        # Do not retain customer events or transport objects if the caller keeps
        # a reference to the exhausted async generator.
        self.pending.clear()
        self.approved.clear()
        while not self.output.empty():
            try:
                self.output.get_nowait()
            except asyncio.QueueEmpty:
                break
        self.tasks.clear()
        self.events = None
        self.call = None
        self.channel = None

    def client_tls_mode(self) -> str:
        """Describe TLS without exposing endpoint, certificates, or keys."""

        if not self.config.tls:
            return "insecure"
        if self.config.client_certificate is not None:
            return "mutual_tls"
        if self.config.root_certificates is not None:
            return "custom_ca"
        return "default_tls"
