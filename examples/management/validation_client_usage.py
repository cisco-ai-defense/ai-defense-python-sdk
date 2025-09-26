#!/usr/bin/env python3
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
Example script demonstrating how to use the AI Validation API.

This script shows how to:
1. Initialize the AiValidationClient with configuration
2. Start an AI validation job
3. Poll the job status
4. List all validation configs
5. Get a specific validation config by task_id

Prerequisites:
- Set environment variable AIDEFENSE_MANAGEMENT_API_KEY with your tenant API key
"""

import os
import time
from datetime import datetime, timedelta

from aidefense.config import Config
from aidefense.exceptions import ValidationError, ApiError, SDKError
from aidefense.management.validation_client import AiValidationClient
from aidefense.management.models.validation import (
    StartAiValidationRequest,
    AssetType,
    AWSRegion,
    Header,
)


def main():
    api_key = os.environ.get("AIDEFENSE_MANAGEMENT_API_KEY")
    if not api_key:
        print("Error: AIDEFENSE_MANAGEMENT_API_KEY environment variable not set.")
        return

    # Configure the base URL(s). Adjust as appropriate for your environment.
    config = Config(
        management_base_url="https://api.preview.security.cisco.com",
        timeout=60,
    )

    client = AiValidationClient(api_key=api_key, config=config)

    task_id = None

    try:
        print("\n=== Start AI Validation Job ===")
        start_req = StartAiValidationRequest(
            asset_type=AssetType.APPLICATION,
            application_id="your-application-id",  # replace if needed
            validation_scan_name=f"SDK Example Scan {datetime.utcnow().isoformat()}",
            model_provider="OpenAI",
            headers=[Header(key="Authorization", value="Bearer <redacted>")],
            model_endpoint_url_model_id="gpt-4",
            model_request_template='{"messages": [{"role": "user", "content": "Hello"}]}',
            model_response_json_path="choices[0].message.content",
            aws_region=AWSRegion.AWS_REGION_US_EAST_1,
            max_tokens=128,
            temperature=0.2,
            top_p=0.9,
            stop_sequences=["<END>"],
        )

        start_resp = client.start_ai_validation(start_req)
        task_id = start_resp.task_id
        print(f"Started validation job. Task ID: {task_id}")

        print("\n=== Poll Job Status ===")
        for i in range(10):  # poll up to ~50s
            job = client.get_ai_validation_job(task_id)
            print(
                f"Attempt {i+1}: status={job.status} progress={job.progress}% error='{job.error_message or ''}'"
            )
            if str(job.status) in ("JOB_COMPLETED", "JOB_FAILED"):
                break
            time.sleep(5)

        print("\n=== List All Validation Configs ===")
        cfgs = client.list_all_ai_validation_config()
        print(f"Found {len(cfgs.config)} config(s)")
        for c in cfgs.config[:3]:  # print at most 3
            print(
                f"- {c.config_id} | asset_type={c.asset_type} | provider={c.model_provider}"
            )

        if task_id:
            print("\n=== Get Validation Config For Task ===")
            cfg = client.get_ai_validation_config(task_id)
            print(
                f"Config ID: {cfg.config_id} | asset_type={cfg.asset_type} | provider={cfg.model_provider}"
            )

    except (ValidationError, ApiError, SDKError) as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
