# Copyright 2026 Cisco Systems, Inc. and its affiliates
# SPDX-License-Identifier: Apache-2.0

from pydantic import BaseModel

from aidefense.runtime.event_stream.protocol import (
    InspectionEvent,
    InspectStreamRequest,
)


def test_advanced_protocol_models_are_exposed_as_pydantic_not_protobuf():
    assert issubclass(InspectionEvent, BaseModel)
    assert issubclass(InspectStreamRequest, BaseModel)
