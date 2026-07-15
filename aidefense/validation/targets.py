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

"""Targets resource for the AI Defense Validation API."""

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


class Targets(BaseClient):
    """
    Manage validation targets in the AI Defense Validation API.

    Provides methods for creating, retrieving, updating, deleting, and testing
    connectivity of validation targets.
    """

    def __init__(
        self,
        auth: ManagementAuth,
        config: Optional[Config] = None,
        request_handler=None,
    ):
        super().__init__(auth, config, request_handler)

    def create(self, request: CreateTargetRequest) -> CreateTargetResponse:
        """
        Create a new validation target.

        Args:
            request: CreateTargetRequest containing target configuration.

        Returns:
            CreateTargetResponse: Response containing the created target's ID.

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                response = client.targets.create(CreateTargetRequest(
                    name="My Model Target",
                    target_type=TargetType.MODEL,
                    custom=CustomProviderConfig(...)
                ))
        """
        data = request.model_dump(exclude_defaults=True)
        response = self.make_request("POST", ai_validation_targets(), data=data)
        return self._parse_response(
            CreateTargetResponse, response, "create target response"
        )

    def get(self, target_id: str) -> GetTargetResponse:
        """
        Get a validation target by ID.

        Args:
            target_id: Unique identifier of the target to retrieve.

        Returns:
            GetTargetResponse: Full target details.

        Raises:
            ValidationError, ApiError, SDKError
        """
        self._ensure_uuid(target_id, "target_id")
        response = self.make_request("GET", ai_validation_target(target_id))
        return self._parse_response(
            GetTargetResponse, response, "get target response"
        )

    def list(self, request: ListTargetsRequest) -> ListTargetsResponse:
        """
        List validation targets with optional filtering and pagination.

        Args:
            request: ListTargetsRequest containing optional filters.

        Returns:
            ListTargetsResponse: List of target summaries and paging info.

        Raises:
            ValidationError, ApiError, SDKError
        """
        params = request.model_dump(exclude_defaults=True)
        response = self.make_request("GET", ai_validation_targets(), params=params)
        return self._parse_response(
            ListTargetsResponse, response, "list targets response"
        )

    def update(
        self, target_id: str, request: UpdateTargetRequest
    ) -> UpdateTargetResponse:
        """
        Update a validation target.

        Args:
            target_id: Unique identifier of the target to update.
            request: UpdateTargetRequest containing fields to update.

        Returns:
            UpdateTargetResponse: The update response.

        Raises:
            ValidationError, ApiError, SDKError
        """
        self._ensure_uuid(target_id, "target_id")
        data = request.model_dump(exclude_defaults=True)
        response = self.make_request(
            "PATCH", ai_validation_target(target_id), data=data
        )
        return self._parse_response(
            UpdateTargetResponse, response, "update target response"
        )

    def delete(self, target_id: str) -> None:
        """
        Delete a validation target.

        Args:
            target_id: Unique identifier of the target to delete.

        Raises:
            ValidationError, ApiError, SDKError
        """
        self._ensure_uuid(target_id, "target_id")
        self.make_request("DELETE", ai_validation_target(target_id))
        return None

    def test_connection(
        self, request: TestTargetConnectionRequest
    ) -> TestTargetConnectionResponse:
        """
        Test connectivity to a target with inline configuration (before saving).

        Args:
            request: TestTargetConnectionRequest with provider config to test.

        Returns:
            TestTargetConnectionResponse: Success status, latency, and any error.

        Raises:
            ValidationError, ApiError, SDKError
        """
        data = request.model_dump(exclude_defaults=True)
        response = self.make_request("POST", ai_validation_targets_test(), data=data)
        return self._parse_response(
            TestTargetConnectionResponse, response, "test target connection response"
        )

    def get_aggregates(self) -> GetTargetAggregatesResponse:
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
