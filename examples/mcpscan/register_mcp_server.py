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
Example: Register and manage MCP servers using the AI Defense Python SDK.

This example demonstrates how to:
1. Register an MCP server for ongoing monitoring
2. Get server capabilities, threats, and scan summaries
3. Delete a registered server
"""
import os
import time

from aidefense import Config
from aidefense.mcpscan import MCPScan
from aidefense.mcpscan.models import (
    RegisterMCPServerRequest,
    TransportType,
    AuthConfig,
    AuthType,
    CapabilityType,
    OAuthConfig,
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
    client = MCPScan(
        api_key=management_api_key,
        config=Config(management_base_url=management_base_url),
    )

    # ===========================================
    # Register an MCP Server
    # ===========================================
    print("🔧 Registering MCP Server...")
    print("=" * 50)

    oauth_config = OAuthConfig(
        client_id="google_search_client_123",
        client_secret="google_search_secret_456",
        auth_server_url="https://feverous-roderick-vertically.ngrok-free.dev/oauth/token",
    )

    register_request = RegisterMCPServerRequest(
        name="Demo oauth",
        url="https://feverous-roderick-vertically.ngrok-free.dev/mcp/oauth",
        connection_type=TransportType.STREAMABLE,
        scan_enabled=True,
        auth_config=AuthConfig(
            auth_type=AuthType.OAUTH,
            oauth=oauth_config
        ),
    )

    try:
        response = client.register_server(register_request)
        server_id = response.server_id
        print(f"✅ Server registered successfully!")
        print(f"   Server ID: {server_id}")
    except Exception as e:
        print(f"❌ Failed to register server: {e}")
        return

    # ===========================================
    # Get Server Details
    # ===========================================
    print("\n📋 Fetching Server Details...")
    print("=" * 50)

    try:
        response = client.get_server(server_id=server_id)
        if response.mcp_server:
            server = response.mcp_server
            print(f"Server Name:       {server.name}")
            print(f"URL:               {server.url}")
            print(f"Connection Type:   {server.connection_type.value if hasattr(server.connection_type, 'value') else server.connection_type}")
            print(f"Onboarding Status: {server.onboarding_status.value if hasattr(server.onboarding_status, 'value') else server.onboarding_status}")
            print(f"Scan Enabled:      {server.scan_enabled}")
            print(f"Auth Type:         {server.auth_type.value if hasattr(server.auth_type, 'value') else server.auth_type}")
            print(f"Created At:        {server.created_at}")
            if server.status_info:
                print(f"Status Message:    {server.status_info.message}")
    except Exception as e:
        print(f"❌ Failed to get server details: {e}")

    # ===========================================
    # Get Server Capabilities
    # ===========================================
    time.sleep(10)
    print("\n🔧 Fetching Server Capabilities...")
    print("=" * 50)

    try:
        # Get TOOL capabilities
        caps_response = client.get_server_capabilities(
            server_id=server_id,
            capability_type=CapabilityType.TOOL,
            limit=10,
        )
        print(f"Found {len(caps_response.capabilities)} tool capabilities")

        for cap in caps_response.capabilities:
            if cap.tool:
                print(f"  • {cap.tool.name}")
                print(f"    Description: {cap.tool.description[:80]}..." if cap.tool.description and len(cap.tool.description) > 80 else f"    Description: {cap.tool.description}")

        # Get PROMPT capabilities
        prompt_caps = client.get_server_capabilities(
            server_id=server_id,
            capability_type=CapabilityType.PROMPT,
            limit=10,
        )
        print(f"\nFound {len(prompt_caps.capabilities)} prompt capabilities")

        # Get RESOURCE capabilities
        resource_caps = client.get_server_capabilities(
            server_id=server_id,
            capability_type=CapabilityType.RESOURCE,
            limit=10,
        )
        print(f"Found {len(resource_caps.capabilities)} resource capabilities")

    except Exception as e:
        print(f"❌ Failed to get capabilities: {e}")

    # ===========================================
    # Get Server Threats
    # ===========================================
    print("\n🔍 Fetching Server Threats...")
    print("=" * 50)

    try:
        threats_response = client.get_server_threats(
            server_id=server_id,
            limit=25,
        )

        # Filter to only show actual threats (with technique_id, technique_name, or sub_techniques)
        actual_threats = [
            t for t in threats_response.threats
            if t.threat and (t.threat.technique_id or t.threat.technique_name or t.threat.sub_techniques)
        ]

        if actual_threats:
            print(f"Found {len(actual_threats)} threats")
            for threat in actual_threats:
                print(f"\n  📌 Capability ID: {threat.capability_id}")
                print(f"    ⚠️ {threat.threat.technique_name} ({threat.threat.technique_id})")
                print(f"    Analyzer: {threat.threat.analyzer_type.value if hasattr(threat.threat.analyzer_type, 'value') else threat.threat.analyzer_type}")
                if threat.threat.sub_techniques:
                    for sub in threat.threat.sub_techniques:
                        desc = sub.description[:60] + "..." if sub.description and len(sub.description) > 60 else sub.description
                        print(f"       • {sub.sub_technique_name}: {desc}")
        else:
            print("✅ No threats detected")

    except Exception as e:
        print(f"❌ Failed to get threats: {e}")

    # ===========================================
    # Get Scan Summary
    # ===========================================
    print("\n📊 Fetching Scan Summary...")
    print("=" * 50)

    try:
        summary = client.get_server_scan_summary(server_id=server_id)

        if summary.capability_summary:
            cap_sum = summary.capability_summary
            print("Capability Summary:")
            print(f"  Tools:     {cap_sum.tool_count}")
            print(f"  Prompts:   {cap_sum.prompt_count}")
            print(f"  Resources: {cap_sum.resource_count}")

        if summary.scan_threat_summary:
            threat_sum = summary.scan_threat_summary
            print("\nThreat Summary:")
            print(f"  Critical: {threat_sum.critical_count}")
            print(f"  High:     {threat_sum.high_count}")
            print(f"  Medium:   {threat_sum.medium_count}")
            print(f"  Low:      {threat_sum.low_count}")

        if summary.completed_at:
            print(f"\nLast scan completed: {summary.completed_at}")

    except Exception as e:
        print(f"❌ Failed to get scan summary: {e}")

    # ===========================================
    # Delete Server (cleanup)
    # ===========================================
    print("\n🗑️ Deleting Server...")
    print("=" * 50)

    try:
        client.delete_server(server_id=server_id)
        print(f"✅ Server {server_id} deleted successfully")
    except Exception as e:
        print(f"❌ Failed to delete server: {e}")


if __name__ == "__main__":
    main()

