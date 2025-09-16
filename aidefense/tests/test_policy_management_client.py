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
from aidefense.management.models.policy import (
    Policy, Policies, PolicySortBy, Guardrail, Guardrails, GuardrailType,
    ListPoliciesRequest, ListPoliciesResponse, UpdatePolicyRequest, UpdatePolicyResponse,
    DeletePolicyResponse, AddOrUpdatePolicyConnectionsRequest, AddOrUpdatePolicyConnectionsResponse,
    RuleStatus, Direction, Action, Entity, GuardrailRule
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
        api_key=TEST_API_KEY,
        request_handler=mock_request_handler
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
            "items": [
                {
                    "policy_id": "policy-123",
                    "policy_name": "Test Policy 1",
                    "description": "Test Description 1",
                    "status": "active",
                    "connection_type": "API",
                    "created_at": "2025-01-01T00:00:00Z",
                    "updated_at": "2025-01-02T00:00:00Z"
                },
                {
                    "policy_id": "policy-456",
                    "policy_name": "Test Policy 2",
                    "description": "Test Description 2",
                    "status": "inactive",
                    "connection_type": "Gateway",
                    "created_at": "2025-01-03T00:00:00Z",
                    "updated_at": "2025-01-04T00:00:00Z"
                }
            ],
            "paging": {
                "total": 2,
                "count": 2,
                "offset": 0
            }
        }
        policy_client.make_request.return_value = mock_response

        # Create request
        request = ListPoliciesRequest(
            limit=10,
            offset=0,
            sort_by=PolicySortBy.policy_name,
            order="asc"
        )

        # Mock the _parse_response method to avoid validation errors
        policy_client._parse_response = MagicMock()
        policy_client._parse_response.return_value = Policies(
            items=[
                Policy(
                    policy_id="policy-123",
                    policy_name="Test Policy 1",
                    description="Test Description 1",
                    status="active",
                    connection_type=ConnectionType.API,
                    created_at=datetime(2025, 1, 1),
                    updated_at=datetime(2025, 1, 2)
                ),
                Policy(
                    policy_id="policy-456",
                    policy_name="Test Policy 2",
                    description="Test Description 2",
                    status="inactive",
                    connection_type=ConnectionType.Gateway,
                    created_at=datetime(2025, 1, 3),
                    updated_at=datetime(2025, 1, 4)
                )
            ],
            paging=Paging(total=2, count=2, offset=0)
        )

        # Call the method
        response = policy_client.list_policies(request)

        # Verify the make_request call
        policy_client.make_request.assert_called_once_with(
            "GET", 
            "policies", 
            params={
                "limit": 10,
                "offset": 0,
                "sort_by": "policy_name",
                "order": "asc"
            }
        )

        # Verify the _parse_response call
        policy_client._parse_response.assert_called_once_with(
            Policies, mock_response, "policies response"
        )

        # Verify the response
        assert isinstance(response, Policies)
        assert len(response.items) == 2
        assert response.items[0].policy_id == "policy-123"
        assert response.items[0].policy_name == "Test Policy 1"
        assert response.items[1].policy_id == "policy-456"
        assert response.items[1].policy_name == "Test Policy 2"
        assert response.paging.total == 2

    def test_get_policy(self, policy_client):
        """Test getting a policy by ID."""
        # Setup mock response
        mock_response = {
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
                                    "desc": "Security entity description"
                                }
                            }
                        ],
                        "paging": {
                            "total": 1,
                            "count": 1,
                            "offset": 0
                        }
                    }
                ],
                "paging": {
                    "total": 1,
                    "count": 1,
                    "offset": 0
                }
            }
        }
        policy_client.make_request.return_value = mock_response

        # Mock the _parse_response method to avoid validation errors
        policy_client._parse_response = MagicMock()
        guardrail_rule = GuardrailRule(
            ruleset_type="security_ruleset",
            status=RuleStatus.Enabled,
            direction=Direction.Both,
            action=Action.Block,
            entity=Entity(
                name="security_entity",
                desc="Security entity description"
            )
        )
        
        guardrail = Guardrail(
            guardrails_type=GuardrailType.Security,
            items=[guardrail_rule],
            paging=Paging(total=1, count=1, offset=0)
        )
        
        guardrails = Guardrails(
            items=[guardrail],
            paging=Paging(total=1, count=1, offset=0)
        )
        
        policy = Policy(
            policy_id="policy-123",
            policy_name="Test Policy",
            description="Test Description",
            status="active",
            connection_type=ConnectionType.API,
            created_at=datetime(2025, 1, 1),
            updated_at=datetime(2025, 1, 2),
            guardrails=guardrails
        )
        
        policy_client._parse_response.return_value = policy

        # Call the method
        policy_id = "policy-123"
        response = policy_client.get_policy(policy_id, expanded=True)

        # Verify the make_request call
        policy_client.make_request.assert_called_once_with(
            "GET", 
            f"policies/{policy_id}", 
            params={"expanded": True}
        )

        # Verify the _parse_response call
        policy_client._parse_response.assert_called_once_with(
            Policy, mock_response, "policy response"
        )

        # Verify the response
        assert isinstance(response, Policy)
        assert response.policy_id == "policy-123"
        assert response.policy_name == "Test Policy"
        assert response.description == "Test Description"
        assert response.status == "active"
        assert response.connection_type == ConnectionType.API
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
        policy_id = "policy-123"
        request = UpdatePolicyRequest(
            name="Updated Policy Name",
            description="Updated Description",
            status="inactive"
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
                "status": "inactive"
            }
        )

        # Verify the response
        assert isinstance(response, UpdatePolicyResponse)

    def test_delete_policy(self, policy_client):
        """Test deleting a policy."""
        # Setup mock response (empty for delete)
        policy_client.make_request.return_value = {}

        # Call the method
        policy_id = "policy-123"
        response = policy_client.delete_policy(policy_id)

        # Verify the make_request call
        policy_client.make_request.assert_called_once_with(
            "DELETE", 
            f"policies/{policy_id}"
        )

        # Verify the response
        assert isinstance(response, DeletePolicyResponse)

    def test_update_policy_connections(self, policy_client):
        """Test updating policy connections."""
        # Setup mock response (empty for update)
        policy_client.make_request.return_value = {}

        # Create request
        policy_id = "policy-123"
        request = AddOrUpdatePolicyConnectionsRequest(
            connections_to_associate=["conn-123", "conn-456"],
            connections_to_disassociate=["conn-789"]
        )

        # Call the method
        response = policy_client.update_policy_connections(policy_id, request)

        # Verify the make_request call
        policy_client.make_request.assert_called_once_with(
            "POST", 
            f"policies/{policy_id}/connections", 
            data={
                "connections_to_associate": ["conn-123", "conn-456"],
                "connections_to_disassociate": ["conn-789"]
            }
        )

        # Verify the response
        assert isinstance(response, AddOrUpdatePolicyConnectionsResponse)

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
