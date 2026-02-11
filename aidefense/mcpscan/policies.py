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

"""MCP Policy management client for AI Defense.

This module provides policy management capabilities specifically for MCP Gateway
connections. Unlike the general PolicyManagementClient, this client automatically
filters policies to only show those applicable to MCP Gateway connections.

For general policy management across all connection types, use the
PolicyManagementClient from aidefense.management instead.
"""

from typing import Optional

from aidefense.config import Config
from aidefense.management.auth import ManagementAuth
from aidefense.management.base_client import BaseClient
from aidefense.management.models.connection import ConnectionType
from aidefense.management.models.policy import (
    Policy,
    Policies,
    ListPoliciesRequest,
    UpdatePolicyRequest,
    AddOrUpdatePolicyConnectionsRequest,
)
from aidefense.management.routes import POLICIES, policy_by_id, policy_connections


class MCPPolicyClient(BaseClient):
    """
    Client for managing MCP Gateway policies in AI Defense.

    This client provides methods specifically for MCP Gateway policies.
    It automatically filters to only show policies with connection_type=MCPGateway,
    making it easier to work with MCP-specific security configurations.

    For general policy management across all connection types, use
    PolicyManagementClient from aidefense.management instead.

    Typical Usage:
        ```python
        from aidefense.mcpscan import MCPPolicyClient
        from aidefense.management.models.policy import (
            ListPoliciesRequest,
            AddOrUpdatePolicyConnectionsRequest,
        )
        from aidefense import Config

        # Initialize the client
        client = MCPPolicyClient(
            api_key="YOUR_MANAGEMENT_API_KEY",
            config=Config(management_base_url="https://api.security.cisco.com")
        )

        # List MCP Gateway policies (automatically filtered)
        policies = client.list_mcp_policies(ListPoliciesRequest(limit=25))
        for policy in policies.items:
            print(f"  - {policy.policy_name}: {policy.status}")

        # Associate a policy with MCP connections
        client.update_policy_connections(
            policy_id="policy-uuid",
            request=AddOrUpdatePolicyConnectionsRequest(
                connections_to_associate=["connection-uuid-1", "connection-uuid-2"]
            )
        )
        ```

    Attributes:
        Inherits all attributes from the base BaseClient class including:
        - auth: Authentication handler
        - config: Configuration object with service settings
    """

    def __init__(
            self,
            api_key: str,
            config: Optional[Config] = None,
            request_handler=None
    ):
        """
        Initialize an MCPPolicyClient instance.

        Args:
            api_key (str): Your Cisco AI Defense API key for authentication.
            config (Config, optional): SDK-level configuration for endpoints, logging, retries, etc.
                If not provided, a default Config instance is created.
            request_handler: Optional custom request handler for API requests.
        """
        super().__init__(ManagementAuth(api_key), config, request_handler)

    def list_mcp_policies(self, request: Optional[ListPoliciesRequest] = None) -> Policies:
        """
        List MCP Gateway policies only.

        This method retrieves policies specifically for MCP Gateway connections.
        It automatically filters to connection_type=MCPGateway.

        Args:
            request (ListPoliciesRequest, optional): Request object containing:
                - limit: Maximum number of policies to return
                - offset: Number of policies to skip for pagination
                - sort_by: Field to sort by (e.g., policy_name)
                - order: Sort order ('asc' or 'desc')
                - language_type: Filter by language type
                - policy_status: Filter by policy status
                - policy_name: Filter by policy name substring
                Note: connection_type is automatically set to MCPGateway

        Returns:
            Policies: Object containing:
                - items: List of MCP Gateway Policy objects
                - paging: Pagination information

        Raises:
            ValidationError: If request parameters are invalid.
            ApiError: If the API returns an error response.
            SDKError: For other SDK-related errors.

        Example:
            ```python
            from aidefense.mcpscan import MCPPolicyClient
            from aidefense.management.models.policy import ListPoliciesRequest

            client = MCPPolicyClient(api_key="YOUR_API_KEY")

            # List all MCP Gateway policies
            policies = client.list_mcp_policies()
            print(f"Found {len(policies.items)} MCP policies")

            # With custom options
            request = ListPoliciesRequest(
                limit=50,
                policy_status="Enabled",
                order="asc"
            )
            policies = client.list_mcp_policies(request)
            for policy in policies.items:
                print(f"  - {policy.policy_name}: {policy.status}")
            ```
        """
        if request is None:
            request = ListPoliciesRequest()

        # Force MCPGateway connection type filter
        request.connection_type = ConnectionType.MCPGateway

        params = request.to_params()
        response = self.make_request("GET", POLICIES, params=params)
        policies = self._parse_response(
            Policies, response.get("policies"), "list MCP policies response"
        )
        return policies

    def get_mcp_policy(self, policy_id: str, expanded: bool = False) -> Policy:
        """
        Get an MCP Gateway policy by its ID.

        This method retrieves the details of a specific MCP policy including its
        guardrails configuration when expanded is True.

        Args:
            policy_id (str): The unique identifier of the MCP policy (UUID).
            expanded (bool): Whether to include expanded details like guardrails.
                Defaults to False.

        Returns:
            Policy: Policy object containing:
                - policy_id: Policy identifier
                - policy_name: Policy name
                - description: Policy description
                - status: Policy status
                - connection_type: Should be MCPGateway
                - guardrails: Security guardrails (when expanded=True)
                - created_at/updated_at: Timestamps

        Raises:
            ValidationError: If the policy_id is invalid or not an MCP policy.
            ApiError: If the API returns an error response.
            SDKError: For other SDK-related errors.

        Example:
            ```python
            from aidefense.mcpscan import MCPPolicyClient

            client = MCPPolicyClient(api_key="YOUR_API_KEY")

            policy_id = "550e8400-e29b-41d4-a716-446655440000"
            policy = client.get_mcp_policy(policy_id, expanded=True)

            print(f"Policy: {policy.policy_name}")
            print(f"Status: {policy.status}")
            if policy.guardrails:
                for guardrail in policy.guardrails.items:
                    print(f"  Guardrail: {guardrail.guardrails_type}")
            ```
        """
        self._ensure_uuid(policy_id, "policy_id")
        params = {"expanded": expanded} if expanded else None
        response = self.make_request("GET", policy_by_id(policy_id), params=params)
        policy = self._parse_response(
            Policy, response.get("policy"), "get policy response"
        )
        return policy

    def update_mcp_policy(self, policy_id: str, request: UpdatePolicyRequest) -> None:
        """
        Update an MCP Gateway policy's properties.

        This method updates the name, description, or status of an existing MCP policy.

        Args:
            policy_id (str): The unique identifier of the MCP policy to update (UUID).
            request (UpdatePolicyRequest): Request object containing:
                - name: New name for the policy (optional)
                - description: New description for the policy (optional)
                - status: New status for the policy (optional)

        Returns:
            None

        Raises:
            ValidationError: If the policy_id or request is invalid.
            ApiError: If the API returns an error response.
            SDKError: For other SDK-related errors.

        Example:
            ```python
            from aidefense.mcpscan import MCPPolicyClient
            from aidefense.management.models.policy import UpdatePolicyRequest

            client = MCPPolicyClient(api_key="YOUR_API_KEY")

            policy_id = "550e8400-e29b-41d4-a716-446655440000"
            request = UpdatePolicyRequest(
                name="Updated MCP Security Policy",
                description="Enhanced security controls for MCP servers",
                status="Enabled"
            )
            client.update_mcp_policy(policy_id, request)
            print("MCP Policy updated successfully")
            ```
        """
        self._ensure_uuid(policy_id, "policy_id")
        data = request.to_body_dict(patch=True)
        if not data:
            raise ValueError("No fields to update in UpdatePolicyRequest")

        self.make_request("PUT", policy_by_id(policy_id), data=data)

    def delete_mcp_policy(self, policy_id: str) -> None:
        """
        Delete an MCP Gateway policy.

        This method removes an MCP policy from the system. Any MCP connections
        associated with this policy will no longer have this policy applied.

        Args:
            policy_id (str): The unique identifier of the MCP policy to delete (UUID).

        Returns:
            None

        Raises:
            ValidationError: If the policy_id is invalid.
            ApiError: If the API returns an error response.
            SDKError: For other SDK-related errors.

        Example:
            ```python
            from aidefense.mcpscan import MCPPolicyClient

            client = MCPPolicyClient(api_key="YOUR_API_KEY")

            policy_id = "550e8400-e29b-41d4-a716-446655440000"
            client.delete_mcp_policy(policy_id)
            print(f"MCP Policy {policy_id} deleted")
            ```
        """
        self._ensure_uuid(policy_id, "policy_id")
        self.make_request("DELETE", policy_by_id(policy_id))

    def update_mcp_policy_connections(
            self,
            policy_id: str,
            request: AddOrUpdatePolicyConnectionsRequest
    ) -> None:
        """
        Associate or disassociate MCP connections with a policy.

        This method allows you to add MCP Gateway resource connections to a policy
        (so the policy's guardrails apply to those connections) or remove
        MCP connections from a policy.

        Args:
            policy_id (str): The unique identifier of the MCP policy (UUID).
            request (AddOrUpdatePolicyConnectionsRequest): Request object containing:
                - connections_to_associate: List of MCP connection IDs to add to policy
                - connections_to_disassociate: List of MCP connection IDs to remove from policy

        Returns:
            None

        Raises:
            ValidationError: If the policy_id or connection IDs are invalid.
            ApiError: If the API returns an error response.
            SDKError: For other SDK-related errors.

        Example:
            ```python
            from aidefense.mcpscan import MCPPolicyClient
            from aidefense.management.models.policy import AddOrUpdatePolicyConnectionsRequest

            client = MCPPolicyClient(api_key="YOUR_API_KEY")

            # Associate MCP resource connections with an MCP security policy
            policy_id = "550e8400-e29b-41d4-a716-446655440000"
            request = AddOrUpdatePolicyConnectionsRequest(
                connections_to_associate=[
                    "323e4567-e89b-12d3-a456-426614174333",
                    "424e4567-e89b-12d3-a456-426614174444"
                ]
            )
            client.update_mcp_policy_connections(policy_id, request)
            print("MCP Policy connections updated")

            # Later, remove an MCP connection from the policy
            request = AddOrUpdatePolicyConnectionsRequest(
                connections_to_disassociate=["323e4567-e89b-12d3-a456-426614174333"]
            )
            client.update_mcp_policy_connections(policy_id, request)
            ```
        """
        self._ensure_uuid(policy_id, "policy_id")
        # Validate connection IDs in the request payload
        if getattr(request, "connections_to_associate", None):
            for cid in request.connections_to_associate:
                self._ensure_uuid(cid, "connection_id")
        if getattr(request, "connections_to_disassociate", None):
            for cid in request.connections_to_disassociate:
                self._ensure_uuid(cid, "connection_id")

        data = request.to_body_dict(patch=True)
        if not data:
            raise ValueError("No MCP connections specified to update for policy")

        self.make_request("POST", policy_connections(policy_id), data=data)

