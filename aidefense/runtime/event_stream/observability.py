# Copyright 2026 Cisco Systems, Inc. and its affiliates
# SPDX-License-Identifier: Apache-2.0

"""Content-safe logs, spans, and metric hooks for streaming inspection."""

from __future__ import annotations

import logging
from contextlib import nullcontext
from enum import Enum
from typing import Any, ContextManager, Dict, Mapping, Optional


class ReasonCode(str, Enum):
    """Stable, content-safe identifiers used by logs, spans, and metrics.

    Lifecycle-only values may be emitted through :meth:`StreamObserver.debug`
    and therefore do not automatically become metrics. Decision and terminal
    values use :meth:`StreamObserver.event` and are suitable metric dimensions.
    """

    STREAM_CONFIGURED = "STREAM_CONFIGURED"
    CHANNEL_OPENING = "CHANNEL_OPENING"
    CHANNEL_READY = "CHANNEL_READY"
    STREAM_STARTED = "STREAM_STARTED"
    START_FRAME_SENT = "START_FRAME_SENT"
    WORKERS_STARTED = "WORKERS_STARTED"
    REQUEST_GATE_WAIT = "REQUEST_GATE_WAIT"
    REQUEST_GATE_OPEN = "REQUEST_GATE_OPEN"
    SOURCE_EXHAUSTED = "SOURCE_EXHAUSTED"
    EVENT_SENT = "EVENT_SENT"
    RESULT_PARSED = "RESULT_PARSED"
    ACK_RECEIVED = "ACK_RECEIVED"
    EVENTS_RELEASED = "EVENTS_RELEASED"
    DECISION_ALLOW = "DECISION_ALLOW"
    DECISION_BLOCK = "DECISION_BLOCK"
    BACKPRESSURE_WAIT = "BACKPRESSURE_WAIT"
    WORKER_FAILED = "WORKER_FAILED"
    STREAM_TIMEOUT = "STREAM_TIMEOUT"
    STREAM_CANCELLED = "STREAM_CANCELLED"
    STREAM_FAILED = "STREAM_FAILED"
    STREAM_HALF_CLOSED = "STREAM_HALF_CLOSED"
    STREAM_COMPLETED = "STREAM_COMPLETED"
    CLEANUP_STARTED = "CLEANUP_STARTED"
    CLEANUP_COMPLETED = "CLEANUP_COMPLETED"
    CLEANUP_FAILED = "CLEANUP_FAILED"
    CONFIGURATION_INVALID = "CONFIGURATION_INVALID"


class StreamObserver:
    """Content-safe bridge to application logging, tracing, and metrics.

    ``logger`` follows the standard-library ``logging.Logger`` API. ``tracer``
    must expose ``start_as_current_span(name, attributes=...)``. ``metrics`` may
    expose ``record(reason, attributes)``, ``active_streams(delta)``, and
    ``latency(seconds, outcome)``. Every hook is best-effort: observability can
    never change inspection or content-release behavior.
    """

    def __init__(
        self,
        *,
        logger: Optional[logging.Logger] = None,
        tracer: Optional[Any] = None,
        metrics: Optional[Any] = None,
    ) -> None:
        self._logger = logger or logging.getLogger("aidefense.runtime.event_stream")
        self._tracer = tracer
        self._metrics = metrics

    def debug(
        self,
        reason: ReasonCode,
        *,
        attributes: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """Write content-free transport diagnostics when DEBUG is enabled.

        Debug records intentionally do not call ``metrics.record``. This keeps
        operational metrics stable when an application changes its log level.
        """

        # Attribute safety is enforced at the call sites. Keeping this bridge
        # generic lets applications use their normal logging.Logger without an
        # SDK-specific dependency or formatter.
        safe = dict(attributes or {})
        try:
            self._logger.debug(
                "AI Defense event stream debug: %s", reason.value, extra=safe
            )
        except Exception:
            pass

    def span(self, name: str, attributes: Mapping[str, Any]) -> ContextManager[Any]:
        if self._tracer is None:
            return nullcontext()
        try:
            return self._tracer.start_as_current_span(name, attributes=dict(attributes))
        except Exception:
            return nullcontext()

    def event(
        self,
        reason: ReasonCode,
        *,
        level: int = logging.INFO,
        attributes: Optional[Mapping[str, Any]] = None,
    ) -> None:
        safe = dict(attributes or {})
        # Callers only pass bounded transport metadata here. Content, credentials,
        # session IDs, conversation IDs, and request IDs are intentionally absent.
        try:
            self._logger.log(
                level, "AI Defense event stream: %s", reason.value, extra=safe
            )
        except Exception:
            pass
        if self._metrics is not None:
            callback = getattr(self._metrics, "record", None)
            if callback is not None:
                try:
                    callback(reason.value, safe)
                except Exception:
                    pass

    def active_streams(self, delta: int) -> None:
        if self._metrics is not None:
            callback = getattr(self._metrics, "active_streams", None)
            if callback is not None:
                try:
                    callback(delta)
                except Exception:
                    pass

    def latency(self, seconds: float, outcome: str) -> None:
        if self._metrics is not None:
            callback = getattr(self._metrics, "latency", None)
            if callback is not None:
                try:
                    callback(seconds, outcome)
                except Exception:
                    pass
