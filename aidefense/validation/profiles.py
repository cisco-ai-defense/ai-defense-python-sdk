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

"""Profiles resource for the AI Defense Validation API."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import _Api

from aidefense.pydantic.validation.ai_validation.v1.ai_validation_pydantic import (
    CreateAiValidationProfileRequest,
    CreateAiValidationProfileResponse,
    GetAiValidationProfileResponse,
    ListAiValidationProfilesRequest,
    ListAiValidationProfilesResponse,
    ListAiValidationProfilesByGoalIDResponse,
    ProfileUpdate,
    UpdateAiValidationProfileResponse,
)
from .routes import (
    ai_validation_profiles,
    ai_validation_profile,
    ai_validation_profiles_by_goal,
)


class Profiles:
    """
    Manage validation profiles in the AI Defense Validation API.

    All methods are coroutines — call them with ``await``.
    """

    def __init__(self, api: _Api):
        self._api = api

    async def create(
        self, request: CreateAiValidationProfileRequest
    ) -> CreateAiValidationProfileResponse:
        """Create a new validation profile."""
        data = request.model_dump(exclude_defaults=True)
        response = await self._api.request("POST", ai_validation_profiles(), data=data)
        return self._api.parse(
            CreateAiValidationProfileResponse, response, "create profile response"
        )

    async def get(self, profile_id: str) -> GetAiValidationProfileResponse:
        """Get a validation profile by ID."""
        self._api.ensure_uuid(profile_id, "profile_id")
        response = await self._api.request("GET", ai_validation_profile(profile_id))
        return self._api.parse(
            GetAiValidationProfileResponse, response, "get profile response"
        )

    async def list(
        self, request: ListAiValidationProfilesRequest
    ) -> ListAiValidationProfilesResponse:
        """List validation profiles with optional filtering and pagination."""
        params = request.model_dump(exclude_defaults=True)
        response = await self._api.request("GET", ai_validation_profiles(), params=params)
        return self._api.parse(
            ListAiValidationProfilesResponse, response, "list profiles response"
        )

    async def list_by_goal(
        self, goal_id: str
    ) -> ListAiValidationProfilesByGoalIDResponse:
        """List profiles associated with a specific goal."""
        self._api.ensure_uuid(goal_id, "goal_id")
        response = await self._api.request("GET", ai_validation_profiles_by_goal(goal_id))
        return self._api.parse(
            ListAiValidationProfilesByGoalIDResponse,
            response,
            "list profiles by goal response",
        )

    async def update(
        self, profile_id: str, request: ProfileUpdate
    ) -> UpdateAiValidationProfileResponse:
        """
        Update a validation profile.

        The request body should contain only the fields to change.
        grpc-gateway auto-derives the update mask from the JSON keys present.
        """
        self._api.ensure_uuid(profile_id, "profile_id")
        data = request.model_dump(exclude_none=True)
        response = await self._api.request(
            "PATCH", ai_validation_profile(profile_id), data=data
        )
        return self._api.parse(
            UpdateAiValidationProfileResponse, response, "update profile response"
        )

    async def delete(self, profile_id: str) -> None:
        """Delete a validation profile."""
        self._api.ensure_uuid(profile_id, "profile_id")
        await self._api.request("DELETE", ai_validation_profile(profile_id))
        return None
