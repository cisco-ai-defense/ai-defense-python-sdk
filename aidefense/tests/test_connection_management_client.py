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

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from aidefense.management.connections import ConnectionManagementClient
from aidefense.management.auth import ManagementAuth
from aidefense.management.models.connection import (
    Connection,
    Connections,
    ConnectionSortBy,
    ConnectionType,
    EditConnectionOperationType,
    ApiKeys,
    ApiKeyRequest,
    ApiKeyResponse,
    ListConnectionsRequest,
    CreateConnectionRequest,
    CreateConnectionResponse,
    UpdateConnectionRequest,
)
from aidefense.management.models.common import Paging
from aidefense.config import Config
from aidefense.exceptions import ValidationError, ApiError, SDKError


# Create a valid format dummy API key for testing
TEST_API_KEY = "0123456789" * 6 + "0123"  # 64 characters


@pytest.fixture(autouse=True)
def reset_config_singleton():
    """Reset Config singleton before each test."""
    # Reset the singleton instance
    Config._instance = None
    yield
    # Clean up after test
    Config._instance = None


@pytest.fixture
def mock_request_handler():
    """Create a mock request handler."""
    mock_handler = MagicMock()
    return mock_handler


@pytest.fixture
def connection_client(mock_request_handler):
    """Create a ConnectionManagementClient with a mock request handler."""
    client = ConnectionManagementClient(
        auth=ManagementAuth(TEST_API_KEY), request_handler=mock_request_handler
    )
    # Replace the make_request method with a mock
    client.make_request = MagicMock()
    return client


class TestConnectionManagementClient:
    """Tests for the ConnectionManagementClient."""

    def test_list_connections(self, connection_client):
        """Test listing connections."""
        # Setup mock response
        mock_response = {
            "connections": {
                "items": [
                    {
                        "connection_id": "conn-123",
                        "connection_name": "Test Connection 1",
                        "application_id": "app-123",
                        "endpoint_id": "endpoint-123",
                        "connection_status": "Connected",
                        "created_at": "2025-01-01T00:00:00Z",
                        "updated_at": "2025-01-02T00:00:00Z",
                    },
                    {
                        "connection_id": "conn-456",
                        "connection_name": "Test Connection 2",
                        "application_id": "app-456",
                        "endpoint_id": "endpoint-456",
                        "connection_status": "Disconnected",
                        "created_at": "2025-01-03T00:00:00Z",
                        "updated_at": "2025-01-04T00:00:00Z",
                    },
                ],
                "paging": {"total": 2, "count": 2, "offset": 0},
            }
        }
        connection_client.make_request.return_value = mock_response

        # Create request
        request = ListConnectionsRequest(
            limit=10,
            offset=0,
            expanded=True,
            sort_by=ConnectionSortBy.connection_name,
            order="asc",
        )

        # Call the method
        response = connection_client.list_connections(request)

        # Verify the make_request call
        connection_client.make_request.assert_called_once_with(
            "GET",
            "connections",
            params={
                "limit": 10,
                "offset": 0,
                "expanded": True,
                "sort_by": "connection_name",
                "order": "asc",
            },
        )

        # Verify the response
        assert isinstance(response, Connections)
        assert len(response.items) == 2
        assert response.items[0].connection_id == "conn-123"
        assert response.items[0].connection_name == "Test Connection 1"
        assert response.items[1].connection_id == "conn-456"
        assert response.items[1].connection_name == "Test Connection 2"
        assert response.paging.total == 2
        assert response.paging.count == 2
        assert response.paging.offset == 0

    def test_get_connection(self, connection_client):
        """Test getting a connection by ID."""
        # Setup mock response
        mock_response = {
            "connection": {
                "connection_id": "conn-123",
                "connection_name": "Test Connection",
                "application_id": "app-123",
                "endpoint_id": "endpoint-123",
                "connection_status": "Connected",
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-02T00:00:00Z",
            }
        }
        connection_client.make_request.return_value = mock_response

        # Call the method
        connection_id = "323e4567-e89b-12d3-a456-426614174333"
        response = connection_client.get_connection(connection_id, expanded=True)

        # Verify the make_request call
        connection_client.make_request.assert_called_once_with(
            "GET", f"connections/{connection_id}", params={"expanded": True}
        )

        # Verify the response
        assert isinstance(response, Connection)
        assert response.connection_id == "conn-123"
        assert response.connection_name == "Test Connection"
        assert response.application_id == "app-123"
        assert response.connection_status == "Connected"

    def test_create_connection(self, connection_client):
        """Test creating a connection."""
        # Setup mock response
        mock_response = {
            "connection_id": "123e4567-e89b-12d3-a456-426614174331",
            "key": {"key_id": "key-123", "api_key": "test-api-key-value"},
        }
        connection_client.make_request.return_value = mock_response

        # Create request
        request = CreateConnectionRequest(
            application_id="123e4567-e89b-12d3-a456-426614174000",
            connection_name="New Test Connection",
            connection_type=ConnectionType.API,
            key=ApiKeyRequest(name="Test API Key", expiry=datetime(2026, 1, 1)),
        )

        # Call the method
        response = connection_client.create_connection(request)

        # Verify the make_request call
        connection_client.make_request.assert_called_once_with(
            "POST",
            "connections",
            data={
                "application_id": "123e4567-e89b-12d3-a456-426614174000",
                "connectionName": "New Test Connection",
                "connection_type": "API",
                "key": {"name": "Test API Key", "expiry": "2026-01-01T00:00:00Z"},
            },
        )

        # Verify the response
        assert isinstance(response, CreateConnectionResponse)
        assert response.connection_id == "123e4567-e89b-12d3-a456-426614174331"
        assert response.key.key_id == "key-123"
        assert response.key.api_key == "test-api-key-value"

    def test_delete_connection(self, connection_client):
        """Test deleting a connection."""
        # Setup mock response (empty for delete)
        connection_client.make_request.return_value = {}

        # Call the method
        connection_id = "323e4567-e89b-12d3-a456-426614174333"
        response = connection_client.delete_connection(connection_id)

        # Verify the make_request call
        connection_client.make_request.assert_called_once_with(
            "DELETE", f"connections/{connection_id}"
        )

        # Verify the response
        assert response is None

    def test_get_api_keys(self, connection_client):
        """Test getting API keys for a connection."""
        # Setup mock response
        mock_response = {
            "keys": {
                "items": [
                    {
                        "id": "key-123",
                        "name": "Test API Key 1",
                        "status": "active",
                        "expiry": "2026-01-01T00:00:00Z",
                    },
                    {
                        "id": "key-456",
                        "name": "Test API Key 2",
                        "status": "revoked",
                        "expiry": "2026-02-01T00:00:00Z",
                    },
                ],
                "paging": {"total": 2, "count": 2, "offset": 0},
            }
        }
        connection_client.make_request.return_value = mock_response

        # Call the method
        connection_id = "323e4567-e89b-12d3-a456-426614174333"
        response = connection_client.get_api_keys(connection_id)

        # Verify the make_request call
        connection_client.make_request.assert_called_once_with(
            "GET", f"connections/{connection_id}/keys"
        )

        # Verify the response
        assert isinstance(response, ApiKeys)
        assert len(response.items) == 2
        assert response.items[0].id == "key-123"
        assert response.items[0].name == "Test API Key 1"
        assert response.items[1].id == "key-456"
        assert response.items[1].name == "Test API Key 2"
        assert response.paging.total == 2
        assert response.paging.count == 2
        assert response.paging.offset == 0

    def test_update_api_key_generate(self, connection_client):
        """Test generating a new API key."""
        # Setup mock response
        mock_response = {"key": {"key_id": "key-123", "api_key": "test-api-key-value"}}
        connection_client.make_request.return_value = mock_response

        # Create request
        connection_id = "323e4567-e89b-12d3-a456-426614174333"
        request = UpdateConnectionRequest(
            key_id="123",
            operation_type=EditConnectionOperationType.GENERATE_API_KEY,
            key=ApiKeyRequest(name="New API Key", expiry=datetime(2026, 1, 1)),
        )

        # Call the method
        response = connection_client.update_api_key(connection_id, request)

        # Verify the make_request call
        connection_client.make_request.assert_called_once_with(
            "POST",
            f"connections/{connection_id}/keys",
            data={
                "key_id": "123",
                "op": "GENERATE_API_KEY",
                "key": {"name": "New API Key", "expiry": "2026-01-01T00:00:00Z"},
            },
        )

        # Verify the response
        assert isinstance(response, ApiKeyResponse)
        assert response.key_id == "key-123"
        assert response.api_key == "test-api-key-value"

    def test_update_api_key_revoke(self, connection_client):
        """Test revoking an API key."""
        # Setup mock response
        mock_response = {}
        connection_client.make_request.return_value = mock_response

        # Create request
        connection_id = "323e4567-e89b-12d3-a456-426614174333"
        request = UpdateConnectionRequest(
            key_id="key-123",
            operation_type=EditConnectionOperationType.REVOKE_API_KEY,
            key=None,
        )

        # Mock the parse_obj method to avoid validation errors
        with patch(
            "aidefense.management.models.connection.ApiKeyResponse.parse_obj"
        ) as mock_parse_obj:
            mock_parse_obj.return_value = ApiKeyResponse(key_id="key-123", api_key="")

            # Call the method
            response = connection_client.update_api_key(connection_id, request)

        # Verify the make_request call
        connection_client.make_request.assert_called_once_with(
            "POST",
            f"connections/{connection_id}/keys",
            data={"op": "REVOKE_API_KEY", "key_id": "key-123"},
        )

        # Verify the response
        assert isinstance(response, ApiKeyResponse)

    def test_error_handling(self, connection_client):
        """Test error handling in the client."""
        # Setup mock to raise an exception
        connection_client.make_request.side_effect = ApiError("API Error", 400)

        # Create request
        request = ListConnectionsRequest(limit=10)

        # Verify that the exception is propagated
        with pytest.raises(ApiError) as excinfo:
            connection_client.list_connections(request)

        assert "API Error" in str(excinfo.value)

    def test_update_api_key_generate_without_key(self, connection_client):
        """Fail fast when GENERATE_API_KEY op is missing key payload."""
        req = UpdateConnectionRequest(
            operation_type=EditConnectionOperationType.GENERATE_API_KEY
        )
        with pytest.raises(ValueError) as excinfo:
            connection_client.update_api_key(
                "123e4567-e89b-12d3-a456-426614174331", req
            )
        assert "must be provided for API key generation" in str(excinfo.value)
        connection_client.make_request.assert_not_called()

    def test_update_api_key_revoke_without_key_id(self, connection_client):
        """Fail fast when REVOKE_API_KEY op is missing key_id."""
        req = UpdateConnectionRequest(
            operation_type=EditConnectionOperationType.REVOKE_API_KEY
        )
        with pytest.raises(ValueError) as excinfo:
            connection_client.update_api_key(
                "123e4567-e89b-12d3-a456-426614174331", req
            )
        assert "key_id' must be provided" in str(excinfo.value)
        connection_client.make_request.assert_not_called()
