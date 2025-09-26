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

from typing import Optional, Dict

from .auth import ManagementAuth
from .base_client import BaseClient
from .models.connection import (
    Connection,
    Connections,
    EditConnectionOperationType,
    ApiKeys,
    ListConnectionsRequest,
    CreateConnectionRequest,
    CreateConnectionResponse,
    UpdateConnectionRequest,
    ApiKeyResponse,
)
from ..config import Config
from .routes import CONNECTIONS, connection_by_id, connection_keys


class ConnectionManagementClient(BaseClient):
    """
    Client for managing connections in the AI Defense Management API.

    Provides methods for creating, retrieving, updating, and deleting
    connections in the AI Defense Management API.
    """

    def __init__(
        self,
        auth: ManagementAuth,
        config: Optional[Config] = None,
        request_handler=None,
    ):
        """
        Initialize the ConnectionManagementClient.

        Args:
            auth (ManagementAuth): Your AI Defense Management API authentication object.
            config (Config, optional): SDK configuration for endpoints, logging, retries, etc.
                Defaults to the singleton Config if not provided.
            request_handler: Request handler for making API requests
        """
        super().__init__(auth, config, request_handler)

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
        params = request.to_params()

        response = self.make_request("GET", CONNECTIONS, params=params)
        connections = self._parse_response(
            Connections, response.get("connections", {}), "list connections response"
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
        # Validate referenced IDs
        self._ensure_uuid(request.application_id, "application_id")
        data = request.to_body_dict()

        response = self.make_request("POST", CONNECTIONS, data=data)

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
        # Validate IDs
        self._ensure_uuid(connection_id, "connection_id")
        params = {"expanded": expanded} if expanded is not None else None
        response = self.make_request(
            "GET", connection_by_id(connection_id), params=params
        )
        connection = self._parse_response(
            Connection, response.get("connection", {}), "get connection response"
        )
        return connection

    def delete_connection(self, connection_id: str) -> None:
        """
        Delete a connection.

        Args:
            connection_id (str): ID of the connection to delete

        Returns:
            None

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                connection_id = "323e4567-e89b-12d3-a456-426614174333"
                response = client.connections.delete_connection(connection_id)
        """
        # Validate IDs
        self._ensure_uuid(connection_id, "connection_id")
        self.make_request("DELETE", connection_by_id(connection_id))
        return None

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
        # Validate IDs
        self._ensure_uuid(connection_id, "connection_id")
        response = self.make_request("GET", connection_keys(connection_id))
        keys = self._parse_response(
            ApiKeys, response.get("keys", {}), "list api keys response"
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
        # Validate IDs
        self._ensure_uuid(connection_id, "connection_id")
        data = request.to_body_dict(patch=True)
        if not data:
            raise ValueError("No fields to update in UpdateConnectionRequest")

        # Fail-fast: validate required fields based on operation type
        op = data.get("op")
        if op in (
            EditConnectionOperationType.GENERATE_API_KEY.value,
            EditConnectionOperationType.REGENERATE_API_KEY.value,
        ):
            if "key" not in data or data["key"] is None:
                raise ValueError(
                    "'key' must be provided for API key generation/regeneration"
                )
        elif op == EditConnectionOperationType.REVOKE_API_KEY.value:
            if not data.get("key_id"):
                raise ValueError(
                    "'key_id' must be provided for API key revoke operation"
                )

        response = self.make_request("POST", connection_keys(connection_id), data=data)
        # For revoke, API may return empty body. Synthesize a minimal response using input key_id.
        if op == EditConnectionOperationType.REVOKE_API_KEY.value:
            return ApiKeyResponse(key_id=data.get("key_id", ""), api_key="")
        return self._parse_response(
            ApiKeyResponse, response.get("key"), "update api key response"
        )
