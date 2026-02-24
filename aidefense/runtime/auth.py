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

from aiohttp import ClientHandlerType, ClientRequest, ClientResponse
from requests.auth import AuthBase


class BaseAuth:
    """
    Base authentication class for AI Defense API requests.

    Provides common authentication functionality including API key storage,
    validation, and the standard auth header name.

    Attributes:
        AUTH_HEADER (str): The HTTP header name for the API key.
        token (str): The API key token.
    """

    AUTH_HEADER = "X-Cisco-AI-Defense-API-Key"

    def __init__(self, token: str):
        """
        Initialize the authentication handler.

        Args:
            token (str): The API key for authentication. Must be a 64-character string.

        Raises:
            ValueError: If the token format is invalid.
        """
        self.token = token
        self.validate()

    def validate(self):
        """Validate the API key format."""
        if not self.token or not isinstance(self.token, str) or len(self.token) != 64:
            raise ValueError("Invalid API key format")

        return True


class RuntimeAuth(BaseAuth, AuthBase):
    """Custom authentication class for runtime authentication."""

    def __call__(self, request):
        """
        Add authentication header to the request.

        Args:
            request: The HTTP request object to authenticate.

        Returns:
            The request object with the authentication header added.
        """
        request.headers[self.AUTH_HEADER] = self.token
        return request


class AsyncAuth(BaseAuth):
    """Custom authentication class for async runtime authentication."""

    async def __call__(self, request: ClientRequest, handler: ClientHandlerType) -> ClientResponse:
        """
        Async middleware that adds authentication header to the request.

        This method is called by aiohttp's client middleware system before
        each request is sent.

        Args:
            request (ClientRequest): The aiohttp client request object.
            handler (ClientHandlerType): The next handler in the middleware chain.

        Returns:
            ClientResponse: The response from the API after the request is processed.
        """
        request.headers[self.AUTH_HEADER] = self.token
        return await handler(request)
