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

"""Example of using the MCPScanClient to start a server scan and check its status.
This example demonstrates how to:
1. Start a scan on a registered MCP server
2. Poll for scan status until completion
3. Retrieve and print the scan results
"""

import os
import time

from aidefense import Config
from aidefense.mcpscan import MCPScan
from aidefense.mcpscan.models import (
    CapabilityType,
    FilterOptions,
    GetMCPServerScanReportRequest,
)

from utils import (
    print_server_scan_summary,
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

    server_id = os.environ.get("MCP_SERVER_ID")
    if not server_id:
        print("❌ Error: MCP_SERVER_ID environment variable is not set")
        return

    # Initialize the client
    client = MCPScan(
        api_key=management_api_key,
        config=Config(management_base_url=management_base_url),
    )

    # ===========================================
    # Start an MCP Server Scan
    # ===========================================
    print(f"🚀 Starting scan for MCP Server ID: {server_id}...")
    print("=" * 50)

    try:
        client.trigger_server_scan(server_id=server_id)
    except Exception as e:
        print(f"❌ Failed to trigger scan: {e}")
        return

    print("✅ Scan triggered successfully. Polling for status...")

    # ===========================================
    # Poll for Scan Status
    # ===========================================
    while True:
        time.sleep(5)  # Wait for 5 seconds before polling

        try:
            scan_summary = client.get_server_scan_summary(server_id=server_id)
            if scan_summary.completed_at:
                print("✅ Scan completed!")
                print_server_scan_summary(scan_summary)
                break
        except Exception as e:
            print(f"❌ Failed to get scan status: {e}")
            return

        print("⏳ Scan still in progress... waiting before next check.")

    # Optionally, you can also retrieve filtered report
    print("📄 Retrieving Tools scan report...")
    try:
        scan_report = client.server_scan_report(
            request=GetMCPServerScanReportRequest(
                server_id=server_id,
                offset=1,
                filter_options=FilterOptions(
                    capability_type=CapabilityType.TOOL
                ),
            )
        )
        print(f"Scan report  entries: {scan_report.paging.total if scan_report.paging else len(scan_report.entries)}")
    except Exception as e:
        print(f"❌ Failed to get scan report: {e}")


if __name__ == "__main__":
    main()
