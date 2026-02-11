# Copyright 2025 Cisco Systems, Inc. and its affiliates
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
Tests for the MCP (Model Context Protocol) inspection client.
"""

import pytest
from unittest.mock import MagicMock, patch

from aidefense.runtime.mcp_inspect import MCPInspectionClient
from aidefense.runtime.mcp_models import MCPMessage, MCPError, MCPInspectResponse, MCPInspectError
from aidefense.runtime.models import InspectResponse, Action, Classification
from aidefense.config import Config
from aidefense.exceptions import ValidationError


# Create a valid format dummy API key for testing (must be 64 characters)
TEST_API_KEY = "0123456789" * 6 + "0123"  # 64 characters


@pytest.fixture(autouse=True)
def reset_config_singleton():
    """Reset Config singleton before each test."""
    Config._instance = None
    yield
    Config._instance = None


@pytest.fixture
def mock_request_handler():
    """Create a mock request handler."""
    return MagicMock()


@pytest.fixture
def mcp_client(mock_request_handler):
    """Create an MCPInspectionClient with a mock request handler."""
    with patch('aidefense.runtime.inspection_client.RequestHandler') as MockHandler:
        MockHandler.return_value = mock_request_handler
        client = MCPInspectionClient(api_key=TEST_API_KEY)
        client._request_handler = mock_request_handler
        return client


class TestMCPInspectionClient:
    """Tests for the MCPInspectionClient."""

    def test_client_initialization(self):
        """Test MCPInspectionClient can be instantiated."""
        client = MCPInspectionClient(api_key=TEST_API_KEY)
        assert client is not None
        assert "/api/v1/inspect/mcp" in client.endpoint

    def test_inspect_tool_call(self, mcp_client, mock_request_handler):
        """Test inspecting an MCP tool call."""
        mock_request_handler.request.return_value = {
            "jsonrpc": "2.0",
            "result": {
                "is_safe": True,
                "classifications": [],
                "action": "ALLOW",
            },
            "id": 1,
        }

        result = mcp_client.inspect_tool_call(
            tool_name="search_documentation",
            arguments={"query": "SSL configuration"},
            message_id=1
        )

        mock_request_handler.request.assert_called_once()
        assert isinstance(result, MCPInspectResponse)
        assert result.jsonrpc == "2.0"
        assert result.result is not None
        assert result.result.is_safe is True
        assert result.id == 1

    def test_inspect_resource_read(self, mcp_client, mock_request_handler):
        """Test inspecting an MCP resource read request."""
        mock_request_handler.request.return_value = {
            "jsonrpc": "2.0",
            "result": {
                "is_safe": False,
                "classifications": ["SECURITY_VIOLATION"],
                "action": "BLOCK",
                "explanation": "Sensitive file access detected",
            },
            "id": "read-123",
        }

        result = mcp_client.inspect_resource_read(
            uri="file:///etc/passwd",
            message_id="read-123"
        )

        mock_request_handler.request.assert_called_once()
        assert isinstance(result, MCPInspectResponse)
        assert result.result is not None
        assert result.result.is_safe is False
        assert result.id == "read-123"

    def test_inspect_response(self, mcp_client, mock_request_handler):
        """Test inspecting an MCP response message."""
        mock_request_handler.request.return_value = {
            "jsonrpc": "2.0",
            "result": {
                "is_safe": False,
                "classifications": ["PII"],
                "action": "BLOCK",
                "explanation": "Response contains PII",
            },
            "id": 1,
        }

        result = mcp_client.inspect_response(
            result_data={
                "content": [
                    {"type": "text", "text": "User SSN: 123-45-6789"}
                ]
            },
            method="tools/call",
            params={"name": "get_user_info", "arguments": {"user_id": "123"}},
            message_id=1
        )

        mock_request_handler.request.assert_called_once()
        assert isinstance(result, MCPInspectResponse)
        assert result.result is not None
        assert result.result.is_safe is False

    def test_inspect_raw_message(self, mcp_client, mock_request_handler):
        """Test inspecting a raw MCPMessage."""
        mock_request_handler.request.return_value = {
            "jsonrpc": "2.0",
            "result": {
                "is_safe": True,
                "classifications": [],
                "action": "ALLOW",
            },
            "id": 42,
        }

        message = MCPMessage(
            jsonrpc="2.0",
            method="tools/call",
            params={"name": "echo", "arguments": {"text": "hello"}},
            id=42
        )

        result = mcp_client.inspect(message)

        mock_request_handler.request.assert_called_once()
        assert isinstance(result, MCPInspectResponse)
        assert result.result.is_safe is True
        assert result.id == 42

    def test_inspect_notification(self, mcp_client, mock_request_handler):
        """Test inspecting an MCP notification (no id)."""
        mock_request_handler.request.return_value = {
            "jsonrpc": "2.0",
            "result": {
                "is_safe": True,
                "classifications": [],
                "action": "ALLOW",
            },
        }

        message = MCPMessage(
            jsonrpc="2.0",
            method="notifications/progress",
            params={"progress": 50, "message": "Processing..."},
            # No id for notifications
        )

        result = mcp_client.inspect(message)

        mock_request_handler.request.assert_called_once()
        assert result.id is None

    def test_inspect_error_response(self, mcp_client, mock_request_handler):
        """Test handling an error response from the API."""
        mock_request_handler.request.return_value = {
            "jsonrpc": "2.0",
            "error": {
                "code": -32600,
                "message": "Invalid Request",
                "data": {"details": "Missing required field"},
            },
            "id": 1,
        }

        message = MCPMessage(
            jsonrpc="2.0",
            method="tools/call",
            params={"name": "test"},
            id=1
        )

        result = mcp_client.inspect(message)

        assert isinstance(result, MCPInspectResponse)
        assert result.error is not None
        assert result.error.code == -32600
        assert result.error.message == "Invalid Request"
        assert result.result is None


class TestMCPMessageValidation:
    """Tests for MCP message validation."""

    def test_validate_invalid_jsonrpc_version(self, mcp_client):
        """Test validation rejects invalid jsonrpc version."""
        request_dict = {
            "jsonrpc": "1.0",
            "method": "test",
            "id": 1,
        }

        with pytest.raises(ValidationError) as excinfo:
            mcp_client.validate_mcp_message(request_dict)

        assert "'jsonrpc' must be '2.0'" in str(excinfo.value)

    def test_validate_missing_method_and_result(self, mcp_client):
        """Test validation rejects message without method or result."""
        request_dict = {
            "jsonrpc": "2.0",
            "id": 1,
        }

        with pytest.raises(ValidationError) as excinfo:
            mcp_client.validate_mcp_message(request_dict)

        assert "must have 'method'" in str(excinfo.value)

    def test_validate_invalid_params_type(self, mcp_client):
        """Test validation rejects non-dict params."""
        request_dict = {
            "jsonrpc": "2.0",
            "method": "test",
            "params": "invalid_string",
            "id": 1,
        }

        with pytest.raises(ValidationError) as excinfo:
            mcp_client.validate_mcp_message(request_dict)

        assert "'params' must be a dict" in str(excinfo.value)

    def test_validate_invalid_result_type(self, mcp_client):
        """Test validation rejects non-dict result."""
        request_dict = {
            "jsonrpc": "2.0",
            "result": "invalid_string",
            "id": 1,
        }

        with pytest.raises(ValidationError) as excinfo:
            mcp_client.validate_mcp_message(request_dict)

        assert "'result' must be a dict" in str(excinfo.value)

    def test_validate_invalid_error_structure(self, mcp_client):
        """Test validation rejects invalid error structure."""
        request_dict = {
            "jsonrpc": "2.0",
            "error": {"message": "test"},  # Missing 'code'
            "id": 1,
        }

        with pytest.raises(ValidationError) as excinfo:
            mcp_client.validate_mcp_message(request_dict)

        assert "'error.code' must be an integer" in str(excinfo.value)

    def test_validate_valid_request(self, mcp_client):
        """Test validation passes for valid request message."""
        request_dict = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "test", "arguments": {}},
            "id": 1,
        }

        # Should not raise
        mcp_client.validate_mcp_message(request_dict)

    def test_validate_valid_response(self, mcp_client):
        """Test validation passes for valid response message (method and params required)."""
        request_dict = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "get_info", "arguments": {}},
            "result": {"content": []},
            "id": 1,
        }

        # Should not raise
        mcp_client.validate_mcp_message(request_dict)

    def test_validate_response_requires_method(self, mcp_client):
        """Test response body without method raises ValidationError."""
        request_dict = {
            "jsonrpc": "2.0",
            "params": {},
            "result": {"content": []},
            "id": 1,
        }
        with pytest.raises(ValidationError, match="method"):
            mcp_client.validate_mcp_message(request_dict)

    def test_validate_response_requires_params(self, mcp_client):
        """Test response body without params raises ValidationError."""
        request_dict = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "result": {"content": []},
            "id": 1,
        }
        with pytest.raises(ValidationError, match="params"):
            mcp_client.validate_mcp_message(request_dict)

    def test_validate_valid_error_response(self, mcp_client):
        """Test validation passes for valid error response."""
        request_dict = {
            "jsonrpc": "2.0",
            "error": {
                "code": -32600,
                "message": "Invalid Request",
            },
            "id": 1,
        }

        # Should not raise
        mcp_client.validate_mcp_message(request_dict)


class TestMCPModels:
    """Tests for MCP data models."""

    def test_mcp_message_creation(self):
        """Test MCPMessage dataclass creation."""
        message = MCPMessage(
            jsonrpc="2.0",
            method="tools/call",
            params={"name": "test", "arguments": {"key": "value"}},
            id=1
        )

        assert message.jsonrpc == "2.0"
        assert message.method == "tools/call"
        assert message.params == {"name": "test", "arguments": {"key": "value"}}
        assert message.id == 1
        assert message.result is None
        assert message.error is None

    def test_mcp_message_response(self):
        """Test MCPMessage as response."""
        message = MCPMessage(
            jsonrpc="2.0",
            result={"content": [{"type": "text", "text": "Hello"}]},
            id="resp-123"
        )

        assert message.result == {"content": [{"type": "text", "text": "Hello"}]}
        assert message.id == "resp-123"
        assert message.method is None

    def test_mcp_error_creation(self):
        """Test MCPError dataclass creation."""
        error = MCPError(
            code=-32600,
            message="Invalid Request",
            data={"field": "method"}
        )

        assert error.code == -32600
        assert error.message == "Invalid Request"
        assert error.data == {"field": "method"}

    def test_mcp_inspect_response_success(self):
        """Test MCPInspectResponse with success result."""
        inspect_result = InspectResponse(
            is_safe=True,
            classifications=[],
            action=Action.ALLOW,
        )

        response = MCPInspectResponse(
            jsonrpc="2.0",
            result=inspect_result,
            id=1
        )

        assert response.jsonrpc == "2.0"
        assert response.result is not None
        assert response.result.is_safe is True
        assert response.error is None

    def test_mcp_inspect_response_error(self):
        """Test MCPInspectResponse with error."""
        error = MCPInspectError(
            code=-32603,
            message="Internal error"
        )

        response = MCPInspectResponse(
            jsonrpc="2.0",
            error=error,
            id=1
        )

        assert response.error is not None
        assert response.error.code == -32603
        assert response.result is None


class TestMCPClientInput:
    """Tests for invalid input handling."""

    def test_inspect_requires_mcp_message(self, mcp_client):
        """Test inspect raises error for non-MCPMessage input."""
        with pytest.raises(ValidationError) as excinfo:
            mcp_client.inspect({"not": "a message"})

        assert "'message' must be an MCPMessage object" in str(excinfo.value)

    def test_inspect_tool_call_with_empty_arguments(self, mcp_client, mock_request_handler):
        """Test inspect_tool_call works with no arguments."""
        mock_request_handler.request.return_value = {
            "jsonrpc": "2.0",
            "result": {"is_safe": True, "classifications": [], "action": "ALLOW"},
            "id": 1,
        }

        result = mcp_client.inspect_tool_call(
            tool_name="list_files",
            message_id=1
        )

        assert result.result.is_safe is True

    def test_inspect_response_requires_method(self, mcp_client):
        """Test inspect_response raises ValidationError when method is missing or empty."""
        with pytest.raises(ValidationError, match="method"):
            mcp_client.inspect_response(
                result_data={"content": []},
                method="",
                params={},
            )
        with pytest.raises(ValidationError, match="method"):
            mcp_client.inspect_response(
                result_data={"content": []},
                method=None,
                params={},
            )

    def test_inspect_response_requires_params(self, mcp_client):
        """Test inspect_response raises ValidationError when params is missing or not a dict."""
        with pytest.raises(ValidationError, match="params"):
            mcp_client.inspect_response(
                result_data={"content": []},
                method="tools/call",
                params=None,
            )
        with pytest.raises(ValidationError, match="params"):
            mcp_client.inspect_response(
                result_data={"content": []},
                method="tools/call",
                params="not-a-dict",
            )
