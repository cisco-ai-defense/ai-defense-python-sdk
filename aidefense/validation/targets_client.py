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

"""Targets client for the AI Defense Validation API."""

from typing import Optional

from ..management.auth import ManagementAuth
from ..management.base_client import BaseClient
from ..config import Config
from ._generated.ai_validation.v1.ai_validation_pydantic import (
    CreateTargetRequest,
    CreateTargetResponse,
    GetTargetResponse,
    ListTargetsRequest,
    ListTargetsResponse,
    UpdateTargetRequest,
    UpdateTargetResponse,
    TestTargetConnectionRequest,
    TestTargetConnectionResponse,
    GetTargetAggregatesResponse,
    ListAwsAccountsRequest,
    ListAwsAccountsResponse,
)
from .routes import (
    ai_validation_targets,
    ai_validation_target,
    ai_validation_targets_test,
    ai_validation_targets_aggregates,
    ai_validation_targets_aws_accounts,
)


class TargetsClient(BaseClient):
    """
    Client for managing validation targets in the AI Defense Validation API.

    Provides methods for creating, retrieving, updating, deleting, and testing
    connectivity of validation targets.
    """

    def __init__(
        self,
        auth: ManagementAuth,
        config: Optional[Config] = None,
        request_handler=None,
    ):
        """
        Initialize the TargetsClient.

        Args:
            auth (ManagementAuth): Your AI Defense API authentication object.
            config (Config, optional): SDK configuration for endpoints, logging, retries, etc.
                Defaults to the singleton Config if not provided.
            request_handler: Request handler for making API requests.
        """
        super().__init__(auth, config, request_handler)

    def create_target(self, request: CreateTargetRequest) -> CreateTargetResponse:
        """
        Create a new validation target.

        Args:
            request: CreateTargetRequest containing target configuration including:
                - name: Human-readable name for the target
                - target_type: Type of target (MODEL, APPLICATION, AGENT)
                - Provider config (one of aws_bedrock, custom, aws_agentcore)

        Returns:
            CreateTargetResponse: Response containing the created target's ID.

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                request = CreateTargetRequest(
                    name="My Model Target",
                    target_type=TargetType.MODEL,
                    custom=CustomProviderConfig(...)
                )
                response = client.targets.create_target(request)
                print(f"Created target: {response.target_id}")
        """
        data = request.model_dump(exclude_defaults=True)
        response = self.make_request("POST", ai_validation_targets(), data=data)
        return self._parse_response(
            CreateTargetResponse, response, "create target response"
        )

    def get_target(self, target_id: str) -> GetTargetResponse:
        """
        Get a validation target by ID.

        Args:
            target_id (str): Unique identifier of the target to retrieve.

        Returns:
            GetTargetResponse: Full target details.

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                target = client.targets.get_target("target-uuid-here")
                print(f"Target name: {target.name}")
        """
        self._ensure_uuid(target_id, "target_id")
        response = self.make_request("GET", ai_validation_target(target_id))
        return self._parse_response(
            GetTargetResponse, response, "get target response"
        )

    def list_targets(self, request: ListTargetsRequest) -> ListTargetsResponse:
        """
        List validation targets with optional filtering and pagination.

        Args:
            request: ListTargetsRequest containing optional filters:
                - target_type: Filter by target type
                - provider: Filter by provider
                - search_string: Text search
                - status: Filter by status
                - limit: Max results to return
                - offset: Pagination offset

        Returns:
            ListTargetsResponse: Response containing a list of target summaries and paging info.

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                request = ListTargetsRequest(limit=10, target_type=TargetType.MODEL)
                response = client.targets.list_targets(request)
                for target in response.targets:
                    print(f"{target.target_id}: {target.name}")
        """
        params = request.model_dump(exclude_defaults=True)
        response = self.make_request("GET", ai_validation_targets(), params=params)
        return self._parse_response(
            ListTargetsResponse, response, "list targets response"
        )

    def update_target(
        self, target_id: str, request: UpdateTargetRequest
    ) -> UpdateTargetResponse:
        """
        Update a validation target.

        Args:
            target_id (str): Unique identifier of the target to update.
            request: UpdateTargetRequest containing fields to update.

        Returns:
            UpdateTargetResponse: The update response.

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                request = UpdateTargetRequest(name="Updated Target Name")
                response = client.targets.update_target("target-uuid-here", request)
        """
        self._ensure_uuid(target_id, "target_id")
        data = request.model_dump(exclude_defaults=True)
        response = self.make_request("PATCH", ai_validation_target(target_id), data=data)
        return self._parse_response(
            UpdateTargetResponse, response, "update target response"
        )

    def delete_target(self, target_id: str) -> None:
        """
        Delete a validation target.

        Args:
            target_id (str): Unique identifier of the target to delete.

        Returns:
            None

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                client.targets.delete_target("target-uuid-here")
        """
        self._ensure_uuid(target_id, "target_id")
        self.make_request("DELETE", ai_validation_target(target_id))
        return None

    def test_target_connection(
        self, request: TestTargetConnectionRequest
    ) -> TestTargetConnectionResponse:
        """
        Test connectivity to a target with inline configuration (before saving).

        Args:
            request: TestTargetConnectionRequest containing the target connection
                configuration to test, including provider config.

        Returns:
            TestTargetConnectionResponse: Response with success status, latency, and any error.

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                request = TestTargetConnectionRequest(
                    target_type=TargetType.MODEL,
                    provider=TargetProvider.CUSTOM_ENDPOINT,
                    custom=CustomProviderConfig(...)
                )
                result = client.targets.test_target_connection(request)
                if result.success:
                    print(f"Connection OK, latency: {result.latency_ms}ms")
                else:
                    print(f"Connection failed: {result.error}")
        """
        data = request.model_dump(exclude_defaults=True)
        response = self.make_request("POST", ai_validation_targets_test(), data=data)
        return self._parse_response(
            TestTargetConnectionResponse, response, "test target connection response"
        )

    def get_target_aggregates(self) -> GetTargetAggregatesResponse:
        """
        Get aggregate counts for targets grouped by type.

        Returns:
            GetTargetAggregatesResponse: Aggregate counts by target type.

        Raises:
            ValidationError, ApiError, SDKError
        """
        response = self.make_request("GET", ai_validation_targets_aggregates())
        return self._parse_response(
            GetTargetAggregatesResponse, response, "get target aggregates response"
        )

    def list_aws_accounts(
        self, request: ListAwsAccountsRequest
    ) -> ListAwsAccountsResponse:
        """
        List AWS accounts available for targeting.

        Args:
            request: ListAwsAccountsRequest with optional pagination.

        Returns:
            ListAwsAccountsResponse: List of available AWS accounts.

        Raises:
            ValidationError, ApiError, SDKError
        """
        params = request.model_dump(exclude_defaults=True)
        response = self.make_request(
            "GET", ai_validation_targets_aws_accounts(), params=params
        )
        return self._parse_response(
            ListAwsAccountsResponse, response, "list aws accounts response"
        )
