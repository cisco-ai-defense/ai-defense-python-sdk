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

"""
Example: Manage MCP Gateway policies using the AI Defense Python SDK.

This example demonstrates how to:
1. List MCP Gateway policies (automatically filtered by connection_type=MCPGateway)
2. Get MCP policy details with guardrails
3. Associate MCP policies with MCP resource connections
4. Update MCP policy properties

Note: For general policy management across all connection types, use
PolicyManagementClient from aidefense.management instead.
"""
import os

from aidefense import Config
from aidefense.mcpscan import (
    MCPPolicyClient,
    ListPoliciesRequest,
    UpdatePolicyRequest,
    AddOrUpdatePolicyConnectionsRequest,
    PolicySortBy,
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
    client = MCPPolicyClient(
        api_key=management_api_key,
        config=Config(management_base_url=management_base_url),
    )

    # ===========================================
    # List MCP Gateway Policies
    # ===========================================
    print("📋 Listing MCP Gateway Policies...")
    print("=" * 50)

    list_request = ListPoliciesRequest(
        limit=25,
        offset=0,
        sort_by=PolicySortBy.policy_name,
        order="asc",
    )

    policy_id = None

    try:
        # list_mcp_policies automatically filters to MCPGateway connection_type
        policies = client.list_mcp_policies(list_request)

        if policies.items:
            print(f"Found {len(policies.items)} policies\n")

            for policy in policies.items:
                status_icon = "🟢" if policy.status == "active" or policy.status == "Enabled" else "🔴"
                print(f"  {status_icon} {policy.policy_name}")
                print(f"     ID: {policy.policy_id}")
                print(f"     Status: {policy.status}")
                print(f"     Type: {policy.connection_type}")
                if policy.description:
                    desc = policy.description[:60] + "..." if len(policy.description) > 60 else policy.description
                    print(f"     Description: {desc}")
                print()

                # Save first policy ID for later examples
                if not policy_id:
                    policy_id = policy.policy_id
        else:
            print("No policies found")

        if policies.paging:
            print(f"Pagination: offset={policies.paging.offset}, total={policies.paging.total}")

    except Exception as e:
        print(f"❌ Failed to list policies: {e}")

    if not policy_id:
        print("\n⚠️ No policy available for further examples")
        return

    # ===========================================
    # Get MCP Policy Details (Expanded)
    # ===========================================
    print(f"\n🔍 Getting MCP Policy Details...")
    print("=" * 50)

    try:
        policy = client.get_mcp_policy(policy_id=policy_id, expanded=True)

        print(f"Policy: {policy.policy_name}")
        print(f"  ID: {policy.policy_id}")
        print(f"  Status: {policy.status}")
        print(f"  Connection Type: {policy.connection_type}")
        print(f"  Language: {policy.language_type}")

        if policy.description:
            print(f"  Description: {policy.description}")

        if policy.created_at:
            print(f"  Created: {policy.created_at}")
        if policy.updated_at:
            print(f"  Updated: {policy.updated_at}")

        # Display guardrails if available
        if policy.guardrails and policy.guardrails.items:
            print(f"\n  🛡️ Guardrails ({len(policy.guardrails.items)}):")
            for guardrail in policy.guardrails.items:
                print(f"    • Type: {guardrail.guardrails_type}")
                if guardrail.items:
                    print(f"      Rules: {len(guardrail.items)}")
                    for rule in guardrail.items[:3]:  # Show first 3 rules
                        # Privacy rules don't have direction/action, only status
                        if rule.action and rule.direction:
                            print(f"        - {rule.ruleset_type}: {rule.action} ({rule.direction})")
                        else:
                            print(f"        - {rule.ruleset_type}: {rule.status}")
                    if len(guardrail.items) > 3:
                        print(f"        ... and {len(guardrail.items) - 3} more rules")

    except Exception as e:
        print(f"❌ Failed to get policy: {e}")

    # ===========================================
    # Update MCP Policy (Example - commented for safety)
    # ===========================================
    print(f"\n✏️ Update MCP Policy Example")
    print("=" * 50)

    update_request = UpdatePolicyRequest(
        description="Updated description for MCP security policy",
    )

    print("# To update an MCP policy, use:")
    print(f"# client.update_mcp_policy(policy_id='{policy_id}', request=update_request)")
    print("# Where update_request can contain: name, description, status")

    # Uncomment to actually update:
    # try:
    #     client.update_mcp_policy(policy_id=policy_id, request=update_request)
    #     print("✅ MCP Policy updated successfully")
    # except Exception as e:
    #     print(f"❌ Failed to update MCP policy: {e}")

    # ===========================================
    # Associate MCP Policy with MCP Connections
    # ===========================================
    print(f"\n🔗 Associate MCP Policy with MCP Connections Example")
    print("=" * 50)

    # Note: Replace with actual connection IDs from your MCP resource connections
    connection_request = AddOrUpdatePolicyConnectionsRequest(
        connections_to_associate=[],  # Add MCP connection UUIDs to associate
        connections_to_disassociate=[],  # Add MCP connection UUIDs to remove
    )

    print("# To associate MCP connections with an MCP policy, use:")
    print(f"# client.update_mcp_policy_connections(")
    print(f"#     policy_id='{policy_id}',")
    print(f"#     request=AddOrUpdatePolicyConnectionsRequest(")
    print(f"#         connections_to_associate=['<mcp-connection-uuid-1>', '<mcp-connection-uuid-2>'],")
    print(f"#         connections_to_disassociate=['<mcp-connection-uuid-3>']")
    print(f"#     )")
    print(f"# )")

    # Example with actual MCP connection IDs:
    # try:
    #     client.update_mcp_policy_connections(
    #         policy_id=policy_id,
    #         request=AddOrUpdatePolicyConnectionsRequest(
    #             connections_to_associate=["550e8400-e29b-41d4-a716-446655440000"]
    #         )
    #     )
    #     print("✅ MCP Policy connections updated")
    # except Exception as e:
    #     print(f"❌ Failed to update MCP connections: {e}")

    # ===========================================
    # Filter MCP Policies by Status
    # ===========================================
    print(f"\n🔎 Filter MCP Policies by Status...")
    print("=" * 50)

    # Filter for enabled MCP policies only
    filter_request = ListPoliciesRequest(
        limit=10,
        policy_status="Enabled",
    )

    try:
        # Automatically filters to MCPGateway connection_type
        active_policies = client.list_mcp_policies(filter_request)

        if active_policies.items:
            print(f"Found {len(active_policies.items)} enabled MCP policies:")
            for p in active_policies.items:
                print(f"  • {p.policy_name}")
        else:
            print("No enabled MCP policies found")

    except Exception as e:
        print(f"❌ Failed to filter MCP policies: {e}")


if __name__ == "__main__":
    main()

