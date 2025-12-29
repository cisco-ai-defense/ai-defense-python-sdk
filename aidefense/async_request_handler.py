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

from typing import Dict, Optional

import aiohttp
import asyncio

from .config import AsyncConfig
from .request_handler import BaseRequestHandler
from .runtime.auth import AsyncAuth


class AsyncRequestHandler(BaseRequestHandler):
    """Async request handler for interacting with APIs."""

    def __init__(self, config: AsyncConfig):
        super().__init__(config)
        self._session = None
        self._timeout = aiohttp.ClientTimeout(total=config.timeout)
        self._session_lock = asyncio.Lock()
        self._connector = config.connection_pool
        self._retry_config = config.retry_config

    async def close(self):
        """Clean up resources."""
        if self._session:
            await self._session.close()
        if self._connector:
            await self._connector.close()

    async def ensure_session(self):
        """Ensure session is created and configured."""
        # Acquire lock only if session is not already created
        if self._session is not None and not self._session.closed:
            return

        async with self._session_lock:
            # Double check if session is still not created to avoid race condition
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession(
                    connector=self._connector,
                    timeout=self._timeout,
                    headers={
                        "User-Agent": self.USER_AGENT,
                        "Content-Type": "application/json",
                    },
                )

    async def request(
        self,
        method: str,
        url: str,
        auth: AsyncAuth,
        request_id: str = None,
        headers: Dict = None,
        params: Dict = None,
        json_data: Dict = None,
        timeout: int = None,
    ) -> Dict:
        """
        Make an HTTP request to the specified URL.

        Args:
            method (str): HTTP method, e.g. GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS.
            url (str): URL of the request.
            auth (AsyncAuth): Authentication handler.
            request_id (str, optional): Unique identifier for the request (usually a UUID) to enable request tracing.
            headers (dict, optional): HTTP request headers.
            params (dict, optional): Query parameters.
            json_data (dict, optional): Request body as a JSON-serializable dictionary.
            timeout (int, optional): Request timeout in seconds.

        Returns:
            Dict: The JSON response from the API.

        Raises:
            SDKError: For authentication errors.
            ValidationError: For bad requests.
            ApiError: For other API errors.
        """
        self.config.logger.debug(
            f"request called | method: {method}, url: {url}, request_id: {request_id}, headers: {headers}, json_data: {json_data}"
        )

        if not self._session:
            raise RuntimeError("Session not initialized. Use 'async with AsyncRequestHandler(config)'")

        try:
            self._validate_method(method)
            self._validate_url(url)

            request_headers = self._session.headers
            if headers:
                request_headers.update(headers)

            request_id = request_id or self.get_request_id()
            request_headers[self.REQUEST_ID_HEADER] = request_id

            timeout_instance = self._timeout
            # bool is a subclass of int in Python
            if isinstance(timeout, int) and not isinstance(timeout, bool):
                timeout_instance = aiohttp.ClientTimeout(total=timeout)

            async with self._session.request(
                method=method,
                url=url,
                middlewares=(auth,),
                headers=headers,
                params=params,
                json=json_data,
                timeout=timeout_instance,
            ) as response:
                if response.status >= 400:
                    return await self._handle_error_response(response, request_id)

                return await response.json()

        except aiohttp.ClientError as e:
            self.config.logger.error(f"Async request failed: {e}")
            raise
        except Exception as e:
            self.config.logger.error(f"Unexpected error in async request: {e}")
            raise

    async def _handle_error_response(self, response: aiohttp.ClientResponse, request_id: Optional[str] = None):
        """
        Handle error responses from the API.

        Args:
            response (aiohttp.ClientResponse): The HTTP response object.
            request_id (str, optional): The unique request ID for tracing the failed API call.

        Raises:
            SDKError: For authentication errors.
            ValidationError: For bad requests.
            ApiError: For other API errors.
        """
        response_text = await response.text()
        self.config.logger.debug(
            f"_handle_error_response called | status_code: {response.status}, response: {response_text}"
        )
        try:
            error_data = await response.json()
        except (ValueError, aiohttp.ContentTypeError):
            error_data = {"message": response_text or "Unknown error"}

        error_message = error_data.get("message", "Unknown error")
        self._raise_appropriate_exception(response.status, error_message, request_id)
