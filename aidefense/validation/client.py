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

"""Facade client for the AI Defense Validation API."""

from typing import Optional

from ..management.auth import ManagementAuth
from ..config import Config
from ..request_handler import RequestHandler
from .targets import Targets
from .profiles import Profiles
from .custom_goals import CustomGoals
from .standard_validation import StandardValidation
from .adaptive_validation import AdaptiveValidation


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
            targets = client.targets.list(ListTargetsRequest())

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

        self._targets = Targets(
            self._auth, self.config, request_handler=self._request_handler
        )
        self._profiles = Profiles(
            self._auth, self.config, request_handler=self._request_handler
        )
        self._custom_goals = CustomGoals(
            self._auth, self.config, request_handler=self._request_handler
        )
        self._standard = StandardValidation(
            self._auth, self.config, request_handler=self._request_handler
        )
        self._adaptive = AdaptiveValidation(
            self._auth, self.config, request_handler=self._request_handler
        )

    @property
    def targets(self) -> Targets:
        """Sub-client for managing validation targets."""
        return self._targets

    @property
    def profiles(self) -> Profiles:
        """Sub-client for managing validation profiles."""
        return self._profiles

    @property
    def custom_goals(self) -> CustomGoals:
        """Sub-client for managing custom validation goals."""
        return self._custom_goals

    @property
    def standard(self) -> StandardValidation:
        """Sub-client for standard (non-adaptive) validation jobs."""
        return self._standard

    @property
    def adaptive(self) -> AdaptiveValidation:
        """Sub-client for adaptive (red-team) validation jobs."""
        return self._adaptive

    @property
    def api_key(self) -> str:
        """Expose the API key for compatibility."""
        return self._auth.api_key
