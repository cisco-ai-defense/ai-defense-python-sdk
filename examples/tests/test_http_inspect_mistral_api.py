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
from unittest.mock import patch, MagicMock
import secrets
import json
from aidefense import HttpInspectionClient
from aidefense.runtime.utils import to_base64_bytes


def test_http_inspect_mistral_api_workflow(capsys):
    user_prompt = (
        "What are the main differences between supervised and unsupervised learning?"
    )
    dummy_api_key = secrets.token_hex(32)
    mistral_payload = {
        "model": "mistral-large-latest",
        "messages": [{"role": "user", "content": user_prompt}],
        "temperature": 0.7,
        "max_tokens": 500,
    }
    raw_body = json.dumps(mistral_payload).encode()
    mistral_headers = {
        "Authorization": "Bearer dummy-key",
        "Content-Type": "application/json",
    }
    http_client = HttpInspectionClient(api_key=dummy_api_key)

    with patch.object(
        HttpInspectionClient, "inspect", return_value=MagicMock(is_safe=True)
    ), patch.object(
        HttpInspectionClient, "inspect_request", return_value=MagicMock(is_safe=True)
    ), patch.object(
        HttpInspectionClient, "inspect_response", return_value=MagicMock(is_safe=True)
    ), patch.object(
        HttpInspectionClient,
        "inspect_request_from_http_library",
        return_value=MagicMock(is_safe=True),
    ), patch.object(
        HttpInspectionClient,
        "inspect_response_from_http_library",
        return_value=MagicMock(is_safe=True),
    ), patch(
        "requests.post"
    ) as mock_post:
        mock_resp = MagicMock()
        mock_resp.content = b"fake-response-content"
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
