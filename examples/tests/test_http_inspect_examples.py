import pytest
from unittest.mock import patch, MagicMock
import secrets
from aidefense import HttpInspectionClient, Config
from aidefense.runtime.utils import to_base64_bytes
import requests


@pytest.fixture
def fake_client():
    dummy_api_key = secrets.token_hex(32)  # 32 bytes = 64 hex chars

    # Patch the HttpInspectionClient methods to avoid real API calls
    with patch.object(HttpInspectionClient, 'inspect',
                      return_value=MagicMock(is_safe=True, __str__=lambda self: "fake_result")) as mock_inspect, \
            patch.object(HttpInspectionClient, 'inspect_request', return_value=MagicMock(is_safe=True, __str__=lambda
                    self: "fake_result")) as mock_inspect_request, \
            patch.object(HttpInspectionClient, 'inspect_response', return_value=MagicMock(is_safe=True, __str__=lambda
                    self: "fake_result")) as mock_inspect_response, \
            patch.object(HttpInspectionClient, 'inspect_request_from_http_library', return_value=MagicMock(is_safe=True,
                                                                                                           __str__=lambda
                                                                                                                   self: "fake_result")) as mock_inspect_req_lib, \
            patch.object(HttpInspectionClient, 'inspect_response_from_http_library',
                         return_value=MagicMock(is_safe=True,
                                                __str__=lambda self: "fake_result")) as mock_inspect_resp_lib:
        yield HttpInspectionClient(api_key=dummy_api_key)


def test_http_inspect_api(fake_client):
    json_bytes = b'{"key": "value"}'
    http_req = {
        "method": "POST",
        "headers": {"Content-Type": "application/json"},
        "body": to_base64_bytes(json_bytes),
    }
    http_meta = {"url": "https://api.example.com/myendpoint"}
    result = fake_client.inspect(http_req=http_req, http_meta=http_meta)
    assert result.is_safe
    assert str(result) == "fake_result"


def test_http_inspect_multiple_clients():
    config = Config(logger_params={"level": "INFO"})
    dummy_api_key_1 = secrets.token_hex(32)
    dummy_api_key_2 = secrets.token_hex(32)
    with patch.object(HttpInspectionClient, 'inspect', return_value=MagicMock(is_safe=True)), \
            patch.object(HttpInspectionClient, 'inspect_request', return_value=MagicMock(is_safe=True)):
        client1 = HttpInspectionClient(api_key=dummy_api_key_1, config=config)
        client2 = HttpInspectionClient(api_key=dummy_api_key_2, config=config)
        json_bytes = b'{"key": "value"}'
        http_req = {
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": to_base64_bytes(json_bytes),
        }
        http_meta = {"url": "https://api.example.com/myendpoint"}
        result1 = client1.inspect(http_req=http_req, http_meta=http_meta)
        assert result1.is_safe
        result2 = client2.inspect_request(
            method="GET",
            url="https://example.com/endpoint",
            headers={"Accept": "application/json"},
            body=None,
        )
        assert result2.is_safe


def test_http_inspect_request(fake_client):
    result = fake_client.inspect_request(
        method="POST",
        url="https://api.example.com/endpoint",
        headers={"Authorization": "Bearer TOKEN", "Content-Type": "application/json"},
        body="{'key': 'value'}",
    )
    assert result.is_safe
    assert str(result) == "fake_result"


def test_http_inspect_request_from_http_library(fake_client):
    with patch("requests.Request.prepare", return_value=MagicMock()):
        req = requests.Request("GET", "https://example.com").prepare()
        result = fake_client.inspect_request_from_http_library(req)
        assert result.is_safe
        assert str(result) == "fake_result"


def test_http_inspect_response(fake_client):
    result = fake_client.inspect_response(
        status_code=200,
        url="https://api.example.com/endpoint",
        headers={"Content-Type": "application/json"},
        body='{"key": "value"}',
    )
    assert result.is_safe
    assert str(result) == "fake_result"


def test_http_inspect_response_from_http_library(fake_client):
    fake_response = MagicMock(spec=requests.Response)
    result = fake_client.inspect_response_from_http_library(fake_response)
    assert result.is_safe
    assert str(result) == "fake_result"
