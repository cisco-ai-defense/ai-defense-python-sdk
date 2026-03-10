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
Example: List AI-BOMs using the AI Defense Python SDK.

This example demonstrates how to list AI-BOM (AI Bill of Materials) analyses
with optional filters and pagination.
"""
import os

from aidefense import AIBom, Config
from aidefense.aibom.models import ListBomsRequest, SortBy, BomSortOrder


def main():
    management_api_key = os.environ.get("AIDEFENSE_MANAGEMENT_API_KEY")
    management_base_url = os.environ.get(
        "AIDEFENSE_MANAGEMENT_BASE_URL",
        "https://api.security.cisco.com",
    )

    if not management_api_key:
        print("Error: AIDEFENSE_MANAGEMENT_API_KEY environment variable is not set")
        return

    client = AIBom(
        api_key=management_api_key,
        config=Config(management_base_url=management_base_url),
    )

    # List first 10 BOMs
    request = ListBomsRequest(
        limit=10,
        offset=0,
        sort_by=SortBy.SORT_BY_LAST_GENERATED_AT,
        order=BomSortOrder.DESC,
    )

    try:
        response = client.list_boms(request)
        items = response.items
        paging = response.paging

        total = paging.total if paging else len(items)
        print(f"Found {len(items)} BOMs (total: {total}):")
        for item in items:
            print(f"  • {item.analysis_id}")
            print(f"    Source: {item.source_name} | Kind: {item.source_kind}")
            print(f"    Assets: {item.assets_discovered} | Status: {item.status}")
            if item.last_generated_at:
                print(f"    Last generated: {item.last_generated_at}")
            print()
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
