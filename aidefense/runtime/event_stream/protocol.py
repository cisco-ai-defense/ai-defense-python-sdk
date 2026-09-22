# Copyright 2026 Cisco Systems, Inc. and its affiliates
# SPDX-License-Identifier: Apache-2.0

"""Optional validated protocol models for advanced integrations.

Most applications should use :class:`EventStreamClient`, ``StreamEvent``, and
an adapter. These Pydantic models provide a stable SDK import path when an
integration needs the underlying event-stream contract without depending on
generated protobuf modules.
"""

from aidefense.pydantic.runtime.ai_defense.inspection_grpc.v1.inspection_grpc_pydantic import (
    ConversationPayload,
    Direction,
    InspectionContext,
    InspectionEvent,
    InspectionResult,
    InspectStreamEvents,
    InspectStreamRequest,
    InspectStreamStart,
)

__all__ = [
    "ConversationPayload",
    "Direction",
    "InspectionContext",
    "InspectionEvent",
    "InspectionResult",
    "InspectStreamEvents",
    "InspectStreamRequest",
    "InspectStreamStart",
]
