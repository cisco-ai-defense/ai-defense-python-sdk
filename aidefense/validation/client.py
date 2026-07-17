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

"""Async facade client for the AI Defense Validation API."""

from __future__ import annotations

import logging
import platform
import uuid
from typing import Any, Dict, Optional, Type, TypeVar, cast

import aiohttp
from pydantic import BaseModel, ValidationError as PydanticValidationError

from ..exceptions import ApiError, ResponseParseError, SDKError, ValidationError
from ..version import version
from .targets import Targets
from .profiles import Profiles
from .custom_goals import CustomGoals
from .standard_validation import StandardValidation
from .adaptive_validation import AdaptiveValidation

T = TypeVar("T", bound=BaseModel)

_USER_AGENT = f"Cisco-AI-Defense-Python-SDK/{version} (Python {platform.python_version()})"
_AUTH_HEADER = "X-Cisco-AI-Defense-Tenant-API-Key"
_REQUEST_ID_HEADER = "x-aidefense-request-id"


class _Api:
    """Shared async request helper injected into every validation resource class."""

    _API_PREFIX_TEMPLATE = "{base}/api/ai-defense/v1"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout: int = 30,
        logger: Optional[logging.Logger] = None,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._logger = logger or logging.getLogger("aidefense_sdk.validation")
        self._api_prefix = self._API_PREFIX_TEMPLATE.format(base=self._base_url)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=self._timeout,
                headers={
                    "User-Agent": _USER_AGENT,
                    "Content-Type": "application/json",
                    _AUTH_HEADER: self._api_key,
                },
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Build the full URL and dispatch the async HTTP request."""
        session = await self._ensure_session()
        url = f"{self._api_prefix}/{path.lstrip('/')}"
        request_id = str(uuid.uuid4())

        req_headers: Dict[str, str] = {_REQUEST_ID_HEADER: request_id}
        if headers:
            req_headers.update(headers)

        self._logger.debug("request %s %s", method, url)

        async with session.request(
            method=method,
            url=url,
            headers=req_headers,
            params=params,
            json=data,
        ) as response:
            if response.status >= 400:
                return await self._handle_error(response, request_id)
            if response.status == 204 or response.content_length == 0:
                return {}
            return await response.json()

    async def _handle_error(
        self, response: aiohttp.ClientResponse, request_id: str
    ) -> Dict[str, Any]:
        try:
            error_data = await response.json()
        except (ValueError, aiohttp.ContentTypeError):
            text = await response.text()
            error_data = {"message": text or "Unknown error"}

        msg = error_data.get("message", "Unknown error")
        status = response.status

        if status == 401:
            raise SDKError(f"Authentication error: {msg}", status)
        elif status == 400:
            raise ValidationError(f"Bad request: {msg}", status)
        else:
            raise ApiError(f"API error {status}: {msg}", status, request_id=request_id)

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
            self._logger.warning("Failed to parse %s: %s", context, e)
            raise ResponseParseError(f"Failed to parse {context}: {e}") from e

    @staticmethod
    def ensure_uuid(value: str, field_name: str) -> None:
        """Validate that *value* is a UUID string."""
        try:
            uuid.UUID(str(value))
        except Exception:
            raise ValueError(f"Invalid {field_name}: must be a UUID string")


# Default region endpoints for convenience when Config is not used.
_MANAGEMENT_REGION_ENDPOINTS = {
    "us": "https://us.api.aidefense.security.cisco.com",
    "eu": "https://eu.api.aidefense.security.cisco.com",
    "ap": "https://ap.api.aidefense.security.cisco.com",
}


class ValidationClient:
    """
    Async client for the AI Defense Validation API.

    Use as an async context manager to ensure the HTTP session is closed::

        async with ValidationClient(api_key="...") as client:
            targets = await client.targets.list(ListTargetsRequest())

    Args:
        api_key: Your AI Defense API key for authentication.
        base_url: Management API base URL. Defaults to the US endpoint.
        timeout: HTTP request timeout in seconds. Defaults to 30.
        logger: Optional custom logger instance.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://us.api.aidefense.security.cisco.com",
        timeout: int = 30,
        logger: Optional[logging.Logger] = None,
    ):
        if not api_key or not isinstance(api_key, str) or api_key.strip() == "":
            raise ValueError("API key is required")

        self._api = _Api(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            logger=logger,
        )
        self._targets = Targets(self._api)
        self._profiles = Profiles(self._api)
        self._custom_goals = CustomGoals(self._api)
        self._standard = StandardValidation(self._api)
        self._adaptive = AdaptiveValidation(self._api)

    async def __aenter__(self) -> ValidationClient:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        await self._api.close()

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
