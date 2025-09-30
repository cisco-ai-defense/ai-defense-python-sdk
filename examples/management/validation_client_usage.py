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
import json
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


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def pretty_model(model) -> None:
    try:
        print(
            json.dumps(
                model.dict(by_alias=True, exclude_none=True),
                indent=2,
                default=str,
            )
        )
    except Exception:
        # Fallback
        print(model)


def fmt_ts(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%d %H:%M:%S") if ts else "-"


def main():
    api_key = os.environ.get("AIDEFENSE_MANAGEMENT_API_KEY")
    if not api_key:
        print("Error: AIDEFENSE_MANAGEMENT_API_KEY environment variable not set.")
        return

    # Configure the base URL(s). Adjust as appropriate for your environment.
    config = Config(
        management_base_url="https://api.security.cisco.com",
        timeout=60,
    )

    client = AiValidationClient(api_key=api_key, config=config)

    task_id = None

    try:
        section("Start AI Validation Job")
        start_req = StartAiValidationRequest(
            asset_type=AssetType.EXTERNAL,
            application_id="",  # replace if needed
            validation_scan_name=f"SDK Example Scan {datetime.utcnow().isoformat()}",
            model_provider="",
            headers=[Header(key="Authorization", value="Bearer <redacted>")],
            model_endpoint_url_model_id="https://abcd.tools.mock.io/success",
            model_request_template='{"a": "{{prompt}}"}',
            model_response_json_path="response",
            aws_region=AWSRegion.AWS_REGION_US_WEST_2,
            max_tokens=128,
            temperature=0.2,
            top_p=0.9,
            stop_sequences=["<END>"],
        )

        # Summarize request
        print("Request summary:")
        print(f"- asset_type:            {start_req.asset_type}")
        print(f"- validation_scan_name:  {start_req.validation_scan_name}")
        print(f"- endpoint/model_id:     {start_req.model_endpoint_url_model_id}")
        print(f"- response_json_path:    {start_req.model_response_json_path}")
        print(f"- aws_region:            {start_req.aws_region}")

        start_time = time.time()
        start_resp = client.start_ai_validation(start_req)
        task_id = start_resp.task_id
        print(f"\nStarted validation job. Task ID: {task_id}")

        section("Poll Job Status")
        header = "{:>3s}  {:<15s}  {}".format("#", "status", "error")
        print(header)
        print("-" * len(header))
        final_job = None
        for i in range(10):  # poll up to ~50s
            job = client.get_ai_validation_job(task_id)
            final_job = job
            status_str = str(job.status or "")
            err = job.error_message or ""
            print("{:>3d}  {:<15s} {}".format(i + 1, status_str, err))
            if status_str in ("JOB_COMPLETED", "JOB_FAILED"):
                break
            time.sleep(5)

        if final_job is not None:
            print("\nTimestamps:")
            print(f"- created_at:   {fmt_ts(final_job.created_at)}")
            print(f"- started_at:   {fmt_ts(final_job.started_at)}")
            print(f"- completed_at: {fmt_ts(final_job.completed_at)}")

        duration = time.time() - start_time
        print(f"\nElapsed: {duration:.1f}s")

        section("List All Validation Configs")
        cfgs = client.list_all_ai_validation_config()
        print(f"Found {len(cfgs.config)} config(s)")
        if cfgs.config:
            print("{:<38s}  {:<10s}  {}".format("config_id", "asset", "provider"))
            print("-" * 70)
            for c in cfgs.config[:3]:  # print at most 3
                print(
                    "{:<38s}  {:<10s}  {}".format(
                        c.config_id or "-",
                        (c.asset_type or "-") if isinstance(c.asset_type, str) else str(c.asset_type or "-"),
                        c.model_provider or "-",
                    )
                )
        if task_id:
            section("Get Validation Config For Task")
            cfg = client.get_ai_validation_config(task_id)
            pretty_model(cfg)

    except (ValidationError, ApiError, SDKError) as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
