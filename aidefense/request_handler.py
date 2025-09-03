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

import requests
import uuid
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from requests.auth import AuthBase

from .version import version
from .config import Config
from .exceptions import SDKError, ValidationError, ApiError

REQUEST_ID_HEADER = "x-aidefense-request-id"


class BaseRequestHandler(ABC):
    """
    Abstract parent for all request handlers (sync, async, http2, etc).
    Defines the interface and shared logic for request handlers.
    """

    USER_AGENT = f"Cisco-AI-Defense-Python-SDK/{version}"
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
    Synchronous HTTP/1.1 request handler using requests.Session.
    """

    def __init__(self, config: Config):
        super().__init__(config)
        self._session = requests.Session()
        self._session.mount("https://", config.connection_pool)
        self._session.headers.update(
            {"User-Agent": self.USER_AGENT, "Content-Type": "application/json"}
        )

    def request(
        self,
        method: str,
        url: str,
        auth: AuthBase,
        request_id: str = None,
        headers: dict = None,
        json_data: dict = None,
        timeout: int = None,
    ) -> dict:
        """
        Make an HTTP request to the specified URL.

        Args:
            method (str): HTTP method, e.g. GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS.
            url (str): URL of the request.
            auth (AuthBase): Authentication handler.
            request_id (str, optional): Unique identifier for the request (usually a UUID) to enable request tracing.
            headers (dict, optional): HTTP request headers.
            json_data (dict, optional): Request body as a JSON-serializable dictionary.
            timeout (int, optional): Request timeout in seconds.

        Returns:
            dict: JSON-decoded response body.

        Raises:
            ValueError: If the HTTP method is invalid.
            requests.RequestException: If the request fails.
            SDKError: If the request is not successful.
        """
        if method not in self.VALID_HTTP_METHODS:
            raise ValueError(f"Invalid HTTP method: {method}")
        headers = headers or {}
        headers.setdefault("User-Agent", self.USER_AGENT)
        headers.setdefault("Content-Type", "application/json")
        if request_id:
            headers[REQUEST_ID_HEADER] = request_id
        try:
            if auth:
                prepared_request = auth(requests.Request(url=url).prepare())
                headers.update(prepared_request.headers)
            response = self._session.request(
                method=method,
                url=url,
                headers=headers,
                json=json_data,
                timeout=timeout or self.config.timeout,
            )
            if response.status_code >= 400:
                return self._handle_error_response(response, request_id)
            return response.json()
        except requests.RequestException as e:
            self.config.logger.error(f"Request failed: {e}")
            raise

    def _handle_error_response(
        self, response: requests.Response, request_id: str = None
    ) -> dict:
        self.config.logger.debug(
            f"_handle_error_response called | status_code: {response.status_code}, response: {response.text}"
        )
        try:
            error_data = response.json()
        except ValueError:
            error_data = {"message": response.text or "Unknown error"}
        error_message = error_data.get("message", "Unknown error")
        if response.status_code == 401:
            raise SDKError(
                f"Authentication error: {error_message}", response.status_code
            )
        elif response.status_code == 400:
            raise ValidationError(f"Bad request: {error_message}", response.status_code)
        else:
            raise ApiError(
                f"API error {response.status_code}: {error_message}",
                response.status_code,
                request_id=request_id,
            )
