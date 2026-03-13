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
from unittest.mock import MagicMock, call

from aidefense.mcpscan.mcp_scan_base import MCPScan
from aidefense.mcpscan.models import (
    StartMCPServerScanRequest,
    StartMCPServerScanResponse,
    GetMCPScanStatusResponse,
    RegisterMCPServerRequest,
    RegisterMCPServerResponse,
    GetMCPServerCapabilitiesResponse,
    GetMCPServerThreatsResponse,
    GetMCPServerScanSummaryResponse,
    GetMCPServerResponse,
    ListMCPServersRequest,
    ListMCPServersResponse,
    UpdateAuthConfigRequest,
    UpdateAuthConfigResponse,
    CapabilityType,
    OnboardingStatus,
    SeverityLevel,
    TransportType,
    ServersSortBy,
    SortOrder,
    MCPScanStatus,
    AuthConfig,
    AuthType,
    ApiKeyConfig,
    OAuthConfig,
    ServerType,
    RemoteServerInput,
)
from aidefense.config import Config
from aidefense.request_handler import HttpMethod
from aidefense.exceptions import ApiError


# Create a valid format dummy API key for testing
TEST_API_KEY = "0123456789" * 6 + "0123"  # 64 characters


# ─────────────────────────────────────────────────────────────────────────────
# Helper: reusable mock MCP server items for list_servers responses
# ─────────────────────────────────────────────────────────────────────────────
def _make_mock_server_item(
    server_id="srv-default",
    name="Default Server",
    url="https://mcp-default.example.com/sse",
    connection_type="SSE",
    onboarding_status="COMPLETED",
    scan_enabled=False,
    auth_type="NO_AUTH",
    created_at="2026-01-10T08:00:00Z",
    description=None,
    status_info=None,
):
    """Build a mock MCP server dict for list_servers responses."""
    item = {
        "id": server_id,
        "name": name,
        "url": url,
        "connection_type": connection_type,
        "onboarding_status": onboarding_status,
        "scan_enabled": scan_enabled,
        "auth_type": auth_type,
        "created_at": created_at,
    }
    if description is not None:
        item["description"] = description
    if status_info is not None:
        item["status_info"] = status_info
    return item


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
def mcp_scan(mock_request_handler):
    """Create an MCPScan instance with a mock request handler."""
    client = MCPScan(
        api_key=TEST_API_KEY, request_handler=mock_request_handler
    )
    client.make_request = MagicMock()
    return client


# ─────────────────────────────────────────────────────────────────────────────
# TestMCPScanInitialization
# ─────────────────────────────────────────────────────────────────────────────
class TestMCPScanInitialization:
    """Tests for MCPScan client initialization."""

    def test_client_initialization_default_config(self):
        """Test MCPScan can be instantiated with default Config."""
        client = MCPScan(api_key=TEST_API_KEY)
        assert client is not None

    def test_client_initialization_custom_config(self):
        """Test MCPScan can be instantiated with a custom Config."""
        config = Config()
        client = MCPScan(api_key=TEST_API_KEY, config=config)
        assert client is not None
        assert client.config is config

    def test_client_initialization_with_request_handler(self, mock_request_handler):
        """Test MCPScan can be instantiated with a custom request handler."""
        client = MCPScan(
            api_key=TEST_API_KEY, request_handler=mock_request_handler
        )
        assert client is not None

    def test_client_stores_api_key(self):
        """Test that the API key is stored via ManagementAuth."""
        client = MCPScan(api_key=TEST_API_KEY)
        assert client._auth is not None

    def test_client_initialization_all_params(self, mock_request_handler):
        """Test MCPScan instantiation with all optional parameters."""
        config = Config()
        client = MCPScan(
            api_key=TEST_API_KEY,
            config=config,
            request_handler=mock_request_handler,
        )
        assert client is not None
        assert client.config is config


# ─────────────────────────────────────────────────────────────────────────────
# TestStartScan
# ─────────────────────────────────────────────────────────────────────────────
class TestStartScan:
    """Tests for the MCPScan.start_scan method."""

    def test_start_scan_basic_sse(self, mcp_scan):
        """Test starting a scan with basic SSE remote server."""
        mock_response = {
            "scan_id": "scan-001",
            "status": "QUEUED",
            "created_at": "2026-01-15T10:00:00Z",
        }
        mcp_scan.make_request.return_value = mock_response

        request = StartMCPServerScanRequest(
            name="Basic SSE Server",
            server_type=ServerType.REMOTE,
            remote=RemoteServerInput(
                url="https://mcp-server.example.com/sse",
                connection_type=TransportType.SSE,
            ),
        )

        result = mcp_scan.start_scan(request)

        mcp_scan.make_request.assert_called_once()
        call_kwargs = mcp_scan.make_request.call_args
        assert call_kwargs.kwargs["method"] == HttpMethod.POST
        assert result.scan_id == "scan-001"
        assert isinstance(result, StartMCPServerScanResponse)

    def test_start_scan_streamable_transport(self, mcp_scan):
        """Test starting a scan with STREAMABLE transport type."""
        mock_response = {
            "scan_id": "scan-002",
            "status": "QUEUED",
            "created_at": "2026-01-15T10:01:00Z",
        }
        mcp_scan.make_request.return_value = mock_response

        request = StartMCPServerScanRequest(
            name="Streamable Server",
            server_type=ServerType.REMOTE,
            remote=RemoteServerInput(
                url="https://streamable.example.com/stream",
                connection_type=TransportType.STREAMABLE,
            ),
        )

        result = mcp_scan.start_scan(request)
        assert result.scan_id == "scan-002"
        assert isinstance(result, StartMCPServerScanResponse)

    def test_start_scan_with_api_key_auth(self, mcp_scan):
        """Test starting a scan with API key authentication."""
        mock_response = {
            "scan_id": "scan-003",
            "status": "IN_PROGRESS",
            "created_at": "2026-01-15T10:02:00Z",
        }
        mcp_scan.make_request.return_value = mock_response

        request = StartMCPServerScanRequest(
            name="Auth Server",
            server_type=ServerType.REMOTE,
            remote=RemoteServerInput(
                url="https://secure-mcp.example.com/sse",
                connection_type=TransportType.SSE,
            ),
            auth_config=AuthConfig(
                auth_type=AuthType.API_KEY,
                api_key=ApiKeyConfig(
                    header_name="X-API-Key",
                    api_key="test-server-api-key",
                ),
            ),
        )

        result = mcp_scan.start_scan(request)

        assert result.scan_id == "scan-003"
        mcp_scan.make_request.assert_called_once()
        # Verify body includes auth_config
        call_kwargs = mcp_scan.make_request.call_args
        body = call_kwargs.kwargs["data"]
        assert "auth_config" in body

    def test_start_scan_with_oauth_auth(self, mcp_scan):
        """Test starting a scan with OAuth authentication."""
        mock_response = {
            "scan_id": "scan-004",
            "status": "QUEUED",
            "created_at": "2026-01-15T10:03:00Z",
        }
        mcp_scan.make_request.return_value = mock_response

        request = StartMCPServerScanRequest(
            name="OAuth MCP Server",
            server_type=ServerType.REMOTE,
            remote=RemoteServerInput(
                url="https://oauth-mcp.example.com/sse",
                connection_type=TransportType.SSE,
            ),
            auth_config=AuthConfig(
                auth_type=AuthType.OAUTH,
                oauth=OAuthConfig(
                    client_id="my-client-id",
                    client_secret="my-client-secret",
                    auth_server_url="https://auth.example.com/token",
                ),
            ),
        )

        result = mcp_scan.start_scan(request)
        assert result.scan_id == "scan-004"
        assert isinstance(result, StartMCPServerScanResponse)

    def test_start_scan_with_no_auth(self, mcp_scan):
        """Test starting a scan with NO_AUTH explicitly set."""
        mock_response = {
            "scan_id": "scan-005",
            "status": "QUEUED",
            "created_at": "2026-01-15T10:04:00Z",
        }
        mcp_scan.make_request.return_value = mock_response

        request = StartMCPServerScanRequest(
            name="No Auth Server",
            server_type=ServerType.REMOTE,
            remote=RemoteServerInput(
                url="https://open-mcp.example.com/sse",
                connection_type=TransportType.SSE,
            ),
            auth_config=AuthConfig(auth_type=AuthType.NO_AUTH),
        )

        result = mcp_scan.start_scan(request)
        assert result.scan_id == "scan-005"

    def test_start_scan_with_description(self, mcp_scan):
        """Test starting a scan with a description on the remote input."""
        mock_response = {
            "scan_id": "scan-006",
            "status": "QUEUED",
            "created_at": "2026-01-15T10:05:00Z",
        }
        mcp_scan.make_request.return_value = mock_response

        request = StartMCPServerScanRequest(
            name="Described Server",
            server_type=ServerType.REMOTE,
            remote=RemoteServerInput(
                url="https://described-mcp.example.com/sse",
                description="A fully-described test MCP server",
                connection_type=TransportType.SSE,
            ),
        )

        result = mcp_scan.start_scan(request)
        assert result.scan_id == "scan-006"

    def test_start_scan_api_error(self, mcp_scan):
        """Test start_scan propagates ApiError."""
        mcp_scan.make_request.side_effect = ApiError("Server not reachable", 502)

        request = StartMCPServerScanRequest(
            name="Unreachable Server",
            server_type=ServerType.REMOTE,
            remote=RemoteServerInput(
                url="https://unreachable.example.com/sse",
                connection_type=TransportType.SSE,
            ),
        )

        with pytest.raises(ApiError) as excinfo:
            mcp_scan.start_scan(request)

        assert "Server not reachable" in str(excinfo.value)


# ─────────────────────────────────────────────────────────────────────────────
# TestGetScanStatus
# ─────────────────────────────────────────────────────────────────────────────
class TestGetScanStatus:
    """Tests for the MCPScan.get_scan_status method."""

    def test_get_scan_status_queued(self, mcp_scan):
        """Test getting scan status when QUEUED."""
        mock_response = {
            "scan_id": "scan-100",
            "name": "Queued Server",
            "status": "QUEUED",
            "created_at": "2026-01-15T10:00:00Z",
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_scan_status("scan-100")

        mcp_scan.make_request.assert_called_once()
        call_kwargs = mcp_scan.make_request.call_args
        assert call_kwargs.kwargs["method"] == HttpMethod.GET
        assert result.scan_id == "scan-100"
        assert result.status == MCPScanStatus.QUEUED
        assert isinstance(result, GetMCPScanStatusResponse)

    def test_get_scan_status_in_progress(self, mcp_scan):
        """Test getting scan status when IN_PROGRESS."""
        mock_response = {
            "scan_id": "scan-101",
            "name": "In Progress Server",
            "status": "IN_PROGRESS",
            "created_at": "2026-01-15T10:01:00Z",
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_scan_status("scan-101")
        assert result.scan_id == "scan-101"
        assert result.status == MCPScanStatus.IN_PROGRESS
        assert result.result is None

    def test_get_scan_status_completed_safe(self, mcp_scan):
        """Test getting scan status when COMPLETED and is_safe=True."""
        mock_response = {
            "scan_id": "scan-102",
            "name": "Completed Safe Server",
            "status": "COMPLETED",
            "created_at": "2026-01-15T10:00:00Z",
            "completed_at": "2026-01-15T10:02:00Z",
            "result": {
                "is_safe": True,
            },
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_scan_status("scan-102")

        assert result.scan_id == "scan-102"
        assert result.status == MCPScanStatus.COMPLETED
        assert result.completed_at is not None
        assert result.result is not None
        assert result.result.is_safe is True

    def test_get_scan_status_completed_unsafe(self, mcp_scan):
        """Test getting scan status when COMPLETED and is_safe=False."""
        mock_response = {
            "scan_id": "scan-103",
            "name": "Completed Unsafe Server",
            "status": "COMPLETED",
            "created_at": "2026-01-15T10:00:00Z",
            "completed_at": "2026-01-15T10:03:00Z",
            "result": {
                "is_safe": False,
            },
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_scan_status("scan-103")

        assert result.scan_id == "scan-103"
        assert result.status == MCPScanStatus.COMPLETED
        assert result.completed_at is not None
        assert result.result is not None
        assert result.result.is_safe is False

    def test_get_scan_status_failed(self, mcp_scan):
        """Test getting scan status when FAILED with error_info."""
        mock_response = {
            "scan_id": "scan-104",
            "name": "Failed Server",
            "status": "FAILED",
            "created_at": "2026-01-15T10:00:00Z",
            "error_info": {
                "message": "Connection timed out to MCP server",
            },
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_scan_status("scan-104")

        assert result.scan_id == "scan-104"
        assert result.status == MCPScanStatus.FAILED
        assert result.error_info is not None
        assert result.error_info.message == "Connection timed out to MCP server"
        assert result.result is None

    def test_get_scan_status_with_expires_at(self, mcp_scan):
        """Test scan status response includes expires_at."""
        mock_response = {
            "scan_id": "scan-105",
            "name": "Expiring Results",
            "status": "COMPLETED",
            "created_at": "2026-01-15T10:00:00Z",
            "completed_at": "2026-01-15T10:01:00Z",
            "expires_at": "2026-01-22T10:01:00Z",
            "result": {"is_safe": True},
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_scan_status("scan-105")

        assert result.scan_id == "scan-105"
        assert result.expires_at is not None
        assert result.completed_at is not None
        assert result.result.is_safe is True

    def test_get_scan_status_api_error(self, mcp_scan):
        """Test get_scan_status propagates ApiError."""
        mcp_scan.make_request.side_effect = ApiError("Scan not found", 404)

        with pytest.raises(ApiError) as excinfo:
            mcp_scan.get_scan_status("non-existent-scan-id")

        assert "Scan not found" in str(excinfo.value)


# ─────────────────────────────────────────────────────────────────────────────
# TestRegisterServer
# ─────────────────────────────────────────────────────────────────────────────
class TestRegisterServer:
    """Tests for the MCPScan.register_server method."""

    def test_register_server_basic_sse(self, mcp_scan):
        """Test registering a basic SSE server."""
        mock_response = {"server_id": "srv-001"}
        mcp_scan.make_request.return_value = mock_response

        request = RegisterMCPServerRequest(
            name="Production SSE Server",
            url="https://mcp-prod.example.com/sse",
            connection_type=TransportType.SSE,
        )

        result = mcp_scan.register_server(request)

        mcp_scan.make_request.assert_called_once()
        call_kwargs = mcp_scan.make_request.call_args
        assert call_kwargs.kwargs["method"] == HttpMethod.POST
        assert result.server_id == "srv-001"
        assert isinstance(result, RegisterMCPServerResponse)

    def test_register_server_streamable(self, mcp_scan):
        """Test registering a STREAMABLE transport server."""
        mock_response = {"server_id": "srv-002"}
        mcp_scan.make_request.return_value = mock_response

        request = RegisterMCPServerRequest(
            name="Streamable Server",
            url="https://mcp-stream.example.com/stream",
            connection_type=TransportType.STREAMABLE,
        )

        result = mcp_scan.register_server(request)
        assert result.server_id == "srv-002"
        assert isinstance(result, RegisterMCPServerResponse)

    def test_register_server_with_description(self, mcp_scan):
        """Test registering a server with a description."""
        mock_response = {"server_id": "srv-003"}
        mcp_scan.make_request.return_value = mock_response

        request = RegisterMCPServerRequest(
            name="Described Server",
            url="https://mcp-desc.example.com/sse",
            description="This is a staging MCP server for testing",
            connection_type=TransportType.SSE,
        )

        result = mcp_scan.register_server(request)
        assert result.server_id == "srv-003"

        # Verify body includes description
        call_kwargs = mcp_scan.make_request.call_args
        body = call_kwargs.kwargs["data"]
        assert "description" in body
        assert body["description"] == "This is a staging MCP server for testing"

    def test_register_server_with_scan_enabled(self, mcp_scan):
        """Test registering a server with scan_enabled=True."""
        mock_response = {"server_id": "srv-004"}
        mcp_scan.make_request.return_value = mock_response

        request = RegisterMCPServerRequest(
            name="Scan-Enabled Server",
            url="https://mcp-scanned.example.com/sse",
            connection_type=TransportType.SSE,
            scan_enabled=True,
        )

        result = mcp_scan.register_server(request)
        assert result.server_id == "srv-004"

        call_kwargs = mcp_scan.make_request.call_args
        body = call_kwargs.kwargs["data"]
        assert body.get("scan_enabled") is True

    def test_register_server_with_api_key_auth(self, mcp_scan):
        """Test registering a server with API key auth config."""
        mock_response = {"server_id": "srv-005"}
        mcp_scan.make_request.return_value = mock_response

        request = RegisterMCPServerRequest(
            name="API Key Auth Server",
            url="https://mcp-auth.example.com/sse",
            connection_type=TransportType.SSE,
            auth_config=AuthConfig(
                auth_type=AuthType.API_KEY,
                api_key=ApiKeyConfig(
                    header_name="Authorization",
                    api_key="Bearer my-secret-token",
                ),
            ),
        )

        result = mcp_scan.register_server(request)
        assert result.server_id == "srv-005"

        call_kwargs = mcp_scan.make_request.call_args
        body = call_kwargs.kwargs["data"]
        assert "auth_config" in body

    def test_register_server_with_oauth_auth(self, mcp_scan):
        """Test registering a server with OAuth auth config."""
        mock_response = {"server_id": "srv-006"}
        mcp_scan.make_request.return_value = mock_response

        request = RegisterMCPServerRequest(
            name="OAuth Auth Server",
            url="https://mcp-oauth.example.com/sse",
            connection_type=TransportType.SSE,
            auth_config=AuthConfig(
                auth_type=AuthType.OAUTH,
                oauth=OAuthConfig(
                    client_id="oauth-client-id",
                    client_secret="oauth-client-secret",
                    auth_server_url="https://auth.example.com/oauth/token",
                ),
            ),
        )

        result = mcp_scan.register_server(request)
        assert result.server_id == "srv-006"

    def test_register_server_api_error_conflict(self, mcp_scan):
        """Test register_server propagates ApiError on conflict."""
        mcp_scan.make_request.side_effect = ApiError("Server already exists", 409)

        request = RegisterMCPServerRequest(
            name="Duplicate Server",
            url="https://mcp-dup.example.com/sse",
            connection_type=TransportType.SSE,
        )

        with pytest.raises(ApiError) as excinfo:
            mcp_scan.register_server(request)

        assert "Server already exists" in str(excinfo.value)


# ─────────────────────────────────────────────────────────────────────────────
# TestDeleteServer
# ─────────────────────────────────────────────────────────────────────────────
class TestDeleteServer:
    """Tests for the MCPScan.delete_server method."""

    def test_delete_server_success(self, mcp_scan):
        """Test deleting a server successfully."""
        mcp_scan.make_request.return_value = None

        mcp_scan.delete_server("srv-001")

        mcp_scan.make_request.assert_called_once()
        call_kwargs = mcp_scan.make_request.call_args
        assert call_kwargs.kwargs["method"] == HttpMethod.DELETE

    def test_delete_server_uuid_format(self, mcp_scan):
        """Test deleting a server with UUID format ID."""
        mcp_scan.make_request.return_value = None

        mcp_scan.delete_server("550e8400-e29b-41d4-a716-446655440000")
        mcp_scan.make_request.assert_called_once()

    def test_delete_server_not_found(self, mcp_scan):
        """Test deleting a non-existent server raises ApiError."""
        mcp_scan.make_request.side_effect = ApiError("Server not found", 404)

        with pytest.raises(ApiError) as excinfo:
            mcp_scan.delete_server("non-existent-id")

        assert "Server not found" in str(excinfo.value)

    def test_delete_server_forbidden(self, mcp_scan):
        """Test deleting a server without permissions raises ApiError."""
        mcp_scan.make_request.side_effect = ApiError("Forbidden", 403)

        with pytest.raises(ApiError) as excinfo:
            mcp_scan.delete_server("srv-forbidden")

        assert "Forbidden" in str(excinfo.value)

    def test_delete_server_returns_none(self, mcp_scan):
        """Test that delete_server returns None on success."""
        mcp_scan.make_request.return_value = None

        result = mcp_scan.delete_server("srv-to-delete")
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# TestGetServerCapabilities
# ─────────────────────────────────────────────────────────────────────────────
class TestGetServerCapabilities:
    """Tests for the MCPScan.get_server_capabilities method."""

    def test_get_capabilities_tools(self, mcp_scan):
        """Test getting TOOL capabilities."""
        mock_response = {
            "capabilities": [
                {
                    "capability_type": "TOOL",
                    "tool": {
                        "id":"tool-001",
                        "name": "execute_query",
                        "description": "Execute a SQL query",
                    },
                },
            ],
            "paging": {"total": 1, "limit": 25, "offset": 0},
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_server_capabilities(
            server_id="srv-001",
            capability_type=CapabilityType.TOOL,
        )

        mcp_scan.make_request.assert_called_once()
        call_kwargs = mcp_scan.make_request.call_args
        assert call_kwargs.kwargs["method"] == HttpMethod.GET
        assert call_kwargs.kwargs["params"]["capability_type"] == CapabilityType.TOOL.value
        assert isinstance(result, GetMCPServerCapabilitiesResponse)
        assert len(result.capabilities) == 1
        assert result.capabilities[0].tool.id == "tool-001"

    def test_get_capabilities_prompts(self, mcp_scan):
        """Test getting PROMPT capabilities."""
        mock_response = {
            "capabilities": [
                {
                    "capability_type": "PROMPT",
                    "prompt": {
                        "id": "prompt-001",
                        "name": "summarize",
                        "description": "Summarize text content",
                    },
                },
                {
                    "capability_type": "PROMPT",
                    "prompt": {
                        "id": "prompt-002",
                        "name": "translate",
                        "description": "Translate text between languages",
                    },
                },
            ],
            "paging": {"total": 2, "limit": 25, "offset": 0},
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_server_capabilities(
            server_id="srv-002",
            capability_type=CapabilityType.PROMPT,
        )

        call_kwargs = mcp_scan.make_request.call_args
        assert call_kwargs.kwargs["params"]["capability_type"] == CapabilityType.PROMPT.value
        assert len(result.capabilities) == 2
        assert result.capabilities[0].prompt.id == "prompt-001"
        assert result.capabilities[1].prompt.id == "prompt-002"

    def test_get_capabilities_resources(self, mcp_scan):
        """Test getting RESOURCE capabilities."""
        mock_response = {
            "capabilities": [
                {
                    "capability_type": "RESOURCE",
                    "resource": {
                        "id": "res-001",
                        "name": "config_file",
                        "uri": "file:///etc/mcp/config.yaml",
                    },
                },
            ],
            "paging": {"total": 1, "limit": 10, "offset": 0},
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_server_capabilities(
            server_id="srv-003",
            capability_type=CapabilityType.RESOURCE,
            limit=10,
        )

        call_kwargs = mcp_scan.make_request.call_args
        assert call_kwargs.kwargs["params"]["capability_type"] == CapabilityType.RESOURCE.value
        assert call_kwargs.kwargs["params"]["limit"] == 10
        assert len(result.capabilities) == 1
        assert result.capabilities[0].resource.id == "res-001"

    def test_get_capabilities_with_name_filter(self, mcp_scan):
        """Test getting capabilities filtered by capability_name."""
        mock_response = {
            "capabilities": [
                {
                    "capability_type": "TOOL",
                    "tool": {
                        "id": "tool-exec",
                        "name": "execute_command",
                        "description": "Execute a shell command",
                    },
                },
            ],
            "paging": {"total": 1, "limit": 25, "offset": 0},
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_server_capabilities(
            server_id="srv-004",
            capability_type=CapabilityType.TOOL,
            capability_name="execute",
        )

        call_kwargs = mcp_scan.make_request.call_args
        assert call_kwargs.kwargs["params"]["capability_name"] == "execute"
        assert len(result.capabilities) == 1
        assert result.capabilities[0].tool.id == "tool-exec"

    def test_get_capabilities_with_pagination(self, mcp_scan):
        """Test getting capabilities with custom limit and offset."""
        mock_response = {
            "capabilities": [
                {
                    "capability_type": "TOOL",
                    "tool": {
                        "id": f"tool-{i:03d}",
                        "name": f"tool_{i}",
                        "description": f"Tool number {i}",
                    },
                }
                for i in range(26, 31)  # items 26-30
            ],
            "paging": {"total": 100, "limit": 50, "offset": 25},
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_server_capabilities(
            server_id="srv-005",
            capability_type=CapabilityType.TOOL,
            limit=50,
            offset=25,
        )

        call_kwargs = mcp_scan.make_request.call_args
        assert call_kwargs.kwargs["params"]["limit"] == 50
        assert call_kwargs.kwargs["params"]["offset"] == 25
        assert len(result.capabilities) == 5
        assert result.paging.total == 100
        assert result.paging.limit == 50
        assert result.paging.offset == 25

    def test_get_capabilities_empty_name_not_in_params(self, mcp_scan):
        """Test that empty capability_name is not added to params."""
        mock_response = {
            "capabilities": [],
            "paging": {"total": 0, "limit": 25, "offset": 0},
        }
        mcp_scan.make_request.return_value = mock_response

        mcp_scan.get_server_capabilities(
            server_id="srv-006",
            capability_type=CapabilityType.TOOL,
            capability_name="",
        )

        call_kwargs = mcp_scan.make_request.call_args
        assert "capability_name" not in call_kwargs.kwargs["params"]

    def test_get_capabilities_api_error(self, mcp_scan):
        """Test get_server_capabilities propagates ApiError."""
        mcp_scan.make_request.side_effect = ApiError("Server not found", 404)

        with pytest.raises(ApiError):
            mcp_scan.get_server_capabilities(
                server_id="invalid-id",
                capability_type=CapabilityType.TOOL,
            )


# ─────────────────────────────────────────────────────────────────────────────
# TestGetServerThreats
# ─────────────────────────────────────────────────────────────────────────────
class TestGetServerThreats:
    """Tests for the MCPScan.get_server_threats method."""

    def test_get_threats_no_filters(self, mcp_scan):
        """Test getting threats with no optional filters."""
        mock_response = {
            "threats": [
                {
                    "capabilityId": "cap-001",
                    "capability_type": "TOOL",
                    "capability_name": "execute_query",
                    "threat": {
                        "technique_name": "SQL Injection",
                        "sub_techniques": [
                            {
                                "subTechniqueId": "tech-001",
                                "sub_technique_name": "Blind SQL Injection",
                                "severity": "HIGH",
                            },
                        ],
                    },
                },
            ],
            "paging": {"total": 1, "limit": 25, "offset": 0},
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_server_threats(server_id="srv-001")

        mcp_scan.make_request.assert_called_once()
        call_kwargs = mcp_scan.make_request.call_args
        assert call_kwargs.kwargs["method"] == HttpMethod.GET
        assert "capability_type" not in call_kwargs.kwargs["params"]
        assert "threat_severity" not in call_kwargs.kwargs["params"]
        assert isinstance(result, GetMCPServerThreatsResponse)
        assert len(result.threats) == 1
        assert result.threats[0].capability_id == "cap-001"

    def test_get_threats_filter_by_capability_type_tool(self, mcp_scan):
        """Test getting threats filtered by TOOL capability type."""
        mock_response = {
            "threats": [
                {
                    "capability_id": "cap-tech-001",
                    "capability_type": "TOOL",
                    "threat": {
                        "technique_name": "Path Traversal",
                        "sub_techniques": [
                            {
                                "subTechniqueId": "tech-001",
                                "sub_technique_name": "Directory Traversal",
                                "severity": "CRITICAL",
                            },
                        ],
                    },
                },
            ],
            "paging": {"total": 1, "limit": 25, "offset": 0},
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_server_threats(
            server_id="srv-002",
            capability_type=CapabilityType.TOOL,
        )

        call_kwargs = mcp_scan.make_request.call_args
        assert call_kwargs.kwargs["params"]["capability_type"] == CapabilityType.TOOL.value
        assert len(result.threats) == 1
        assert result.threats[0].capability_id == "cap-tech-001"

    def test_get_threats_filter_by_capability_type_prompt(self, mcp_scan):
        """Test getting threats filtered by PROMPT capability type."""
        mock_response = {
            "threats": [
                {
                    "capability_id": "cap-tech-001",
                    "capability_type": "PROMPT",
                    "capability_name": "code_gen",
                    "threat": {
                        "technique_name": "Prompt Injection",
                        "sub_techniques": [
                            {
                                "subTechniqueId": "tech-001",
                                "sub_technique_name": "Indirect Prompt Injection",
                                "severity": "MEDIUM",
                            },
                        ],
                    },
                },
            ],
            "paging": {"total": 1, "limit": 25, "offset": 0},
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_server_threats(
            server_id="srv-003",
            capability_type=CapabilityType.PROMPT,
        )

        call_kwargs = mcp_scan.make_request.call_args
        assert call_kwargs.kwargs["params"]["capability_type"] == CapabilityType.PROMPT.value
        assert len(result.threats) == 1
        assert result.threats[0].capability_id == "cap-tech-001"

    def test_get_threats_filter_by_severity_high_critical(self, mcp_scan):
        """Test getting threats filtered by HIGH and CRITICAL severity."""
        mock_response = {
            "threats": [
                {
                    "capabilityId": "cap-tech-001",
                    "capability_type": "TOOL",
                    "capability_name": "shell_exec",
                    "threat": {
                        "technique_name": "Command Injection",
                        "sub_techniques": [
                            {
                                "subTechniqueId": "tech-001",
                                "sub_technique_name": "OS Command Injection",
                                "severity": "CRITICAL",
                            },
                        ],
                    },
                },
                {
                    "capabilityId": "cap-tech-002",
                    "capability_type": "TOOL",
                    "capability_name": "file_write",
                    "threat": {
                        "technique_name": "Arbitrary File Write",
                        "sub_techniques": [
                            {
                                "subTechniqueId": "tech-002",
                                "sub_technique_name": "Overwrite Config",
                                "severity": "HIGH",
                            },
                        ],
                    },
                },
            ],
            "paging": {"total": 2, "limit": 25, "offset": 0},
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_server_threats(
            server_id="srv-004",
            threat_severity=["HIGH", "CRITICAL"],
        )

        call_kwargs = mcp_scan.make_request.call_args
        assert call_kwargs.kwargs["params"]["threat_severity"] == ["HIGH", "CRITICAL"]
        assert len(result.threats) == 2
        assert result.paging.total == 2

    def test_get_threats_filter_by_severity_low(self, mcp_scan):
        """Test getting threats filtered by LOW severity."""
        mock_response = {
            "threats": [
                {
                    "capability_id": "cap-tech-003",
                    "capability_type": "RESOURCE",
                    "capability_name": "public_data",
                    "threat": {
                        "technique_name": "Information Disclosure",
                        "sub_techniques": [
                            {
                                "subTechniqueId": "tech-003",
                                "sub_technique_name": "Verbose Error Messages",
                                "severity": "LOW",
                            },
                        ],
                    },
                },
            ],
            "paging": {"total": 1, "limit": 25, "offset": 0},
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_server_threats(
            server_id="srv-005",
            threat_severity=["LOW"],
        )

        call_kwargs = mcp_scan.make_request.call_args
        assert call_kwargs.kwargs["params"]["threat_severity"] == ["LOW"]
        assert len(result.threats) == 1

    def test_get_threats_with_pagination(self, mcp_scan):
        """Test getting threats with custom pagination."""
        mock_response = {
            "threats": [
                {
                    "capability_id": "cap-tech-{i:03d}",
                    "capability_type": "TOOL",
                    "capability_name": f"tool_{i}",
                    "threat": {
                        "technique_name": f"Threat {i}",
                        "sub_techniques": [],
                    },
                }
                for i in range(51, 54)  # 3 items in this page
            ],
            "paging": {"total": 200, "limit": 100, "offset": 50},
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_server_threats(
            server_id="srv-006",
            limit=100,
            offset=50,
        )

        call_kwargs = mcp_scan.make_request.call_args
        assert call_kwargs.kwargs["params"]["limit"] == 100
        assert call_kwargs.kwargs["params"]["offset"] == 50
        assert len(result.threats) == 3
        assert result.paging.total == 200

    def test_get_threats_all_filters(self, mcp_scan):
        """Test getting threats with all filters combined."""
        mock_response = {
            "threats": [
                {
                    "capability_id": "cap-res-001",
                    "capability_type": "RESOURCE",
                    "capability_name": "db_connection",
                    "threat": {
                        "technique_name": "Credential Exposure",
                        "sub_techniques": [
                            {
                                "sub_technique_id": "tech-001",
                                "sub_technique_name": "Hardcoded Credentials",
                                "severity": "HIGH",
                            },
                        ],
                    },
                },
            ],
            "paging": {"total": 5, "limit": 10, "offset": 0},
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_server_threats(
            server_id="srv-007",
            capability_type=CapabilityType.RESOURCE,
            threat_severity=["MEDIUM", "HIGH"],
            limit=10,
            offset=0,
        )

        call_kwargs = mcp_scan.make_request.call_args
        assert call_kwargs.kwargs["params"]["capability_type"] == CapabilityType.RESOURCE.value
        assert call_kwargs.kwargs["params"]["threat_severity"] == ["MEDIUM", "HIGH"]
        assert call_kwargs.kwargs["params"]["limit"] == 10
        assert len(result.threats) == 1
        assert result.paging.total == 5

    def test_get_threats_api_error(self, mcp_scan):
        """Test get_server_threats propagates ApiError."""
        mcp_scan.make_request.side_effect = ApiError("Internal error", 500)

        with pytest.raises(ApiError):
            mcp_scan.get_server_threats(server_id="srv-error")


# ─────────────────────────────────────────────────────────────────────────────
# TestGetServerScanSummary
# ─────────────────────────────────────────────────────────────────────────────
class TestGetServerScanSummary:
    """Tests for the MCPScan.get_server_scan_summary method."""

    def test_get_scan_summary_basic(self, mcp_scan):
        """Test getting a basic scan summary."""
        mock_response = {
            "completed_at": "2026-01-15T12:00:00Z",
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_server_scan_summary("srv-001")

        mcp_scan.make_request.assert_called_once()
        call_kwargs = mcp_scan.make_request.call_args
        assert call_kwargs.kwargs["method"] == HttpMethod.GET
        assert isinstance(result, GetMCPServerScanSummaryResponse)
        assert result.completed_at is not None

    def test_get_scan_summary_with_capability_summary(self, mcp_scan):
        """Test scan summary includes capability counts."""
        mock_response = {
            "completed_at": "2026-01-15T12:00:00Z",
            "capability_summary": {
                "tool_count": 5,
                "prompt_count": 3,
                "resource_count": 2,
            },
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_server_scan_summary("srv-002")

        assert result.capability_summary is not None
        assert result.capability_summary.tool_count == 5
        assert result.capability_summary.prompt_count == 3
        assert result.capability_summary.resource_count == 2

    def test_get_scan_summary_with_threat_summary(self, mcp_scan):
        """Test scan summary includes threat severity counts."""
        mock_response = {
            "completed_at": "2026-01-15T12:01:00Z",
            "scan_threat_summary": {
                "critical_count": 1,
                "high_count": 3,
                "medium_count": 5,
                "low_count": 10,
            },
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_server_scan_summary("srv-003")

        assert result.scan_threat_summary is not None
        assert result.scan_threat_summary.critical_count == 1
        assert result.scan_threat_summary.high_count == 3
        assert result.scan_threat_summary.medium_count == 5
        assert result.scan_threat_summary.low_count == 10

    def test_get_scan_summary_no_threats(self, mcp_scan):
        """Test scan summary for a clean server with zero threats."""
        mock_response = {
            "completed_at": "2026-01-15T12:02:00Z",
            "capability_summary": {
                "tool_count": 2,
                "prompt_count": 1,
                "resource_count": 0,
            },
            "scan_threat_summary": {
                "critical_count": 0,
                "high_count": 0,
                "medium_count": 0,
                "low_count": 0,
            },
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_server_scan_summary("srv-004")

        assert result.scan_threat_summary.critical_count == 0
        assert result.scan_threat_summary.high_count == 0
        assert result.scan_threat_summary.medium_count == 0
        assert result.scan_threat_summary.low_count == 0
        assert result.capability_summary.tool_count == 2
        assert result.capability_summary.resource_count == 0

    def test_get_scan_summary_with_both_summaries(self, mcp_scan):
        """Test scan summary with both capability and threat summaries populated."""
        mock_response = {
            "completed_at": "2026-01-15T12:05:00Z",
            "capability_summary": {
                "tool_count": 12,
                "prompt_count": 4,
                "resource_count": 7,
            },
            "scan_threat_summary": {
                "critical_count": 2,
                "high_count": 5,
                "medium_count": 8,
                "low_count": 15,
            },
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_server_scan_summary("srv-005")

        assert result.capability_summary is not None
        assert result.scan_threat_summary is not None
        assert result.capability_summary.tool_count == 12
        assert result.capability_summary.prompt_count == 4
        assert result.capability_summary.resource_count == 7
        assert result.scan_threat_summary.critical_count == 2
        assert result.scan_threat_summary.high_count == 5
        assert result.scan_threat_summary.medium_count == 8
        assert result.scan_threat_summary.low_count == 15

    def test_get_scan_summary_api_error(self, mcp_scan):
        """Test get_server_scan_summary propagates ApiError."""
        mcp_scan.make_request.side_effect = ApiError("Not found", 404)

        with pytest.raises(ApiError):
            mcp_scan.get_server_scan_summary("srv-not-found")


# ─────────────────────────────────────────────────────────────────────────────
# TestGetServer
# ─────────────────────────────────────────────────────────────────────────────
class TestGetServer:
    """Tests for the MCPScan.get_server method."""

    def test_get_server_basic(self, mcp_scan):
        """Test getting basic server details."""
        mock_response = {
            "mcp_server": {
                "id": "srv-001",
                "name": "Test Server",
                "url": "https://mcp.example.com/sse",
                "connection_type": "SSE",
                "onboarding_status": "COMPLETED",
            },
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_server("srv-001")

        mcp_scan.make_request.assert_called_once()
        call_kwargs = mcp_scan.make_request.call_args
        assert call_kwargs.kwargs["method"] == HttpMethod.GET
        assert isinstance(result, GetMCPServerResponse)
        assert result.mcp_server is not None
        assert result.mcp_server.name == "Test Server"
        assert result.mcp_server.url == "https://mcp.example.com/sse"

    def test_get_server_with_scan_enabled(self, mcp_scan):
        """Test getting server details that includes scan_enabled."""
        mock_response = {
            "mcp_server": {
                "id": "srv-002",
                "name": "Scan-Enabled Server",
                "url": "https://mcp-scanned.example.com/sse",
                "connection_type": "SSE",
                "onboarding_status": "COMPLETED",
                "scan_enabled": True,
            },
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_server("srv-002")
        assert result.mcp_server.scan_enabled is True
        assert result.mcp_server.name == "Scan-Enabled Server"
        assert result.mcp_server.onboarding_status == "COMPLETED"

    def test_get_server_with_auth_type(self, mcp_scan):
        """Test getting server details that includes auth_type."""
        mock_response = {
            "mcp_server": {
                "id": "srv-003",
                "name": "Auth Server",
                "url": "https://mcp-auth.example.com/sse",
                "connection_type": "SSE",
                "onboarding_status": "COMPLETED",
                "auth_type": "API_KEY",
            },
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_server("srv-003")
        assert result.mcp_server.auth_type == "API_KEY"
        assert result.mcp_server.name == "Auth Server"

    def test_get_server_with_status_info(self, mcp_scan):
        """Test getting server details that includes status_info."""
        mock_response = {
            "mcp_server": {
                "id": "srv-004",
                "name": "Error Server",
                "url": "https://mcp-error.example.com/sse",
                "connection_type": "SSE",
                "onboarding_status": "FAILED",
                "status_info": {
                    "message": "Unable to connect to the MCP server",
                },
            },
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_server("srv-004")
        assert result.mcp_server.onboarding_status == "FAILED"
        assert result.mcp_server.status_info is not None
        assert "Unable to connect" in result.mcp_server.status_info.message

    def test_get_server_streamable_connection(self, mcp_scan):
        """Test getting server details with STREAMABLE connection type."""
        mock_response = {
            "mcp_server": {
                "id": "srv-005",
                "name": "Streamable Server",
                "url": "https://mcp-stream.example.com/stream",
                "connection_type": "STREAMABLE",
                "onboarding_status": "COMPLETED",
            },
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_server("srv-005")
        assert result.mcp_server.connection_type == "STREAMABLE"
        assert result.mcp_server.url == "https://mcp-stream.example.com/stream"

    def test_get_server_with_created_at(self, mcp_scan):
        """Test getting server details includes created_at timestamp."""
        mock_response = {
            "mcp_server": {
                "id": "srv-006",
                "name": "Timestamped Server",
                "url": "https://mcp-ts.example.com/sse",
                "connection_type": "SSE",
                "onboarding_status": "COMPLETED",
                "created_at": "2026-01-10T08:00:00Z",
            },
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.get_server("srv-006")
        assert result.mcp_server.created_at is not None
        assert result.mcp_server.name == "Timestamped Server"

    def test_get_server_not_found(self, mcp_scan):
        """Test get_server raises ApiError when server not found."""
        mcp_scan.make_request.side_effect = ApiError("Not found", 404)

        with pytest.raises(ApiError):
            mcp_scan.get_server("non-existent-server")


# ─────────────────────────────────────────────────────────────────────────────
# TestListServers
# ─────────────────────────────────────────────────────────────────────────────
class TestListServers:
    """Tests for the MCPScan.list_servers method."""

    def test_list_servers_defaults(self, mcp_scan):
        """Test listing servers with default parameters returns items."""
        mock_items = [
            _make_mock_server_item(
                server_id="srv-default-001",
                name="Default Server Alpha",
                url="https://alpha.example.com/sse",
            ),
            _make_mock_server_item(
                server_id="srv-default-002",
                name="Default Server Beta",
                url="https://beta.example.com/sse",
                scan_enabled=True,
            ),
        ]
        mock_response = {
            "mcp_servers": {
                "items": mock_items,
                "paging": {"total": 2, "limit": 25, "offset": 0},
            },
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.list_servers()

        mcp_scan.make_request.assert_called_once()
        call_kwargs = mcp_scan.make_request.call_args
        assert call_kwargs.kwargs["method"] == HttpMethod.GET
        assert isinstance(result, ListMCPServersResponse)
        assert result.mcp_servers is not None
        assert len(result.mcp_servers.items) == 2
        assert result.mcp_servers.items[0].name == "Default Server Alpha"
        assert result.mcp_servers.items[0].url == "https://alpha.example.com/sse"
        assert result.mcp_servers.items[1].name == "Default Server Beta"
        assert result.mcp_servers.items[1].scan_enabled is True
        assert result.mcp_servers.paging.total == 2
        assert result.mcp_servers.paging.limit == 25
        assert result.mcp_servers.paging.offset == 0

    def test_list_servers_with_custom_pagination(self, mcp_scan):
        """Test listing servers with custom limit and offset."""
        mock_items = [
            _make_mock_server_item(
                server_id=f"srv-page-{i:03d}",
                name=f"Paginated Server {i}",
                url=f"https://page-{i}.example.com/sse",
            )
            for i in range(26, 31)  # 5 items at offset 25
        ]
        mock_response = {
            "mcp_servers": {
                "items": mock_items,
                "paging": {"total": 100, "limit": 50, "offset": 25},
            },
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.list_servers(limit=50, offset=25)

        mcp_scan.make_request.assert_called_once()
        assert len(result.mcp_servers.items) == 5
        assert result.mcp_servers.paging.total == 100
        assert result.mcp_servers.paging.limit == 50
        assert result.mcp_servers.paging.offset == 25
        assert result.mcp_servers.items[0].id == "srv-page-026"
        assert result.mcp_servers.items[4].id == "srv-page-030"

    def test_list_servers_filter_by_name(self, mcp_scan):
        """Test listing servers filtered by name substring."""
        mock_items = [
            _make_mock_server_item(
                server_id="srv-prod-001",
                name="production-mcp-east",
                url="https://prod-east.example.com/sse",
                description="Production MCP in US-East",
            ),
            _make_mock_server_item(
                server_id="srv-prod-002",
                name="production-mcp-west",
                url="https://prod-west.example.com/sse",
                description="Production MCP in US-West",
            ),
        ]
        mock_response = {
            "mcp_servers": {
                "items": mock_items,
                "paging": {"total": 2, "limit": 25, "offset": 0},
            },
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.list_servers(server_name_substr="production")

        mcp_scan.make_request.assert_called_once()
        assert len(result.mcp_servers.items) == 2
        assert "production" in result.mcp_servers.items[0].name
        assert "production" in result.mcp_servers.items[1].name
        assert result.mcp_servers.paging.total == 2

    def test_list_servers_filter_by_onboarding_status(self, mcp_scan):
        """Test listing servers filtered by onboarding status."""
        mock_items = [
            _make_mock_server_item(
                server_id="srv-onboarded-001",
                name="Onboarded Server One",
                url="https://onboarded-1.example.com/sse",
                onboarding_status="COMPLETED",
                scan_enabled=True,
            ),
            _make_mock_server_item(
                server_id="srv-onboarded-002",
                name="Onboarded Server Two",
                url="https://onboarded-2.example.com/sse",
                onboarding_status="COMPLETED",
            ),
            _make_mock_server_item(
                server_id="srv-onboarded-003",
                name="Onboarded Server Three",
                url="https://onboarded-3.example.com/sse",
                onboarding_status="COMPLETED",
                auth_type="API_KEY",
            ),
        ]
        mock_response = {
            "mcp_servers": {
                "items": mock_items,
                "paging": {"total": 3, "limit": 25, "offset": 0},
            },
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.list_servers(
            onboarding_status=[OnboardingStatus.COMPLETED],
        )

        mcp_scan.make_request.assert_called_once()
        assert len(result.mcp_servers.items) == 3
        assert all(
            s.onboarding_status == "COMPLETED"
            for s in result.mcp_servers.items
        )
        assert result.mcp_servers.items[0].scan_enabled is True
        assert result.mcp_servers.items[2].auth_type == "API_KEY"

    def test_list_servers_filter_by_transport_type(self, mcp_scan):
        """Test listing servers filtered by transport type."""
        mock_items = [
            _make_mock_server_item(
                server_id="srv-sse-001",
                name="SSE Server",
                url="https://sse.example.com/sse",
                connection_type="SSE",
            ),
            _make_mock_server_item(
                server_id="srv-stream-001",
                name="Streamable Server",
                url="https://stream.example.com/stream",
                connection_type="STREAMABLE",
            ),
        ]
        mock_response = {
            "mcp_servers": {
                "items": mock_items,
                "paging": {"total": 2, "limit": 25, "offset": 0},
            },
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.list_servers(
            transport_type=[TransportType.SSE, TransportType.STREAMABLE],
        )

        mcp_scan.make_request.assert_called_once()
        assert len(result.mcp_servers.items) == 2
        assert result.mcp_servers.items[0].connection_type == "SSE"
        assert result.mcp_servers.items[1].connection_type == "STREAMABLE"

    def test_list_servers_filter_by_severity(self, mcp_scan):
        """Test listing servers filtered by severity levels."""
        mock_items = [
            _make_mock_server_item(
                server_id="srv-sev-001",
                name="High Severity Server",
                url="https://high-sev.example.com/sse",
                scan_enabled=True,
            ),
            _make_mock_server_item(
                server_id="srv-sev-002",
                name="Medium Severity Server",
                url="https://med-sev.example.com/sse",
                scan_enabled=True,
                connection_type="STREAMABLE",
            ),
        ]
        mock_response = {
            "mcp_servers": {
                "items": mock_items,
                "paging": {"total": 2, "limit": 25, "offset": 0},
            },
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.list_servers(
            severity=[SeverityLevel.HIGH, SeverityLevel.MEDIUM],
        )

        mcp_scan.make_request.assert_called_once()
        assert len(result.mcp_servers.items) == 2
        assert result.mcp_servers.items[0].name == "High Severity Server"
        assert result.mcp_servers.items[0].scan_enabled is True
        assert result.mcp_servers.items[1].name == "Medium Severity Server"
        assert result.mcp_servers.items[1].connection_type == "STREAMABLE"
        assert result.mcp_servers.paging.total == 2

    def test_list_servers_filter_by_registry_id(self, mcp_scan):
        """Test listing servers filtered by registry_id."""
        mock_items = [
            _make_mock_server_item(
                server_id="srv-reg-001",
                name="Registry Server Alpha",
                url="https://reg-alpha.example.com/sse",
            ),
        ]
        mock_response = {
            "mcp_servers": {
                "items": mock_items,
                "paging": {"total": 1, "limit": 25, "offset": 0},
            },
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.list_servers(registry_id="registry-abc-123")

        mcp_scan.make_request.assert_called_once()
        assert len(result.mcp_servers.items) == 1
        assert result.mcp_servers.items[0].id == "srv-reg-001"
        assert result.mcp_servers.items[0].name == "Registry Server Alpha"
        assert result.mcp_servers.paging.total == 1

    def test_list_servers_with_sort(self, mcp_scan):
        """Test listing servers with sort_by and sort_order."""
        mock_items = [
            _make_mock_server_item(
                server_id="srv-sort-001",
                name="Alpha Server",
                url="https://alpha-sort.example.com/sse",
                created_at="2026-01-01T00:00:00Z",
            ),
            _make_mock_server_item(
                server_id="srv-sort-002",
                name="Beta Server",
                url="https://beta-sort.example.com/sse",
                created_at="2026-01-02T00:00:00Z",
            ),
            _make_mock_server_item(
                server_id="srv-sort-003",
                name="Gamma Server",
                url="https://gamma-sort.example.com/sse",
                created_at="2026-01-03T00:00:00Z",
            ),
        ]
        mock_response = {
            "mcp_servers": {
                "items": mock_items,
                "paging": {"total": 3, "limit": 25, "offset": 0},
            },
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.list_servers(
            sort_by=ServersSortBy.NAME if hasattr(ServersSortBy, "NAME") else None,
            sort_order=SortOrder.ASC if hasattr(SortOrder, "ASC") else None,
        )

        mcp_scan.make_request.assert_called_once()
        assert len(result.mcp_servers.items) == 3
        assert result.mcp_servers.items[0].name == "Alpha Server"
        assert result.mcp_servers.items[1].name == "Beta Server"
        assert result.mcp_servers.items[2].name == "Gamma Server"

    def test_list_servers_all_filters(self, mcp_scan):
        """Test listing servers with all filters applied simultaneously."""
        mock_items = [
            _make_mock_server_item(
                server_id="srv-all-001",
                name="staging-mcp-server",
                url="https://staging.example.com/sse",
                connection_type="SSE",
                onboarding_status="COMPLETED",
                scan_enabled=True,
                auth_type="API_KEY",
                created_at="2026-01-05T14:30:00Z",
                description="Staging MCP server with full configuration",
            ),
        ]
        mock_response = {
            "mcp_servers": {
                "items": mock_items,
                "paging": {"total": 1, "limit": 10, "offset": 5},
            },
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.list_servers(
            limit=10,
            offset=5,
            server_name_substr="staging",
            onboarding_status=[OnboardingStatus.COMPLETED],
            transport_type=[TransportType.SSE],
            severity=[SeverityLevel.MEDIUM],
            registry_id="reg-xyz",
        )

        mcp_scan.make_request.assert_called_once()
        assert len(result.mcp_servers.items) == 1
        server = result.mcp_servers.items[0]
        assert server.id == "srv-all-001"
        assert server.name == "staging-mcp-server"
        assert server.url == "https://staging.example.com/sse"
        assert server.connection_type == "SSE"
        assert server.onboarding_status == "COMPLETED"
        assert server.scan_enabled is True
        assert server.auth_type == "API_KEY"
        assert server.created_at is not None
        assert result.mcp_servers.paging.total == 1
        assert result.mcp_servers.paging.limit == 10
        assert result.mcp_servers.paging.offset == 5

    def test_list_servers_empty_result(self, mcp_scan):
        """Test listing servers with no matching results."""
        mock_response = {
            "mcp_servers": {
                "items": [],
                "paging": {"total": 0, "limit": 25, "offset": 0},
            },
        }
        mcp_scan.make_request.return_value = mock_response

        result = mcp_scan.list_servers(server_name_substr="nonexistent")

        assert result.mcp_servers is not None
        assert len(result.mcp_servers.items) == 0
        assert result.mcp_servers.paging.total == 0

    def test_list_servers_api_error(self, mcp_scan):
        """Test list_servers propagates ApiError."""
        mcp_scan.make_request.side_effect = ApiError("Unauthorized", 401)

        with pytest.raises(ApiError):
            mcp_scan.list_servers()


# ─────────────────────────────────────────────────────────────────────────────
# TestUpdateAuthConfig
# ─────────────────────────────────────────────────────────────────────────────
class TestUpdateAuthConfig:
    """Tests for the MCPScan.update_auth_config method."""

    def test_update_auth_config_to_api_key(self, mcp_scan):
        """Test updating auth config to API_KEY type."""
        mock_response = {"server_id": "srv-001"}
        mcp_scan.make_request.return_value = mock_response

        request = UpdateAuthConfigRequest(
            server_id="srv-001",
            auth_config=AuthConfig(
                auth_type=AuthType.API_KEY,
                api_key=ApiKeyConfig(
                    header_name="X-API-Key",
                    api_key="new-api-key-value",
                ),
            ),
        )

        result = mcp_scan.update_auth_config(request)

        mcp_scan.make_request.assert_called_once()
        call_kwargs = mcp_scan.make_request.call_args
        assert call_kwargs.kwargs["method"] == HttpMethod.PUT
        assert isinstance(result, UpdateAuthConfigResponse)
        assert result.server_id == "srv-001"

    def test_update_auth_config_to_no_auth(self, mcp_scan):
        """Test updating auth config to NO_AUTH type."""
        mock_response = {"server_id": "srv-002"}
        mcp_scan.make_request.return_value = mock_response

        request = UpdateAuthConfigRequest(
            server_id="srv-002",
            auth_config=AuthConfig(auth_type=AuthType.NO_AUTH),
        )

        result = mcp_scan.update_auth_config(request)
        assert result.server_id == "srv-002"

        call_kwargs = mcp_scan.make_request.call_args
        body = call_kwargs.kwargs["data"]
        assert body is not None

    def test_update_auth_config_to_oauth(self, mcp_scan):
        """Test updating auth config to OAUTH type."""
        mock_response = {"server_id": "srv-003"}
        mcp_scan.make_request.return_value = mock_response

        request = UpdateAuthConfigRequest(
            server_id="srv-003",
            auth_config=AuthConfig(
                auth_type=AuthType.OAUTH,
                oauth=OAuthConfig(
                    client_id="new-client-id",
                    client_secret="new-client-secret",
                    auth_server_url="https://new-auth.example.com/token",
                ),
            ),
        )

        result = mcp_scan.update_auth_config(request)
        assert result.server_id == "srv-003"
        assert isinstance(result, UpdateAuthConfigResponse)

    def test_update_auth_config_change_api_key_header(self, mcp_scan):
        """Test updating auth config with a different header name."""
        mock_response = {"server_id": "srv-004"}
        mcp_scan.make_request.return_value = mock_response

        request = UpdateAuthConfigRequest(
            server_id="srv-004",
            auth_config=AuthConfig(
                auth_type=AuthType.API_KEY,
                api_key=ApiKeyConfig(
                    header_name="Authorization",
                    api_key="Bearer my-new-bearer-token",
                ),
            ),
        )

        result = mcp_scan.update_auth_config(request)
        assert result.server_id == "srv-004"

    def test_update_auth_config_uses_put_method(self, mcp_scan):
        """Test that update_auth_config sends a PUT request."""
        mock_response = {"server_id": "srv-005"}
        mcp_scan.make_request.return_value = mock_response

        request = UpdateAuthConfigRequest(
            server_id="srv-005",
            auth_config=AuthConfig(auth_type=AuthType.NO_AUTH),
        )

        mcp_scan.update_auth_config(request)

        call_kwargs = mcp_scan.make_request.call_args
        assert call_kwargs.kwargs["method"] == HttpMethod.PUT

    def test_update_auth_config_sends_body(self, mcp_scan):
        """Test that update_auth_config sends the request body."""
        mock_response = {"server_id": "srv-006"}
        mcp_scan.make_request.return_value = mock_response

        request = UpdateAuthConfigRequest(
            server_id="srv-006",
            auth_config=AuthConfig(
                auth_type=AuthType.API_KEY,
                api_key=ApiKeyConfig(
                    header_name="X-Custom-Header",
                    api_key="custom-key-value",
                ),
            ),
        )

        mcp_scan.update_auth_config(request)

        call_kwargs = mcp_scan.make_request.call_args
        assert call_kwargs.kwargs["data"] is not None
        assert isinstance(call_kwargs.kwargs["data"], dict)

    def test_update_auth_config_server_not_found(self, mcp_scan):
        """Test update_auth_config raises ApiError when server not found."""
        mcp_scan.make_request.side_effect = ApiError("Server not found", 404)

        request = UpdateAuthConfigRequest(
            server_id="non-existent-server",
            auth_config=AuthConfig(auth_type=AuthType.NO_AUTH),
        )

        with pytest.raises(ApiError) as excinfo:
            mcp_scan.update_auth_config(request)

        assert "Server not found" in str(excinfo.value)

    def test_update_auth_config_forbidden(self, mcp_scan):
        """Test update_auth_config raises ApiError on forbidden access."""
        mcp_scan.make_request.side_effect = ApiError("Forbidden", 403)

        request = UpdateAuthConfigRequest(
            server_id="srv-forbidden",
            auth_config=AuthConfig(auth_type=AuthType.NO_AUTH),
        )

        with pytest.raises(ApiError) as excinfo:
            mcp_scan.update_auth_config(request)

        assert "Forbidden" in str(excinfo.value)
