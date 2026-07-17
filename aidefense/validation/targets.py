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

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import _Api

from aidefense.pydantic.validation.ai_validation.v1.ai_validation_pydantic import (
    CreateTargetRequest,
    CreateTargetResponse,
    GetTargetResponse,
    ListTargetsRequest,
    ListTargetsResponse,
    TargetUpdate,
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


class Targets:
    """
    Manage validation targets in the AI Defense Validation API.

    All methods are coroutines — call them with ``await``.
    """

    def __init__(self, api: _Api):
        self._api = api

    async def create(self, request: CreateTargetRequest) -> CreateTargetResponse:
        """Create a new validation target."""
        data = request.model_dump(exclude_defaults=True)
        response = await self._api.request("POST", ai_validation_targets(), data=data)
        return self._api.parse(
            CreateTargetResponse, response, "create target response"
        )

    async def get(self, target_id: str) -> GetTargetResponse:
        """Get a validation target by ID."""
        self._api.ensure_uuid(target_id, "target_id")
        response = await self._api.request("GET", ai_validation_target(target_id))
        return self._api.parse(
            GetTargetResponse, response, "get target response"
        )

    async def list(self, request: ListTargetsRequest) -> ListTargetsResponse:
        """List validation targets with optional filtering and pagination."""
        params = request.model_dump(exclude_defaults=True)
        response = await self._api.request("GET", ai_validation_targets(), params=params)
        return self._api.parse(
            ListTargetsResponse, response, "list targets response"
        )

    async def update(
        self, target_id: str, request: TargetUpdate
    ) -> UpdateTargetResponse:
        """
        Update a validation target.

        The request body should contain only the fields to change.
        grpc-gateway auto-derives the update mask from the JSON keys present.
        """
        self._api.ensure_uuid(target_id, "target_id")
        data = request.model_dump(exclude_none=True)
        response = await self._api.request(
            "PATCH", ai_validation_target(target_id), data=data
        )
        return self._api.parse(
            UpdateTargetResponse, response, "update target response"
        )

    async def delete(self, target_id: str) -> None:
        """Delete a validation target."""
        self._api.ensure_uuid(target_id, "target_id")
        await self._api.request("DELETE", ai_validation_target(target_id))
        return None

    async def test_connection(
        self, request: TestTargetConnectionRequest
    ) -> TestTargetConnectionResponse:
        """Test connectivity to a target with inline configuration (before saving)."""
        data = request.model_dump(exclude_defaults=True)
        response = await self._api.request("POST", ai_validation_targets_test(), data=data)
        return self._api.parse(
            TestTargetConnectionResponse, response, "test target connection response"
        )

    async def get_aggregates(self) -> GetTargetAggregatesResponse:
        """Get aggregate counts for targets grouped by type."""
        response = await self._api.request("GET", ai_validation_targets_aggregates())
        return self._api.parse(
            GetTargetAggregatesResponse, response, "get target aggregates response"
        )

    async def list_aws_accounts(
        self, request: ListAwsAccountsRequest
    ) -> ListAwsAccountsResponse:
        """List AWS accounts available for targeting."""
        params = request.model_dump(exclude_defaults=True)
        response = await self._api.request(
            "GET", ai_validation_targets_aws_accounts(), params=params
        )
        return self._api.parse(
            ListAwsAccountsResponse, response, "list aws accounts response"
        )
