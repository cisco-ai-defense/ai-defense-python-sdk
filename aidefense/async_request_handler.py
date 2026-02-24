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

from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    RetryCallState,
    wait_random_exponential,
)

from .config import AsyncConfig
from .exceptions import ApiError
from .request_handler import BaseRequestHandler
from .runtime.auth import AsyncAuth


class AsyncRequestHandler(BaseRequestHandler):
    """Async request handler for interacting with APIs."""

    def __init__(self, config: AsyncConfig):
        """
        Initialize the async request handler.

        Args:
            config (AsyncConfig): Async configuration object containing timeout,
                connection pool, retry settings, and other HTTP client options.
        """
        super().__init__(config)
        self._session = None
        self._timeout = aiohttp.ClientTimeout(total=config.timeout)
        self._session_lock = asyncio.Lock()
        self._connector = config.connection_pool
        self._retry_config = config.retry_config
        self._apply_retry_decorator()

    async def close(self):
        """Clean up resources."""
        if self._session and not self._session.closed:
            await self._session.close()
        # Note: We don't close the connector here because it's owned by AsyncConfig (singleton)
        # and may be shared across multiple handlers. The connector will be cleaned up when
        # the process exits or when AsyncConfig is explicitly cleaned up.

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
                    # connector_owner=False ensures the session doesn't close the connector
                    # when session.close() is called. The connector is owned by AsyncConfig
                    # and may be shared across multiple handlers/clients.
                    connector_owner=False,
                    timeout=self._timeout,
                    headers={
                        "User-Agent": self.USER_AGENT,
                        "Content-Type": "application/json",
                    },
                )

    def _apply_retry_decorator(self):
        """Apply tenacity retry decorator."""

        max_tries = self._retry_config.get("total") + 1
        backoff_factor = self._retry_config.get("backoff_factor")

        self.request = retry(
            stop=stop_after_attempt(max_tries),
            wait=wait_random_exponential(multiplier=backoff_factor, min=backoff_factor, max=60),
            retry=retry_if_exception(self._should_retry_exception),
            before_sleep=self._log_retry_attempt,
            reraise=True,
        )(self.request)

    def _should_retry_exception(self, exception):
        """Determines whether to give up retrying."""
        # Retry asyncio timeout errors
        if isinstance(exception, asyncio.TimeoutError):
            return True

        # Retry network/timeout errors (but not HTTP status errors)
        if isinstance(exception, aiohttp.ClientError):
            # HTTP errors are handled as ApiError
            if isinstance(exception, aiohttp.ClientResponseError):
                return False

            return True

        if isinstance(exception, ApiError):
            return exception.status_code in self._retry_config.get("status_forcelist")

        # Don't retry ValidationError, SDKError, or other exceptions
        return False

    def _log_retry_attempt(self, retry_state: RetryCallState) -> None:
        """Logs retry attempt."""
        self.config.logger.info(f"Retry state: {retry_state.__dict__}, Retry attempt: {retry_state.attempt_number}")


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

        if not self._session or self._session.closed:
            raise RuntimeError(
                "Session not initialized. Use 'async with AsyncChatInspectionClient(...) as client' "
                "or call ensure_session() before request()."
            )

        try:
            self._validate_method(method)
            self._validate_url(url)

            # Make a copy of the session headers to avoid modifying the original headers
            request_headers = dict(self._session.headers)
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
                headers=request_headers,
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
