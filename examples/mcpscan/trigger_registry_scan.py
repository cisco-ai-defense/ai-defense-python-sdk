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
Example: Trigger a bulk scan on an MCP registry using the AI Defense Python SDK.

This example demonstrates how to trigger a bulk security scan for MCP servers
in a registry, either for all registered servers or for specific server IDs.
"""
import os

from aidefense import Config
from aidefense.mcpscan import MCPScanClient


def main():
    management_api_key = os.environ.get("AIDEFENSE_MANAGEMENT_API_KEY")
    management_base_url = os.environ.get(
        "AIDEFENSE_MANAGEMENT_BASE_URL",
        "https://api.security.cisco.com",
    )

    if not management_api_key:
        print("Error: AIDEFENSE_MANAGEMENT_API_KEY environment variable is not set")
        return

    registry_id = os.environ.get("MCP_REGISTRY_ID")
    if not registry_id:
        print("Error: MCP_REGISTRY_ID environment variable is not set")
        print("Set it to a registry UUID, e.g.: export MCP_REGISTRY_ID=550e8400-e29b-41d4-a716-446655440000")
        return

    client = MCPScanClient(
        api_key=management_api_key,
        config=Config(management_base_url=management_base_url),
    )

    # Optional: specify server IDs to scan (omit to scan all servers in registry)
    server_ids_env = os.environ.get("MCP_SERVER_IDS")  # comma-separated list
    server_id_list = None
    if server_ids_env and server_ids_env.strip():
        server_id_list = [s.strip() for s in server_ids_env.split(",") if s.strip()]

    try:
        if server_id_list:
            response = client.trigger_bulk_scan(
                registry_id=registry_id,
                server_ids=server_id_list,
            )
            print(f"Bulk scan triggered for {len(server_id_list)} server(s)")
        else:
            response = client.trigger_bulk_scan(registry_id=registry_id)
            print("Bulk scan triggered for all servers in registry")

        print(f"Scan ID: {response.scan_id}")
        print("\nUse get_registry_scan_summary(registry_id) to check progress.")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
