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
Example: Scan a file for AI/ML model threats using the AI Defense Python SDK.

This example demonstrates how to scan a file for potential AI/ML model threats
using the hierarchical threat classification system.
"""
from aidefense import Config
from aidefense.modelscan import ModelScanClient
from aidefense.modelscan.models import ScanStatus

# Import utility functions for displaying results
from examples.modelscan.utils import print_analysis_results

def main():
    # Initialize the client
    client = ModelScanClient(
        api_key="YOUR_MANAGEMENT_API_KEY",
        config=Config(management_base_url="https://api.security.cisco.com"),
    )

    # Replace with your file path
    file_path = "FILE_PATH"
    print(f"🔍 Scanning file: {file_path}")
    
    try:
        # Scan the file
        result = client.scan_file(file_path)
        print("\n📊 Scan Results:")
        print("=" * 50)
        
        # Display scan ID
        if hasattr(result, 'scan_id') and result.scan_id:
            print(f"🔑 Scan ID:     {result.scan_id}")

        if result.status == ScanStatus.COMPLETED:
            print("✅ Scan completed successfully\n")
            
            # Display analysis results using the utility function
            print_analysis_results(result.analysis_results)
                
        elif result.status == ScanStatus.FAILED:
            print("❌ Scan failed")
            if hasattr(result, 'error_message') and result.error_message:
                print(f"Error: {result.error_message}")
        else:
            print(f"ℹ️  Scan status: {result.status.value}")
            
    except Exception as e:
        print(f"\n❌ An error occurred during scanning:")
        print(f"   {str(e)}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            print(f"   Response: {e.response.text}")

if __name__ == "__main__":
    main()
