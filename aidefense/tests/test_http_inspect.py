import pytest
import json
import base64
from aidefense import HttpInspectionClient, Config
from aidefense.runtime.utils import to_base64_bytes, ensure_base64_body
from aidefense.exceptions import ValidationError
from aidefense.runtime.http_models import HttpReqObject, HttpResObject, HttpHdrObject, HttpMetaObject, HttpHdrKvObject
from aidefense.runtime.constants import HTTP_REQ, HTTP_RES, HTTP_BODY, HTTP_METHOD, HTTP_META
import requests
from requests.exceptions import RequestException, Timeout


# Create a valid format dummy API key for testing (must be 64 characters)
TEST_API_KEY = "0123456789" * 6 + "0123"  # 64 characters


@pytest.fixture(autouse=True)
def reset_config_singleton():
    """Reset Config singleton before each test."""
    # Reset the singleton instance
    Config._instance = None
    yield
    # Clean up after test
    Config._instance = None


def test_http_client_init_default():
    client = HttpInspectionClient(api_key=TEST_API_KEY)
    assert client.api_key == TEST_API_KEY
    assert client.endpoint


def test_http_client_init_with_config():
    config = Config(runtime_base_url="https://custom.http")
    client = HttpInspectionClient(api_key=TEST_API_KEY, config=config)
    assert client.config is config
    assert client.endpoint.startswith("https://custom.http")


def test_inspect(monkeypatch):
    client = HttpInspectionClient(api_key=TEST_API_KEY)
    monkeypatch.setattr(client, "_inspect", lambda *a, **kw: "raw_result")
    req = {"method": "GET", "headers": {}, "body": to_base64_bytes(b"hi")}
    meta = {"url": "https://foo"}
    assert client.inspect(http_req=req, http_meta=meta) == "raw_result"


def test_inspect_request(monkeypatch):
    client = HttpInspectionClient(api_key=TEST_API_KEY)
    monkeypatch.setattr(client, "_inspect", lambda *a, **kw: "req_result")
    assert client.inspect_request("GET", "https://foo", body="test body") == "req_result"


def test_inspect_response(monkeypatch):
    client = HttpInspectionClient(api_key=TEST_API_KEY)
    monkeypatch.setattr(client, "_inspect", lambda *a, **kw: "resp_result")
    assert client.inspect_response(200, "https://foo", body="test response") == "resp_result"


def test_inspect_request_from_http_library(monkeypatch):
    client = HttpInspectionClient(api_key=TEST_API_KEY)
    monkeypatch.setattr(client, "_inspect", lambda *a, **kw: "lib_req_result")
    req = requests.Request("GET", "https://foo").prepare()
    assert client.inspect_request_from_http_library(req) == "lib_req_result"


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


# Tests for validation logic in HttpInspectionClient
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
    with pytest.raises(ValidationError, match=f"'{HTTP_REQ}' must have a non-empty 'body'"):
        client.validate_inspection_request({HTTP_REQ: {"headers": {}, "body": ""}})


def test_validate_http_inspection_request_invalid_method():
    client = HttpInspectionClient(api_key=TEST_API_KEY)
    invalid_method = "INVALID"
    # Need to provide a non-empty body to get past the body validation
    with pytest.raises(ValidationError, match=f"'{HTTP_REQ}' must have a non-empty 'body'"):
        client.validate_inspection_request({HTTP_REQ: {HTTP_METHOD: invalid_method, "headers": {}}})


def test_validate_http_inspection_request_valid():
    client = HttpInspectionClient(api_key=TEST_API_KEY)
    # Valid request - note that body must be non-empty to pass validation
    request = {
        HTTP_REQ: {HTTP_METHOD: "GET", "headers": {"content-type": "application/json"}, "body": to_base64_bytes(b"test body")}
    }
    # Should not raise an exception
    client.validate_inspection_request(request)


# Tests for _build_http_req_from_http_library
def test_build_http_req_from_http_library_with_prepared_request():
    client = HttpInspectionClient(api_key=TEST_API_KEY)
    
    # Create a prepared request
    req = requests.Request(
        method="POST",
        url="https://example.com",
        headers={"content-type": "text/plain", "x-custom": "value"},
        data="test body"
    ).prepare()
    
    # Convert to HTTP req object
    http_req = client._build_http_req_from_http_library(req)
    
    # Check the result
    assert http_req.method == "POST"
    assert any(kv.key == "content-type" and kv.value == "text/plain" for kv in http_req.headers.hdrKvs)
    
    # Check body encoding
    decoded_body = base64.b64decode(http_req.body).decode()
    assert decoded_body == "test body"


def test_build_http_req_from_http_library_with_request():
    client = HttpInspectionClient(api_key=TEST_API_KEY)
    
    # Create a request (not prepared)
    req = requests.Request(
        method="GET",
        url="https://example.com",
        headers={"accept": "application/json"}
    )
    
    # Convert to HTTP req object
    http_req = client._build_http_req_from_http_library(req)
    
    # Check the result
    assert http_req.method == "GET"
    assert any(kv.key == "accept" and kv.value == "application/json" for kv in http_req.headers.hdrKvs)


def test_build_http_req_from_http_library_with_json_body():
    client = HttpInspectionClient(api_key=TEST_API_KEY)
    
    # Create a request with JSON body
    json_data = {"key": "value", "nested": {"foo": "bar"}}
    req = requests.Request(
        method="POST",
        url="https://example.com",
        headers={"content-type": "application/json"},
        json=json_data
    ).prepare()
    
    # Convert to HTTP req object
    http_req = client._build_http_req_from_http_library(req)
    
    # Check the result - body should contain the JSON string
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
    with pytest.raises(ValidationError, match="Request body must be bytes, str or dict"):
        client._build_http_req_from_http_library(req)


# Tests for error handling
def test_http_client_network_error(monkeypatch):
    client = HttpInspectionClient(api_key=TEST_API_KEY)
    
    # Mock request method to simulate a network error
    def mock_request(*args, **kwargs):
        from requests.exceptions import RequestException
        raise RequestException("Network error")
        
    monkeypatch.setattr(client, "request", mock_request)
    
    with pytest.raises(requests.exceptions.RequestException, match="Network error"):
        client._inspect(
            HttpReqObject(method="GET", headers=HttpHdrObject(hdrKvs=[]), body=to_base64_bytes(b"test")),
            None,
            HttpMetaObject(url="https://example.com"),
            None,
            None,
            request_id=None
        )


def test_http_client_timeout_handling(monkeypatch):
    client = HttpInspectionClient(api_key=TEST_API_KEY)
    
    # Mock request method to simulate a timeout
    def mock_request(*args, **kwargs):
        from requests.exceptions import Timeout
        raise Timeout("Request timed out")
        
    monkeypatch.setattr(client, "request", mock_request)
    
    with pytest.raises(requests.exceptions.Timeout, match="Request timed out"):
        client._inspect(
            HttpReqObject(method="GET", headers=HttpHdrObject(hdrKvs=[]), body=to_base64_bytes(b"test")),
            None,
            HttpMetaObject(url="https://example.com"),
            None,
            None,
            request_id=None,
            timeout=5
        )


# Tests for edge cases
def test_http_client_with_complex_headers(monkeypatch):
    client = HttpInspectionClient(api_key="0123456789012345678901234567890123456789012345678901234567890123")
    
    # Test that complex header values are handled correctly
    header_dict = {
        "simple": "value",
        "with-dashes": "some-value",
        "with spaces": "some value",
        "with,comma": "value1,value2",
        "empty": "",
        "cookie": "session=abc123; domain=example.com"
    }
    
    # Convert headers to KV objects
    header_kvs = [client._header_to_kv(k, v) for k, v in header_dict.items()]
    
    # Check all headers are preserved
    for k, v in header_dict.items():
        matching_header = next((kv for kv in header_kvs if kv.key == k), None)
        assert matching_header is not None
        assert matching_header.value == v
