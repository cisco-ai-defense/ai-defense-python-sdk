"""
Tests specifically designed to improve code coverage for the HTTP inspection module.
"""

import base64
import json
import pytest
import requests
from unittest.mock import MagicMock, patch
from aidefense import Config

from aidefense.runtime.http_inspect import HttpInspectionClient
from aidefense.runtime.models import InspectionConfig, Rule, RuleName
from aidefense.exceptions import ValidationError

# Test API key for all tests (must be 64 characters)
TEST_API_KEY = "a" * 64  # 64 character string


@pytest.fixture(autouse=True)
def reset_config_singleton():
    """Reset Config singleton before each test."""
    # Reset the singleton instance
    Config._instance = None

@pytest.fixture
def client():
    """Create a test HTTP inspection client."""
    return HttpInspectionClient(api_key=TEST_API_KEY)


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


def test_request_with_dict_body(client):
    """Test request with dictionary body to cover JSON conversion."""
    client._inspect = MagicMock(return_value="mock_result")
    
    # Dictionary body
    dict_body = {"message": "test", "nested": {"data": [1, 2, 3]}}
    
    result = client.inspect_request(
        method="POST",
        url="https://example.com",
        headers={"Content-Type": "application/json"},
        body=dict_body
    )
    
    assert result == "mock_result"
    client._inspect.assert_called_once()


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
        request_body=request_body
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
        request_body="test"
    )
    
    assert result == "mock_result"


def test_validation_for_config_enabled_rules(client):
    """Test validation for config with enabled rules."""
    # Valid request with valid config
    request = {
        "http_req": {
            "method": "GET",
            "headers": {},
            "body": base64.b64encode(b"test").decode()
        },
        "config": {
            "enabled_rules": [
                {"rule_name": "CUSTOM_RULE", "parameters": {"key": "value"}}
            ]
        }
    }
    
    # This should validate successfully
    client.validate_inspection_request(request)
    
    # Test empty rule list
    empty_rule_list_request = {
        "http_req": {
            "method": "GET",
            "headers": {},
            "body": base64.b64encode(b"test").decode()
        },
        "config": {
            "enabled_rules": []  # Empty list
        }
    }
    
    with pytest.raises(ValidationError, match="must be a non-empty list"):
        client.validate_inspection_request(empty_rule_list_request)


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


def test_build_http_req_from_http_library_with_none_body():
    """Test _build_http_req_from_http_library with None body."""
    import requests
    
    client = HttpInspectionClient(api_key=TEST_API_KEY)
    
    # Create a request with None body
    req = requests.Request("GET", "https://example.com").prepare()
    req.body = None
    
    http_req = client._build_http_req_from_http_library(req)
    assert http_req.body == ""  # Body should be empty string


def test_validation_of_response_with_invalid_body():
    """Test validation of HTTP response body types."""
    client = HttpInspectionClient(api_key=TEST_API_KEY)
    
    # Test with invalid body type (int)
    with pytest.raises(ValidationError):
        client.inspect_response(
            status_code=200,
            url="https://example.com",
            body=12345  # Invalid body type
        )


def test_validation_of_request_with_invalid_body():
    """Test validation of HTTP request body types."""
    client = HttpInspectionClient(api_key=TEST_API_KEY)
    
    # Test with invalid body type (int)
    with pytest.raises(ValidationError):
        client.inspect_request(
            method="POST",
            url="https://example.com",
            body=12345  # Invalid body type
        )
