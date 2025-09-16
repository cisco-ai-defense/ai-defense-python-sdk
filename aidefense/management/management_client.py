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

from typing import Optional, Dict, Any
import threading

from ..config import Config
from .base_client import BaseClient
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
        api_key (str): The API key used for management API authentication.
        config (Config): The runtime configuration object.
        API_BASE_PATH (str): Base path for the management API.
    """

    # Base URL for the management API
    API_BASE_PATH = "/api/ai-defense/v1"

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

        # Initialize resource clients lazily with thread safety
        self._applications_client = None
        self._connections_client = None
        self._policies_client = None
        self._events_client = None

        # Locks for thread-safe lazy initialization
        self._applications_lock = threading.RLock()
        self._connections_lock = threading.RLock()
        self._policies_lock = threading.RLock()
        self._events_lock = threading.RLock()

        self.config = config or Config()
        self.api_key = api_key
        self._request_handler = RequestHandler(self.config)

    @property
    def applications(self):
        """
        Get the applications client.

        Returns:
            ApplicationManagementClient: The applications client.
        """
        if self._applications_client is None:
            with self._applications_lock:
                if self._applications_client is None:
                    # Import here to avoid circular imports
                    from .applications import ApplicationManagementClient

                    self._applications_client = ApplicationManagementClient(
                        api_key=self.api_key,
                        config=self.config,
                        request_handler=self._request_handler,
                    )
        return self._applications_client

    @property
    def connections(self):
        """
        Get the connections client.

        Returns:
            ConnectionManagementClient: The connections client.
        """
        if self._connections_client is None:
            with self._connections_lock:
                if self._connections_client is None:
                    # Import here to avoid circular imports
                    from .connections import ConnectionManagementClient

                    self._connections_client = ConnectionManagementClient(
                        api_key=self.api_key,
                        config=self.config,
                        request_handler=self._request_handler,
                    )
        return self._connections_client

    @property
    def policies(self):
        """
        Get the policies client.

        Returns:
            PolicyManagementClient: The policies client.
        """
        if self._policies_client is None:
            with self._policies_lock:
                if self._policies_client is None:
                    # Import here to avoid circular imports
                    from .policies import PolicyManagementClient

                    self._policies_client = PolicyManagementClient(
                        api_key=self.api_key,
                        config=self.config,
                        request_handler=self._request_handler,
                    )
        return self._policies_client

    @property
    def events(self):
        """
        Get the events client.

        Returns:
            EventManagementClient: The events client.
        """
        if self._events_client is None:
            with self._events_lock:
                if self._events_client is None:
                    # Import here to avoid circular imports
                    from .events import EventManagementClient

                    self._events_client = EventManagementClient(
                        api_key=self.api_key,
                        config=self.config,
                        request_handler=self._request_handler,
                    )
        return self._events_client
