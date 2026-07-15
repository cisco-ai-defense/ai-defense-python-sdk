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

"""Custom goals client for the AI Defense Validation API."""

from typing import Optional

from ..management.auth import ManagementAuth
from ..management.base_client import BaseClient
from ..config import Config
from ._generated.ai_validation.v1.ai_validation_pydantic import (
    CreateAiValidationCustomGoalRequest,
    CreateAiValidationCustomGoalResponse,
    ListAiValidationCustomGoalsRequest,
    ListAiValidationCustomGoalsResponse,
    UpdateAiValidationCustomGoalRequest,
    UpdateAiValidationCustomGoalResponse,
)
from .routes import ai_validation_custom_goals, ai_validation_custom_goal


class CustomGoalsClient(BaseClient):
    """
    Client for managing custom validation goals in the AI Defense Validation API.

    Custom goals allow users to define organization-specific attack objectives
    that extend the built-in goal library.
    """

    def __init__(
        self,
        auth: ManagementAuth,
        config: Optional[Config] = None,
        request_handler=None,
    ):
        super().__init__(auth, config, request_handler)

    def create_custom_goal(
        self, request: CreateAiValidationCustomGoalRequest
    ) -> CreateAiValidationCustomGoalResponse:
        """
        Create a new custom goal.

        Args:
            request: Custom goal creation request with name, description,
                and prompt configuration.

        Returns:
            CreateAiValidationCustomGoalResponse: The created goal ID.

        Raises:
            ValidationError, ApiError, SDKError
        """
        data = request.model_dump(exclude_defaults=True)
        response = self.make_request("POST", ai_validation_custom_goals(), data=data)
        return self._parse_response(
            CreateAiValidationCustomGoalResponse,
            response,
            "create custom goal response",
        )

    def list_custom_goals(
        self, request: ListAiValidationCustomGoalsRequest
    ) -> ListAiValidationCustomGoalsResponse:
        """
        List custom goals with optional filtering and pagination.

        Args:
            request: List request with optional search, limit, offset.

        Returns:
            ListAiValidationCustomGoalsResponse: List of custom goals.

        Raises:
            ValidationError, ApiError, SDKError
        """
        params = request.model_dump(exclude_defaults=True)
        response = self.make_request(
            "GET", ai_validation_custom_goals(), params=params
        )
        return self._parse_response(
            ListAiValidationCustomGoalsResponse,
            response,
            "list custom goals response",
        )

    def update_custom_goal(
        self, custom_goal_id: str, request: UpdateAiValidationCustomGoalRequest
    ) -> UpdateAiValidationCustomGoalResponse:
        """
        Update a custom goal.

        Args:
            custom_goal_id: Unique identifier of the custom goal to update.
            request: Fields to update on the custom goal.

        Returns:
            UpdateAiValidationCustomGoalResponse: The update response.

        Raises:
            ValidationError, ApiError, SDKError
        """
        self._ensure_uuid(custom_goal_id, "custom_goal_id")
        data = request.model_dump(exclude_defaults=True)
        response = self.make_request(
            "PATCH", ai_validation_custom_goal(custom_goal_id), data=data
        )
        return self._parse_response(
            UpdateAiValidationCustomGoalResponse,
            response,
            "update custom goal response",
        )

    def delete_custom_goal(self, custom_goal_id: str) -> None:
        """
        Delete a custom goal.

        Args:
            custom_goal_id: Unique identifier of the custom goal to delete.

        Raises:
            ValidationError, ApiError, SDKError
        """
        self._ensure_uuid(custom_goal_id, "custom_goal_id")
        self.make_request("DELETE", ai_validation_custom_goal(custom_goal_id))
        return None
