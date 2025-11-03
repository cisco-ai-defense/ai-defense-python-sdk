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

"""Base client implementation for interacting with APIs."""
from enum import Enum

import requests
import uuid
import platform
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from requests.auth import AuthBase

from .version import version
from .config import Config
from .exceptions import SDKError, ValidationError, ApiError

REQUEST_ID_HEADER = "x-aidefense-request-id"


class HttpMethod(str, Enum):
    GET = "GET"
    PUT = "PUT"
    POST = "POST"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class BaseRequestHandler(ABC):
    """
    Abstract parent for all request handlers (sync, async, http2, etc).
    Defines the interface and shared logic for request handlers.
    """

    USER_AGENT = f"Cisco-AI-Defense-Python-SDK/{version} (Python {platform.python_version()})"
    VALID_HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}

    def __init__(self, config: Config):
        self.config = config

    def get_request_id(self) -> str:
        request_id = str(uuid.uuid4())
        self.config.logger.debug(f"get_request_id called | returning: {request_id}")
        return request_id

    @abstractmethod
    def request(self, *args, **kwargs):
        pass


class RequestHandler(BaseRequestHandler):
    """
    Request handler for all API interactions.

    Provides methods for making HTTP requests, handling errors, and managing
    session configurations.

    Attributes:
        USER_AGENT (str): The user agent string for the SDK.
        config (Config): The configuration object for the client.
        _session (requests.Session): The HTTP session used for making requests.
    """

    def __init__(self, config: Config):
        super().__init__(config)
        self._session = requests.Session()
        self._session.mount("https://", config.connection_pool)
        self._session.headers.update({"User-Agent": self.USER_AGENT, "Content-Type": "application/json"})

    def request(
        self,
        method: str,
        url: str,
        auth: AuthBase,
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
            auth (AuthBase): Authentication handler.
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
        try:
            if method not in self.VALID_HTTP_METHODS:
                raise ValidationError(f"Invalid HTTP method: {method}")

            if not url or not url.startswith(("http://", "https://")):
                raise ValidationError(f"Invalid URL: {url}")

            request_headers = dict(self._session.headers)

            # Update with any custom headers
            if headers:
                request_headers.update(headers)

            request_id = request_id or self.get_request_id()
            request_headers[REQUEST_ID_HEADER] = request_id

            if auth:
                request = requests.Request(
                    method=method,
                    url=url,
                    headers=request_headers,
                    params=params,
                    json=json_data,
                )
                prepared_request = auth(request.prepare())
                request_headers.update(prepared_request.headers)

            response = self._session.request(
                method=method,
                url=url,
                headers=request_headers,
                params=params,
                json=json_data,
                timeout=timeout or self.config.timeout,
            )

            if response.status_code >= 400:
                return self._handle_error_response(response, request_id)

            return response.json()

        except requests.RequestException as e:
            self.config.logger.error(f"Request failed: {e}")
            raise

    def _handle_error_response(self, response: requests.Response, request_id: str = None) -> Dict:
        """Handle error responses from the API.

        Args:
            response (requests.Response): The HTTP response object.
            request_id (str, optional): The unique request ID for tracing the failed API call.

        Returns:
            Dict: The parsed error data.

        Raises:
            SDKError: For authentication errors.
            ValidationError: For bad requests.
            ApiError: For other API errors.
        """
        self.config.logger.debug(
            f"_handle_error_response called | status_code: {response.status_code}, response: {response.text}"
        )
        try:
            error_data = response.json()
        except ValueError:
            error_data = {"message": response.text or "Unknown error"}
        error_message = error_data.get("message", "Unknown error")
        if response.status_code == 401:
            raise SDKError(f"Authentication error: {error_message}", response.status_code)
        elif response.status_code == 400:
            raise ValidationError(f"Bad request: {error_message}", response.status_code)
        else:
            raise ApiError(
                f"API error {response.status_code}: {error_message}",
                response.status_code,
                request_id=request_id,
            )
