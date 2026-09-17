# Copyright 2026 Cisco Systems, Inc. and its affiliates
# SPDX-License-Identifier: Apache-2.0

"""Public models for high-level streaming inspection."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Tuple

from aidefense.pydantic.runtime.ai_defense.inspection.v1.inspection_pydantic import (
    Message as CanonicalMessage,
    ToolCall,
)

from .exceptions import StreamConfigurationError


class StreamDirection(str, Enum):
    """Direction of content relative to the model."""

    REQUEST = "request"
    RESPONSE = "response"


@dataclass(frozen=True)
class StreamContext:
    """Correlation context whose lifetime is one gRPC stream."""

    session_id: str
    request_id: str
    conversation_id: str
    actor_id: str = ""

    def validate(self) -> None:
        for name in ("session_id", "request_id", "conversation_id"):
            if not getattr(self, name).strip():
                raise StreamConfigurationError(f"{name} must not be empty")


@dataclass(frozen=True)
class SourceRange:
    """Half-open offsets in the canonical, non-overlapped logical message."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise StreamConfigurationError(
                "source range must satisfy 0 <= start <= end"
            )


@dataclass(frozen=True)
class StreamEvent:
    """One application event and the canonical content derived from it."""

    application_event: Any
    message: Optional[CanonicalMessage]
    direction: StreamDirection
    message_id: str
    source_range: Optional[SourceRange] = None


@dataclass(frozen=True)
class StreamDecision:
    """Content-safe summary of a server inspection decision."""

    is_safe: bool
    action: str
    event_id: str = ""
    classifications: Tuple[str, ...] = ()
    rules: Tuple[str, ...] = ()
    redacted_content: Optional[str] = None


@dataclass(frozen=True)
class StreamInspectionResult:
    """One ordered server acknowledgement with its client-known origin."""

    decision: StreamDecision
    through_sequences: Tuple[int, ...]
    directions: Tuple[StreamDirection, ...]


@dataclass(frozen=True)
class EventStreamConfig:
    """Validated connection, batching, timeout, and backpressure settings."""

    endpoint: str
    api_key: str = field(repr=False)
    use_tls: bool = True
    root_certificates: Optional[bytes] = field(default=None, repr=False)
    batch_interval: float = 0.05
    token_limit: int = 512
    overlap_tokens: int = 32
    idle_timeout: float = 30.0
    absolute_timeout: float = 300.0
    max_pending_batches: int = 32
    input_queue_size: int = 128
    max_events_per_frame: int = 256
    max_stream_events: int = 4096
    max_stream_bytes: int = 8 * 1024 * 1024
    metadata: Tuple[Tuple[str, str], ...] = ()

    API_KEY_ENV = "AI_DEFENSE_EVENT_STREAM_API_KEY"
    FALLBACK_API_KEY_ENV = "AI_DEFENSE_API_MODE_LLM_API_KEY"
    ENDPOINT_ENV = "AI_DEFENSE_EVENT_STREAM_ENDPOINT"

    def __post_init__(self) -> None:
        self.validate()

    @classmethod
    def from_env(cls, **overrides: Any) -> "EventStreamConfig":
        """Load the credential and endpoint from runtime environment secrets."""

        values = dict(overrides)
        values.setdefault("endpoint", os.getenv(cls.ENDPOINT_ENV, ""))
        values.setdefault(
            "api_key",
            os.getenv(cls.API_KEY_ENV) or os.getenv(cls.FALLBACK_API_KEY_ENV, ""),
        )
        return cls(**values)

    def validate(self) -> None:
        if not self.endpoint.strip():
            raise StreamConfigurationError("endpoint must not be empty")
        if not self.api_key.strip():
            raise StreamConfigurationError(
                f"api_key is required; set {self.API_KEY_ENV} in secure runtime configuration"
            )
        if self.batch_interval <= 0:
            raise StreamConfigurationError("batch_interval must be greater than zero")
        if self.token_limit < 1:
            raise StreamConfigurationError("token_limit must be at least 1")
        if self.overlap_tokens < 0 or self.overlap_tokens >= self.token_limit:
            raise StreamConfigurationError(
                "overlap_tokens must be non-negative and smaller than token_limit"
            )
        if self.idle_timeout <= 0 or self.absolute_timeout <= 0:
            raise StreamConfigurationError("timeouts must be greater than zero")
        if self.absolute_timeout < self.idle_timeout:
            raise StreamConfigurationError(
                "absolute_timeout must be greater than or equal to idle_timeout"
            )
        if not 1 <= self.max_pending_batches <= self.max_stream_events:
            raise StreamConfigurationError(
                "max_pending_batches must be between 1 and max_stream_events"
            )
        if self.input_queue_size < 1:
            raise StreamConfigurationError("input_queue_size must be at least 1")
        if not 1 <= self.max_events_per_frame <= 256:
            raise StreamConfigurationError(
                "max_events_per_frame must be between 1 and the server limit of 256"
            )
        if not 1 <= self.max_stream_events <= 4096:
            raise StreamConfigurationError(
                "max_stream_events must be between 1 and the server limit of 4096"
            )
        if not 1 <= self.max_stream_bytes <= 8 * 1024 * 1024:
            raise StreamConfigurationError(
                "max_stream_bytes must not exceed the server limit of 8 MiB"
            )
        reserved = {
            "x-cisco-ai-defense-api-key",
            "x-aidefense-request-id",
        }
        for key, value in self.metadata:
            if key.lower() in reserved:
                raise StreamConfigurationError(
                    f"metadata key {key!r} is managed by the SDK"
                )
            if key.lower() != key or not value:
                raise StreamConfigurationError(
                    "metadata keys must be lowercase and metadata values must not be empty"
                )
