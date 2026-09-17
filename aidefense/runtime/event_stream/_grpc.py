# Copyright 2026 Cisco Systems, Inc. and its affiliates
# SPDX-License-Identifier: Apache-2.0

"""Minimal private gRPC stub for the generated streaming messages."""

from typing import Any

from aidefense.runtime.event_stream._generated.ai_defense.inspection_grpc.v1 import (
    inspection_grpc_pb2,
)


class InspectionServiceStub:
    def __init__(self, channel: Any) -> None:
        self.InspectEventStream = channel.stream_stream(
            "/inspection_grpc.v1.InspectionService/InspectEventStream",
            request_serializer=inspection_grpc_pb2.InspectStreamRequest.SerializeToString,
            response_deserializer=inspection_grpc_pb2.InspectionResult.FromString,
        )
