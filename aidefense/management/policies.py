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

"""Policy management client for the AI Defense Management API."""

from typing import Optional, List

from .base_client import BaseClient
from .models.policy import (
    Policy,
    Policies,
    PolicySortBy,
    Guardrail,
    Guardrails,
    ListPoliciesRequest,
    ListPoliciesResponse,
    UpdatePolicyRequest,
    UpdatePolicyResponse,
    DeletePolicyResponse,
    AddOrUpdatePolicyConnectionsRequest,
    AddOrUpdatePolicyConnectionsResponse,
)
from ..config import Config


class PolicyManagementClient(BaseClient):
    """
    Client for managing policies in the AI Defense Management API.

    Provides methods for creating, retrieving, updating, and deleting
    policies in the AI Defense Management API.
    """

    def __init__(
        self, api_key: str, config: Optional[Config] = None, request_handler=None
    ):
        """
        Initialize the PolicyManagementClient.

        Args:
            api_key (str): Your AI Defense Management API key for authentication.
            config (Config, optional): SDK configuration for endpoints, logging, retries, etc.
                Defaults to the singleton Config if not provided.
            request_handler: Request handler for making API requests (should be an instance of ManagementClient).
        """
        super().__init__(api_key, config, request_handler)

    def list_policies(self, request: ListPoliciesRequest) -> Policies:
        """
        List policies.

        Args:
            request: ListPoliciesRequest object containing optional parameters:
                - limit: Maximum number of policies to return
                - offset: Number of policies to skip
                - sort_by: Field to sort by
                - order: Sort order ('asc' or 'desc')

        Returns:
            ListPoliciesResponse: Response containing a list of policies.

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                request = ListPoliciesRequest(
                    limit=10,
                    sort_by=PolicySortBy.policy_name,
                    order="asc"
                )
                response = client.policies.list_policies(request)
                for policy in response.policies.items:
                    print(f"{policy.policy_id}: {policy.policy_name}")
        """
        params = self._filter_none(
            {
                "limit": request.limit,
                "offset": request.offset,
                "sort_by": (
                    request.sort_by.value
                    if isinstance(request.sort_by, PolicySortBy)
                    else request.sort_by
                ),
                "order": (
                    request.order.value
                    if hasattr(request.order, "value")
                    else request.order
                ),
            }
        )

        response = self.make_request("GET", "policies", params=params)
        policies = self._parse_response(Policies, response, "policies response")
        return policies

    def get_policy(self, policy_id: str, expanded: bool = None) -> Policy:
        """
        Get a policy by ID.

        Args:
            policy_id (str): ID of the policy
            expanded (bool, optional): Whether to include expanded details

        Returns:
            Policy: Response containing policy details.

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                policy_id = "550e8400-e29b-41d4-a716-446655440000"
                response = client.policies.get_policy(policy_id, expanded=True)
                print(f"Policy name: {response.policy_name}")
        """
        params = self._filter_none({"expanded": expanded})
        response = self.make_request("GET", f"policies/{policy_id}", params=params)
        policy = self._parse_response(Policy, response, "policy response")
        return policy

    def update_policy(
        self, policy_id: str, request: UpdatePolicyRequest
    ) -> UpdatePolicyResponse:
        """
        Update a policy.

        Args:
            policy_id (str): ID of the policy to update
            request: UpdatePolicyRequest containing:
                - name: New name for the policy (optional)
                - description: New description for the policy (optional)
                - status: New status for the policy (optional)

        Returns:
            UpdatePolicyResponse: Empty response object.

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                policy_id = "550e8400-e29b-41d4-a716-446655440000"
                request = UpdatePolicyRequest(
                    name="Updated Security Policy",
                    description="Enhanced security controls for LLM access",
                    status="active"
                )
                response = client.policies.update_policy(policy_id, request)
        """
        data = self._filter_none(
            {
                "name": request.name,
                "description": request.description,
                "status": request.status,
            }
        )

        self.make_request("PUT", f"policies/{policy_id}", data=data)
        return UpdatePolicyResponse()

    def delete_policy(self, policy_id: str) -> DeletePolicyResponse:
        """
        Delete a policy.

        Args:
            policy_id (str): ID of the policy to delete

        Returns:
            DeletePolicyResponse: Empty response object.

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                policy_id = "550e8400-e29b-41d4-a716-446655440000"
                response = client.policies.delete_policy(policy_id)
        """
        self.make_request("DELETE", f"policies/{policy_id}")
        return DeletePolicyResponse()

    def update_policy_connections(
        self, policy_id: str, request: AddOrUpdatePolicyConnectionsRequest
    ) -> AddOrUpdatePolicyConnectionsResponse:
        """
        Add or update connections for a policy.

        Args:
            policy_id (str): ID of the policy to update
            request: AddOrUpdatePolicyConnectionsRequest containing:
                - connections_to_associate: List of connection IDs to associate with the policy (optional)
                - connections_to_disassociate: List of connection IDs to disassociate from the policy (optional)

        Returns:
            AddOrUpdatePolicyConnectionsResponse: Empty response object.

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                policy_id = "550e8400-e29b-41d4-a716-446655440000"
                request = AddOrUpdatePolicyConnectionsRequest(
                    connections_to_associate=["323e4567-e89b-12d3-a456-426614174333"],
                    connections_to_disassociate=["150e8400-e89b-a716-a456-426614174334"]
                )
                response = client.policies.update_policy_connections(policy_id, request)
        """
        data = {}

        if request.connections_to_associate:
            data["connections_to_associate"] = request.connections_to_associate

        if request.connections_to_disassociate:
            data["connections_to_disassociate"] = request.connections_to_disassociate

        self.make_request("POST", f"policies/{policy_id}/connections", data=data)
        return AddOrUpdatePolicyConnectionsResponse()
