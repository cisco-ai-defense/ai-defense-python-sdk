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

"""Event management client for the AI Defense Management API."""

from typing import Optional, Dict, Any

from .auth import ManagementAuth
from .base_client import BaseClient
from .models.event import (
    Event,
    Events,
    EventMessages,
    ListEventsRequest,
)
from ..config import Config
from .routes import EVENTS, event_by_id, event_conversation


class EventManagementClient(BaseClient):
    """
    Client for managing events in the AI Defense Management API.

    Provides methods for retrieving events and event details
    in the AI Defense Management API.
    """

    def __init__(
        self,
        auth: ManagementAuth,
        config: Optional[Config] = None,
        request_handler=None,
    ):
        """
        Initialize the EventManagementClient.

        Args:
            auth (ManagementAuth): Your AI Defense Management API authentication object.
            config (Config, optional): SDK configuration for endpoints, logging, retries, etc.
                Defaults to the singleton Config if not provided.
            request_handler: Request handler for making API requests (should be an instance of ManagementClient).
        """
        super().__init__(auth, config, request_handler)

    def list_events(self, request: ListEventsRequest) -> Events:
        """
        List events.

        Args:
            request: ListEventsRequest object containing optional parameters:
                - limit: Maximum number of events to return
                - offset: Number of events to skip
                - start_date: Start date for filtering events
                - end_date: End date for filtering events
                - expanded: Whether to include expanded event details
                - sort_by: Field to sort by
                - order: Sort order ('asc' or 'desc')

        Returns:
            Events: A list of events with pagination information.

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                request = ListEventsRequest(
                    limit=10,
                    start_date=datetime(2025, 5, 1),
                    end_date=datetime(2025, 6, 1),
                    sort_by=EventSortBy.event_timestamp,
                    order="desc"
                )
                events = client.events.list_events(request)
                for event in events.items:
                    print(f"{event.event_id}: {event.event_date}")
        """
        # Prepare data for the POST request using model serializer
        data = request.to_body_dict()

        response = self.make_request("POST", EVENTS, data=data)
        events = self._parse_response(
            Events, response.get("events", {}), "list events response"
        )
        return events

    def get_event(self, event_id: str, expanded: bool = None) -> Event:
        """
        Get an event by ID.

        Args:
            event_id (str): ID of the event
            expanded (bool, optional): Whether to include expanded details

        Returns:
            Event: The event details.

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                event_id = "456e4567-e89b-12d3-a456-426614174456"
                event = client.events.get_event(event_id, expanded=True)
                print(f"Event action: {event.event_action}")
        """
        # Validate IDs
        self._ensure_uuid(event_id, "event_id")
        params = {"expanded": expanded} if expanded is not None else None
        response = self.make_request("GET", event_by_id(event_id), params=params)
        event = self._parse_response(
            Event, response.get("event", {}), "get event response"
        )
        return event

    def get_event_conversation(self, event_id: str) -> Dict[str, Any]:
        """
        Get conversation for an event.

        Args:
            event_id (str): ID of the event

        Returns:
            Dict[str, Any]: Dictionary containing:
                - event_conversation_id: ID of the event conversation
                - messages: EventMessages object with conversation messages

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                event_id = "456e4567-e89b-12d3-a456-426614174456"
                result = client.events.get_event_conversation(event_id, expanded=True)
                print(f"Conversation ID: {result['event_conversation_id']}")
                for message in result['messages'].items:
                    print(f"{message.direction}: {message.content}")
        """
        response = self.make_request("GET", event_conversation(event_id))

        # Extract the event_conversation_id from the response
        event_conversation_id = response.get("event_conversation_id", "")

        # Parse the messages from the response
        messages = self._parse_response(
            EventMessages,
            response.get("messages", {}),
            "get event conversation response",
        )

        # Return a dictionary with both the ID and messages
        return {"event_conversation_id": event_conversation_id, "messages": messages}
