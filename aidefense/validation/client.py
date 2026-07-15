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

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional, Type, TypeVar, cast

from pydantic import BaseModel, ValidationError as PydanticValidationError

from ..management.auth import ManagementAuth
from ..config import Config
from ..exceptions import ResponseParseError
from ..request_handler import RequestHandler
from .targets import Targets
from .profiles import Profiles
from .custom_goals import CustomGoals
from .standard_validation import StandardValidation
from .adaptive_validation import AdaptiveValidation

T = TypeVar("T", bound=BaseModel)


class _Api:
    """Shared request helper injected into every validation resource class.

    Owns URL construction, HTTP dispatch, response parsing, and input
    validation so that resource classes stay free of infrastructure concerns.
    """

    _API_PREFIX_TEMPLATE = "{base}/api/ai-defense/v1"

    def __init__(
        self,
        auth: ManagementAuth,
        config: Config,
        request_handler: RequestHandler,
    ):
        self._auth = auth
        self.config = config
        self._request_handler = request_handler
        self._api_prefix = self._API_PREFIX_TEMPLATE.format(
            base=config.management_base_url
        )

    def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Build the full URL and dispatch the HTTP request."""
        url = f"{self._api_prefix}/{path.lstrip('/')}"
        return self._request_handler.request(
            method=method,
            url=url,
            auth=self._auth,
            headers=headers,
            json_data=data,
            params=params,
            timeout=self.config.timeout,
        )

    def parse(self, model_class: Type[T], data: Any, context: str) -> T:
        """Parse raw API response data into a Pydantic model."""
        if data is None:
            raise ResponseParseError(
                message=f"Missing required data for {context}",
                response_data=data,
            )
        try:
            return cast(T, model_class.model_validate(data))
        except PydanticValidationError as e:
            self.config.logger.warning(f"Failed to parse {context}: {e}")
            raise ResponseParseError(f"Failed to parse {context}: {e}") from e

    @staticmethod
    def ensure_uuid(value: str, field_name: str) -> None:
        """Validate that *value* is a UUID string."""
        try:
            uuid.UUID(str(value))
        except Exception:
            raise ValueError(f"Invalid {field_name}: must be a UUID string")


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

        api = _Api(self._auth, self.config, self._request_handler)
        self._targets = Targets(api)
        self._profiles = Profiles(api)
        self._custom_goals = CustomGoals(api)
        self._standard = StandardValidation(api)
        self._adaptive = AdaptiveValidation(api)

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
