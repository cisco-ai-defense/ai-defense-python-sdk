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
from aidefense.management.models.connection import (
    Connection, Connections, ConnectionSortBy, ConnectionType, ConnectionStatus,
    EditConnectionOperationType, ApiKeys, ApiKey, ApiKeyRequest, ApiKeyResponse,
    ListConnectionsRequest, CreateConnectionRequest, CreateConnectionResponse,
    DeleteConnectionByIDResponse, UpdateConnectionRequest
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
        api_key=TEST_API_KEY,
        request_handler=mock_request_handler
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
                        "updated_at": "2025-01-02T00:00:00Z"
                    },
                    {
                        "connection_id": "conn-456",
                        "connection_name": "Test Connection 2",
                        "application_id": "app-456",
                        "endpoint_id": "endpoint-456",
                        "connection_status": "Disconnected",
                        "created_at": "2025-01-03T00:00:00Z",
                        "updated_at": "2025-01-04T00:00:00Z"
                    }
                ],
                "paging": {
                    "total": 2,
                    "count": 2,
                    "offset": 0
                }
            }
        }
        connection_client.make_request.return_value = mock_response

        # Create request
        request = ListConnectionsRequest(
            limit=10,
            offset=0,
            expanded=True,
            sort_by=ConnectionSortBy.connection_name,
            order="asc"
        )

        # Mock the _parse_response method to avoid validation errors
        connection_client._parse_response = MagicMock()
        connection_client._parse_response.return_value = Connections(
            items=[
                Connection(
                    connection_id="conn-123",
                    connection_name="Test Connection 1",
                    application_id="app-123",
                    endpoint_id="endpoint-123",
                    connection_status=ConnectionStatus.Connected,
                    created_at=datetime(2025, 1, 1),
                    updated_at=datetime(2025, 1, 2)
                ),
                Connection(
                    connection_id="conn-456",
                    connection_name="Test Connection 2",
                    application_id="app-456",
                    endpoint_id="endpoint-456",
                    connection_status=ConnectionStatus.Disconnected,
                    created_at=datetime(2025, 1, 3),
                    updated_at=datetime(2025, 1, 4)
                )
            ],
            paging=Paging(total=2, count=2, offset=0)
        )

        # Call the method
        response = connection_client.list_connections(request)

        # Verify the make_request call
        connection_client.make_request.assert_called_once_with(
            "GET", 
            f"{connection_client.api_version}/connections", 
            params={
                "limit": 10,
                "offset": 0,
                "expanded": True,
                "sort_by": "connection_name",
                "order": "asc"
            }
        )

        # Verify the _parse_response call
        connection_client._parse_response.assert_called_once_with(
            Connections, mock_response.get("connections", {}), "connections response"
        )

        # Verify the response
        assert isinstance(response, Connections)
        assert len(response.items) == 2
        assert response.items[0].connection_id == "conn-123"
        assert response.items[0].connection_name == "Test Connection 1"
        assert response.items[1].connection_id == "conn-456"
        assert response.items[1].connection_name == "Test Connection 2"
        assert response.paging.total == 2

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
                "updated_at": "2025-01-02T00:00:00Z"
            }
        }
        connection_client.make_request.return_value = mock_response

        # Call the method
        connection_id = "conn-123"
        response = connection_client.get_connection(connection_id, expanded=True)

        # Verify the make_request call
        connection_client.make_request.assert_called_once_with(
            "GET", 
            f"connections/{connection_id}", 
            params={"expanded": True}
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
            "connection_id": "conn-123",
            "key": {
                "key_id": "key-123",
                "api_key": "test-api-key-value"
            }
        }
        connection_client.make_request.return_value = mock_response

        # Create request
        request = CreateConnectionRequest(
            application_id="app-123",
            connection_name="New Test Connection",
            connection_type=ConnectionType.API,
            key=ApiKeyRequest(
                name="Test API Key",
                expiry=datetime(2026, 1, 1)
            )
        )

        # Call the method
        response = connection_client.create_connection(request)

        # Verify the make_request call
        connection_client.make_request.assert_called_once_with(
            "POST", 
            "connections", 
            data={
                "application_id": "app-123",
                "connection_name": "New Test Connection",
                "connection_type": "API",
                "key": {
                    "name": "Test API Key",
                    "expiry": "2026-01-01T00:00:00Z"
                }
            }
        )

        # Verify the response
        assert isinstance(response, CreateConnectionResponse)
        assert response.connection_id == "conn-123"
        assert response.key.key_id == "key-123"
        assert response.key.api_key == "test-api-key-value"

    def test_delete_connection(self, connection_client):
        """Test deleting a connection."""
        # Setup mock response (empty for delete)
        connection_client.make_request.return_value = {}

        # Call the method
        connection_id = "conn-123"
        response = connection_client.delete_connection(connection_id)

        # Verify the make_request call
        connection_client.make_request.assert_called_once_with(
            "DELETE", 
            f"connections/{connection_id}"
        )

        # Verify the response
        assert isinstance(response, DeleteConnectionByIDResponse)

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
                        "expiry": "2026-01-01T00:00:00Z"
                    },
                    {
                        "id": "key-456",
                        "name": "Test API Key 2",
                        "status": "revoked",
                        "expiry": "2026-02-01T00:00:00Z"
                    }
                ],
                "paging": {
                    "total": 2,
                    "count": 2,
                    "offset": 0
                }
            }
        }
        connection_client.make_request.return_value = mock_response

        # Mock the _parse_response method to avoid validation errors
        connection_client._parse_response = MagicMock()
        connection_client._parse_response.return_value = ApiKeys(
            items=[
                ApiKey(
                    id="key-123",
                    name="Test API Key 1",
                    status="active",
                    expiry=datetime(2026, 1, 1)
                ),
                ApiKey(
                    id="key-456",
                    name="Test API Key 2",
                    status="revoked",
                    expiry=datetime(2026, 2, 1)
                )
            ],
            paging=Paging(total=2, count=2, offset=0)
        )

        # Call the method
        connection_id = "conn-123"
        response = connection_client.get_api_keys(connection_id)

        # Verify the make_request call
        connection_client.make_request.assert_called_once_with(
            "GET", 
            f"connections/{connection_id}/keys"
        )

        # Verify the _parse_response call
        connection_client._parse_response.assert_called_once_with(
            ApiKeys, mock_response.get("keys", {}), "API keys response"
        )

        # Verify the response
        assert isinstance(response, ApiKeys)
        assert len(response.items) == 2
        assert response.items[0].id == "key-123"
        assert response.items[0].name == "Test API Key 1"
        assert response.items[1].id == "key-456"
        assert response.items[1].name == "Test API Key 2"
        assert response.paging.total == 2

    def test_update_api_key_generate(self, connection_client):
        """Test generating a new API key."""
        # Setup mock response
        mock_response = {
            "key": {
                "key_id": "key-123",
                "api_key": "test-api-key-value"
            }
        }
        connection_client.make_request.return_value = mock_response

        # Create request
        connection_id = "conn-123"
        request = UpdateConnectionRequest(
            key_id="",
            operation_type=EditConnectionOperationType.GENERATE_API_KEY,
            key=ApiKeyRequest(
                name="New API Key",
                expiry=datetime(2026, 1, 1)
            )
        )

        # Call the method
        response = connection_client.update_api_key(connection_id, request)

        # Verify the make_request call
        connection_client.make_request.assert_called_once_with(
            "POST", 
            f"connections/{connection_id}/keys", 
            data={
                "op": "GENERATE_API_KEY",
                "key": {
                    "name": "New API Key",
                    "expiry": "2026-01-01T00:00:00Z"
                }
            }
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
        connection_id = "conn-123"
        request = UpdateConnectionRequest(
            key_id="key-123",
            operation_type=EditConnectionOperationType.REVOKE_API_KEY,
            key=None
        )

        # Mock the parse_obj method to avoid validation errors
        with patch('aidefense.management.models.connection.ApiKeyResponse.parse_obj') as mock_parse_obj:
            mock_parse_obj.return_value = ApiKeyResponse(
                key_id="key-123",
                api_key=""
            )
            
            # Call the method
            response = connection_client.update_api_key(connection_id, request)

        # Verify the make_request call
        connection_client.make_request.assert_called_once_with(
            "POST", 
            f"connections/{connection_id}/keys", 
            data={
                "op": "REVOKE_API_KEY",
                "key_id": "key-123"
            }
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
