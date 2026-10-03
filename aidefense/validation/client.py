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
import uuid
from typing import Any, Dict, Optional, Type, TypeVar, cast

import aiohttp
from pydantic import BaseModel, ValidationError as PydanticValidationError

from ..config import AsyncConfig
from ..exceptions import ApiError, ResponseParseError, SDKError, ValidationError
from ..management.base_client import BaseClient
from ..request_handler import BaseRequestHandler
from .targets import Targets
from .profiles import Profiles
from .custom_goals import CustomGoals
from .standard_validation import StandardValidation
from .adaptive_validation import AdaptiveValidation

T = TypeVar("T", bound=BaseModel)


class _Api:
    """Shared async request helper injected into every validation resource class.

    Delegates session management to :class:`~aidefense.config.AsyncConfig` and
    reuses constants from :class:`~aidefense.management.base_client.BaseClient`
    and :class:`~aidefense.request_handler.BaseRequestHandler` so that the API
    prefix, User-Agent, and request-id header are defined in a single place.
    """

    _AUTH_HEADER = "X-Cisco-AI-Defense-Tenant-API-Key"

    def __init__(
        self,
        config: AsyncConfig,
        api_key: str,
    ):
        self._config = config
        self._api_key = api_key
        base = config.management_base_url
        self._api_prefix = (
            f"{base}/{BaseClient.AI_DEFENSE_API_PREFIX}"
            f"/{BaseClient.DEFAULT_API_VERSION}"
        )
        self._logger = config.logger
        self._timeout = aiohttp.ClientTimeout(total=config.timeout)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                connector=self._config.connection_pool,
                connector_owner=False,
                timeout=self._timeout,
                headers={
                    "User-Agent": BaseRequestHandler.USER_AGENT,
                    "Content-Type": "application/json",
                    self._AUTH_HEADER: self._api_key,
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

        req_headers: Dict[str, str] = {
            BaseRequestHandler.REQUEST_ID_HEADER: request_id,
        }
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
            raise ApiError(
                f"API error {status}: {msg}", status, request_id=request_id
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
            self._logger.warning("Failed to parse %s: %s", context, e)
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
    Async client for the AI Defense Validation API.

    Use as an async context manager to ensure the HTTP session is closed::

        async with ValidationClient(api_key="...") as client:
            targets = await client.targets.list(ListTargetsRequest())

    Args:
        api_key: Your AI Defense API key for authentication.
        base_url: Management API base URL. Overrides the region default.
            Defaults to the US endpoint when neither *base_url* nor *config*
            is provided.
        timeout: HTTP request timeout in seconds. Defaults to 30.
        logger: Optional custom logger instance.
        config: Optional :class:`~aidefense.config.AsyncConfig` for full
            control over region, retries, connection pool, and logging.
            When provided, *base_url*, *timeout*, and *logger* are ignored.
    """

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        timeout: int = 30,
        logger: Optional[logging.Logger] = None,
        config: Optional[AsyncConfig] = None,
    ):
        if not api_key or not isinstance(api_key, str) or api_key.strip() == "":
            raise ValueError("API key is required")

        if config is None:
            kwargs: Dict[str, Any] = {"timeout": timeout}
            if base_url is not None:
                kwargs["management_base_url"] = base_url
            if logger is not None:
                kwargs["logger"] = logger
            config = AsyncConfig(**kwargs)

        self._config = config
        self._api = _Api(config=config, api_key=api_key)
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
