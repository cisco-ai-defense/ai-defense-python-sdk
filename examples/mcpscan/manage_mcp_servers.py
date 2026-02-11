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
Example: List and get MCP servers using the AI Defense Python SDK.

This example demonstrates how to:
1. List all registered MCP servers with pagination
2. Filter MCP servers by various criteria
3. Get details of a specific MCP server by ID
4. Update authentication configuration for an MCP server
"""
import os

from aidefense import Config
from aidefense.mcpscan import MCPScan
from aidefense.mcpscan.models import (
    TransportType,
    AuthConfig,
    AuthType,
    ApiKeyConfig,
    OnboardingStatus,
    UpdateAuthConfigRequest,
)


def format_onboarding_status(status) -> str:
    """Format onboarding status with appropriate emoji."""
    status_str = status.value if hasattr(status, 'value') else str(status)
    status_icons = {
        "COMPLETED": "✅",
        "INPROGRESS": "🔄",
        "FAILED": "❌",
    }
    icon = status_icons.get(status_str.upper(), "❓")
    return f"{icon} {status_str}"


def format_auth_type(auth_type) -> str:
    """Format auth type with appropriate emoji."""
    auth_str = auth_type.value if hasattr(auth_type, 'value') else str(auth_type)
    auth_icons = {
        "NO_AUTH": "🔓",
        "API_KEY": "🔑",
        "OAUTH": "🔐",
    }
    icon = auth_icons.get(auth_str.upper(), "❓")
    return f"{icon} {auth_str}"


def print_server_details(server, verbose: bool = True) -> None:
    """Print details of an MCP server."""
    print(f"\n  📦 {server.name}")
    print(f"     ID: {server.id}")
    print(f"     URL: {server.url}")
    if server.description:
        desc = server.description[:80] + "..." if len(server.description) > 80 else server.description
        print(f"     Description: {desc}")
    print(f"     Connection Type: {server.connection_type.value if hasattr(server.connection_type, 'value') else server.connection_type}")
    if server.created_at:
        print(f"     Created At: {server.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"     Onboarding Status: {format_onboarding_status(server.onboarding_status)}")
    print(f"     Scan Enabled: {'✅' if server.scan_enabled else '❌'}")
    print(f"     Scan Periodically: {'✅' if server.scan_periodically else '❌'}")
    print(f"     Auth Type: {format_auth_type(server.auth_type)}")

    if verbose:
        if server.status_info:
            print(f"     ⚠️ Status Error: {server.status_info.message}")


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
    # List All MCP Servers
    # ===========================================
    print("📋 Listing All MCP Servers...")
    print("=" * 50)

    try:
        response = client.list_servers(limit=25, offset=0)

        if response.mcp_servers and response.mcp_servers.items:
            servers = response.mcp_servers.items
            paging = response.mcp_servers.paging

            print(f"Found {len(servers)} servers (total: {paging.total if paging else len(servers)})")

            for server in servers:
                print_server_details(server, verbose=False)

            # Store first server ID for later use
            first_server_id = servers[0].id if servers else None
        else:
            print("No MCP servers found")
            first_server_id = None

    except Exception as e:
        print(f"❌ Failed to list servers: {e}")
        first_server_id = None

    # ===========================================
    # Get Specific MCP Server by ID
    # ===========================================
    if first_server_id:
        print("\n\n📦 Getting Specific MCP Server Details...")
        print("=" * 50)

        try:
            response = client.get_server(server_id=first_server_id)

            if response.mcp_server:
                server = response.mcp_server
                print(f"Server Details for ID: {first_server_id}")
                print_server_details(server, verbose=True)

                # Show auth config details if available
                if server.auth_config:
                    print(f"\n     Auth Configuration:")
                    print(f"       Type: {server.auth_config.auth_type.value if hasattr(server.auth_config.auth_type, 'value') else server.auth_config.auth_type}")
                    if server.auth_config.oauth:
                        print(f"       OAuth Client ID: {server.auth_config.oauth.client_id}")
                        print(f"       OAuth Server URL: {server.auth_config.oauth.auth_server_url}")
                    if server.auth_config.api_key:
                        print(f"       API Key Header: {server.auth_config.api_key.header_name}")
            else:
                print(f"Server {first_server_id} not found")

        except Exception as e:
            print(f"❌ Failed to get server details: {e}")


if __name__ == "__main__":
    main()

