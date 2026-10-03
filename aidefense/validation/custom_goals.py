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

"""Custom goals resource for the AI Defense Validation API."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import _Api

from aidefense.pydantic.validation.ai_validation.v1.ai_validation_pydantic import (
    CreateAiValidationCustomGoalRequest,
    CreateAiValidationCustomGoalResponse,
    ListAiValidationCustomGoalsRequest,
    ListAiValidationCustomGoalsResponse,
    CustomGoalUpdate,
    UpdateAiValidationCustomGoalResponse,
)
from .routes import ai_validation_custom_goals, ai_validation_custom_goal


class CustomGoals:
    """
    Manage custom validation goals in the AI Defense Validation API.

    All methods are coroutines — call them with ``await``.
    """

    def __init__(self, api: _Api):
        self._api = api

    async def create(
        self, request: CreateAiValidationCustomGoalRequest
    ) -> CreateAiValidationCustomGoalResponse:
        """Create a new custom goal."""
        data = request.model_dump(exclude_defaults=True)
        response = await self._api.request("POST", ai_validation_custom_goals(), data=data)
        return self._api.parse(
            CreateAiValidationCustomGoalResponse,
            response,
            "create custom goal response",
        )

    async def list(
        self, request: ListAiValidationCustomGoalsRequest
    ) -> ListAiValidationCustomGoalsResponse:
        """List custom goals with optional filtering and pagination."""
        params = request.model_dump(exclude_defaults=True)
        response = await self._api.request(
            "GET", ai_validation_custom_goals(), params=params
        )
        return self._api.parse(
            ListAiValidationCustomGoalsResponse,
            response,
            "list custom goals response",
        )

    async def update(
        self, custom_goal_id: str, request: CustomGoalUpdate
    ) -> UpdateAiValidationCustomGoalResponse:
        """
        Update a custom goal.

        The request body should contain only the fields to change.
        grpc-gateway auto-derives the update mask from the JSON keys present.
        """
        self._api.ensure_uuid(custom_goal_id, "custom_goal_id")
        data = request.model_dump(exclude_none=True)
        response = await self._api.request(
            "PATCH", ai_validation_custom_goal(custom_goal_id), data=data
        )
        return self._api.parse(
            UpdateAiValidationCustomGoalResponse,
            response,
            "update custom goal response",
        )

    async def delete(self, custom_goal_id: str) -> None:
        """Delete a custom goal."""
        self._api.ensure_uuid(custom_goal_id, "custom_goal_id")
        await self._api.request("DELETE", ai_validation_custom_goal(custom_goal_id))
        return None
