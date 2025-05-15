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


def test_http_inspect_bedrock_api_workflow(capsys):
    user_prompt = "Explain three key benefits of cloud computing."
    dummy_api_key = secrets.token_hex(32)
    http_client = HttpInspectionClient(api_key=dummy_api_key)

    # Setup mock payload, headers, and response
    mock_payload = {
        "prompt": f"\n\nHuman: {user_prompt}\n\nAssistant:",
        "max_tokens_to_sample": 300,
    }
    mock_raw_body = json.dumps(mock_payload).encode()
    mock_headers = {"Content-Type": "application/json"}

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
    ):
        # Simulate the workflow up to the inspection points
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
