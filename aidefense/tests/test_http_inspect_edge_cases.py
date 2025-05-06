import pytest
import requests
from unittest.mock import MagicMock, patch

from aidefense.config import Config
from aidefense.runtime.http_inspect import HttpInspectionClient
from aidefense.runtime.models import InspectionConfig, Rule, RuleName
from aidefense.exceptions import ValidationError, ApiError

# Test API Key for all tests
TEST_API_KEY = "0123456789012345678901234567890123456789012345678901234567890123"


@pytest.fixture
def reset_config_singleton():
    """Reset the Config singleton before each test."""
    Config._instance = None
    yield
    Config._instance = None


@pytest.fixture
def client(reset_config_singleton):
    """Create a fresh HTTP client for each test."""
    return HttpInspectionClient(api_key=TEST_API_KEY)


def test_http_validate_with_empty_body_and_valid_method(client):
    """Test validation with empty body but valid method."""
    # This test will fail due to body validation (which happens first)
    with pytest.raises(ValidationError, match="must have a non-empty 'body'"):
        client.validate_inspection_request({
            "http_req": {
                "method": "GET", 
                "headers": {"content-type": "application/json"}, 
                "body": ""
            }
        })


def test_http_validate_request_valid_rule_list(client):
    """Test validation with valid config rule list."""
    # Create a valid inspection config with rules
    request = {
        "http_req": {
            "method": "GET", 
            "headers": {"content-type": "application/json"}, 
            "body": "dGVzdCBib2R5"  # base64 for "test body"
        },
        "config": {
            "enabled_rules": [
                {"rule_name": "PROMPT_INJECTION"}
            ]
        }
    }
    # Should validate successfully
    client.validate_inspection_request(request)


def test_http_validate_request_invalid_rule_list(client):
    """Test validation with invalid config rule list."""
    request = {
        "http_req": {
            "method": "GET", 
            "headers": {"content-type": "application/json"}, 
            "body": "dGVzdCBib2R5"  # base64 for "test body"
        },
        "config": {
            "enabled_rules": {}  # Invalid: should be a list
        }
    }
    with pytest.raises(ValidationError, match="config.enabled_rules must be a non-empty list"):
        client.validate_inspection_request(request)


def test_http_validate_request_empty_rule_list(client):
    """Test validation with empty config rule list."""
    request = {
        "http_req": {
            "method": "GET", 
            "headers": {"content-type": "application/json"}, 
            "body": "dGVzdCBib2R5"  # base64 for "test body"
        },
        "config": {
            "enabled_rules": []  # Invalid: should be non-empty
        }
    }
    with pytest.raises(ValidationError, match="config.enabled_rules must be a non-empty list"):
        client.validate_inspection_request(request)


def test_http_inspect_with_json_content_type(client):
    """Test HTTP inspection with JSON content type."""
    # Mock _inspect method to avoid actual API calls
    client._inspect = MagicMock(return_value="mock_result")
    
    result = client.inspect_request(
        method="POST",
        url="https://api.example.com",
        headers={"Content-Type": "application/json"},
        body='{"key": "value"}'
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
        body=binary_data
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
        body=""  # Empty string for 204 No Content
    )
    
    # Verify the result
    assert result == "mock_result"
    client._inspect.assert_called_once()


def test_http_inspect_with_large_body(client):
    """Test HTTP inspection with a large body."""
    # Mock _inspect method to avoid actual API calls
    client._inspect = MagicMock(return_value="mock_result")
    
    # Create a large body (50KB)
    large_body = "x" * 50000
    
    result = client.inspect_request(
        method="POST",
        url="https://api.example.com",
        headers={"Content-Type": "text/plain"},
        body=large_body
    )
    
    # Verify the result
    assert result == "mock_result"
    client._inspect.assert_called_once()


def test_request_id_passing(client):
    """Test passing request ID through the stack."""
    # Mock _inspect method to avoid actual API calls
    client._inspect = MagicMock(return_value="mock_result")
    
    custom_request_id = "test-request-123"
    result = client.inspect_request(
        method="GET",
        url="https://api.example.com",
        headers={"Content-Type": "text/plain"},
        body="test",
        request_id=custom_request_id
    )
    
    # Verify request_id was passed correctly
    assert result == "mock_result"
    args, kwargs = client._inspect.call_args
    assert kwargs["request_id"] == custom_request_id


def test_custom_timeout_passing(client):
    """Test passing custom timeout through the stack."""
    # Mock _inspect method to avoid actual API calls
    client._inspect = MagicMock(return_value="mock_result")
    
    custom_timeout = 60
    result = client.inspect_request(
        method="GET",
        url="https://api.example.com",
        headers={"Content-Type": "text/plain"},
        body="test",
        timeout=custom_timeout
    )
    
    # Verify timeout was passed correctly
    assert result == "mock_result"
    args, kwargs = client._inspect.call_args
    assert kwargs["timeout"] == custom_timeout
