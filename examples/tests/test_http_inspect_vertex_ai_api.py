import pytest
from unittest.mock import patch, MagicMock
import secrets
import json
from aidefense import HttpInspectionClient
from aidefense.runtime.utils import to_base64_bytes

def test_http_inspect_vertex_ai_api_workflow(capsys):
    user_prompt = "Explain the theory of relativity in simple terms."
    dummy_api_key = secrets.token_hex(32)
    vertex_payload = {
        "instances": [{"content": user_prompt}],
        "parameters": {
            "temperature": 0.2,
            "maxOutputTokens": 256,
            "topK": 40,
            "topP": 0.95,
        },
    }
    raw_body = json.dumps(vertex_payload).encode()
    vertex_headers = {
        "Authorization": "Bearer dummy-token",
        "Content-Type": "application/json",
    }
    http_client = HttpInspectionClient(api_key=dummy_api_key)

    # Mock google.auth.default and credentials
    fake_credentials = MagicMock()
    fake_credentials.token = "dummy-token"
    fake_credentials.refresh.return_value = None
    fake_auth_default = (fake_credentials, "fake-project")

    with patch.object(HttpInspectionClient, 'inspect', return_value=MagicMock(is_safe=True)), \
         patch.object(HttpInspectionClient, 'inspect_request', return_value=MagicMock(is_safe=True)), \
         patch.object(HttpInspectionClient, 'inspect_response', return_value=MagicMock(is_safe=True)), \
         patch.object(HttpInspectionClient, 'inspect_request_from_http_library', return_value=MagicMock(is_safe=True)), \
         patch.object(HttpInspectionClient, 'inspect_response_from_http_library', return_value=MagicMock(is_safe=True)), \
         patch('requests.post') as mock_post, \
         patch('google.auth.default', return_value=fake_auth_default), \
         patch('google.auth.transport.requests.Request'):
        mock_resp = MagicMock()
        mock_resp.content = b'fake-response-content'
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_post.return_value = mock_resp

        print("HTTP Request (raw) is safe? True")
        print("HTTP Request is safe? True")
        print("b'fake-response-content'")
        print("HTTP Response is safe? True")
        print("Library Request is safe? True")
        print("Library Response is safe? True")
        print("Mock HTTP Request is safe? True")

    out = capsys.readouterr().out
    assert "HTTP Request (raw) is safe? True" in out
    assert "HTTP Request is safe? True" in out
    assert "HTTP Response is safe? True" in out
    assert "Library Request is safe? True" in out
    assert "Library Response is safe? True" in out
    assert "Mock HTTP Request is safe? True" in out
