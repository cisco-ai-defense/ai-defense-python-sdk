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

from aidefense.management.applications import ApplicationManagementClient
from aidefense.management.auth import ManagementAuth
from aidefense.management.models.application import (
    Application,
    ApplicationSortBy,
    ListApplicationsRequest,
    ListApplicationsResponse,
    CreateApplicationRequest,
    CreateApplicationResponse,
    UpdateApplicationRequest,
)
from aidefense.management.models.connection import ConnectionType
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
def application_client(mock_request_handler):
    """Create an ApplicationManagementClient with a mock request handler."""
    client = ApplicationManagementClient(
        auth=ManagementAuth(TEST_API_KEY), request_handler=mock_request_handler
    )
    # Replace the make_request method with a mock
    client.make_request = MagicMock()
    return client


class TestApplicationManagementClient:
    """Tests for the ApplicationManagementClient."""

    def test_list_applications(self, application_client):
        """Test listing applications."""
        # Setup mock response
        mock_response = {
            "applications": {
                "items": [
                    {
                        "application_id": "app-123",
                        "application_name": "Test App 1",
                        "description": "Test Description 1",
                        "connection_type": "API",
                        "created_at": "2025-01-01T00:00:00Z",
                        "updated_at": "2025-01-02T00:00:00Z",
                    },
                    {
                        "application_id": "app-456",
                        "application_name": "Test App 2",
                        "description": "Test Description 2",
                        "connection_type": "Gateway",
                        "created_at": "2025-01-03T00:00:00Z",
                        "updated_at": "2025-01-04T00:00:00Z",
                    },
                ],
                "paging": {"total": 2, "count": 2, "offset": 0},
            }
        }
        application_client.make_request.return_value = mock_response

        # Create request
        request = ListApplicationsRequest(
            limit=10,
            offset=0,
            expanded=True,
            sort_by=ApplicationSortBy.application_name,
            order="asc",
        )

        # Call the method
        response = application_client.list_applications(request)

        # Verify the make_request call
        application_client.make_request.assert_called_once_with(
            "GET",
            "applications",
            params={
                "limit": 10,
                "offset": 0,
                "expanded": True,
                "sort_by": "application_name",
                "order": "asc",
            },
        )

        # Verify the response
        assert isinstance(response, ListApplicationsResponse)
        assert len(response.applications.items) == 2
        assert response.applications.items[0].application_id == "app-123"
        assert response.applications.items[0].application_name == "Test App 1"
        assert response.applications.items[1].application_id == "app-456"
        assert response.applications.items[1].application_name == "Test App 2"
        assert response.applications.paging.total == 2
        assert response.applications.paging.count == 2
        assert response.applications.paging.offset == 0

    def test_get_application(self, application_client):
        """Test getting an application by ID."""
        # Setup mock response
        mock_response = {
            "application": {
                "application_id": "app-123",
                "application_name": "Test App",
                "description": "Test Description",
                "connection_type": "API",
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-02T00:00:00Z",
            }
        }
        application_client.make_request.return_value = mock_response

        # Call the method
        application_id = "123e4567-e89b-12d3-a456-426614174000"
        response = application_client.get_application(application_id, expanded=True)

        # Verify the make_request call
        application_client.make_request.assert_called_once_with(
            "GET", f"applications/{application_id}", params={"expanded": True}
        )

        # Verify the response
        assert isinstance(response, Application)
        assert response.application_id == "app-123"
        assert response.application_name == "Test App"
        assert response.description == "Test Description"
        assert response.connection_type == "API"

    def test_create_application(self, application_client):
        """Test creating an application."""
        # Setup mock response
        mock_response = {"application_id": "app-123"}
        application_client.make_request.return_value = mock_response

        # Create request
        request = CreateApplicationRequest(
            application_name="New Test App",
            description="New Test Description",
            connection_type=ConnectionType.API,
        )

        # Call the method
        response = application_client.create_application(request)

        # Verify the make_request call
        application_client.make_request.assert_called_once_with(
            "POST",
            "applications",
            data={
                "application_name": "New Test App",
                "description": "New Test Description",
                "connection_type": "API",
            },
        )

        # Verify the response
        assert isinstance(response, CreateApplicationResponse)
        assert response.application_id == "app-123"

    def test_update_application(self, application_client):
        """Test updating an application."""
        # Setup mock response (empty for update)
        application_client.make_request.return_value = {}

        # Create request
        application_id = "123e4567-e89b-12d3-a456-426614174000"
        request = UpdateApplicationRequest(
            application_name="Updated App Name", description="Updated Description"
        )

        # Call the method
        response = application_client.update_application(application_id, request)

        # Verify the make_request call
        application_client.make_request.assert_called_once_with(
            "PUT",
            f"applications/{application_id}",
            data={
                "application_name": "Updated App Name",
                "description": "Updated Description",
            },
        )

        # Verify the response
        assert response is None

    def test_delete_application(self, application_client):
        """Test deleting an application."""
        # Setup mock response (empty for delete)
        application_client.make_request.return_value = {}

        # Call the method
        application_id = "123e4567-e89b-12d3-a456-426614174000"
        response = application_client.delete_application(application_id)

        # Verify the make_request call
        application_client.make_request.assert_called_once_with(
            "DELETE", f"applications/{application_id}"
        )

        # Verify the response
        assert response is None

    def test_error_handling(self, application_client):
        """Test error handling in the client."""
        # Setup mock to raise an exception
        application_client.make_request.side_effect = ApiError("API Error", 400)

        # Create request
        request = ListApplicationsRequest(limit=10)

        # Verify that the exception is propagated
        with pytest.raises(ApiError) as excinfo:
            application_client.list_applications(request)

        assert "API Error" in str(excinfo.value)

    def test_update_application_failfast_empty(self, application_client):
        """Fail fast when no fields are provided to update."""
        with pytest.raises(ValueError) as excinfo:
            application_client.update_application(
                "123e4567-e89b-12d3-a456-426614174331", UpdateApplicationRequest()
            )
        assert "No fields to update" in str(excinfo.value)
        application_client.make_request.assert_not_called()
