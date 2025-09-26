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

"""AI Validation client for the AI Defense Validation API."""

from typing import Optional

from .auth import ManagementAuth
from ..config import Config
from ..management.base_client import BaseClient
from .models.validation import (
    StartAiValidationRequest,
    StartAiValidationResponse,
    GetAiValidationJobResponse,
    ListAllAiValidationConfigResponse,
    GetAiValidationConfigResponse,
)
from .routes import (
    ai_validation_start,
    ai_validation_job,
    ai_validation_config,
    ai_validation_config_by_task,
)
from ..request_handler import RequestHandler


class AiValidationClient(BaseClient):
    """
    Client for AI Validation operations in the AI Defense Validation API.

    Provides methods to start AI validation jobs, retrieve job status/details,
    and list or fetch AI validation configurations.
    """

    def __init__(
        self, api_key: str, config: Optional[Config] = None, request_handler=None
    ):
        """
        Initialize the AiValidationClient.

        Args:
            api_key (str): Your AI Defense API key for authentication.
            config (Config, optional): SDK configuration for endpoints, logging, retries, etc.
                Defaults to the singleton Config if not provided.
            request_handler: Request handler for making API requests (should be an instance of ValidationClient/RequestHandler).
        """
        self._auth = ManagementAuth(api_key)
        self.config = config or Config()
        self._request_handler = RequestHandler(self.config)

        super().__init__(self._auth, config, request_handler)

    def start_ai_validation(
        self, request: StartAiValidationRequest
    ) -> StartAiValidationResponse:
        """
        Start an AI validation job.

        Endpoint: POST /ai-validation/start

        Args:
            request (StartAiValidationRequest): The request payload containing validation
                configuration and inputs to start the job.

        Returns:
            StartAiValidationResponse: Response containing the created validation task identifier
            and any immediate metadata.

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                request = StartAiValidationRequest(
                    # populate fields as needed
                )
                response = client.start_ai_validation(request)
                print(f"Started validation task: {response.task_id}")
        """
        # Build JSON body using AIDefenseModel helper for consistent serialization
        data = request.to_body_dict()
        resp = self.make_request("POST", ai_validation_start(), data=data)
        return self._parse_response(
            StartAiValidationResponse, resp, "start AI validation response"
        )

    def get_ai_validation_job(self, task_id: str) -> GetAiValidationJobResponse:
        """
        Get AI validation job details by task ID.

        Endpoint: GET /ai-validation/job/{task_id}

        Args:
            task_id (str): The validation task identifier returned when the job was started.

        Returns:
            GetAiValidationJobResponse: Response containing the status, results, and details
            of the AI validation job.

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                task_id = "123e4567-e89b-12d3-a456-426614174000"
                job = client.get_ai_validation_job(task_id)
                print(f"Status: {job.status}")
        """
        resp = self.make_request("GET", ai_validation_job(task_id))
        return self._parse_response(
            GetAiValidationJobResponse, resp, "get AI validation job response"
        )

    def list_all_ai_validation_config(self) -> ListAllAiValidationConfigResponse:
        """
        List all AI validation configurations.

        Endpoint: GET /ai-validation/config

        Args:
            None

        Returns:
            ListAllAiValidationConfigResponse: Response containing a list of available
            AI validation configurations.

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                configs = client.list_all_ai_validation_config()
                for cfg in configs.config:
                    print(cfg.config_id)
        """
        resp = self.make_request("GET", ai_validation_config())
        return self._parse_response(
            ListAllAiValidationConfigResponse,
            resp,
            "list AI validation configs response",
        )

    def get_ai_validation_config(self, task_id: str) -> GetAiValidationConfigResponse:
        """
        Get AI validation configuration by task ID.

        Endpoint: GET /ai-validation/config/{task_id}

        Args:
            task_id (str): The validation task identifier.

        Returns:
            GetAiValidationConfigResponse: Response containing the configuration details
            for the specified validation task.

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                task_id = "123e4567-e89b-12d3-a456-426614174000"
                config = client.get_ai_validation_config(task_id)
                print(config)
        """
        resp = self.make_request("GET", ai_validation_config_by_task(task_id))
        return self._parse_response(
            GetAiValidationConfigResponse, resp, "get AI validation config response"
        )
