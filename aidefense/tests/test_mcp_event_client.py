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
from unittest.mock import MagicMock

from aidefense.mcpscan import MCPEventClient
from aidefense.management.models.event import (
    Events,
    ListEventsRequest,
)
from aidefense.config import Config
from aidefense.exceptions import ApiError


# Create a valid format dummy API key for testing
TEST_API_KEY = "0123456789" * 6 + "0123"  # 64 characters


@pytest.fixture(autouse=True)
def reset_config_singleton():
    """Reset Config singleton before each test."""
    Config._instance = None
    yield
    Config._instance = None


@pytest.fixture
def mock_request_handler():
    """Create a mock request handler."""
    return MagicMock()


@pytest.fixture
def mcp_event_client(mock_request_handler):
    """Create an MCPEventClient with a mock request handler."""
    client = MCPEventClient(
        api_key=TEST_API_KEY, request_handler=mock_request_handler
    )
    client.make_request = MagicMock()
    return client


class TestMCPEventClient:
    """Tests for the MCPEventClient."""

    def test_client_initialization(self):
        """Test MCPEventClient can be instantiated."""
        client = MCPEventClient(api_key=TEST_API_KEY)
        assert client is not None

    def test_list_mcp_events(self, mcp_event_client):
        """Test listing MCP Gateway events."""
        mock_response = {
            "events": {
                "items": [
                    {
                        "event_id": "event-123",
                        "event_type": "Security",
                        "connection_id": "conn-456",
                        "policy_id": "policy-789",
                        "created_at": "2025-01-01T00:00:00Z",
                        "action": "Block",
                    },
                ],
                "paging": {"total": 1, "count": 1, "offset": 0},
            }
        }
        mcp_event_client.make_request.return_value = mock_response

        request = ListEventsRequest(limit=25)

        response = mcp_event_client.list_mcp_events(request)

        mcp_event_client.make_request.assert_called_once()
        assert isinstance(response, Events)
        assert len(response.items) == 1
        assert response.items[0].event_id == "event-123"

    def test_list_mcp_events_default_request(self, mcp_event_client):
        """Test listing MCP Gateway events with default request."""
        mock_response = {
            "events": {
                "items": [],
                "paging": {"total": 0, "count": 0, "offset": 0},
            }
        }
        mcp_event_client.make_request.return_value = mock_response

        response = mcp_event_client.list_mcp_events()

        mcp_event_client.make_request.assert_called_once()
