# Copyright 2026 Cisco Systems, Inc. and its affiliates
# SPDX-License-Identifier: Apache-2.0

"""Deferred imports for the optional event-stream transport dependencies."""

from typing import Any, Tuple


_INSTALL_HINT = (
    "Event-stream support requires the optional transport dependencies; "
    "install cisco-aidefense-sdk[streaming]."
)


def require_grpc() -> Any:
    """Load grpcio only when a stream transport is actually opened."""

    try:
        import grpc  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError(_INSTALL_HINT) from exc
    return grpc


def require_wire_dependencies() -> Tuple[Any, Any, Any, Any]:
    """Load protobuf-backed wire types only when a frame is constructed."""

    try:
        from google.protobuf.json_format import (  # type: ignore[import-untyped]
            MessageToDict,
            ParseDict,
        )
        from aidefense.pydantic.runtime.ai_defense.inspection_grpc.v1 import (
            inspection_grpc_pb2 as stream_api,
        )
        from aidefense.pydantic.runtime.ai_defense.inspection_grpc.v1 import (
            inspection_grpc_pydantic as runtime_stream,
        )
    except ImportError as exc:
        raise ImportError(_INSTALL_HINT) from exc
    return MessageToDict, ParseDict, stream_api, runtime_stream
