# Copyright 2026 Cisco Systems, Inc. and its affiliates
# SPDX-License-Identifier: Apache-2.0

"""Typed failures raised by the bidirectional inspection client."""

from typing import Optional

from aidefense.exceptions import SDKError


class EventStreamError(SDKError):
    """Base class for event-stream failures."""

    reason_code = "STREAM_FAILURE"

    def __init__(self, message: str, *, cause: Optional[BaseException] = None):
        super().__init__(message)
        self.cause = cause


class StreamConfigurationError(EventStreamError, ValueError):
    """The stream configuration is invalid and nothing was sent."""

    reason_code = "CONFIGURATION_INVALID"


class UnsafeContentError(EventStreamError):
    """AI Defense blocked content before it was released to the application."""

    reason_code = "CONTENT_UNSAFE"

    def __init__(
        self,
        message: str,
        *,
        decision: object,
        sequences: tuple,
        directions: tuple = (),
    ):
        super().__init__(message)
        self.decision = decision
        self.sequences = sequences
        self.directions = directions


class StreamTimeoutError(EventStreamError, TimeoutError):
    """The stream exceeded its idle or absolute deadline."""

    reason_code = "STREAM_TIMEOUT"


class StreamCancelledError(EventStreamError):
    """The caller or remote endpoint cancelled the stream."""

    reason_code = "STREAM_CANCELLED"


class StreamConnectionError(EventStreamError, ConnectionError):
    """The gRPC stream could not be opened or failed in transit."""

    reason_code = "CONNECTION_FAILURE"


class StreamSourceError(EventStreamError, RuntimeError):
    """The application/framework event source failed while producing content."""

    reason_code = "SOURCE_FAILURE"


class StreamProtocolError(EventStreamError):
    """The server returned an invalid or inconsistent acknowledgement."""

    reason_code = "PROTOCOL_FAILURE"


class StreamBackpressureError(EventStreamError):
    """The configured local buffering limit was exceeded."""

    reason_code = "BACKPRESSURE_LIMIT"
