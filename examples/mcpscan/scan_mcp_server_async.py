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
Example: Asynchronously scan an MCP server using the AI Defense Python SDK.

This example demonstrates how to start an MCP server scan without waiting
for completion, and then poll for results separately. Useful for non-blocking
operations or when integrating with async frameworks.
"""
import os
import sys
import time
from pathlib import Path

from aidefense import Config
from aidefense.mcpscan import MCPScanClient
from aidefense.mcpscan.models import (
    StartMCPServerScanRequest,
    TransportType,
    MCPScanStatus,
    AuthConfig,
    AuthType,
    ApiKeyConfig,
    OAuthConfig,
    ServerType,
    RemoteServerInput,
)

# Allow importing utils when run as script (e.g. python examples/mcpscan/scan_mcp_server_async.py)
_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))
from utils import print_scan_status, format_status


def main():
    # Get API key from environment variable
    management_api_key = os.environ.get("AIDEFENSE_MANAGEMENT_API_KEY")
    management_base_url = os.environ.get("AIDEFENSE_MANAGEMENT_BASE_URL", "https://api.security.cisco.com")

    if not management_api_key:
        print("❌ Error: AIDEFENSE_MANAGEMENT_API_KEY environment variable is not set")
        return

    # Initialize the client
    client = MCPScanClient(
        api_key=management_api_key,
        config=Config(management_base_url=management_base_url),
    )

    # Create scan request for an MCP server
    # Option 1: No authentication (public server)
    request = StartMCPServerScanRequest(
        name="Async Scan Server",
        server_type=ServerType.REMOTE,
        remote=RemoteServerInput(
            url="https://mcp.exa.ai/mcp",  # e.g., "https://mcp-server.example.com/sse"
            connection_type=TransportType.STREAMABLE,
        ),
        auth_config=AuthConfig(auth_type=AuthType.NO_AUTH),
    )

    # Option 2: With API key authentication (uncomment to use)
    # request = StartMCPServerScanRequest(
    #     name="Authenticated MCP Server",
    #     server_type=ServerType.REMOTE,
    #     remote=RemoteServerInput(
    #         url="https://feverous-roderick-vertically.ngrok-free.dev/mcp/api-key",
    #         connection_type=TransportType.SSE,
    #     ),
    #     auth_config=AuthConfig(
    #         auth_type=AuthType.API_KEY,
    #         api_key=ApiKeyConfig(
    #             header_name="X-API-Key",
    #             api_key="google_search_api_key_123"
    #         )
    #     ),
    # )

    # Option 3: With Oauth authentication (uncomment to use)
    # Configure OAuth authentication for the MCP server
    # oauth_config = OAuthConfig(
    #     client_id="google_search_client_123",
    #     client_secret="google_search_secret_456",
    #     auth_server_url="https://feverous-roderick-vertically.ngrok-free.dev/oauth/token",
    #     # scope="mcp:read mcp:execute",  # Optional: OAuth scopes
    # )
    #
    # # Create scan request with OAuth authentication
    # request = StartMCPServerScanRequest(
    #     name="OAuth Protected MCP Server",
    #     server_type=ServerType.REMOTE,
    #     remote=RemoteServerInput(
    #         url="https://feverous-roderick-vertically.ngrok-free.dev/mcp/oauth",  # e.g., "https://secure-mcp.example.com/sse"
    #         connection_type=TransportType.SSE,
    #     ),
    #     auth_config=AuthConfig(
    #         auth_type=AuthType.OAUTH,
    #         oauth=oauth_config,
    #     ),
    # )

    print(f"🔍 Starting async scan for: {request.name}")
    print(f"   URL: {request.remote.url}")

    try:
        # Start scan without waiting for completion
        scan_id = client.scan_mcp_server_async(request)
        print(f"\n📝 Scan started successfully!")
        print(f"   Scan ID: {scan_id}")

        # Simulate doing other work
        print("\n🔧 Performing other tasks while scan runs...")
        print("   (In a real application, you would do actual work here)")

        # Poll for completion
        print("\n📊 Polling for scan completion...")
        max_attempts = 30
        poll_interval = 1  # seconds

        for attempt in range(max_attempts):
            status = client.get_scan_status(scan_id)
            print(f"   Attempt {attempt + 1}/{max_attempts}: {format_status(status.status)}")

            if status.status == MCPScanStatus.COMPLETED:
                print("\n" + "=" * 50)
                print("✅ Scan completed!")
                print_scan_status(status)

                if status.result:
                    if status.result.is_safe:
                        print("\n✅ MCP server is safe")
                    else:
                        print("\n⚠️ Security issues detected")
                break

            elif status.status == MCPScanStatus.FAILED:
                print("\n" + "=" * 50)
                error_msg = status.error_info.message if status.error_info else "Unknown error"
                print(f"❌ Scan failed: {error_msg}")
                break

            elif status.status == MCPScanStatus.CANCELLED:
                print("\n" + "=" * 50)
                print("🚫 Scan was cancelled")
                break

            elif status.status in [MCPScanStatus.QUEUED, MCPScanStatus.IN_PROGRESS]:
                time.sleep(poll_interval)

            else:
                print(f"\n⚠️ Unexpected status: {status.status}")
                break

        else:
            print(f"\n⏰ Scan timed out after {max_attempts * poll_interval} seconds")
            print(f"   Last status: {status.status}")
            print(f"   You can continue checking with scan ID: {scan_id}")

    except Exception as e:
        print(f"\n❌ An error occurred:")
        print(f"   {str(e)}")
        if hasattr(e, "response") and hasattr(e.response, "text"):
            print(f"   Response: {e.response.text}")


if __name__ == "__main__":
    main()

