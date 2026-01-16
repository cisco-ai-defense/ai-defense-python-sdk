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

"""
Example: View MCP Server security events using the AI Defense Python SDK.

This example demonstrates how to:
1. List recent MCP Server security events (automatically filtered to MCP_SERVER)
2. Get detailed event information
3. View event conversation history
4. Filter events by action (Block/Allow)

The MCPEventClient automatically filters events to resource_types=["MCP_SERVER"].

For general event management across all resource types, use
EventManagementClient from aidefense.management instead.
"""
import os
from datetime import datetime, timedelta

from aidefense import Config
from aidefense.mcpscan import (
    MCPEventClient,
    ListEventsRequest,
    EventSortBy,
)


def main():
    # Get API key from environment variable
    management_api_key = os.environ.get("AIDEFENSE_MANAGEMENT_API_KEY")
    management_base_url = os.environ.get(
        "AIDEFENSE_MANAGEMENT_BASE_URL", "https://api.security.cisco.com"
    )

    if not management_api_key:
        print("❌ Error: AIDEFENSE_MANAGEMENT_API_KEY environment variable is not set")
        return

    # Initialize the client
    client = MCPEventClient(
        api_key=management_api_key,
        config=Config(management_base_url=management_base_url),
    )

    # ===========================================
    # List Recent MCP Server Events
    # ===========================================
    print("📋 Listing Recent MCP Server Events...")
    print("=" * 50)

    # Get events from the last 7 days
    list_request = ListEventsRequest(
        limit=25,
        offset=0,
        #start_date=datetime.now() - timedelta(days=7),
        end_date=datetime.now(),
        expanded=True,
        sort_by=EventSortBy.event_timestamp,
        order="desc",
    )

    event_id = None

    try:
        # list_mcp_events automatically filters to resource_types=["MCP_SERVER"]
        events = client.list_mcp_events(list_request)

        if events.items:
            print(f"Found {len(events.items)} MCP Server events.\n")

            for event in events.items[:5]:  # Show first 5
                action_icon = "🚫" if event.event_action == "Block" else "✅"
                print(f"  {action_icon} Event: {event.event_id[:8]}...")
                print(f"     Date: {event.event_date}")
                print(f"     Action: {event.event_action}")
                if event.direction:
                    print(f"     Direction: {event.direction}")
                if event.policy:
                    print(f"     Policy: {event.policy.policy_name}")
                if event.rule_matches and event.rule_matches.items:
                    print(f"     Rule Matches: {len(event.rule_matches.items)}")
                    for match in event.rule_matches.items[:2]:
                        print(f"       - {match.guardrail_type}: {match.guardrail_ruleset_type}")
                print()

                # Save first event ID for later examples
                if not event_id:
                    event_id = event.event_id

            if len(events.items) > 5:
                print(f"  ... and {len(events.items) - 5} more events")
        else:
            print("No MCP Server events found in the last 7 days")

        if events.paging:
            print(f"\nPagination: offset={events.paging.offset}, total={events.paging.total}")

    except Exception as e:
        print(f"❌ Failed to list MCP events: {e}")

    if not event_id:
        print("\n⚠️ No events available for further examples")
        return

    # ===========================================
    # Get Event Details
    # ===========================================
    print(f"\n📝 Getting Event Details...")
    print("=" * 50)

    try:
        event = client.get_mcp_event(event_id=event_id, expanded=True)

        print(f"Event ID: {event.event_id}")
        print(f"  Date: {event.event_date}")
        print(f"  Action: {event.event_action}")
        print(f"  Direction: {event.direction}")

        if event.policy:
            print(f"\n  📋 Policy:")
            print(f"     Name: {event.policy.policy_name}")
            print(f"     ID: {event.policy.policy_id}")

        if event.connection:
            print(f"\n  🔗 Connection:")
            print(f"     Name: {event.connection.connection_name}")
            conn_type = getattr(event.connection, 'connection_type', 'Unknown')
            print(f"     Type: {conn_type}")

        if event.rule_matches and event.rule_matches.items:
            print(f"\n  🛡️ Rule Matches ({len(event.rule_matches.items)}):")
            for match in event.rule_matches.items:
                print(f"     • {match.guardrail_type}: {match.guardrail_ruleset_type}")
                print(f"       Action: {match.guardrail_action}")
                if match.metadata:
                    if match.metadata.techniques:
                        print(f"       Techniques: {', '.join(match.metadata.techniques)}")
                    if match.metadata.standards:
                        print(f"       Standards: {', '.join(match.metadata.standards)}")

    except Exception as e:
        print(f"❌ Failed to get event details: {e}")

    # ===========================================
    # Get Event Conversation
    # ===========================================
    print(f"\n💬 Getting Event Conversation...")
    print("=" * 50)

    try:
        result = client.get_mcp_event_conversation(event_id=event_id)

        print(f"Conversation ID: {result['event_conversation_id']}")

        if result['messages'] and result['messages'].items:
            print(f"\nMessages ({len(result['messages'].items)}):")
            for msg in result['messages'].items:
                direction_icon = "➡️" if msg.direction == "Prompt" else "⬅️"
                content_preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                print(f"\n  {direction_icon} [{msg.direction}]")
                print(f"     {content_preview}")
        else:
            print("No conversation messages found")

    except Exception as e:
        print(f"❌ Failed to get event conversation: {e}")

    # ===========================================
    # Filter by Event Action
    # ===========================================
    print(f"\n🚫 Filtering Blocked Events...")
    print("=" * 50)

    try:
        # Filter for blocked events only
        blocked_request = ListEventsRequest(
            limit=10,
            start_date=datetime.now() - timedelta(days=7),
            expanded=True,
            event_action="Block",
        )
        blocked_events = client.list_mcp_events(blocked_request)

        if blocked_events.items:
            print(f"Found {len(blocked_events.items)} blocked events:")
            for event in blocked_events.items[:3]:
                print(f"  • {event.event_id[:8]}... - {event.event_date}")
        else:
            print("No blocked events found in the last 7 days")

    except Exception as e:
        print(f"❌ Failed to filter blocked events: {e}")


if __name__ == "__main__":
    main()

