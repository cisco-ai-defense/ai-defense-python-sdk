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
import time
from unittest.mock import MagicMock, patch, Mock
from requests.adapters import HTTPAdapter
from requests.auth import AuthBase
from urllib3.util.retry import Retry

from aidefense.config import Config
from aidefense.exceptions import ValidationError, SDKError, ApiError
from aidefense.request_handler import RequestHandler

# Define header constants for tests - must match what's actually used in the implementation
REQUEST_ID_HEADER = "x-aidefense-request-id"


@pytest.fixture
def reset_config_singleton():
    """Reset the Config singleton before each test."""
    Config._instance = None
    yield
    Config._instance = None


def test_request_handler_init_default():
    handler = RequestHandler(Config())
    assert handler.config is not None
    assert hasattr(handler, "_session")


def test_get_request_id():
    handler = RequestHandler(Config())
    request_id = handler.get_request_id()
    assert isinstance(request_id, str)
    assert len(request_id) > 10


@patch("requests.Session.request")
def test_request_invalid_method(mock_request):
    handler = RequestHandler(Config())
    with pytest.raises(ValidationError, match="Invalid HTTP method: INVALID"):
        handler.request(method="INVALID", url="https://api.example.com", auth=None)


@patch("requests.Session.request")
def test_request_invalid_url(mock_request):
    # Test that invalid URLs are handled by requests library, not our validation
    mock_request.side_effect = requests.exceptions.InvalidURL("Invalid URL")
    handler = RequestHandler(Config())
    with pytest.raises(requests.exceptions.InvalidURL):
        handler.request(method="GET", url="https://invalid-url", auth=None)


@patch("requests.Session.request")
def test_request_success(mock_request):
    # Mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_request.return_value = mock_response

    # Test request
    handler = RequestHandler(Config())
    result = handler.request(
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
    # Note: REQUEST_ID_HEADER is only added when request_id is explicitly provided
    assert kwargs["json"] == {"key": "value"}
    assert kwargs["timeout"] == 30


@patch("requests.Session.request")
def test_request_with_auth(mock_request):
    # Mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_request.return_value = mock_response

    # Mock auth using proper AuthBase
    class MockAuth(AuthBase):
        def __call__(self, r):
            r.headers["Authorization"] = "Bearer test-token"
            return r

    # Test request with auth
    handler = RequestHandler(Config())

    # Mock the auth preparation process
    with patch("requests.Request") as mock_request_class:
        mock_prepared = MagicMock()
        mock_prepared.headers = {"Authorization": "Bearer test-token"}
        mock_request_class.return_value.prepare.return_value = mock_prepared

        result = handler.request(
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
def test_request_with_network_error(mock_request):
    # Mock network error
    mock_request.side_effect = requests.RequestException("Network error")

    # Test request
    handler = RequestHandler(Config())
    with pytest.raises(requests.RequestException, match="Network error"):
        handler.request(method="GET", url="https://api.example.com", auth=None)


@patch("requests.Session.request")
def test_handle_error_response_401(mock_request):
    # Mock 401 response
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.json.return_value = {"message": "Unauthorized access"}
    mock_request.return_value = mock_response

    # Test request
    handler = RequestHandler(Config())
    with pytest.raises(SDKError, match="Authentication error: Unauthorized access"):
        handler.request(method="GET", url="https://api.example.com", auth=None)


@patch("requests.Session.request")
def test_handle_error_response_400(mock_request):
    # Mock 400 response
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"message": "Invalid parameters"}
    mock_request.return_value = mock_response

    # Test request
    handler = RequestHandler(Config())
    with pytest.raises(ValidationError, match="Bad request: Invalid parameters"):
        handler.request(method="GET", url="https://api.example.com", auth=None)


@patch("requests.Session.request")
def test_handle_error_response_500(mock_request):
    # Mock 500 response
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.json.return_value = {"message": "Internal server error"}
    mock_request.return_value = mock_response

    # Test request
    handler = RequestHandler(Config())
    with pytest.raises(ApiError, match="API error 500: Internal server error"):
        handler.request(method="GET", url="https://api.example.com", auth=None)


@patch("requests.Session.request")
def test_api_error_contains_request_id(mock_request):
    # Mock 500 response
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.json.return_value = {"message": "Server error"}
    mock_request.return_value = mock_response

    # Create a specific request_id for testing
    test_request_id = "test-request-id-12345"

    # Test request with explicit request_id
    handler = RequestHandler(Config())
    try:
        handler.request(
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
def test_handle_error_response_non_json(mock_request):
    # Mock error response with non-JSON content
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_response.text = "Internal Server Error"
    mock_request.return_value = mock_response

    # Test request
    handler = RequestHandler(Config())
    with pytest.raises(ApiError, match="API error 500: Internal Server Error"):
        handler.request(method="GET", url="https://api.example.com", auth=None)


@patch("requests.Session.request")
def test_handle_error_response_empty_response(mock_request):
    # Mock error response with empty content
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_response.text = ""
    mock_request.return_value = mock_response

    # Test request
    handler = RequestHandler(Config())
    with pytest.raises(ApiError, match="API error 500: Unknown error"):
        handler.request(method="GET", url="https://api.example.com", auth=None)


# ===== SESSION CONFIGURATION TESTS =====


def test_session_initialization(reset_config_singleton):
    """Test that session is properly initialized with correct configuration."""
    config = Config()
    handler = RequestHandler(config)

    # Verify session exists and has correct headers
    assert hasattr(handler, "_session")
    assert isinstance(handler._session, requests.Session)
    assert handler._session.headers["User-Agent"] == handler.USER_AGENT
    assert handler._session.headers["Content-Type"] == "application/json"


def test_session_connection_pool_mounting(reset_config_singleton):
    """Test that HTTPAdapter is properly mounted to session."""
    config = Config()
    handler = RequestHandler(config)

    # Verify HTTPAdapter is mounted for HTTPS
    https_adapter = handler._session.get_adapter("https://api.example.com")
    assert isinstance(https_adapter, HTTPAdapter)


def test_custom_httpadapter(reset_config_singleton):
    """Test RequestHandler with custom HTTPAdapter."""
    custom_adapter = HTTPAdapter(pool_connections=15, pool_maxsize=25)
    config = Config(connection_pool=custom_adapter)
    handler = RequestHandler(config)

    # Verify custom adapter is used
    https_adapter = handler._session.get_adapter("https://api.example.com")
    assert https_adapter is custom_adapter


# ===== TIMEOUT TESTS =====


@patch("requests.Session.request")
def test_request_uses_config_timeout(mock_request, reset_config_singleton):
    """Test that request uses timeout from config when none provided."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_request.return_value = mock_response

    config = Config(timeout=45)
    handler = RequestHandler(config)
    handler.request(method="GET", url="https://api.example.com", auth=None)

    # Verify config timeout is used
    mock_request.assert_called_once()
    args, kwargs = mock_request.call_args
    assert kwargs["timeout"] == 45


@patch("requests.Session.request")
def test_request_explicit_timeout_overrides_config(
    mock_request, reset_config_singleton
):
    """Test that explicit timeout parameter overrides config timeout."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_request.return_value = mock_response

    config = Config(timeout=45)
    handler = RequestHandler(config)
    handler.request(method="GET", url="https://api.example.com", auth=None, timeout=60)

    # Verify explicit timeout is used
    mock_request.assert_called_once()
    args, kwargs = mock_request.call_args
    assert kwargs["timeout"] == 60


# ===== REQUEST ID TESTS =====


@patch("requests.Session.request")
def test_explicit_request_id_used(mock_request):
    """Test that explicitly provided request ID is used."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_request.return_value = mock_response

    handler = RequestHandler(Config())
    test_request_id = "explicit-request-id-123"

    handler.request(
        method="GET",
        url="https://api.example.com",
        auth=None,
        request_id=test_request_id,
    )

    # Verify explicit request ID is included in headers
    mock_request.assert_called_once()
    args, kwargs = mock_request.call_args
    assert kwargs["headers"][REQUEST_ID_HEADER] == test_request_id


# ===== HEADER TESTS =====


@patch("requests.Session.request")
def test_default_headers_applied(mock_request):
    """Test that default headers are properly applied."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_request.return_value = mock_response

    handler = RequestHandler(Config())
    handler.request(method="GET", url="https://api.example.com", auth=None)

    # Verify default headers are present
    mock_request.assert_called_once()
    args, kwargs = mock_request.call_args
    headers = kwargs["headers"]
    assert headers["User-Agent"] == handler.USER_AGENT
    assert headers["Content-Type"] == "application/json"


@patch("requests.Session.request")
def test_custom_headers_merge_with_defaults(mock_request):
    """Test that custom headers are merged with defaults."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_request.return_value = mock_response

    handler = RequestHandler(Config())
    custom_headers = {
        "X-Custom-Header": "custom-value",
        "Content-Type": "application/xml",  # Override default
    }

    handler.request(
        method="GET", url="https://api.example.com", auth=None, headers=custom_headers
    )

    # Verify headers are properly merged
    mock_request.assert_called_once()
    args, kwargs = mock_request.call_args
    headers = kwargs["headers"]
    assert headers["User-Agent"] == handler.USER_AGENT  # Default preserved
    assert headers["X-Custom-Header"] == "custom-value"  # Custom added
    assert headers["Content-Type"] == "application/xml"  # Default overridden


# ===== RETRY FUNCTIONALITY TESTS =====


def test_retry_configuration_in_adapter(reset_config_singleton):
    """Test that retry configuration is properly set in HTTPAdapter."""
    retry_config = {
        "total": 5,
        "backoff_factor": 1.0,
        "status_forcelist": [429, 500, 502, 503, 504],
    }
    config = Config(retry_config=retry_config)
    handler = RequestHandler(config)

    # Get the HTTPAdapter and verify retry configuration
    https_adapter = handler._session.get_adapter("https://api.example.com")
    retry_obj = https_adapter.max_retries

    assert isinstance(retry_obj, Retry)
    assert retry_obj.total == 5
    assert retry_obj.backoff_factor == 1.0
    # Note: status_forcelist might be a list or frozenset depending on urllib3 version
    expected_statuses = {429, 500, 502, 503, 504}
    actual_statuses = (
        set(retry_obj.status_forcelist) if retry_obj.status_forcelist else set()
    )
    assert actual_statuses == expected_statuses


def test_default_retry_configuration(reset_config_singleton):
    """Test that default retry configuration is applied."""
    config = Config()
    handler = RequestHandler(config)

    # Verify default retry settings
    https_adapter = handler._session.get_adapter("https://api.example.com")
    retry_obj = https_adapter.max_retries

    assert isinstance(retry_obj, Retry)
    assert retry_obj.total == Config.DEFAULT_TOTAL
    assert retry_obj.backoff_factor == Config.DEFAULT_BACKOFF_FACTOR
    # Note: status_forcelist might be a list or frozenset depending on urllib3 version
    expected_statuses = set(Config.DEFAULT_STATUS_FORCELIST)
    actual_statuses = (
        set(retry_obj.status_forcelist) if retry_obj.status_forcelist else set()
    )
    assert actual_statuses == expected_statuses


# ===== INTEGRATION TESTS =====


@patch("requests.Session.request")
def test_integration_full_request_flow(mock_request, reset_config_singleton):
    """Integration test with minimal mocking for complete request flow."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": "success", "data": [1, 2, 3]}
    mock_request.return_value = mock_response

    # Create config with custom settings
    retry_config = {"total": 3, "backoff_factor": 0.3}
    config = Config(timeout=25, retry_config=retry_config)
    handler = RequestHandler(config)

    # Mock auth
    class TestAuth(AuthBase):
        def __call__(self, r):
            r.headers["Authorization"] = "Bearer integration-test-token"
            return r

    # Make request with all parameters
    with patch("requests.Request") as mock_request_class:
        mock_prepared = MagicMock()
        mock_prepared.headers = {"Authorization": "Bearer integration-test-token"}
        mock_request_class.return_value.prepare.return_value = mock_prepared

        result = handler.request(
            method="POST",
            url="https://api.example.com/endpoint",
            auth=TestAuth(),
            request_id="integration-test-id",
            headers={"X-Test": "integration"},
            json_data={"test": "data"},
            timeout=30,
        )

    # Verify result
    assert result == {"result": "success", "data": [1, 2, 3]}

    # Verify all parameters were passed correctly
    mock_request.assert_called_once()
    args, kwargs = mock_request.call_args

    assert kwargs["method"] == "POST"
    assert kwargs["url"] == "https://api.example.com/endpoint"
    assert kwargs["json"] == {"test": "data"}
    assert kwargs["timeout"] == 30

    headers = kwargs["headers"]
    assert headers["Authorization"] == "Bearer integration-test-token"
    assert headers["X-Test"] == "integration"
    assert headers[REQUEST_ID_HEADER] == "integration-test-id"
    assert headers["User-Agent"] == handler.USER_AGENT
    assert headers["Content-Type"] == "application/json"
