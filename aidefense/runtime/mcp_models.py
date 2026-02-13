# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

"""
MCP (Model Context Protocol) models for inspection requests and responses.

This module defines the data models for MCP JSON-RPC 2.0 message inspection,
following the official MCP specification.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Union, List

from .models import InspectResponse


@dataclass
class MCPError:
    """
    MCP Error object for JSON-RPC 2.0 error responses.

    Standard JSON-RPC 2.0 error codes:
        -32700: Parse error
        -32600: Invalid request
        -32601: Method not found
        -32602: Invalid params
        -32603: Internal error

    Attributes:
        code (int): JSON-RPC error code.
        message (str): Human-readable error message.
        data (Optional[Dict[str, Any]]): Optional additional error data.
    """

    code: int
    message: str
    data: Optional[Dict[str, Any]] = None


@dataclass
class MCPMessage:
    """
    MCP JSON-RPC 2.0 Message following official specification.

    Message type is auto-detected from structure:
        - Request: has 'method' + 'id' fields
        - Response: has ('result' or 'error') + 'id' fields
        - Notification: has 'method' field without 'id'

    Common MCP methods:
        - tools/call, tools/list
        - resources/read, resources/list
        - prompts/get, prompts/list
        - notifications/progress

    Attributes:
        jsonrpc (str): JSON-RPC version, must be "2.0".
        method (Optional[str]): Method name (present in requests and notifications).
        params (Optional[Dict[str, Any]]): Method parameters (flexible JSON object).
        result (Optional[Dict[str, Any]]): Success result (present in successful responses).
        error (Optional[MCPError]): Error object (present in error responses).
        id (Optional[Union[str, int]]): Request/response correlation ID.
            Present in requests and responses, absent in notifications.
            Can be string or number per JSON-RPC 2.0 spec.
    """

    jsonrpc: str = "2.0"
    method: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[MCPError] = None
    id: Optional[Union[str, int]] = None


@dataclass
class MCPInspectError:
    """
    Error response for MCP inspection failures.

    Standard JSON-RPC 2.0 error codes:
        -32700: Parse error
        -32600: Invalid Request
        -32601: Method not found
        -32602: Invalid params
        -32603: Internal error

    Custom error codes:
        -32000: Service unavailable
        -32001: Unauthorized
        -32002: Forbidden
        -32003: Rate limited

    Attributes:
        code (int): JSON-RPC error code.
        message (str): Human-readable error message.
        data (Optional[Dict[str, Any]]): Optional additional error context.
    """

    code: int
    message: str
    data: Optional[Dict[str, Any]] = None


@dataclass
class MCPInspectResponse:
    """
    MCP Inspect Response wrapping inspection results in JSON-RPC 2.0 format.

    The response follows MCP protocol with inspection data in the 'result' field.

    Attributes:
        jsonrpc (str): JSON-RPC version, always "2.0".
        result (Optional[InspectResponse]): Success result containing inspection details.
        error (Optional[MCPInspectError]): Error result for failed inspections.
        id (Optional[Union[str, int]]): Request ID echoed from the inspected MCP message.
            Null if the inspected message was a notification.
    """

    jsonrpc: str = "2.0"
    result: Optional[InspectResponse] = None
    error: Optional[MCPInspectError] = None
    id: Optional[Union[str, int]] = None

