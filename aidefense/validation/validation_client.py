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

"""Facade client for the AI Defense Validation API.

Provides a single entry point to all validation sub-clients: targets,
profiles, custom goals, standard validation, and adaptive (red-team)
validation.
"""

from typing import Optional

from ..management.auth import ManagementAuth
from ..config import Config
from ..request_handler import RequestHandler
from .targets_client import TargetsClient
from .profiles_client import ProfilesClient
from .custom_goals_client import CustomGoalsClient
from .standard_validation_client import StandardValidationClient
from .adaptive_validation_client import AdaptiveValidationClient


class ValidationClient:
    """
    Client for the AI Defense Validation API.

    Provides access to all validation API functionality through
    resource-specific sub-clients. Creates a shared ``RequestHandler``
    for connection pooling across all sub-clients.

    Args:
        api_key: Your AI Defense API key for authentication.
        config: SDK configuration for endpoints, logging, retries, etc.
            If not provided, a default singleton ``Config`` is used.

    Example:
        .. code-block:: python

            from aidefense.validation import ValidationClient

            client = ValidationClient(api_key="your-api-key")

            # Manage targets
            targets = client.targets.list_targets(ListTargetsRequest())

            # Run standard validation
            response = client.standard.start(StartAiValidationRequest(...))

            # Run adaptive (red-team) validation
            response = client.adaptive.start(StartAdaptiveRedTeamRequest(...))
    """

    def __init__(
        self,
        api_key: str,
        config: Optional[Config] = None,
    ):
        if not api_key or not isinstance(api_key, str) or api_key.strip() == "":
            raise ValueError("API key is required")

        self._auth = ManagementAuth(api_key)
        self.config = config or Config()
        self._request_handler = RequestHandler(self.config)

        self._targets_client = TargetsClient(
            self._auth, self.config, request_handler=self._request_handler
        )
        self._profiles_client = ProfilesClient(
            self._auth, self.config, request_handler=self._request_handler
        )
        self._custom_goals_client = CustomGoalsClient(
            self._auth, self.config, request_handler=self._request_handler
        )
        self._standard_client = StandardValidationClient(
            self._auth, self.config, request_handler=self._request_handler
        )
        self._adaptive_client = AdaptiveValidationClient(
            self._auth, self.config, request_handler=self._request_handler
        )

    @property
    def targets(self) -> TargetsClient:
        """Sub-client for managing validation targets."""
        return self._targets_client

    @property
    def profiles(self) -> ProfilesClient:
        """Sub-client for managing validation profiles."""
        return self._profiles_client

    @property
    def custom_goals(self) -> CustomGoalsClient:
        """Sub-client for managing custom validation goals."""
        return self._custom_goals_client

    @property
    def standard(self) -> StandardValidationClient:
        """Sub-client for standard (non-adaptive) validation jobs."""
        return self._standard_client

    @property
    def adaptive(self) -> AdaptiveValidationClient:
        """Sub-client for adaptive (red-team) validation jobs."""
        return self._adaptive_client

    @property
    def api_key(self) -> str:
        """Expose the API key for compatibility."""
        return self._auth.api_key
