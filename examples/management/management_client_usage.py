#!/usr/bin/env python3
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
Updated example script demonstrating how to use the AI Defense Management API.

This script shows how to:
1. Initialize the ManagementClient with the updated configuration
2. Create an application with API
3. Create a connection with a specific endpoint
4. Generate an API key for the connection
5. Use the API key to perform inspection
6. Manage policies and events

To run this script, you need to have a valid Management API key for the AI Defense Management API.
"""

import os
import time
from datetime import datetime, timedelta

from aidefense import Config, Message, Role
from aidefense.exceptions import ValidationError, ApiError, SDKError
from aidefense.management import ManagementClient
from aidefense.management.models import ApiKeyRequest
from aidefense.management.models.application import (
    CreateApplicationRequest,
    ListApplicationsRequest,
    UpdateApplicationRequest,
)
from aidefense.management.models.connection import (
    ConnectionType,
    EditConnectionOperationType,
    CreateConnectionRequest,
    UpdateConnectionRequest,
    ListConnectionsRequest,
)
from aidefense.management.models.event import ListEventsRequest
from aidefense.management.models.policy import (
    ListPoliciesRequest,
    AddOrUpdatePolicyConnectionsRequest,
    UpdatePolicyRequest,
)
from aidefense.runtime import ChatInspectionClient


def main():
    """Run the example."""
    # Get Management API key from environment variable
    global generated_key_id
    management_api_key = os.environ.get("AIDEFENSE_MANAGEMENT_API_KEY")
    if not management_api_key:
        print("Error: AIDEFENSE_MANAGEMENT_API_KEY environment variable not set.")
        print(
            "Please set the AIDEFENSE_MANAGEMENT_API_KEY environment variable to your AI Defense Management API key."
        )
        return

    # Initialize the ManagementClient with the updated configuration
    print("Initializing ManagementClient...")
    config = Config(
        management_base_url="https://api.security.cisco.com",
        timeout=60,  # Increase timeout for management API calls if needed,
        runtime_base_url="https://api.inspect.aidefense.aiteam.cisco.com",
    )
    client = ManagementClient(api_key=management_api_key, config=config)

    # Store created resources for later use
    created_app_id = None
    created_connection_id = None
    generated_api_key = None

    try:
        # Example 1: Create an application
        print("\n=== Example 1: Create Application ===")
        try:
            app_name = f"Test App {datetime.now().strftime('%Y%m%d%H%M%S')}"
            app_description = "Test application created via SDK example"

            print(f"Creating application '{app_name}'...")

            # Create a request model for application creation
            create_app_request = CreateApplicationRequest(
                application_name=app_name,
                description=app_description,
                connection_type=ConnectionType.API,
            )

            # Call the API with the request model
            result = client.applications.create_application(create_app_request)

            created_app_id = result.application_id
            print(f"Application created successfully!")
            print(f"ID: {created_app_id}")
        except SDKError as e:
            print(f"SDK error: {e}")

        # Example 1b: List and Get applications, then Update application
        print("\n=== Example 1b: List/Get/Update Applications ===")
        try:
            # List applications
            list_apps_req = ListApplicationsRequest(limit=5, order="asc")
            apps_resp = client.applications.list_applications(list_apps_req)
            print(f"Listed {len(apps_resp.applications.items)} applications")

            # Get the just-created application (or first available)
            target_app_id = created_app_id or (
                apps_resp.applications.items[0].application_id
                if apps_resp.applications.items
                else None
            )
            if target_app_id:
                app = client.applications.get_application(target_app_id, expanded=True)
                print(
                    f"Fetched application: {app.application_id} | {app.application_name}"
                )

                # Update application (rename)
                upd_req = UpdateApplicationRequest(
                    application_name=f"{app.application_name} - Updated",
                    description=app.description or "Updated via SDK example",
                )
                client.applications.update_application(target_app_id, upd_req)
                print("Application updated successfully!")
        except (ValidationError, ApiError, SDKError) as e:
            print(f"Management error (applications list/get/update): {e}")

        # Example 2: Create a connection with a specific endpoint
        print("\n=== Example 2: Create Connection with Specific Endpoint ===")
        try:
            if not created_app_id:
                print("Skipping connection creation as application creation failed.")
            else:
                connection_name = (
                    f"Test Connection {datetime.now().strftime('%Y%m%d%H%M%S')}"
                )
                key_name = f"test_key {datetime.now().strftime('%Y%m%d%H%M%S')}"

                # Create a request model for connection creation with an API key
                create_conn_request = CreateConnectionRequest(
                    application_id=created_app_id,
                    connection_name=connection_name,
                    connection_type=ConnectionType.API,
                    key={
                        "name": key_name,
                        "expiry": (datetime.now() + timedelta(days=30)).strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        ),
                    },
                )

                print(f"Creating connection '{connection_name}'...")
                result = client.connections.create_connection(create_conn_request)

                created_connection_id = result.connection_id
                print(f"Connection created successfully!")
                print(f"ID: {created_connection_id}")

                generated_key_id = ""
                # If an API key was generated as part of the connection creation
                if result.key:
                    generated_api_key = result.key.api_key
                    generated_key_id = result.key.key_id
                    print(
                        f"API Key: {generated_api_key[:5]}...{generated_api_key[-5:]} (masked for security)"
                    )
        except ValidationError as e:
            print(f"Validation error: {e}")
        except ApiError as e:
            print(f"API error: {e}")
        except SDKError as e:
            print(f"SDK error: {e}")

        # Example 2b: List/Get connections and Get API Keys
        print("\n=== Example 2b: List/Get Connections & API Keys ===")
        try:
            # List connections
            list_conns_req = ListConnectionsRequest(limit=5, order="asc")
            conns = client.connections.list_connections(list_conns_req)
            print(f"Listed {len(conns.items)} connections")

            # Get the just-created connection (or first available)
            target_conn_id = created_connection_id or (
                conns.items[0].connection_id if conns.items else None
            )
            if target_conn_id:
                conn = client.connections.get_connection(target_conn_id)
                print(
                    f"Fetched connection: {conn.connection_id} | {conn.connection_name}"
                )

                # Get API keys for the connection
                keys = client.connections.get_api_keys(target_conn_id)
                print(f"Fetched {len(keys.items)} API keys for connection")
        except (ValidationError, ApiError, SDKError) as e:
            print(f"Management error (connections list/get/keys): {e}")

        # Example 3: Generate an API key for the connection
        print("\n=== Example 3: Generate API Key ===")
        try:
            if not created_connection_id:
                print("Skipping API key generation as connection creation failed.")
            else:
                print(f"Generating API key for connection {created_connection_id}...")

                # Create a request model for API key generation
                api_key_request = ApiKeyRequest(
                    name=f"SDK Example Key {datetime.now().strftime('%Y%m%d%H%M%S')}",
                    expiry=datetime.now() + timedelta(days=30),
                )

                key_request = UpdateConnectionRequest(
                    key_id=generated_key_id,
                    operation_type=EditConnectionOperationType.REGENERATE_API_KEY,
                    key=api_key_request,
                )

                # Generate an API key for the connection
                result = client.connections.update_api_key(
                    created_connection_id, key_request
                )

                generated_api_key = result.api_key

                print("API key operation completed successfully!")

        except ValidationError as e:
            print(f"Validation error: {e}")
        except ApiError as e:
            print(f"API error: {e}")
        except SDKError as e:
            print(f"SDK error: {e}")

        # Example 4: Use the API key to perform inspection
        print("\n=== Example 4: Use API Key for Inspection ===")
        try:
            if not generated_api_key:
                print("Skipping inspection as API key generation failed.")
            else:
                print("Initializing ChatInspectionClient with the generated API key...")

                # Wait a moment for the API key to be fully activated
                time.sleep(2)

                # Perform a chat inspection
                print("Performing chat inspection...")
                chat_inspection_client = ChatInspectionClient(
                    api_key=generated_api_key, config=config
                )

                conversation = [
                    Message(
                        role=Role.USER, content="Hi, can you help me with my account?"
                    ),
                    Message(
                        role=Role.ASSISTANT, content="Sure, what do you need help with?"
                    ),
                ]

                inspection_result = chat_inspection_client.inspect_conversation(
                    conversation
                )
                print("Inspection completed successfully!")
                print(f"Inspection ID: {inspection_result.classifications}")
                print(f"Decision: {inspection_result.is_safe}")

        except ValidationError as e:
            print(f"Validation error: {e}")
        except ApiError as e:
            print(f"API error: {e}")
        except SDKError as e:
            print(f"SDK error: {e}")

        # Example 5: List policies
        print("\n=== Example 5: Policy Management ===")
        try:
            print("Listing available policies...")

            # Create a request model for listing policies
            list_policies_request = ListPoliciesRequest(
                limit=10, expanded=True, order="asc"  # Sort in ascending order
            )

            # Call the API with the request model
            policies = client.policies.list_policies(list_policies_request)

            print(f"Found {len(policies.items)} policies:")
            for policy in policies.items:
                print(f"  - {policy.policy_id}: {policy.policy_name}")

                # Print guardrails if available
                if policy.guardrails and policy.guardrails.items:
                    print("    Guardrails:")
                    for guardrail in policy.guardrails.items:
                        print(guardrail.guardrails_type)

            # Optionally get a specific policy by ID
            if policies.items:
                sample_policy_id = policies.items[0].policy_id
                pol = client.policies.get_policy(sample_policy_id)
                print(
                    f"Fetched policy: {pol.policy_id} | {pol.policy_name} | status={pol.status}"
                )

            print("\nPolicy listing completed successfully!")

        except ValidationError as e:
            print(f"Validation error: {e}")
        except ApiError as e:
            print(f"API error: {e}")
        except SDKError as e:
            print(f"SDK error: {e}")

        # Example 5b: Update a policy and update policy connections
        print("\n=== Example 5b: Update Policy & Policy Connections ===")
        try:
            # Pick a policy to update (first listed above if available)
            list_policies_req = ListPoliciesRequest(limit=1)
            pols = client.policies.list_policies(list_policies_req)
            if pols.items:
                policy_id = pols.items[0].policy_id
                print(f"Updating policy {policy_id}...")

                # Ensure updated policy name respects API limit (1-50 chars)
                base = (pols.items[0].policy_name or "Policy").strip()
                suffix = " - Updated"
                max_len = 50
                max_base_len = max_len - len(suffix)
                safe_base = base[:max_base_len].rstrip("- ")
                upd_policy_req = UpdatePolicyRequest(
                    name=f"{safe_base}{suffix}",
                    description=pols.items[0].description or "Updated by SDK example",
                    status=pols.items[0].status or "Enabled",
                )
                client.policies.update_policy(policy_id, upd_policy_req)
                print("Policy updated.")

                # Update policy connections if we have a created connection
                if created_connection_id:
                    print(
                        f"Associating connection {created_connection_id} with policy {policy_id}..."
                    )
                    assoc_req = AddOrUpdatePolicyConnectionsRequest(
                        connections_to_associate=[created_connection_id]
                    )
                    client.policies.update_policy_connections(policy_id, assoc_req)
                    print("Policy connections updated.")
            else:
                print("No policies available to update.")
        except (ValidationError, ApiError, SDKError) as e:
            print(f"Management error (update policy/associations): {e}")

        # Example 6: List events
        print("\n=== Example 6: Event Management ===")
        try:
            # List events from the last 24 hours
            end_time = datetime.now()
            start_time = end_time - timedelta(days=1)

            print(
                f"Listing events from {start_time.strftime('%Y-%m-%dT%H:%M:%SZ')} to {end_time.strftime('%Y-%m-%dT%H:%M:%SZ')}..."
            )

            # Create a request model for listing events
            list_events_request = ListEventsRequest(
                limit=5,
                start_date=start_time,
                end_date=end_time,
                expanded=True,
                sort_by="event_timestamp",
                order="desc",
            )

            events = client.events.list_events(list_events_request)

            print(f"Found {events.paging.total} events")

            # Print the events if available
            if events.items:
                print("\nRecent events:")
                for event in events.items:
                    print(
                        f"  - {event.event_id}: {event.event_date} - {event.event_action}"
                    )

                # Get details for the first event
                if events.items:
                    first_event = events.items[0]
                    print(f"\nGetting details for event {first_event.event_id}...")

                    # Get event details using the new method signature with separate ID parameter
                    event_detail = client.events.get_event(
                        first_event.event_id, expanded=True
                    )
                    print(f"Event action: {event_detail.event_action}")

                    # Get conversation for the event
                    print(f"\nGetting conversation for event {first_event.event_id}...")

                    # Get event conversation using the new method signature with separate ID parameter
                    conversation = client.events.get_event_conversation(
                        first_event.event_id, expanded=True
                    )

                    if "messages" in conversation and conversation["messages"].items:
                        print(
                            f"Found {len(conversation['messages'].items)} messages in conversation:"
                        )
                        for msg in conversation["messages"].items:
                            content_preview = (
                                msg.content[:50] + "..."
                                if len(msg.content) > 50
                                else msg.content
                            )
                            print(
                                f"  - {msg.direction} ({msg.role}): {content_preview}"
                            )
            else:
                print("No events found in the specified time range.")
        except ValidationError as e:
            print(f"Validation error: {e}")
        except ApiError as e:
            print(f"API error: {e}")
        except SDKError as e:
            print(f"SDK error: {e}")

    finally:
        # Clean up resources if needed
        print("\n=== Cleaning Up Resources ===")

        # In a real application, you might want to clean up the resources created during the example
        # Uncomment the following code to delete the created resources

        # Delete the connection if it was created
        if created_connection_id:
            try:
                print(f"Deleting connection {created_connection_id}...")
                client.connections.delete_connection(created_connection_id)
                print("Connection deleted successfully!")
            except Exception as e:
                print(f"Error deleting connection: {e}")

        # Delete the application if it was created
        if created_app_id:
            try:
                print(f"Deleting application {created_app_id}...")
                client.applications.delete_application(created_app_id)
                print("Application deleted successfully!")
            except Exception as e:
                print(f"Error deleting application: {e}")


if __name__ == "__main__":
    main()
