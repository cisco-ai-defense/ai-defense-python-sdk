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
Example: Retrieve and display detailed scan results by scan ID using the AI Defense Python SDK.

This example demonstrates how to fetch and display detailed information about a specific scan
using its unique identifier, including the hierarchical threat classification.
"""

from datetime import datetime

from aidefense import Config
from aidefense.modelscan import ModelScanClient
from aidefense.modelscan.models import GetScanStatusRequest
# Import utility functions for displaying results
from examples.modelscan.utils import print_analysis_results


def format_timestamp(timestamp: datetime) -> str:
    """Format a timestamp into a human-readable string.
    
    Args:
        timestamp: The datetime object to format
        
    Returns:
        Formatted date-time string
    """
    if not timestamp:
        return "N/A"
    return timestamp.strftime("%Y-%m-%d %H:%M:%S %Z")


def get_scan_details(client, scan_id: str, file_limit: int = 10, file_offset: int = 0) -> None:
    """
    Retrieve and display detailed information about a specific scan.

    Args:
        scan_id: The unique identifier of the scan to retrieve
        file_limit: Maximum number of file results to return
        file_offset: Offset for pagination of file results
    """
    try:
        # Create request with pagination
        request = GetScanStatusRequest(
            file_limit=file_limit,
            file_offset=file_offset
        )

        # Fetch scan details
        print(f"🔍 Retrieving scan details for ID: {scan_id}")
        response = client.get_scan(scan_id, request)
        scan_info = response.scan_status_info

        # Display scan metadata
        print("\n📊 Scan Overview:")
        print("=" * 50)
        print(f"  ID:          {scan_id}")
        print(f"  Status:      {scan_info.status.value}")
        print(f"  Type:        {scan_info.type.value}")
        print(f"  Created:     {format_timestamp(scan_info.created_at)}")
        print(f"  Completed:   {format_timestamp(scan_info.completed_at)}")

        # Display repository info if available
        if scan_info.repository:
            print("\n📦 Repository Details:")
            print("-" * 30)
            print(f"  URL:           {scan_info.repository.url}")
            print(f"  Version:       {scan_info.repository.version}")
            print(f"  Files Scanned: {scan_info.repository.files_scanned}")

        # Display analysis results using the utility function
        if hasattr(scan_info, 'analysis_results') and scan_info.analysis_results:
            print_analysis_results(scan_info.analysis_results, scan_id=scan_id)

    except Exception as e:
        print(f"\n❌ Error retrieving scan details:")
        print(f"   {str(e)}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            print(f"   Response: {e.response.text}")


def main():
    # Initialize the client
    client = ModelScanClient(
        api_key="YOUR_MANAGEMENT_API_KEY",
        config=Config(management_base_url="https://api.security.cisco.com"),
    )

    # Replace with your scan ID
    scan_id = "63d01118-353e-4919-8e9a-8f2276275ccf"
    
    # Configure pagination
    file_limit = 10
    file_offset = 0
    
    # Get scan details
    get_scan_details(client, scan_id, file_limit, file_offset)


if __name__ == "__main__":
    main()
