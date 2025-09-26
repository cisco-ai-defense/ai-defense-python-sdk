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
from unittest.mock import MagicMock, patch
from datetime import datetime

from aidefense.management.events import EventManagementClient
from aidefense.management.auth import ManagementAuth
from aidefense.management.models.event import (
    Event,
    Events,
    EventSortBy,
    EventMessage,
    EventMessages,
    ListEventsRequest,
)
from aidefense.management.models.common import Paging
from aidefense.config import Config
from aidefense.exceptions import ValidationError, ApiError, SDKError


# Create a valid format dummy API key for testing
TEST_API_KEY = "0123456789" * 6 + "0123"  # 64 characters


@pytest.fixture(autouse=True)
def reset_config_singleton():
    """Reset Config singleton before each test."""
    # Reset the singleton instance
    Config._instance = None
    yield
    # Clean up after test
    Config._instance = None


@pytest.fixture
def mock_request_handler():
    """Create a mock request handler."""
    mock_handler = MagicMock()
    return mock_handler


@pytest.fixture
def event_client(mock_request_handler):
    """Create an EventManagementClient with a mock request handler."""
    client = EventManagementClient(
        auth=ManagementAuth(TEST_API_KEY), request_handler=mock_request_handler
    )
    # Replace the make_request method with a mock
    client.make_request = MagicMock()
    return client


class TestEventManagementClient:
    """Tests for the EventManagementClient."""

    def test_list_events(self, event_client):
        """Test listing events."""
        # Setup mock response
        mock_response = {
            "events": {
                "items": [
                    {
                        "event_id": "event-123",
                        "event_date": "2025-01-01T00:00:00Z",
                        "application_id": "app-123",
                        "policy_id": "policy-123",
                        "connection_id": "conn-123",
                        "event_action": "block",
                        "message_id": "msg-123",
                        "direction": "outbound",
                        "model_name": "gpt-4",
                    },
                    {
                        "event_id": "event-456",
                        "event_date": "2025-01-02T00:00:00Z",
                        "application_id": "app-456",
                        "policy_id": "policy-456",
                        "connection_id": "conn-456",
                        "event_action": "allow",
                        "message_id": "msg-456",
                        "direction": "inbound",
                        "model_name": "gpt-3.5-turbo",
                    },
                ],
                "paging": {"total": 2, "count": 2, "offset": 0},
            }
        }
        event_client.make_request.return_value = mock_response

        # Create request
        start_date = datetime(2025, 1, 1)
        end_date = datetime(2025, 1, 31)
        request = ListEventsRequest(
            limit=10,
            offset=0,
            start_date=start_date,
            end_date=end_date,
            expanded=True,
            sort_by=EventSortBy.event_timestamp,
            order="desc",
        )

        # Call the method
        response = event_client.list_events(request)

        # Verify the make_request call
        event_client.make_request.assert_called_once_with(
            "POST",
            "events",
            data={
                "limit": 10,
                "offset": 0,
                "start_date": "2025-01-01T00:00:00Z",
                "end_date": "2025-01-31T00:00:00Z",
                "expanded": True,
                "sort_by": "event_timestamp",
                "order": "desc",
            },
        )

        # Verify the response
        assert isinstance(response, Events)
        assert len(response.items) == 2
        assert response.items[0].event_id == "event-123"
        assert response.items[0].event_action == "block"
        assert response.items[1].event_id == "event-456"
        assert response.items[1].event_action == "allow"
        assert response.paging.total == 2
        assert response.paging.count == 2
        assert response.paging.offset == 0

    def test_get_event(self, event_client):
        """Test getting an event by ID."""
        # Setup mock response
        mock_response = {
            "event": {
                "event_id": "event-123",
                "event_date": "2025-01-01T00:00:00Z",
                "application_id": "app-123",
                "policy_id": "policy-123",
                "connection_id": "conn-123",
                "event_action": "block",
                "message_id": "msg-123",
                "direction": "outbound",
                "model_name": "gpt-4",
                "rule_matches": {
                    "items": [
                        {
                            "guardrail_type": "Security",
                            "guardrail_ruleset_type": "security_ruleset",
                            "guardrail_entity": "security_entity",
                            "guardrail_action": "block",
                            "metadata": {
                                "standards": ["PCI DSS", "GDPR"],
                                "techniques": ["T1234"],
                            },
                        }
                    ]
                },
            }
        }
        event_client.make_request.return_value = mock_response

        # Call the method
        event_id = "456e4567-e89b-12d3-a456-426614174456"
        response = event_client.get_event(event_id, expanded=True)

        # Verify the make_request call
        event_client.make_request.assert_called_once_with(
            "GET", f"events/{event_id}", params={"expanded": True}
        )

        # Verify the response
        assert isinstance(response, Event)
        assert response.event_id == "event-123"
        assert response.event_action == "block"
        assert response.application_id == "app-123"
        assert response.policy_id == "policy-123"
        assert response.connection_id == "conn-123"
        assert response.rule_matches is not None
        assert len(response.rule_matches.items) == 1
        assert response.rule_matches.items[0].guardrail_type == "Security"
        assert response.rule_matches.items[0].guardrail_action == "block"
        assert "PCI DSS" in response.rule_matches.items[0].metadata.standards

    def test_get_event_conversation(self, event_client):
        """Test getting a conversation for an event."""
        # Setup mock response
        mock_response = {
            "event_conversation_id": "conv-123",
            "messages": {
                "items": [
                    {
                        "message_id": "msg-123",
                        "event_id": "event-123",
                        "message_date": "2025-01-01T00:00:00Z",
                        "content": "Hello, how can I help you?",
                        "direction": "inbound",
                        "role": "assistant",
                    },
                    {
                        "message_id": "msg-456",
                        "event_id": "event-123",
                        "message_date": "2025-01-01T00:01:00Z",
                        "content": "I need help with security.",
                        "direction": "outbound",
                        "role": "user",
                    },
                ],
                "paging": {"total": 2, "count": 2, "offset": 0},
            },
        }
        event_client.make_request.return_value = mock_response

        # Call the method
        event_id = "456e4567-e89b-12d3-a456-426614174456"
        response = event_client.get_event_conversation(event_id)

        # Verify the make_request call
        event_client.make_request.assert_called_once_with(
            "GET", f"events/{event_id}/conversation"
        )

        # Verify the response
        assert isinstance(response, dict)
        assert response["event_conversation_id"] == "conv-123"
        assert "messages" in response
        assert isinstance(response["messages"], EventMessages)
        assert len(response["messages"].items) == 2
        assert response["messages"].items[0].message_id == "msg-123"
        assert response["messages"].items[0].content == "Hello, how can I help you?"
        assert response["messages"].items[0].role == "assistant"
        assert response["messages"].items[1].message_id == "msg-456"
        assert response["messages"].items[1].content == "I need help with security."
        assert response["messages"].items[1].role == "user"
        assert response["messages"].paging.total == 2
        assert response["messages"].paging.count == 2
        assert response["messages"].paging.offset == 0

    def test_error_handling(self, event_client):
        """Test error handling in the client."""
        # Setup mock to raise an exception
        event_client.make_request.side_effect = ApiError("API Error", 400)

        # Create request
        request = ListEventsRequest(limit=10)

        # Verify that the exception is propagated
        with pytest.raises(ApiError) as excinfo:
            event_client.list_events(request)

        assert "API Error" in str(excinfo.value)
