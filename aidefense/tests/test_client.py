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
import requests
import uuid
from unittest.mock import MagicMock, patch

from aidefense.client import BaseClient
from aidefense.config import Config
from aidefense.exceptions import ValidationError, SDKError, ApiError
from aidefense.runtime.constants import VALID_HTTP_METHODS

# Define header constants for tests - must match what's actually used in the implementation
REQUEST_ID_HEADER = "x-aidefense-request-id"


# Create a TestClient class that extends BaseClient for testing
class TestClient(BaseClient):
    def __init__(self, config=None):
        super().__init__(config or Config())


@pytest.fixture
def reset_config_singleton():
    """Reset the Config singleton before each test."""
    Config._instance = None
    yield
    Config._instance = None


@pytest.fixture
def client(reset_config_singleton):
    """Create a test client with a fresh config for each test."""
    return TestClient()


def test_client_init_default():
    """Test creating a client with default config."""
    client = TestClient()
    assert client.config is not None
    assert isinstance(client.config, Config)
    assert client._session is not None


def test_client_init_with_config():
    """Test creating a client with custom config."""
    # Note: We need to directly access the config's properties instead of trying to override them
    # since the Config class has its own initialization logic
    custom_config = Config()
    client = TestClient(config=custom_config)
    assert client.config is custom_config
    # Verify that the config has a valid runtime_base_url (don't check exact value as it may vary)
    assert client.config.runtime_base_url.startswith("https://")


def test_get_request_id():
    """Test generating a request ID."""
    client = TestClient()
    request_id = client.get_request_id()
    assert request_id is not None
    assert isinstance(request_id, str)
    assert len(request_id) > 0

    # Verify that the request_id is a valid UUID
    try:
        uuid_obj = uuid.UUID(request_id)
        assert str(uuid_obj) == request_id.lower()
    except ValueError:
        pytest.fail(f"Request ID '{request_id}' is not a valid UUID")


def test_request_invalid_method():
    """Test request with invalid HTTP method."""
    client = TestClient()
    with pytest.raises(ValidationError, match="Invalid HTTP method"):
        client.request(method="INVALID", url="https://api.example.com", auth=None)


def test_request_invalid_url():
    """Test request with invalid URL."""
    client = TestClient()
    with pytest.raises(ValidationError, match="Invalid URL"):
        client.request(method="GET", url="invalid-url", auth=None)


@patch("requests.Session.request")
def test_request_success(mock_request, client):
    """Test successful request."""
    # Mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_request.return_value = mock_response

    # Test request
    result = client.request(
        method="GET",
        url="https://api.example.com",
        auth=None,
        headers={"X-Custom": "Value"},
        json_data={"key": "value"},
        timeout=30,
    )

    # Check result
    assert result == {"success": True}

    # Verify request was made correctly
    mock_request.assert_called_once()
    args, kwargs = mock_request.call_args
    assert kwargs["method"] == "GET"
    assert kwargs["url"] == "https://api.example.com"
    assert "X-Custom" in kwargs["headers"]
    assert REQUEST_ID_HEADER in kwargs["headers"]
    assert kwargs["json"] == {"key": "value"}
    assert kwargs["timeout"] == 30


@patch("requests.Session.request")
def test_request_with_auth(mock_request, client):
    """Test request with authentication."""
    # Mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_request.return_value = mock_response

    # Mock auth
    class MockAuth:
        def __call__(self, request):
            request.headers["Authorization"] = "Bearer test-token"
            return request

    # Test request
    result = client.request(
        method="POST",
        url="https://api.example.com",
        auth=MockAuth(),
        json_data={"key": "value"},
    )

    # Check result
    assert result == {"success": True}

    # Verify request includes auth headers
    mock_request.assert_called_once()
    args, kwargs = mock_request.call_args
    assert "Authorization" in kwargs["headers"]
    assert kwargs["headers"]["Authorization"] == "Bearer test-token"


@patch("requests.Session.request")
def test_request_with_network_error(mock_request, client):
    """Test request with network error."""
    # Mock network error
    mock_request.side_effect = requests.RequestException("Network error")

    # Test request
    with pytest.raises(requests.RequestException, match="Network error"):
        client.request(method="GET", url="https://api.example.com", auth=None)


@patch("requests.Session.request")
def test_handle_error_response_401(mock_request, client):
    """Test handling 401 authentication error."""
    # Mock 401 response
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.json.return_value = {"message": "Unauthorized access"}
    mock_request.return_value = mock_response

    # Test request
    with pytest.raises(SDKError, match="Authentication error: Unauthorized access"):
        client.request(method="GET", url="https://api.example.com", auth=None)


@patch("requests.Session.request")
def test_handle_error_response_400(mock_request, client):
    """Test handling 400 validation error."""
    # Mock 400 response
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"message": "Invalid parameters"}
    mock_request.return_value = mock_response

    # Test request
    with pytest.raises(ValidationError, match="Bad request: Invalid parameters"):
        client.request(method="GET", url="https://api.example.com", auth=None)


@patch("requests.Session.request")
def test_handle_error_response_500(mock_request, client):
    """Test handling 500 server error."""
    # Mock 500 response
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.json.return_value = {"message": "Internal server error"}
    mock_request.return_value = mock_response

    # Test request
    with pytest.raises(ApiError, match="API error 500: Internal server error"):
        client.request(method="GET", url="https://api.example.com", auth=None)


@patch("requests.Session.request")
def test_api_error_contains_request_id(mock_request, client):
    """Test that ApiError contains the request_id when provided."""
    # Mock 500 response
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.json.return_value = {"message": "Server error"}
    mock_request.return_value = mock_response

    # Create a specific request_id for testing
    test_request_id = "test-request-id-12345"

    # Test request with explicit request_id
    try:
        client.request(
            method="GET",
            url="https://api.example.com",
            auth=None,
            request_id=test_request_id,
        )
        pytest.fail("Expected ApiError was not raised")
    except ApiError as e:
        # Verify that the error contains the request_id
        assert e.request_id == test_request_id
        assert "API error 500" in str(e)


@patch("requests.Session.request")
def test_handle_error_response_non_json(mock_request, client):
    """Test handling error with non-JSON response."""
    # Mock error response with non-JSON content
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_response.text = "Internal Server Error"
    mock_request.return_value = mock_response

    # Test request
    with pytest.raises(ApiError, match="API error 500: Internal Server Error"):
        client.request(method="GET", url="https://api.example.com", auth=None)


@patch("requests.Session.request")
def test_handle_error_response_empty_response(mock_request, client):
    """Test handling error with empty response."""
    # Mock error response with empty content
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_response.text = ""
    mock_request.return_value = mock_response

    # Test request
    with pytest.raises(ApiError, match="API error 500: Unknown error"):
        client.request(method="GET", url="https://api.example.com", auth=None)
