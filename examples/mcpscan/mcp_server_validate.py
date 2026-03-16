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

"""Example of using the MCPScanClient to validate MCP server connectivity and authentication.
This example demonstrates how to:
1. Validate one or more MCP servers using the validate_servers method
2. Print the validation results for each server
"""

import os

from aidefense.config import Config
from aidefense.mcpscan.mcp_scan_base import MCPScan
from aidefense.mcpscan.models import TransportType, ValidateMCPServersRequest


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

    urls = os.environ.get("MCP_SERVER_URLS")
    if not urls:
        print("❌ Error: MCP_SERVER_URLS environment variable is not set")
        return

    transport_type_str = os.environ.get("MCP_SERVER_TRANSPORT_TYPE", "STREAMABLE")
    transport_type = TransportType(transport_type_str)

    server_urls = [url.strip() for url in urls.split(",") if url.strip()]

    # ===========================================
    # Validate MCP Servers
    # ===========================================
    print("🔍 Validating MCP Servers...")
    print("=" * 50)

    request = ValidateMCPServersRequest(urls=server_urls, transport_type=transport_type)

    try:
        response = client.validate_servers(request)
        print("✅ MCP Servers validation successful")
        print("Validation Results:")
        print("Valid urls:", response.valid_urls)
        print("Invalid urls:", response.invalid_urls)
    except Exception as e:
        print(f"❌ Error validating MCP Servers: {e}")

if __name__ == "__main__":
    main()
