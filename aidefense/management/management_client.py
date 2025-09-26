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

"""Management client for the AI Defense Management API."""

from typing import Optional

from .auth import ManagementAuth
from .applications import ApplicationManagementClient
from .connections import ConnectionManagementClient
from .policies import PolicyManagementClient
from .events import EventManagementClient
from ..config import Config
from ..request_handler import RequestHandler


class ManagementClient:
    """
    Client for the AI Defense Management API.

    This client provides access to all management API functionality through resource-specific clients.
    It uses lazy initialization to create the resource clients only when they are first accessed.
    It creates a shared RequestHandler that is used by all resource clients to ensure
    proper connection pooling.

    Args:
        api_key (str, optional): Your AI Defense Management API key for authentication.
        config (Config, optional): SDK configuration for endpoints, logging, retries, etc.
            If not provided, a default singleton Config is used.

    Attributes:
        config (Config): The runtime configuration object.
    """

    def __init__(
        self,
        api_key: str,
        config: Optional[Config] = None,
    ):
        """
        Initialize the ManagementClient.

        Args:
            api_key (str, optional): Your AI Defense Management API key for authentication.
            config (Config, optional): SDK configuration for endpoints, logging, retries, etc.
                If not provided, a default singleton Config is used.
        """
        if not api_key or not isinstance(api_key, str) or api_key.strip() == "":
            raise ValueError("API key is required")

        self._auth = ManagementAuth(api_key)

        self.config = config or Config()
        self._request_handler = RequestHandler(self.config)

        # Create resource clients with shared handler and config
        self._applications_client = ApplicationManagementClient(
            self._auth, self.config, request_handler=self._request_handler
        )
        self._connections_client = ConnectionManagementClient(
            self._auth, self.config, request_handler=self._request_handler
        )
        self._policies_client = PolicyManagementClient(
            self._auth, self.config, request_handler=self._request_handler
        )
        self._events_client = EventManagementClient(
            self._auth, self.config, request_handler=self._request_handler
        )

    @property
    def applications(self):
        """
        Get the application client.

        Returns:
            ApplicationManagementClient: The application client.
        """
        return self._applications_client

    @property
    def connections(self):
        """
        Get the connection client.

        Returns:
            ConnectionManagementClient: The connection client.
        """
        return self._connections_client

    @property
    def policies(self):
        """
        Get the policies client.

        Returns:
            PolicyManagementClient: The policies client.
        """
        return self._policies_client

    @property
    def events(self):
        """
        Get the events client.

        Returns:
            EventManagementClient: The events client.
        """
        return self._events_client

    @property
    def api_key(self) -> str:
        """Expose the API key for compatibility with existing tests."""
        return self._auth.api_key
