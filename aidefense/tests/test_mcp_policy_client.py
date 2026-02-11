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

import pytest
from unittest.mock import MagicMock

from aidefense.mcpscan import MCPPolicyClient
from aidefense.management.models.policy import (
    Policies,
    ListPoliciesRequest,
    UpdatePolicyRequest,
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
def mcp_policy_client(mock_request_handler):
    """Create an MCPPolicyClient with a mock request handler."""
    client = MCPPolicyClient(
        api_key=TEST_API_KEY, request_handler=mock_request_handler
    )
    client.make_request = MagicMock()
    return client


class TestMCPPolicyClient:
    """Tests for the MCPPolicyClient."""

    def test_client_initialization(self):
        """Test MCPPolicyClient can be instantiated."""
        client = MCPPolicyClient(api_key=TEST_API_KEY)
        assert client is not None

    def test_list_mcp_policies(self, mcp_policy_client):
        """Test listing MCP Gateway policies."""
        mock_response = {
            "policies": {
                "items": [
                    {
                        "policy_id": "policy-123",
                        "policy_name": "MCP Security Policy",
                        "description": "Security policy for MCP Gateway",
                        "status": "Enabled",
                        "connection_type": "MCPGateway",
                        "created_at": "2025-01-01T00:00:00Z",
                    },
                ],
                "paging": {"total": 1, "count": 1, "offset": 0},
            }
        }
        mcp_policy_client.make_request.return_value = mock_response

        request = ListPoliciesRequest(limit=25)

        response = mcp_policy_client.list_mcp_policies(request)

        mcp_policy_client.make_request.assert_called_once()
        call_args = mcp_policy_client.make_request.call_args
        # Verify MCPGateway filter is applied
        assert call_args[1]["params"]["connection_type"] == "MCPGateway"

        assert isinstance(response, Policies)
        assert len(response.items) == 1
        assert response.items[0].policy_id == "policy-123"

    def test_list_mcp_policies_default_request(self, mcp_policy_client):
        """Test listing MCP Gateway policies with default request."""
        mock_response = {
            "policies": {
                "items": [],
                "paging": {"total": 0, "count": 0, "offset": 0},
            }
        }
        mcp_policy_client.make_request.return_value = mock_response

        # Call without request argument
        response = mcp_policy_client.list_mcp_policies()

        mcp_policy_client.make_request.assert_called_once()
        call_args = mcp_policy_client.make_request.call_args
        # Verify MCPGateway filter is still applied
        assert call_args[1]["params"]["connection_type"] == "MCPGateway"

    def test_update_mcp_policy(self, mcp_policy_client):
        """Test updating an MCP policy."""
        mcp_policy_client.make_request.return_value = {}

        policy_id = "550e8400-e29b-41d4-a716-446655440000"
        request = UpdatePolicyRequest(
            name="Updated MCP Policy",
            description="Updated description",
            status="Disabled",
        )

        mcp_policy_client.update_mcp_policy(policy_id, request)

        mcp_policy_client.make_request.assert_called_once()
        call_args = mcp_policy_client.make_request.call_args
        assert call_args[0][0] == "PUT"
        assert call_args[0][1] == f"policies/{policy_id}"

    def test_update_mcp_policy_empty_request(self, mcp_policy_client):
        """Test that updating with empty request raises ValueError."""
        policy_id = "550e8400-e29b-41d4-a716-446655440000"
        request = UpdatePolicyRequest()

        with pytest.raises(ValueError) as excinfo:
            mcp_policy_client.update_mcp_policy(policy_id, request)

        assert "No fields to update" in str(excinfo.value)
        mcp_policy_client.make_request.assert_not_called()
