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
Example: Using inspect_conversation for chat conversation inspection
"""
from aidefense import Config
from aidefense.modelscan import ModelScanClient
from aidefense.modelscan.models import ListScansRequest

# Initialize the client
client = ModelScanClient(
    api_key="YOUR_MANAGEMENT_API_KEY",
    config=Config(management_base_url="https://api.security.cisco.com"),
)

# Get first 10 scans
request = ListScansRequest(limit=10, offset=0)
response = client.list_scans(request)

scans = response.scans.items
paging = response.scans.paging

print(f"📋 Found {len(scans)} scans (total: {paging.total}):")
for scan in scans:
    # Create issue summary
    issue_summary = []
    for severity, count in scan.issues_by_severity.items():
        if count > 0:
            issue_summary.append(f"{severity}: {count}")
    issue_text = ", ".join(issue_summary) if issue_summary else "No issues"

    print(f"  • {scan.scan_id}")
    print(f"    Name: {scan.name} | Type: {scan.type.value} | Status: {scan.status}")
    print(f"    Files: {scan.files_scanned} | Issues: {issue_text}")
    print(f"    Created: {scan.created_at}")
    print()

# Get next page of scans
next_request = ListScansRequest(limit=10, offset=10)
more_scans = client.list_scans(next_request)

if __name__ == "__main__":
    pass
