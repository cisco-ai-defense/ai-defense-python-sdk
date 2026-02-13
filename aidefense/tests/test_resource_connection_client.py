# Copyright 2026 Cisco Systems, Inc. and its affiliates
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
from unittest.mock import MagicMock

from aidefense.mcpscan import ResourceConnectionClient
from aidefense.mcpscan.models import (
    ResourceConnectionType,
    CreateResourceConnectionRequest,
    CreateResourceConnectionResponse,
    FilterResourceConnectionsRequest,
)
from aidefense.config import Config
from aidefense.exceptions import ApiError


# Create a valid format dummy API key for testing
TEST_API_KEY = "0123456789" * 6 + "0123"  # 64 characters


@pytest.fixture(autouse=True)
def reset_config_singleton():
    """Reset Config singleton before each test."""
    Config._instance = None
    yield
    Config._instance = None


@pytest.fixture
def mock_request_handler():
    """Create a mock request handler."""
    return MagicMock()


@pytest.fixture
def resource_client(mock_request_handler):
    """Create a ResourceConnectionClient with a mock request handler."""
    client = ResourceConnectionClient(
        api_key=TEST_API_KEY, request_handler=mock_request_handler
    )
    client.make_request = MagicMock()
    return client


class TestResourceConnectionClient:
    """Tests for the ResourceConnectionClient."""

    def test_client_initialization(self):
        """Test ResourceConnectionClient can be instantiated."""
        client = ResourceConnectionClient(api_key=TEST_API_KEY)
        assert client is not None

    def test_create_connection_empty_resources(self, resource_client):
        """Test creating a resource connection with empty resource list."""
        mock_response = {
            "connection_id": "conn-empty-789"
        }
        resource_client.make_request.return_value = mock_response

        request = CreateResourceConnectionRequest(
            connection_name="Empty Connection",
            connection_type=ResourceConnectionType.MCP_GATEWAY,
            resource_ids=[],
        )

        response = resource_client.create_connection(request)

        resource_client.make_request.assert_called_once()
        assert isinstance(response, CreateResourceConnectionResponse)
        assert response.connection_id == "conn-empty-789"

    def test_delete_connection(self, resource_client):
        """Test deleting a resource connection."""
        resource_client.make_request.return_value = {}

        connection_id = "323e4567-e89b-12d3-a456-426614174333"
        resource_client.delete_connection(connection_id)

        resource_client.make_request.assert_called_once()

    def test_error_handling(self, resource_client):
        """Test error handling in the client."""
        resource_client.make_request.side_effect = ApiError("API Error", 404)

        with pytest.raises(ApiError) as excinfo:
            resource_client.get_connection("nonexistent-id")

        assert "API Error" in str(excinfo.value)
