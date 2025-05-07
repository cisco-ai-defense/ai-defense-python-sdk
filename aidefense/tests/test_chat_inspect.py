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
from aidefense import ChatInspectionClient, Config
from aidefense.runtime.chat_models import Message, Role
from aidefense.exceptions import ValidationError
import os
import uuid
from requests.exceptions import RequestException, Timeout


# Create a valid format dummy API key for testing (must be 64 characters)
TEST_API_KEY = "0123456789" * 6 + "0123"  # 64 characters


def test_chat_client_init_default():
    client = ChatInspectionClient(api_key=TEST_API_KEY)
    assert client.api_key == TEST_API_KEY
    assert client.endpoint


def test_chat_client_init_with_config():
    # Reset the Config singleton before this test
    Config._instance = None

    config = Config(runtime_base_url="https://custom.chat")
    client = ChatInspectionClient(api_key=TEST_API_KEY, config=config)
    assert client.config is config
    assert client.endpoint.startswith("https://custom.chat")


def test_inspect_prompt(monkeypatch):
    client = ChatInspectionClient(api_key=TEST_API_KEY)
    monkeypatch.setattr(client, "_inspect", lambda *a, **kw: "prompt_result")
    assert client.inspect_prompt("hi") == "prompt_result"


def test_inspect_response(monkeypatch):
    client = ChatInspectionClient(api_key=TEST_API_KEY)
    monkeypatch.setattr(client, "_inspect", lambda *a, **kw: "resp_result")
    assert client.inspect_response("ok") == "resp_result"


def test_inspect_conversation(monkeypatch):
    client = ChatInspectionClient(api_key=TEST_API_KEY)
    monkeypatch.setattr(client, "_inspect", lambda *a, **kw: "conv_result")
    msgs = [
        Message(role=Role.USER, content="hi"),
        Message(role=Role.ASSISTANT, content="ok"),
    ]
    assert client.inspect_conversation(msgs) == "conv_result"


# Tests for validation logic
def test_validate_inspection_request_empty_messages():
    client = ChatInspectionClient(api_key=TEST_API_KEY)
    with pytest.raises(ValidationError, match="'messages' must be a non-empty list"):
        client.validate_inspection_request({"messages": []})


def test_validate_inspection_request_non_list_messages():
    client = ChatInspectionClient(api_key=TEST_API_KEY)
    with pytest.raises(ValidationError, match="'messages' must be a non-empty list"):
        client.validate_inspection_request({"messages": "not a list"})


def test_validate_inspection_request_message_not_dict():
    client = ChatInspectionClient(api_key=TEST_API_KEY)
    with pytest.raises(ValidationError, match="Each message must be a dict"):
        client.validate_inspection_request({"messages": ["not a dict"]})


def test_validate_inspection_request_invalid_role():
    client = ChatInspectionClient(api_key=TEST_API_KEY)
    with pytest.raises(ValidationError, match="Message role must be one of"):
        client.validate_inspection_request({"messages": [{"role": "invalid_role", "content": "hi"}]})


def test_validate_inspection_request_empty_content():
    client = ChatInspectionClient(api_key=TEST_API_KEY)
    with pytest.raises(ValidationError, match="Each message must have non-empty string content"):
        client.validate_inspection_request({"messages": [{"role": "user", "content": ""}]})


def test_validate_inspection_request_no_prompt_or_completion():
    client = ChatInspectionClient(api_key=TEST_API_KEY)
    # Only system message, no user or assistant
    with pytest.raises(ValidationError, match="At least one message must be a prompt.*or completion"):
        client.validate_inspection_request({"messages": [{"role": "system", "content": "instruction"}]})


def test_validate_inspection_request_invalid_metadata():
    client = ChatInspectionClient(api_key=TEST_API_KEY)
    with pytest.raises(ValidationError, match="'metadata' must be a dict"):
        client.validate_inspection_request({
            "messages": [{"role": "user", "content": "valid content"}],
            "metadata": "not a dict"
        })


def test_validate_inspection_request_invalid_config():
    client = ChatInspectionClient(api_key=TEST_API_KEY)
    with pytest.raises(ValidationError, match="'config' must be a dict"):
        client.validate_inspection_request({
            "messages": [{"role": "user", "content": "valid content"}],
            "config": "not a dict"
        })


def test_validate_inspection_request_valid():
    client = ChatInspectionClient(api_key=TEST_API_KEY)
    # This should not raise any exception
    request_dict = {
        "messages": [
            {"role": "system", "content": "instruction"},
            {"role": "user", "content": "question"},
            {"role": "assistant", "content": "answer"}
        ],
        "metadata": {"user": "test_user"},
        "config": {"enabled_rules": []}
    }
    # If no exception is raised, the test passes
    client.validate_inspection_request(request_dict)


# Tests for error handling
def test_inspect_empty_messages():
    client = ChatInspectionClient(api_key=TEST_API_KEY)
    with pytest.raises(ValidationError, match="must be a non-empty list"):
        client._inspect([])


def test_inspect_network_error(monkeypatch):
    client = ChatInspectionClient(api_key=TEST_API_KEY)
    # Mock request method to simulate a network error
    def mock_request(*args, **kwargs):
        from requests.exceptions import RequestException
        raise RequestException("Network error")

    monkeypatch.setattr(client, "request", mock_request)
    with pytest.raises(RequestException, match="Network error"):
        client._inspect([Message(role=Role.USER, content="test")])


def test_inspect_timeout_handling(monkeypatch):
    client = ChatInspectionClient(api_key=TEST_API_KEY)
    # Mock request method to simulate a timeout
    def mock_request(*args, **kwargs):
        from requests.exceptions import Timeout
        raise Timeout("Request timed out")

    monkeypatch.setattr(client, "request", mock_request)
    with pytest.raises(Timeout, match="Request timed out"):
        client._inspect([Message(role=Role.USER, content="test")], timeout=5)


# Tests for edge cases
def test_inspect_with_empty_content():
    client = ChatInspectionClient(api_key=TEST_API_KEY)
    # Mock to avoid actual API call
    def mock_request(*args, **kwargs):
        return {"is_safe": True}

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(client, "request", mock_request)
    monkeypatch.setattr(client, "_parse_inspect_response", lambda x: x)
    # Also mock the validation method to allow empty content
    monkeypatch.setattr(client, "validate_inspection_request", lambda x: None)

    result = client._inspect([Message(role=Role.USER, content="")])
    # Should get a basic response even with empty content
    assert result == {"is_safe": True}


def test_inspect_with_very_long_content(monkeypatch):
    client = ChatInspectionClient(api_key=TEST_API_KEY)
    # Mock to avoid actual API call
    def mock_request(*args, **kwargs):
        # Check that the request was made with the long content
        content = kwargs.get("json_data", {}).get("messages", [{}])[0].get("content")
        assert content == "x" * 10000
        return {"is_safe": True}

    monkeypatch.setattr(client, "request", mock_request)
    monkeypatch.setattr(client, "_parse_inspect_response", lambda x: x)

    # Create a message with very long content
    result = client._inspect([Message(role=Role.USER, content="x" * 10000)])
    assert result == {"is_safe": True}


def test_chat_client_with_request_id():
    client = ChatInspectionClient(api_key=TEST_API_KEY)
    # Mock to check if request_id is properly passed
    def mock_request(*args, **kwargs):
        assert kwargs.get("request_id") == "test-request-id"
        return {"is_safe": True}

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(client, "request", mock_request)
    monkeypatch.setattr(client, "_parse_inspect_response", lambda x: x)

    client._inspect([Message(role=Role.USER, content="test")], request_id="test-request-id")
