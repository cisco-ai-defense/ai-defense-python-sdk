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

"""MCP Event management client for AI Defense.

This module provides event management capabilities specifically for MCP Server
resources. Unlike the general EventManagementClient, this client automatically
filters events to only show those related to MCP Server resources.

For general event management across all resource types, use the
EventManagementClient from aidefense.management instead.
"""

from typing import Optional, Dict, Any

from aidefense.config import Config
from aidefense.management.auth import ManagementAuth
from aidefense.management.base_client import BaseClient
from aidefense.management.models.event import (
    Event,
    Events,
    EventMessages,
    ListEventsRequest,
)
from aidefense.management.routes import EVENTS, event_by_id, event_conversation

# MCP Server resource type for filtering events
MCP_SERVER_RESOURCE_TYPE = "MCP_SERVER"


class MCPEventClient(BaseClient):
    """
    Client for viewing MCP Server security events in AI Defense.

    This client provides methods for listing and retrieving security events
    related to MCP Server resources. Events include policy violations,
    guardrail triggers, and other security-related occurrences during MCP
    server interactions.

    It automatically filters events to resource_types=["MCP_SERVER"], making
    it easier to work with MCP-specific security events.

    For general event management across all resource types, use
    EventManagementClient from aidefense.management instead.

    Typical Usage:
        ```python
        from aidefense.mcpscan import MCPEventClient
        from aidefense.management.models.event import ListEventsRequest
        from aidefense import Config
        from datetime import datetime, timedelta

        # Initialize the client
        client = MCPEventClient(
            api_key="YOUR_MANAGEMENT_API_KEY",
            config=Config(management_base_url="https://api.security.cisco.com")
        )

        # List recent MCP Server events (automatically filtered)
        request = ListEventsRequest(
            limit=50,
            start_date=datetime.now() - timedelta(days=7),
            expanded=True
        )
        events = client.list_mcp_events(request)
        print(f"Found {len(events.items)} MCP Server events")
        for event in events.items:
            print(f"  - {event.event_date}: {event.event_action}")
        ```

    Attributes:
        Inherits all attributes from the base BaseClient class including:
        - auth: Authentication handler
        - config: Configuration object with service settings
    """

    def __init__(
            self,
            api_key: str,
            config: Optional[Config] = None,
            request_handler=None
    ):
        """
        Initialize an MCPEventClient instance.

        Args:
            api_key (str): Your Cisco AI Defense API key for authentication.
            config (Config, optional): SDK-level configuration for endpoints, logging, retries, etc.
                If not provided, a default Config instance is created.
            request_handler: Optional custom request handler for API requests.
        """
        super().__init__(ManagementAuth(api_key), config, request_handler)

    def list_mcp_events(self, request: Optional[ListEventsRequest] = None) -> Events:
        """
        List MCP Server security events.

        This method retrieves a paginated list of security events for MCP Server
        resources. It automatically filters to resource_types=["MCP_SERVER"].

        Args:
            request (ListEventsRequest, optional): Request object containing:
                - limit: Maximum number of events to return (default/max: 100)
                - offset: Number of events to skip for pagination
                - start_date: Start date for filtering events
                - end_date: End date for filtering events
                - expanded: Whether to include expanded event details
                - sort_by: Field to sort by (event_timestamp, rule_action, message_type)
                - order: Sort order ('asc' or 'desc')
                - event_action: Filter by action (Allow, Block)
                - direction: Filter by direction (Prompt, Response, Both)
                Note: resource_types is automatically set to ["MCP_SERVER"]

        Returns:
            Events: Object containing:
                - items: List of MCP Event objects
                - paging: Pagination information

        Raises:
            ValidationError: If request parameters are invalid.
            ApiError: If the API returns an error response.
            SDKError: For other SDK-related errors.

        Example:
            ```python
            from aidefense.mcpscan import MCPEventClient
            from aidefense.management.models.event import ListEventsRequest
            from datetime import datetime, timedelta

            client = MCPEventClient(api_key="YOUR_API_KEY")

            # List recent MCP events (automatically filtered to MCP_SERVER)
            request = ListEventsRequest(
                limit=50,
                start_date=datetime.now() - timedelta(days=7),
                expanded=True
            )
            events = client.list_mcp_events(request)

            print(f"Found {len(events.items)} MCP events")
            for event in events.items:
                print(f"  - {event.event_date}: {event.event_action}")
            ```
        """
        if request is None:
            request = ListEventsRequest()

        # Force MCP_SERVER resource type filter
        request.resource_types = [MCP_SERVER_RESOURCE_TYPE]

        data = request.to_body_dict()
        response = self.make_request("POST", EVENTS, data=data)
        events = self._parse_response(
            Events, response.get("events", {}), "list MCP events response"
        )
        return events

    def get_mcp_event(self, event_id: str, expanded: bool = False) -> Event:
        """
        Get an MCP event by its ID.

        This method retrieves the details of a specific security event.

        Args:
            event_id (str): The unique identifier of the event (UUID).
            expanded (bool): Whether to include expanded details like
                connection and policy information. Defaults to False.

        Returns:
            Event: Event object containing:
                - event_id: Event identifier
                - event_date: When the event occurred
                - application_id: Associated application ID
                - policy_id: Policy that triggered the event
                - connection_id: Connection where event occurred
                - event_action: Action taken (Allow, Block)
                - direction: Message direction (Prompt, Response)
                - rule_matches: Matched guardrail rules
                - connection: Connection details (when expanded=True)
                - policy: Policy details (when expanded=True)

        Raises:
            ValidationError: If the event_id is invalid.
            ApiError: If the API returns an error response.
            SDKError: For other SDK-related errors.

        Example:
            ```python
            from aidefense.mcpscan import MCPEventClient

            client = MCPEventClient(api_key="YOUR_API_KEY")

            event_id = "456e4567-e89b-12d3-a456-426614174456"
            event = client.get_mcp_event(event_id, expanded=True)

            print(f"Event: {event.event_id}")
            print(f"Action: {event.event_action}")
            print(f"Date: {event.event_date}")
            if event.rule_matches and event.rule_matches.items:
                for match in event.rule_matches.items:
                    print(f"  Rule: {match.guardrail_type} - {match.guardrail_action}")
            ```
        """
        self._ensure_uuid(event_id, "event_id")
        params = {"expanded": expanded} if expanded else None
        response = self.make_request("GET", event_by_id(event_id), params=params)
        event = self._parse_response(
            Event, response.get("event", {}), "get MCP event response"
        )
        return event

    def get_mcp_event_conversation(self, event_id: str) -> Dict[str, Any]:
        """
        Get the conversation associated with an MCP event.

        This method retrieves the full conversation (prompts and responses)
        that triggered or was affected by a security event.

        Args:
            event_id (str): The unique identifier of the event (UUID).

        Returns:
            Dict[str, Any]: Dictionary containing:
                - event_conversation_id: ID of the conversation
                - messages: EventMessages object with conversation messages
                    - items: List of EventMessage objects
                        - message_id: Message identifier
                        - event_id: Associated event ID
                        - message_date: When the message was sent
                        - content: Message content
                        - direction: Message direction (Prompt, Response)
                        - role: Message role

        Raises:
            ValidationError: If the event_id is invalid.
            ApiError: If the API returns an error response.
            SDKError: For other SDK-related errors.

        Example:
            ```python
            from aidefense.mcpscan import MCPEventClient

            client = MCPEventClient(api_key="YOUR_API_KEY")

            event_id = "456e4567-e89b-12d3-a456-426614174456"
            result = client.get_mcp_event_conversation(event_id)

            print(f"Conversation ID: {result['event_conversation_id']}")
            for message in result['messages'].items:
                print(f"  [{message.direction}] {message.content[:50]}...")
            ```
        """
        self._ensure_uuid(event_id, "event_id")
        response = self.make_request("GET", event_conversation(event_id))

        # Extract the event_conversation_id from the response
        event_conversation_id = response.get("event_conversation_id", "")

        # Parse the messages from the response
        messages = self._parse_response(
            EventMessages,
            response.get("messages", {}),
            "get MCP event conversation response",
        )

        return {"event_conversation_id": event_conversation_id, "messages": messages}

