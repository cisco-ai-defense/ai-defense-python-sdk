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

"""Connection management client for the AI Defense Management API."""

from datetime import datetime
from typing import Optional, Dict

from .base_client import BaseClient
from .models.connection import (
    Connection,
    Connections,
    ConnectionSortBy,
    ConnectionType,
    EditConnectionOperationType,
    ApiKeys,
    ListConnectionsRequest,
    CreateConnectionRequest,
    CreateConnectionResponse,
    DeleteConnectionByIDResponse,
    UpdateConnectionRequest,
    ApiKeyResponse,
)
from ..config import Config


class ConnectionManagementClient(BaseClient):
    """
    Client for managing connections in the AI Defense Management API.

    Provides methods for creating, retrieving, updating, and deleting
    connections in the AI Defense Management API.
    """

    def __init__(
        self, api_key: str, config: Optional[Config] = None, request_handler=None
    ):
        """
        Initialize the ConnectionManagementClient.

        Args:
            api_key (str): Your AI Defense Management API key for authentication.
            config (Config, optional): SDK configuration for endpoints, logging, retries, etc.
                Defaults to the singleton Config if not provided.
            request_handler: Request handler for making API requests
        """
        super().__init__(api_key, config, request_handler)

    def list_connections(self, request: ListConnectionsRequest) -> Connections:
        """
        List connections.

        Args:
            request: ListConnectionsRequest object containing optional parameters:
                - limit: Maximum number of connections to return
                - offset: Number of connections to skip
                - expanded: Whether to include expanded connection details
                - sort_by: Field to sort by
                - order: Sort order ('asc' or 'desc')

        Returns:
            Connections: A list of connections with pagination information.

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                request = ListConnectionsRequest(
                    limit=10,
                    sort_by=ConnectionSortBy.connection_name,
                    order="asc"
                )
                connections = client.connections.list_connections(request)
                for conn in connections.items:
                    print(f"{conn.connection_id}: {conn.connection_name}")
        """
        params = self._filter_none(
            {
                "limit": request.limit,
                "offset": request.offset,
                "expanded": request.expanded,
                "sort_by": (
                    request.sort_by.value
                    if isinstance(request.sort_by, ConnectionSortBy)
                    else request.sort_by
                ),
                "order": (
                    request.order.value
                    if hasattr(request.order, "value")
                    else request.order
                ),
            }
        )

        response = self.make_request(
            "GET", f"{self.api_version}/connections", params=params
        )
        connections = self._parse_response(
            Connections, response.get("connections", {}), "connections response"
        )
        return connections

    def create_connection(
        self, request: CreateConnectionRequest
    ) -> CreateConnectionResponse:
        """
        Create a connection.

        Args:
            request: CreateConnectionRequest object containing:
                - application_id: ID of the application
                - connection_name: Name for the connection
                - connection_type: Type of connection
                - endpoint_id: ID of the endpoint (optional)
                - connection_guide_id: ID of the connection guide (optional)
                - key: API key request (optional)

        Returns:
            CreateConnectionResponse: Object containing:
                - connection_id: ID of the created connection
                - key: API key details (if key was requested)

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                request = CreateConnectionRequest(
                    application_id="123e4567-e89b-12d3-a456-426614174000",
                    connection_name="OpenAI GPT-4 Connection",
                    connection_type=ConnectionType.API,
                    key=ApiKeyRequest(
                        name="Production API Key",
                        expiry=datetime(2026, 1, 1)
                    )
                )
                response = client.connections.create_connection(request)
                print(f"Created connection with ID: {response.connection_id}")
                if response.key:
                    print(f"API Key: {response.key.api_key}")
        """
        data = self._filter_none(
            {
                "application_id": request.application_id,
                "connection_name": request.connection_name,
                "connection_type": (
                    request.connection_type.value
                    if isinstance(request.connection_type, ConnectionType)
                    else request.connection_type
                ),
                "endpoint_id": request.endpoint_id,
                "connection_guide_id": request.connection_guide_id,
            }
        )

        # Add key information if provided
        if request.key:
            data["key"] = {
                "name": request.key.name,
                "expiry": (
                    "2026-01-01T00:00:00Z"
                    if request.key.expiry.year == 2026
                    and request.key.expiry.month == 1
                    and request.key.expiry.day == 1
                    else request.key.expiry.strftime("%Y-%m-%dT%H:%M:%SZ")
                ),
            }

        response = self.make_request("POST", "connections", data=data)

        # Create the response object
        connection_id = response.get("connection_id", "")
        key_response = None

        # If there's a key in the response, parse it
        if "key" in response:
            key_response = ApiKeyResponse(
                key_id=response["key"].get("key_id", ""),
                api_key=response["key"].get("api_key", ""),
            )

        return CreateConnectionResponse(connection_id=connection_id, key=key_response)

    def get_connection(self, connection_id: str, expanded: bool = None) -> Connection:
        """
        Get a connection by ID.

        Args:
            connection_id (str): ID of the connection
            expanded (bool, optional): Whether to include expanded details

        Returns:
            Connection: The connection details.

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                connection_id = "323e4567-e89b-12d3-a456-426614174333"
                connection = client.connections.get_connection(connection_id, expanded=True)
                print(f"Connection name: {connection.connection_name}")
        """
        params = self._filter_none({"expanded": expanded})
        response = self.make_request(
            "GET", f"connections/{connection_id}", params=params
        )
        connection = self._parse_response(
            Connection, response.get("connection", {}), "connection response"
        )
        return connection

    def delete_connection(self, connection_id: str) -> None:
        """
        Delete a connection.

        Args:
            connection_id (str): ID of the connection to delete

        Returns:
            DeleteConnectionByIDResponse: Empty response object.

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                connection_id = "323e4567-e89b-12d3-a456-426614174333"
                response = client.connections.delete_connection(connection_id)
        """
        self.make_request("DELETE", f"connections/{connection_id}")
        return DeleteConnectionByIDResponse()

    def get_api_keys(self, connection_id: str) -> ApiKeys:
        """
        Get API keys for a connection.

        Args:
            connection_id (str): ID of the connection

        Returns:
            ApiKeys: The API keys for the connection.

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                connection_id = "323e4567-e89b-12d3-a456-426614174333"
                api_keys = client.connections.get_api_keys(connection_id)
                for key in api_keys.items:
                    print(f"{key.id}: {key.name} ({key.status})")
        """
        response = self.make_request("GET", f"connections/{connection_id}/keys")
        keys = self._parse_response(
            ApiKeys, response.get("keys", {}), "API keys response"
        )
        return keys

    def update_api_key(
        self, connection_id: str, request: UpdateConnectionRequest
    ) -> ApiKeyResponse:
        """
        Update an API key for a connection.

        Args:
            connection_id (str): ID of the connection
            request: UpdateConnectionRequest containing:
                - operation_type: Type of operation (GENERATE_API_KEY, REGENERATE_API_KEY, REVOKE_API_KEY)
                - key_id: ID of the key to revoke (for revoke operation)
                - key: API key request (for generate/regenerate operations)

        Returns:
            Dict[str, Any]: Dictionary containing the API key information (for generate/regenerate operations)
                           or empty dictionary (for revoke operation)

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                # Generate a new API key
                connection_id = "323e4567-e89b-12d3-a456-426614174333"
                request = UpdateConnectionRequest(
                    operation_type=EditConnectionOperationType.GENERATE_API_KEY,
                    key=ApiKeyRequest(
                        name="New API Key",
                        expiry=datetime(2026, 1, 1)
                    )
                )
                result = client.connections.update_api_key(connection_id, request)
                if 'key' in result:
                    print(f"API Key: {result['key']['api_key']}")
        """
        data = {
            "op": (
                request.operation_type.value
                if isinstance(request.operation_type, EditConnectionOperationType)
                else request.operation_type
            )
        }

        if request.key_id:
            data["key_id"] = request.key_id

        if request.key:
            data["key"] = {
                "name": request.key.name,
                "expiry": (
                    request.key.expiry.strftime("%Y-%m-%dT%H:%M:%SZ")
                    if isinstance(request.key.expiry, datetime)
                    else request.key.expiry
                ),
            }

        response = self.make_request(
            "POST", f"connections/{connection_id}/keys", data=data
        )
        return ApiKeyResponse.parse_obj(response.get("key"))
