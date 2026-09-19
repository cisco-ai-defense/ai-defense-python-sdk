# Copyright 2026 Cisco Systems, Inc. and its affiliates
# SPDX-License-Identifier: Apache-2.0

"""Content-safe logs, spans, and metric hooks for streaming inspection."""

from __future__ import annotations

import logging
from contextlib import nullcontext
from enum import Enum
from typing import Any, ContextManager, Dict, Mapping, Optional


class ReasonCode(str, Enum):
    STREAM_STARTED = "STREAM_STARTED"
    EVENT_SENT = "EVENT_SENT"
    ACK_RECEIVED = "ACK_RECEIVED"
    DECISION_ALLOW = "DECISION_ALLOW"
    DECISION_BLOCK = "DECISION_BLOCK"
    BACKPRESSURE_WAIT = "BACKPRESSURE_WAIT"
    STREAM_TIMEOUT = "STREAM_TIMEOUT"
    STREAM_CANCELLED = "STREAM_CANCELLED"
    STREAM_FAILED = "STREAM_FAILED"
    STREAM_COMPLETED = "STREAM_COMPLETED"
    CONFIGURATION_INVALID = "CONFIGURATION_INVALID"


class StreamObserver:
    """Small dependency-free bridge to an application's tracer and metrics."""

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
