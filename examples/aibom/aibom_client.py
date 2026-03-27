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
Example: Using the AIBOM Client to analyze a BOM.

This example demonstrates how to use the AiBomClient to analyze a Bill of Materials (BOM) from various sources such as repository URLs or file paths. The analysis results can be saved to a JSON file for further inspection.
"""

import os
import json
import sys
from pathlib import Path

# Allow running as a script without requiring editable install.
_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from aidefense import Config
from aidefense.aibom.aibom_client import AiBomClient


def main():
    # This is a placeholder for the actual implementation of the example.
    # You would initialize the AiBomClient, call the analyze method with appropriate sources,
    # and handle the results as needed.

    print("This is an example of how to use the AiBomClient to analyze a BOM.")
    print("Please refer to the documentation and implement the logic as needed.")


    # Get API key from environment variable
    management_api_key = os.environ.get("AIDEFENSE_MANAGEMENT_API_KEY")
    management_base_url = os.environ.get(
        "AIDEFENSE_MANAGEMENT_BASE_URL", "https://api.security.cisco.com"
    )

    if not management_api_key:
        print("❌ Error: AIDEFENSE_MANAGEMENT_API_KEY environment variable is not set")
        return

    client = AiBomClient(
        api_key=management_api_key,
        config=Config(management_base_url=management_base_url),
    )


    # comma-separated list of sources to analyze (e.g. "repo_url1,repo_url2,file_path1")
    sources_str = os.environ.get("AIBOM_SOURCES")
    if not sources_str:
        print("❌ Error: AIBOM_SOURCES environment variable is not set")
        return

    # do not strip whitespace as it may be part of file paths
    sources = sources_str.split(",")

    output_file = os.environ.get("AIBOM_OUTPUTS") # optional
    print(f"Using output file: {output_file}")

    print("🚀 Start analyzing BOM with sources:", sources)
    analyze_result = client.analyze(sources=sources, output_file=output_file)
    print("✅ Analysis completed. Result:")
    print(json.dumps(analyze_result, indent=2))

    print("🚀 Submitting report... ")
    report_response = client.submit_report_file(analyze_result)
    print("✅ Report submitted. Response:")
    print(report_response.model_dump_json(indent=2))


    # Alternative: submit from file path
    # if output_file:
    #     report_response = client.submit_report_file(file_path=Path(output_file))
    #     print("✅ Report submitted from file. Response:")
    #     print(report_response.model_dump_json(indent=2))

    # Alternative: analyze and submit in one step
    # report_response = client.analyze_and_submit(sources=sources)
    # print("✅ Analyze and submit completed. Response:")
    # print(report_response.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
