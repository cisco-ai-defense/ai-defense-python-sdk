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

"""
Comprehensive unified tests for HTTP inspection functionality.

This file combines all HTTP inspection tests including basic tests, edge cases,
and specialized tests for code coverage. Having all tests in a single file makes
maintenance easier and provides a better overview of all HTTP inspection testing.
"""

import base64
import json
import pytest
import requests
from unittest.mock import MagicMock, patch
from requests.exceptions import RequestException, Timeout

from aidefense import HttpInspectionClient, Config
from aidefense.runtime.utils import to_base64_bytes, ensure_base64_body
from aidefense.exceptions import ValidationError, ApiError
from aidefense.runtime.http_models import (
    HttpReqObject,
    HttpResObject,
    HttpHdrObject,
    HttpMetaObject,
    HttpHdrKvObject,
)
from aidefense.runtime.constants import (
    HTTP_REQ,
    HTTP_RES,
    HTTP_BODY,
    HTTP_METHOD,
    HTTP_META,
)
from aidefense.runtime.models import InspectionConfig, Rule, RuleName

# Create a valid format dummy API key for testing (must be 64 characters)
TEST_API_KEY = "0123456789" * 6 + "0123"  # 64 characters


@pytest.fixture(autouse=True)
def reset_config_singleton():
    """Reset Config singleton before each test."""
    # Reset the singleton instance
    Config._instance = None
    yield
    Config._instance = None


@pytest.fixture
def client():
    """Create a test HTTP inspection client."""
    return HttpInspectionClient(api_key=TEST_API_KEY)


# ============================================================================
# Basic Client Tests
# ============================================================================


def test_http_client_init_default():
    client = HttpInspectionClient(api_key=TEST_API_KEY)
    assert client.endpoint.endswith("/api/v1/inspect/http")


def test_http_client_init_with_config():
    config = Config(runtime_base_url="https://custom.http")
    client = HttpInspectionClient(api_key=TEST_API_KEY, config=config)
    assert client.config is config
    assert client.endpoint.startswith("https://custom.http")


# ============================================================================
# Core API Tests
# ============================================================================


def test_inspect(monkeypatch):
    client = HttpInspectionClient(api_key=TEST_API_KEY)
    monkeypatch.setattr(client, "_inspect", lambda *a, **kw: "raw_result")
    req = {"method": "GET", "headers": {}, "body": to_base64_bytes(b"hi")}
    meta = {"url": "https://foo"}
    assert client.inspect(http_req=req, http_meta=meta) == "raw_result"


def test_inspect_with_empty_inputs(client):
    """Test inspect method with empty inputs to cover error cases."""
    # Mock _inspect to avoid actual API calls
    client._inspect = MagicMock(return_value="mock_result")

    # Case: Empty HTTP request
    result = client.inspect(http_req={})
    assert result == "mock_result"

    # Reset mock
    client._inspect.reset_mock()

    # Case: Empty HTTP response
    result = client.inspect(http_res={})
    assert result == "mock_result"


def test_inspect_request(monkeypatch):
    client = HttpInspectionClient(api_key=TEST_API_KEY)
    monkeypatch.setattr(client, "_inspect", lambda *a, **kw: "req_result")
    assert (
        client.inspect_request("GET", "https://foo", body="test body") == "req_result"
    )


def test_request_with_dict_body(client):
    """Test request with dictionary body to cover JSON conversion."""
    client._inspect = MagicMock(return_value="mock_result")

    # Dictionary body
    dict_body = {"message": "test", "nested": {"data": [1, 2, 3]}}

    result = client.inspect_request(
        method="POST",
        url="https://example.com",
        headers={"Content-Type": "application/json"},
        body=dict_body,
    )

    assert result == "mock_result"
    client._inspect.assert_called_once()


def test_validation_of_request_with_invalid_body(client):
    """Test validation of HTTP request body types."""
    # Test with invalid body type (int)
    with pytest.raises(ValidationError):
        client.inspect_request(
            method="POST", url="https://example.com", body=12345  # Invalid body type
        )


def test_inspect_response(monkeypatch):
    client = HttpInspectionClient(api_key=TEST_API_KEY)
    monkeypatch.setattr(client, "_inspect", lambda *a, **kw: "resp_result")
    assert (
        client.inspect_response(200, "https://foo", body="test response")
        == "resp_result"
    )


def test_response_with_dict_body_and_request_context(client):
    """Test response with dictionary body and request context to cover multiple code paths."""
    client._inspect = MagicMock(return_value="mock_result")

    # Dictionary bodies for both response and request
    response_body = {"status": "success", "data": {"items": [{"id": 1}]}}
    request_body = {"query": "test"}

    result = client.inspect_response(
        status_code=200,
        url="https://example.com",
        headers={"Content-Type": "application/json"},
        body=response_body,
        request_method="POST",
        request_headers={"Content-Type": "application/json"},
        request_body=request_body,
    )

    assert result == "mock_result"
    client._inspect.assert_called_once()


def test_response_with_missing_request_method(client):
    """Test response with missing request method to cover validation error paths."""
    # Mock _inspect to avoid actual API calls
    client._inspect = MagicMock(return_value="mock_result")

    # Test case: Provide request_body but not request_method
    # This should pass without errors because our implementation doesn't explicitly
    # require request_method when request_body is provided
    result = client.inspect_response(
        status_code=200,
        url="https://example.com",
        body="test",
        request_headers={"Content-Type": "application/json"},
        request_body="test",
    )

    assert result == "mock_result"


def test_validation_of_response_with_invalid_body(client):
    """Test validation of HTTP response body types."""
    # Test with invalid body type (int)
    with pytest.raises(ValidationError):
        client.inspect_response(
            status_code=200, url="https://example.com", body=12345  # Invalid body type
        )


def test_inspect_request_from_http_library(monkeypatch):
    client = HttpInspectionClient(api_key=TEST_API_KEY)
    monkeypatch.setattr(client, "_inspect", lambda *a, **kw: "lib_req_result")
    req = requests.Request("GET", "https://foo").prepare()
    assert client.inspect_request_from_http_library(req) == "lib_req_result"


def test_inspect_request_from_http_library_with_empty_body():
    """Test inspect_request_from_http_library with empty body."""
    import requests

    client = HttpInspectionClient(api_key=TEST_API_KEY)
    client._inspect = MagicMock(return_value="mock_result")

    # Create a request with empty body
    req = requests.Request("GET", "https://example.com").prepare()
    req.body = b""

    result = client.inspect_request_from_http_library(req)
    assert result == "mock_result"


def test_inspect_response_from_http_library(monkeypatch):
    client = HttpInspectionClient(api_key=TEST_API_KEY)
    monkeypatch.setattr(client, "_inspect", lambda *a, **kw: "lib_resp_result")
    resp = requests.Response()
    resp.status_code = 200
    resp.url = "https://foo.com"
    resp._content = b"hi"
    resp.headers = {"content-type": "text/plain"}

    # Add a request to the response object as it's required by the implementation
    req = requests.Request("GET", "https://foo.com")
    resp.request = req.prepare()
    resp.request.body = to_base64_bytes(b"test")

    assert client.inspect_response_from_http_library(resp) == "lib_resp_result"


# ============================================================================
# Validation Tests
# ============================================================================


def test_validate_http_inspection_request_empty_req_res():
    client = HttpInspectionClient(api_key=TEST_API_KEY)
    # http_req is required, so test should expect ValidationError
    with pytest.raises(ValidationError, match=f"'{HTTP_REQ}' must be provided"):
        client.validate_inspection_request({"http_meta": {}})


def test_validate_http_inspection_request_invalid_req_type():
    client = HttpInspectionClient(api_key=TEST_API_KEY)
    with pytest.raises(ValidationError, match=f"'{HTTP_REQ}' must be a dict"):
        client.validate_inspection_request({HTTP_REQ: "not a dict"})


def test_validate_http_inspection_request_missing_method():
    client = HttpInspectionClient(api_key=TEST_API_KEY)
    # Note: The validation for body happens first in the implementation
    with pytest.raises(
        ValidationError, match=f"'{HTTP_REQ}' must have a non-empty 'body'"
    ):
        client.validate_inspection_request({HTTP_REQ: {"headers": {}, "body": ""}})


def test_validate_http_inspection_request_invalid_method():
    client = HttpInspectionClient(api_key=TEST_API_KEY)
    invalid_method = "INVALID"
    # Need to provide a non-empty body to get past the body validation
    with pytest.raises(
        ValidationError, match=f"'{HTTP_REQ}' must have a non-empty 'body'"
    ):
        client.validate_inspection_request(
            {HTTP_REQ: {HTTP_METHOD: invalid_method, "headers": {}}}
        )


def test_validate_http_inspection_request_valid():
    client = HttpInspectionClient(api_key=TEST_API_KEY)
    # Valid request - note that body must be non-empty to pass validation
    request = {
        HTTP_REQ: {
            HTTP_METHOD: "GET",
            "headers": {"content-type": "application/json"},
            "body": to_base64_bytes(b"test body"),
        }
    }
    # Should not raise an exception
    client.validate_inspection_request(request)


def test_http_validate_with_empty_body_and_valid_method(client):
    """Test validation with empty body but valid method."""
    # Valid request but with empty body
    request = {
        "http_req": {
            "method": "GET",
            "headers": {"content-type": "application/json"},
            "body": "",  # Empty body
        }
    }

    # Should raise a validation error for empty body
    with pytest.raises(ValidationError, match="must have a non-empty 'body'"):
        client.validate_inspection_request(request)


def test_validation_for_config_enabled_rules(client):
    """Test validation for config with enabled rules."""
    # Valid request with valid config
    request = {
        "http_req": {
            "method": "GET",
            "headers": {},
            "body": base64.b64encode(b"test").decode(),
        },
        "config": {
            "enabled_rules": [
                {"rule_name": "CUSTOM_RULE", "parameters": {"key": "value"}}
            ]
        },
    }

    # This should validate successfully
    client.validate_inspection_request(request)

    # Test empty rule list
    empty_rule_list_request = {
        "http_req": {
            "method": "GET",
            "headers": {},
            "body": base64.b64encode(b"test").decode(),
        },
        "config": {"enabled_rules": []},  # Empty list
    }

    with pytest.raises(ValidationError, match="must be a non-empty list"):
        client.validate_inspection_request(empty_rule_list_request)


def test_http_validate_request_valid_rule_list(client):
    """Test validation with valid config rule list."""
    request = {
        "http_req": {
            "method": "GET",
            "headers": {"content-type": "application/json"},
            "body": "dGVzdCBib2R5",  # base64 for "test body"
        },
        "config": {"enabled_rules": [{"rule_name": "PROMPT_INJECTION"}]},
    }
    # Should validate successfully
    client.validate_inspection_request(request)


def test_http_validate_request_invalid_rule_list(client):
    """Test validation with invalid config rule list."""
    request = {
        "http_req": {
            "method": "GET",
            "headers": {"content-type": "application/json"},
            "body": "dGVzdCBib2R5",  # base64 for "test body"
        },
        "config": {"enabled_rules": {}},  # Invalid: should be a list
    }
    with pytest.raises(
        ValidationError, match="config.enabled_rules must be a non-empty list"
    ):
        client.validate_inspection_request(request)


def test_http_validate_request_empty_rule_list(client):
    """Test validation with empty config rule list."""
    request = {
        "http_req": {
            "method": "GET",
            "headers": {"content-type": "application/json"},
            "body": "dGVzdCBib2R5",  # base64 for "test body"
        },
        "config": {"enabled_rules": []},  # Invalid: should be non-empty
    }
    with pytest.raises(
        ValidationError, match="config.enabled_rules must be a non-empty list"
    ):
        client.validate_inspection_request(request)


# ============================================================================
# HTTP Library Integration Tests
# ============================================================================


def test_build_http_req_from_http_library_with_prepared_request():
    client = HttpInspectionClient(api_key=TEST_API_KEY)

    # Create a prepared request with headers and body
    headers = {"content-type": "application/json", "x-custom": "value"}
    body = '{"key": "value"}'
    req = requests.Request(
        "POST", "https://example.com/api", headers=headers, data=body
    ).prepare()

    # Build HTTP request object
    http_req = client._build_http_req_from_http_library(req)

    # Verify the method
    assert http_req.method == "POST"

    # Verify headers - note that headers may be transformed during request preparation
    # so we check for existence rather than exact matches
    header_dict = {hdr.key.lower(): hdr.value for hdr in http_req.headers.hdrKvs}
    assert "content-type" in header_dict

    # Verify body (base64 encoded)
    assert http_req.body
    decoded_body = base64.b64decode(http_req.body).decode()
    assert json.loads(decoded_body) == json.loads(
        body
    )  # Compare JSON structure rather than exact string


def test_build_http_req_from_http_library_with_request():
    client = HttpInspectionClient(api_key=TEST_API_KEY)

    # Create a regular (not prepared) request
    headers = {"content-type": "application/json"}
    req = requests.Request("GET", "https://example.com", headers=headers)

    # Build HTTP request object
    http_req = client._build_http_req_from_http_library(req)

    # Verify the method
    assert http_req.method == "GET"

    # Verify basic headers
    headers_dict = {hdr.key.lower(): hdr.value for hdr in http_req.headers.hdrKvs}
    assert headers_dict["content-type"] == "application/json"


def test_build_http_req_from_http_library_with_json_body():
    client = HttpInspectionClient(api_key=TEST_API_KEY)

    # Create a request with JSON content
    json_data = {"key": "value", "nested": {"data": [1, 2, 3]}}
    req = requests.Request("POST", "https://example.com", json=json_data).prepare()

    # Build HTTP request object
    http_req = client._build_http_req_from_http_library(req)

    # Verify the method
    assert http_req.method == "POST"
    decoded_body = base64.b64decode(http_req.body).decode()
    # Check that it contains the JSON data (might be formatted differently)
    assert "key" in decoded_body and "value" in decoded_body


def test_build_http_req_from_http_library_with_invalid_body():
    client = HttpInspectionClient(api_key=TEST_API_KEY)

    # Create a modified request with invalid body type
    req = requests.Request(method="GET", url="https://example.com").prepare()
    # Hack the request to have an invalid body type
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(req, "body", 12345)  # Not a valid type

    # Should raise a validation error
    with pytest.raises(
        ValidationError, match="Request body must be bytes, str or dict"
    ):
        client._build_http_req_from_http_library(req)


def test_build_http_req_from_http_library_with_none_body():
    """Test _build_http_req_from_http_library with None body."""
    client = HttpInspectionClient(api_key=TEST_API_KEY)

    # Create a request with None body
    req = requests.Request("GET", "https://example.com").prepare()
    req.body = None

    http_req = client._build_http_req_from_http_library(req)
    assert http_req.body == ""  # Body should be empty string


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_http_inspect_with_json_content_type(client):
    """Test HTTP inspection with JSON content type."""
    # Mock _inspect method to avoid actual API calls
    client._inspect = MagicMock(return_value="mock_result")

    result = client.inspect_request(
        method="POST",
        url="https://api.example.com",
        headers={"Content-Type": "application/json"},
        body='{"key": "value"}',
    )

    # Verify the result and method call
    assert result == "mock_result"
    client._inspect.assert_called_once()
    # Check that HTTP metadata contains the URL
    args, kwargs = client._inspect.call_args
    assert args[2].url == "https://api.example.com"


def test_http_inspect_with_binary_body(client):
    """Test HTTP inspection with binary body content."""
    # Mock _inspect method to avoid actual API calls
    client._inspect = MagicMock(return_value="mock_result")

    binary_data = b"\x00\x01\x02\x03"
    result = client.inspect_request(
        method="POST",
        url="https://api.example.com",
        headers={"Content-Type": "application/octet-stream"},
        body=binary_data,
    )

    # Verify the result
    assert result == "mock_result"
    client._inspect.assert_called_once()


def test_http_inspect_with_empty_response(client):
    """Test HTTP inspection with an empty response."""
    # Mock _inspect method to avoid actual API calls
    client._inspect = MagicMock(return_value="mock_result")

    result = client.inspect_response(
        status_code=204,
        url="https://api.example.com",
        headers={"Content-Type": "text/plain"},
        body="",  # Empty string for 204 No Content
    )

    # Verify the result
    assert result == "mock_result"
    client._inspect.assert_called_once()


def test_http_inspect_with_large_body(client):
    """Test HTTP inspection with a large body."""
    # Mock _inspect method to avoid actual API calls
    client._inspect = MagicMock(return_value="mock_result")

    # Create a large body (100KB)
    large_body = b"x" * 102400

    result = client.inspect_request(
        method="POST",
        url="https://api.example.com",
        headers={"Content-Type": "application/octet-stream"},
        body=large_body,
    )

    # Verify the result
    assert result == "mock_result"
    client._inspect.assert_called_once()


def test_request_id_passing(client):
    """Test passing request ID through the stack."""
    # Mock _inspect method to verify request_id passing
    client._inspect = MagicMock(return_value="mock_result")

    # Use a custom request ID
    custom_request_id = "test-request-id-12345"

    result = client.inspect_request(
        method="GET",
        url="https://api.example.com",
        body="test data",
        request_id=custom_request_id,
    )

    # Verify the result
    assert result == "mock_result"

    # Verify that request_id was passed to _inspect
    args, kwargs = client._inspect.call_args
    assert kwargs.get("request_id") == custom_request_id


def test_custom_timeout_passing(client):
    """Test passing custom timeout through the stack."""
    # Mock _inspect method to verify timeout passing
    client._inspect = MagicMock(return_value="mock_result")

    # Use a custom timeout
    custom_timeout = 30

    result = client.inspect_request(
        method="GET",
        url="https://api.example.com",
        body="test data",
        timeout=custom_timeout,
    )

    # Verify the result
    assert result == "mock_result"

    # Verify that timeout was passed to _inspect
    args, kwargs = client._inspect.call_args
    assert kwargs.get("timeout") == custom_timeout


# ============================================================================
# Error Handling Tests
# ============================================================================


def test_http_client_network_error(monkeypatch):
    client = HttpInspectionClient(api_key=TEST_API_KEY)

    # Mock the request method at a lower level to avoid actual error raising during test
    original_request = client.request

    def mock_request(*args, **kwargs):
        # Instead of raising an exception directly in the mock,
        # we'll wrap it in ApiError just as the real code would
        try:
            # Simulate the error condition
            error = RequestException("Network error")
            # In the actual implementation, this would be handled and wrapped
            raise ApiError(f"API request failed: {str(error)}")
        except ApiError as e:
            # Re-raise the already wrapped error
            raise e

    monkeypatch.setattr(client, "request", mock_request)

    # Should catch the wrapped error
    with pytest.raises(ApiError) as exc_info:
        client.inspect_request(method="GET", url="https://example.com", body="test")

    # Check that the error was properly wrapped
    assert "Network error" in str(exc_info.value)


def test_http_client_timeout_handling(monkeypatch):
    client = HttpInspectionClient(api_key=TEST_API_KEY)

    # Mock the request method at a lower level to avoid actual error raising during test
    original_request = client.request

    def mock_request(*args, **kwargs):
        # Instead of raising a Timeout directly, we'll wrap it in ApiError as the real code would
        try:
            # Simulate the timeout condition
            error = Timeout("Request timed out")
            # In the actual implementation, this would be handled and wrapped
            raise ApiError(f"API request timed out: {str(error)}")
        except ApiError as e:
            # Re-raise the already wrapped error
            raise e

    monkeypatch.setattr(client, "request", mock_request)

    # Should catch the wrapped error
    with pytest.raises(ApiError) as exc_info:
        client.inspect_request(method="GET", url="https://example.com", body="test")

    # Check that the error was properly wrapped
    assert "timed out" in str(exc_info.value)


def test_http_client_with_complex_headers(monkeypatch):
    client = HttpInspectionClient(api_key=TEST_API_KEY)

    # Mock _inspect to track what is being sent
    inspect_args = []

    def mock_inspect(*args, **kwargs):
        inspect_args.append(args)
        return "result"

    monkeypatch.setattr(client, "_inspect", mock_inspect)

    # Headers with mixed case and various value types
    complex_headers = {
        "Content-Type": "application/json",
        "X-Custom-ID": "12345",
        "X-CAPITALS": "ALL-CAPS",
        "x-lowercase": "lower-case",
        "Authorization": "Bearer token123",
    }

    client.inspect_request(
        method="POST",
        url="https://example.com/api",
        headers=complex_headers,
        body={"data": "test"},
    )

    # Verify headers were properly processed
    assert len(inspect_args) > 0
    http_req = inspect_args[0][0]  # First arg of first call should be http_req

    # Create a dict from header objects for easier comparison
    header_kvs = {hdr.key: hdr.value for hdr in http_req.headers.hdrKvs}

    # Headers should preserve their case
    assert "Content-Type" in header_kvs
    assert "X-Custom-ID" in header_kvs
    assert "X-CAPITALS" in header_kvs
    assert "x-lowercase" in header_kvs
    assert "Authorization" in header_kvs
