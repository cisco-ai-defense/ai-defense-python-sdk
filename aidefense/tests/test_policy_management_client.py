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
from unittest.mock import MagicMock, patch
from datetime import datetime

from aidefense.management.policies import PolicyManagementClient
from aidefense.management.auth import ManagementAuth
from aidefense.management.models.policy import (
    Policy,
    Policies,
    PolicySortBy,
    GuardrailType,
    ListPoliciesRequest,
    UpdatePolicyRequest,
    AddOrUpdatePolicyConnectionsRequest,
    RuleStatus,
    Direction,
    Action,
)
from aidefense.management.models.connection import ConnectionType
from aidefense.management.models.common import Paging
from aidefense.config import Config
from aidefense.exceptions import ValidationError, ApiError, SDKError


# Create a valid format dummy API key for testing
TEST_API_KEY = "0123456789" * 6 + "0123"  # 64 characters


@pytest.fixture(autouse=True)
def reset_config_singleton():
    """Reset Config singleton before each test."""
    # Reset the singleton instance
    Config._instance = None
    yield
    # Clean up after test
    Config._instance = None


@pytest.fixture
def mock_request_handler():
    """Create a mock request handler."""
    mock_handler = MagicMock()
    return mock_handler


@pytest.fixture
def policy_client(mock_request_handler):
    """Create a PolicyManagementClient with a mock request handler."""
    client = PolicyManagementClient(
        auth=ManagementAuth(TEST_API_KEY), request_handler=mock_request_handler
    )
    # Replace the make_request method with a mock
    client.make_request = MagicMock()
    return client


class TestPolicyManagementClient:
    """Tests for the PolicyManagementClient."""

    def test_list_policies(self, policy_client):
        """Test listing policies."""
        # Setup mock response
        mock_response = {
            "policies": {
                "items": [
                    {
                        "policy_id": "policy-123",
                        "policy_name": "Test Policy 1",
                        "description": "Test Description 1",
                        "status": "active",
                        "connection_type": "API",
                        "created_at": "2025-01-01T00:00:00Z",
                        "updated_at": "2025-01-02T00:00:00Z",
                    },
                    {
                        "policy_id": "policy-456",
                        "policy_name": "Test Policy 2",
                        "description": "Test Description 2",
                        "status": "inactive",
                        "connection_type": "Gateway",
                        "created_at": "2025-01-03T00:00:00Z",
                        "updated_at": "2025-01-04T00:00:00Z",
                    },
                ],
                "paging": {"total": 2, "count": 2, "offset": 0},
            }
        }
        policy_client.make_request.return_value = mock_response

        # Create request
        request = ListPoliciesRequest(
            limit=10, offset=0, sort_by=PolicySortBy.policy_name, order="asc"
        )

        # Call the method
        response = policy_client.list_policies(request)

        # Verify the make_request call
        policy_client.make_request.assert_called_once_with(
            "GET",
            "policies",
            params={"limit": 10, "offset": 0, "sort_by": "policy_name", "order": "asc"},
        )

        # Verify the response
        assert isinstance(response, Policies)
        assert len(response.items) == 2
        assert response.items[0].policy_id == "policy-123"
        assert response.items[0].policy_name == "Test Policy 1"
        assert response.items[1].policy_id == "policy-456"
        assert response.items[1].policy_name == "Test Policy 2"
        assert response.paging.total == 2
        assert response.paging.count == 2
        assert response.paging.offset == 0

    def test_get_policy(self, policy_client):
        """Test getting a policy by ID."""
        # Setup mock response
        mock_response = {
            "policy": {
                "policy_id": "policy-123",
                "policy_name": "Test Policy",
                "description": "Test Description",
                "status": "active",
                "connection_type": "API",
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-02T00:00:00Z",
                "guardrails": {
                    "items": [
                        {
                            "guardrails_type": "Security",
                            "items": [
                                {
                                    "ruleset_type": "security_ruleset",
                                    "status": "Enabled",
                                    "direction": "Both",
                                    "action": "Block",
                                    "entity": {
                                        "name": "security_entity",
                                        "desc": "Security entity description",
                                    },
                                }
                            ],
                            "paging": {"total": 1, "count": 1, "offset": 0},
                        }
                    ],
                    "paging": {"total": 1, "count": 1, "offset": 0},
                },
            }
        }
        policy_client.make_request.return_value = mock_response

        # Call the method
        policy_id = "550e8400-e29b-41d4-a716-446655440000"
        response = policy_client.get_policy(policy_id, expanded=True)

        # Verify the make_request call
        policy_client.make_request.assert_called_once_with(
            "GET", f"policies/{policy_id}", params={"expanded": True}
        )

        # Verify the response
        assert isinstance(response, Policy)
        assert response.policy_id == "policy-123"
        assert response.policy_name == "Test Policy"
        assert response.description == "Test Description"
        assert response.status == "active"
        assert response.connection_type == "API"
        assert response.guardrails is not None
        assert len(response.guardrails.items) == 1
        assert response.guardrails.items[0].guardrails_type == GuardrailType.Security
        assert len(response.guardrails.items[0].items) == 1
        assert response.guardrails.items[0].items[0].ruleset_type == "security_ruleset"
        assert response.guardrails.items[0].items[0].status == RuleStatus.Enabled
        assert response.guardrails.items[0].items[0].direction == Direction.Both
        assert response.guardrails.items[0].items[0].action == Action.Block

    def test_update_policy(self, policy_client):
        """Test updating a policy."""
        # Setup mock response (empty for update)
        policy_client.make_request.return_value = {}

        # Create request
        policy_id = "550e8400-e29b-41d4-a716-446655440000"
        request = UpdatePolicyRequest(
            name="Updated Policy Name",
            description="Updated Description",
            status="inactive",
        )

        # Call the method
        response = policy_client.update_policy(policy_id, request)

        # Verify the make_request call
        policy_client.make_request.assert_called_once_with(
            "PUT",
            f"policies/{policy_id}",
            data={
                "name": "Updated Policy Name",
                "description": "Updated Description",
                "status": "inactive",
            },
        )

        # Verify the response
        assert response is None

    def test_update_policy_failfast_empty(self, policy_client):
        """Fail fast when no fields are provided to update."""
        with pytest.raises(ValueError) as excinfo:
            policy_client.update_policy(
                "123e4567-e89b-12d3-a456-426614174331", UpdatePolicyRequest()
            )
        assert "No fields to update" in str(excinfo.value)
        policy_client.make_request.assert_not_called()

    def test_delete_policy(self, policy_client):
        """Test deleting a policy."""
        # Setup mock response (empty for delete)
        policy_client.make_request.return_value = {}

        # Call the method
        policy_id = "550e8400-e29b-41d4-a716-446655440000"
        response = policy_client.delete_policy(policy_id)

        # Verify the make_request call
        policy_client.make_request.assert_called_once_with(
            "DELETE", f"policies/{policy_id}"
        )

        # Verify the response
        assert response is None

    def test_update_policy_connections(self, policy_client):
        """Test adding or updating policy connections."""
        # Setup mock response (empty for update)
        policy_client.make_request.return_value = {}

        # Create request
        policy_id = "550e8400-e29b-41d4-a716-446655440000"
        request = AddOrUpdatePolicyConnectionsRequest(
            connections_to_associate=[
                "323e4567-e89b-12d3-a456-426614174333",
                "223e4567-e89b-12d3-a456-426614174332",
            ],
            connections_to_disassociate=["123e4567-e89b-12d3-a456-426614174331"],
        )

        # Call the method
        response = policy_client.update_policy_connections(policy_id, request)

        # Verify the make_request call
        policy_client.make_request.assert_called_once_with(
            "POST",
            f"policies/{policy_id}/connections",
            data={
                "connections_to_associate": [
                    "323e4567-e89b-12d3-a456-426614174333",
                    "223e4567-e89b-12d3-a456-426614174332",
                ],
                "connections_to_disassociate": ["123e4567-e89b-12d3-a456-426614174331"],
            },
        )

        assert policy_client.make_request.call_count == 1
        assert response is None

    def test_update_policy_connections_failfast_empty(self, policy_client):
        """Fail fast when no connections provided for update."""
        with pytest.raises(ValueError) as excinfo:
            policy_client.update_policy_connections(
                "123e4567-e89b-12d3-a456-426614174331",
                AddOrUpdatePolicyConnectionsRequest(),
            )
        assert "No connections specified" in str(excinfo.value)
        policy_client.make_request.assert_not_called()

    def test_error_handling(self, policy_client):
        """Test error handling in the client."""
        # Setup mock to raise an exception
        policy_client.make_request.side_effect = ApiError("API Error", 400)

        # Create request
        request = ListPoliciesRequest(limit=10)

        # Verify that the exception is propagated
        with pytest.raises(ApiError) as excinfo:
            policy_client.list_policies(request)

        assert "API Error" in str(excinfo.value)
