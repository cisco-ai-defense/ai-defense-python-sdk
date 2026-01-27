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
Example: Manage resource connections using the AI Defense Python SDK.

This example demonstrates how to:
1. Create resource connections for MCP servers
2. List and filter resource connections
3. Associate/disassociate resources with connections
4. Delete resource connections
"""
import os

from aidefense import Config
from aidefense.mcpscan import ResourceConnectionClient
from aidefense.mcpscan.models import (
    CreateResourceConnectionRequest,
    FilterResourceConnectionsRequest,
    FilterResourcesByConnectionIDRequest,
    AddOrUpdateResourceConnectionsRequest,
    ResourceConnectionType,
    ResourceConnectionStatus,
    ResourceType,
    ResourceConnectionSortBy,
    SortOrder,
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
    client = ResourceConnectionClient(
        api_key=management_api_key,
        config=Config(management_base_url=management_base_url),
    )

    # ===========================================
    # Create a Resource Connection
    # ===========================================
    print("🔧 Creating Resource Connection...")
    print("=" * 50)

    # Note: You would typically have MCP server resource IDs from registering servers
    # For this example, we'll create a connection without initial resources
    create_request = CreateResourceConnectionRequest(
        connection_name="Demo MCP Connection",
        connection_type=ResourceConnectionType.MCP_GATEWAY,
        resource_ids=["cef2a816-64af-4134-aee4-03d9aab0f5b5"],  # Add MCP server IDs here if you have them
    )

    try:
        response = client.create_connection(create_request)
        connection_id = response.connection_id
        print(f"✅ Connection created successfully!")
        print(f"   Connection ID: {connection_id}")
    except Exception as e:
        print(f"❌ Failed to create connection: {e}")
        # For demo purposes, try to list existing connections instead
        connection_id = None

    # ===========================================
    # Filter/List Resource Connections
    # ===========================================
    print("\n📋 Listing Resource Connections...")
    print("=" * 50)

    filter_request = FilterResourceConnectionsRequest(
        limit=25,
        offset=0,
        connection_type=ResourceConnectionType.MCP_GATEWAY,
        sort_by=ResourceConnectionSortBy.LAST_ACTIVE,
        order=SortOrder.DESC,
    )

    try:
        response = client.filter_connections(filter_request)

        if response.connections and response.connections.items:
            print(f"Found {len(response.connections.items)} connections")

            for conn in response.connections.items:
                status_icon = "🟢" if conn.connection_status == ResourceConnectionStatus.ACTIVE else "🔴"
                print(f"\n  {status_icon} {conn.connection_name}")
                print(f"     ID: {conn.connection_id}")
                print(f"     Type: {conn.connection_type}")
                print(f"     Status: {conn.connection_status}")
                if conn.created_at:
                    print(f"     Created: {conn.created_at}")

                # Use the first connection for subsequent examples if we didn't create one
                if not connection_id:
                    connection_id = conn.connection_id
        else:
            print("No connections found")

    except Exception as e:
        print(f"❌ Failed to filter connections: {e}")

    if not connection_id:
        print("\n⚠️ No connection available for further examples")
        return

    # ===========================================
    # Get Connection Details
    # ===========================================
    print(f"\n🔍 Getting Connection Details...")
    print("=" * 50)

    try:
        conn = client.get_connection(connection_id=connection_id, expanded=True)

        print(f"Connection: {conn.connection_name}")
        print(f"  ID: {conn.connection_id}")
        print(f"  Type: {conn.connection_type}")
        print(f"  Status: {conn.connection_status}")

        if conn.policies and conn.policies.items:
            print(f"\n  Associated Policies ({len(conn.policies.items)}):")
            for policy in conn.policies.items:
                print(f"    • {policy.policy_name} ({policy.policy_id})")

        if conn.resources and conn.resources.items:
            print(f"\n  Associated Resources ({len(conn.resources.items)}):")
            for resource in conn.resources.items:
                print(f"    • {resource.resource_name} ({resource.resource_id})")

    except Exception as e:
        print(f"❌ Failed to get connection: {e}")

    # ===========================================
    # Filter Resources by Connection
    # ===========================================
    print(f"\n📦 Listing Resources for Connection...")
    print("=" * 50)

    filter_resources_request = FilterResourcesByConnectionIDRequest(
        connection_id=connection_id,
        resource_type=ResourceType.MCP_SERVER,
        limit=25,
        offset=0,
    )

    try:
        response = client.filter_resources_by_connection_id(filter_resources_request)

        if response.resources:
            print(f"Found {len(response.resources)} resources")
            for resource in response.resources:
                print(f"  • {resource.resource_name} ({resource.resource_id})")
        else:
            print("No resources associated with this connection")

    except Exception as e:
        print(f"❌ Failed to filter resources: {e}")

    # ===========================================
    # Get Connections by Resource ID
    # ===========================================
    # print(f"\n🔗 Getting Connections by Resource ID...")
    # print("=" * 50)
    #
    # # Use the resource ID we just found associated with the connection
    # resource_id_to_lookup = "cef2a816-64af-4134-aee4-03d9aab0f5b5"
    #
    # try:
    #     connections = client.get_connection_by_resource_id(resource_id=resource_id_to_lookup)
    #
    #     if connections and connections.items:
    #         print(f"Found {len(connections.items)} connections for resource {resource_id_to_lookup}")
    #         for conn in connections.items:
    #             print(f"  • {conn.connection_name} ({conn.connection_id})")
    #     else:
    #         print(f"No connections found for resource {resource_id_to_lookup}")
    #
    # except Exception as e:
    #     print(f"❌ Failed to get connections by resource ID: {e}")

    # ===========================================
    # Add/Update Resources for Connection
    # ===========================================
    print(f"\n🔗 Updating Resource Associations...")
    print("=" * 50)

    # Example: Associate new resources with the connection
    # Note: Replace with actual resource IDs
    update_request = AddOrUpdateResourceConnectionsRequest(
        connection_id=connection_id,
        resource_type=ResourceType.MCP_SERVER,
        associate_resource_ids=["f8c651da-c669-4072-8f11-0b9b12ad7946"],  # Add resource IDs to associate
        disassociate_resource_ids=["cef2a816-64af-4134-aee4-03d9aab0f5b5"],  # Add resource IDs to remove
    )

    # Only run if there are changes to make
    if update_request.associate_resource_ids or update_request.disassociate_resource_ids:
        try:
            client.add_or_update_connections(update_request)
            print("✅ Resource associations updated successfully")
        except Exception as e:
            print(f"❌ Failed to update associations: {e}")
    else:
        print("ℹ️ No resource association changes specified")

    # ===========================================
    # List Resources After Update
    # ===========================================
    print(f"\n📦 Listing Resources After Update...")
    print("=" * 50)

    try:
        response = client.filter_resources_by_connection_id(filter_resources_request)

        if response.resources:
            print(f"Found {len(response.resources)} resources")
            for resource in response.resources:
                print(f"  • {resource.resource_name} ({resource.resource_id})")
        else:
            print("No resources found")
    except Exception as e:
        print(f"❌ Failed to list resources: {e}")

    # ===========================================
    # Delete Connection
    # ===========================================
    print(f"\n🗑️ Deleting Connection...")
    print("=" * 50)
    try:
        client.delete_connection(connection_id=connection_id)
        print(f"✅ Connection {connection_id} deleted successfully")
    except Exception as e:
        print(f"❌ Failed to delete connection: {e}")

    # ===========================================
    # Delete Connections by Resource ID (Example - Commented Out)
    # ===========================================
    # This method deletes ALL connections associated with a resource.
    # Uncomment to use - be careful as this is destructive!

    # print(f"\n🗑️ Deleting All Connections for Resource...")
    # print("=" * 50)
    # resource_id_to_delete = "your-resource-uuid-here"
    # try:
    #     client.delete_connections_by_resource_id(resource_id=resource_id_to_delete)
    #     print(f"✅ All connections for resource {resource_id_to_delete} deleted successfully")
    # except Exception as e:
    #     print(f"❌ Failed to delete connections: {e}")


if __name__ == "__main__":
    main()

