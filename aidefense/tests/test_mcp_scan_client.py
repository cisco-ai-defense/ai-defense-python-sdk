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

import pytest
from unittest.mock import MagicMock

from aidefense.mcpscan import MCPScanClient
from aidefense.mcpscan.models import (
    StartMCPServerScanRequest,
    TransportType,
    MCPScanStatus,
    AuthConfig,
    AuthType,
    ApiKeyConfig,
    ServerType,
    RemoteServerInput,
)
from aidefense.config import Config
from aidefense.exceptions import ApiError


# Create a valid format dummy API key for testing
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
def mcp_scan_client(mock_request_handler):
    """Create an MCPScanClient with a mock request handler."""
    client = MCPScanClient(
        api_key=TEST_API_KEY, request_handler=mock_request_handler
    )
    client.make_request = MagicMock()
    return client


class TestMCPScanClient:
    """Tests for the MCPScanClient."""

    def test_client_initialization(self):
        """Test MCPScanClient can be instantiated."""
        client = MCPScanClient(api_key=TEST_API_KEY)
        assert client is not None

    def test_scan_mcp_server_async(self, mcp_scan_client):
        """Test starting an async MCP server scan."""
        mock_response = {
            "scan_id": "scan-123-456"
        }
        mcp_scan_client.make_request.return_value = mock_response

        request = StartMCPServerScanRequest(
            name="Test MCP Server",
            server_type=ServerType.REMOTE,
            remote=RemoteServerInput(
                url="https://mcp-server.example.com/sse",
                description="Test server",
                connection_type=TransportType.SSE,
            ),
        )

        scan_id = mcp_scan_client.scan_mcp_server_async(request)

        mcp_scan_client.make_request.assert_called_once()
        assert scan_id == "scan-123-456"

    def test_scan_mcp_server_async_with_auth(self, mcp_scan_client):
        """Test starting an async MCP server scan with authentication."""
        mock_response = {
            "scan_id": "scan-789-012"
        }
        mcp_scan_client.make_request.return_value = mock_response

        auth_config = AuthConfig(
            auth_type=AuthType.API_KEY,
            api_key=ApiKeyConfig(
                header_name="X-API-Key",
                api_key="test-api-key"
            )
        )

        request = StartMCPServerScanRequest(
            name="Authenticated MCP Server",
            server_type=ServerType.REMOTE,
            remote=RemoteServerInput(
                url="https://secure-mcp.example.com/sse",
                connection_type=TransportType.SSE,
            ),
            auth_config=auth_config,
        )

        scan_id = mcp_scan_client.scan_mcp_server_async(request)

        mcp_scan_client.make_request.assert_called_once()
        assert scan_id == "scan-789-012"

    def test_get_scan_status_queued(self, mcp_scan_client):
        """Test getting scan status when queued."""
        mock_response = {
            "scan_id": "scan-123",
            "name": "Test Server",
            "status": "QUEUED",
            "created_at": "2025-01-01T00:00:00Z",
        }
        mcp_scan_client.make_request.return_value = mock_response

        result = mcp_scan_client.get_scan_status("scan-123")

        mcp_scan_client.make_request.assert_called_once()
        assert result.scan_id == "scan-123"
        assert result.status == MCPScanStatus.QUEUED

    def test_get_scan_status_completed(self, mcp_scan_client):
        """Test getting scan status when completed."""
        mock_response = {
            "scan_id": "scan-456",
            "name": "Test Server",
            "status": "COMPLETED",
            "created_at": "2025-01-01T00:00:00Z",
            "completed_at": "2025-01-01T00:01:00Z",
            "result": {
                "is_safe": True,
            }
        }
        mcp_scan_client.make_request.return_value = mock_response

        result = mcp_scan_client.get_scan_status("scan-456")

        assert result.status == MCPScanStatus.COMPLETED
        assert result.result is not None
        assert result.result.is_safe is True

    def test_error_handling(self, mcp_scan_client):
        """Test error handling in the client."""
        mcp_scan_client.make_request.side_effect = ApiError("API Error", 400)

        request = StartMCPServerScanRequest(
            name="Error Test",
            server_type=ServerType.REMOTE,
            remote=RemoteServerInput(
                url="https://error.example.com/sse",
                connection_type=TransportType.SSE,
            ),
        )

        with pytest.raises(ApiError) as excinfo:
            mcp_scan_client.scan_mcp_server_async(request)

        assert "API Error" in str(excinfo.value)

    def test_transport_type_streamable(self, mcp_scan_client):
        """Test scan with STREAMABLE transport type."""
        mock_response = {"scan_id": "scan-streamable"}
        mcp_scan_client.make_request.return_value = mock_response

        request = StartMCPServerScanRequest(
            name="Streamable Server",
            server_type=ServerType.REMOTE,
            remote=RemoteServerInput(
                url="https://streamable.example.com/stream",
                connection_type=TransportType.STREAMABLE,
            ),
        )

        scan_id = mcp_scan_client.scan_mcp_server_async(request)
        assert scan_id == "scan-streamable"
