# Copyright 2026 Cisco Systems, Inc. and its affiliates
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

"""Tests for per-request API key override across runtime inspection clients."""

import pytest
from unittest.mock import Mock, AsyncMock

from aidefense import (
    ChatInspectionClient,
    AsyncChatInspectionClient,
    HttpInspectionClient,
    Config,
    AsyncConfig,
)
from aidefense.runtime.mcp_inspect import MCPInspectionClient
from aidefense.runtime.mcp_models import MCPMessage
from aidefense.exceptions import ValidationError


KEY_A = "a" * 64
KEY_B = "b" * 64
RESPONSE = {"is_safe": True, "classifications": [], "action": "Allow"}
MCP_RESPONSE = {"jsonrpc": "2.0", "result": RESPONSE, "id": 1}


@pytest.fixture(autouse=True)
def reset_config_singleton():
    Config._instances = {}
    AsyncConfig._instances = {}
    yield
    Config._instances = {}
    AsyncConfig._instances = {}


def _sent_auth(mock_handler):
    return mock_handler.request.call_args.kwargs["auth"]


def _make_chat(api_key):
    client = ChatInspectionClient(api_key=api_key, config=Config())
    client._request_handler = Mock()
    client._request_handler.request.return_value = RESPONSE
    return client


def _make_http(api_key):
    client = HttpInspectionClient(api_key=api_key, config=Config())
    client._request_handler = Mock()
    client._request_handler.VALID_HTTP_METHODS = ["GET", "POST", "PUT", "DELETE"]
    client._request_handler.request.return_value = RESPONSE
    return client


def _make_mcp(api_key):
    client = MCPInspectionClient(api_key=api_key, config=Config())
    client._request_handler = Mock()
    client._request_handler.request.return_value = MCP_RESPONSE
    return client


def _call_chat(client, api_key=None):
    return client.inspect_prompt("hello", api_key=api_key)


def _call_http(client, api_key=None):
    return client.inspect_request(
        method="POST", url="https://example.com", body="x", api_key=api_key
    )


def _call_mcp(client, api_key=None):
    msg = MCPMessage(jsonrpc="2.0", method="tools/call", params={"name": "t", "arguments": {}}, id=1)
    return client.inspect(message=msg, api_key=api_key)


SYNC_CLIENTS = [
    pytest.param(_make_chat, _call_chat, id="chat"),
    pytest.param(_make_http, _call_http, id="http"),
    pytest.param(_make_mcp, _call_mcp, id="mcp"),
]


@pytest.mark.parametrize("make_client, call", SYNC_CLIENTS)
def test_per_call_key_overrides_construction_key(make_client, call):
    client = make_client(KEY_A)
    call(client, api_key=KEY_B)
    assert _sent_auth(client._request_handler).token == KEY_B


@pytest.mark.parametrize("make_client, call", SYNC_CLIENTS)
def test_falls_back_to_construction_key(make_client, call):
    client = make_client(KEY_A)
    call(client)
    assert _sent_auth(client._request_handler).token == KEY_A


@pytest.mark.parametrize("make_client, call", SYNC_CLIENTS)
def test_no_construction_key_uses_per_call_key(make_client, call):
    client = make_client(None)
    assert client.auth is None
    call(client, api_key=KEY_B)
    assert _sent_auth(client._request_handler).token == KEY_B


@pytest.mark.parametrize("make_client, call", SYNC_CLIENTS)
def test_no_key_anywhere_raises(make_client, call):
    client = make_client(None)
    with pytest.raises(ValidationError):
        call(client)


@pytest.mark.parametrize("make_client, call", SYNC_CLIENTS)
def test_invalid_per_call_key_raises(make_client, call):
    client = make_client(KEY_A)
    with pytest.raises(ValueError):
        call(client, api_key="too-short")


@pytest.mark.asyncio
async def test_async_chat_per_request_key():
    client = AsyncChatInspectionClient(api_key=KEY_A, config=AsyncConfig())
    client._request_handler = AsyncMock()
    client._request_handler.request.return_value = RESPONSE

    await client.inspect_prompt("hello", api_key=KEY_B)
    assert client._request_handler.request.call_args.kwargs["auth"].token == KEY_B

    await client.inspect_prompt("hello")
    assert client._request_handler.request.call_args.kwargs["auth"].token == KEY_A


@pytest.mark.asyncio
async def test_async_chat_no_key_anywhere_raises():
    client = AsyncChatInspectionClient(config=AsyncConfig())
    client._request_handler = AsyncMock()
    assert client.auth is None
    with pytest.raises(ValidationError):
        await client.inspect_prompt("hello")
