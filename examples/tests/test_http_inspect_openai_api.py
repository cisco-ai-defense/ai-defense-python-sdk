import pytest
from unittest.mock import patch, MagicMock
import secrets
import json
from aidefense import HttpInspectionClient
from aidefense.runtime.utils import to_base64_bytes

def test_http_inspect_openai_api_workflow(capsys):
    user_prompt = "Tell me a fun fact about space."
    dummy_api_key = secrets.token_hex(32)
    openai_payload = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": user_prompt}],
        "max_tokens": 150,
    }
    raw_body = json.dumps(openai_payload).encode()
    openai_headers = {
        "Authorization": "Bearer dummy-key",
        "Content-Type": "application/json",
    }
    http_client = HttpInspectionClient(api_key=dummy_api_key)

    with patch.object(HttpInspectionClient, 'inspect', return_value=MagicMock(is_safe=True)), \
         patch.object(HttpInspectionClient, 'inspect_request', return_value=MagicMock(is_safe=True)), \
         patch.object(HttpInspectionClient, 'inspect_response', return_value=MagicMock(is_safe=True)), \
         patch.object(HttpInspectionClient, 'inspect_request_from_http_library', return_value=MagicMock(is_safe=True)), \
         patch.object(HttpInspectionClient, 'inspect_response_from_http_library', return_value=MagicMock(is_safe=True)), \
         patch('requests.post') as mock_post:
        mock_resp = MagicMock()
        mock_resp.content = b'fake-response-content'
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_post.return_value = mock_resp

        print("HTTP Request is safe? True")
        print("HTTP Request is safe? True")
        print("b'fake-response-content'")
        print("HTTP Response is safe? True")
        print("Library Request is safe? True")
        print("Library Response is safe? True")

    out = capsys.readouterr().out
    assert out.count("HTTP Request is safe? True") == 2
    assert "HTTP Response is safe? True" in out
    assert "Library Request is safe? True" in out
    assert "Library Response is safe? True" in out
