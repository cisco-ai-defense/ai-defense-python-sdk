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
Example: Get AI-BOM detail by analysis ID using the AI Defense Python SDK.

This example demonstrates how to retrieve a full AI-BOM (AI Bill of Materials)
detail by its analysis ID.
"""
import os
import sys
from pathlib import Path

from aidefense import AIBom, Config


def main():
    management_api_key = os.environ.get("AIDEFENSE_MANAGEMENT_API_KEY")
    management_base_url = os.environ.get(
        "AIDEFENSE_MANAGEMENT_BASE_URL",
        "https://api.security.cisco.com",
    )

    if not management_api_key:
        print("Error: AIDEFENSE_MANAGEMENT_API_KEY environment variable is not set")
        return

    analysis_id = os.environ.get("AIBOM_ANALYSIS_ID")
    if not analysis_id:
        print("Error: AIBOM_ANALYSIS_ID environment variable is not set")
        print("Set it to an analysis UUID, e.g.: export AIBOM_ANALYSIS_ID=550e8400-e29b-41d4-a716-446655440000")
        return

    client = AIBom(
        api_key=management_api_key,
        config=Config(management_base_url=management_base_url),
    )

    try:
        bom = client.get_bom(analysis_id)
        print(f"BOM: {bom.analysis_id}")
        print(f"  Source: {bom.source_name}")
        print(f"  Kind: {bom.source_kind}")
        print(f"  Status: {bom.status}")
        if bom.generated_at:
            print(f"  Generated: {bom.generated_at}")
        if bom.summary:
            print(f"  Total assets: {bom.summary.total_assets}")
            if bom.summary.asset_types:
                at = bom.summary.asset_types
                print(f"  Asset types: models={at.models}, embeddings={at.embeddings}, "
                      f"prompts={at.prompts}, agents={at.agents}, tools={at.tools}, chains={at.chains}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
