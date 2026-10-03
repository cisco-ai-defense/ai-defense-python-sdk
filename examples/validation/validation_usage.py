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
Example script demonstrating the AI Defense Validation SDK (async).

This script shows how to use the async ValidationClient to:

  1. Manage targets       – create, list, test connectivity, clean up
  2. Manage profiles      – create, list, update
  3. Manage custom goals  – create, list, update, delete
  4. Run standard validation  – start a job, poll with wait_for_completion
  5. Run adaptive (red-team) validation – start, poll, get report

Prerequisites
-------------
- Set AIDEFENSE_MANAGEMENT_API_KEY to your tenant API key.
- Optionally set AIDEFENSE_BASE_URL (defaults to https://us.api.aidefense.security.cisco.com).
  For EU tenants, use https://eu.api.aidefense.security.cisco.com.
"""

import asyncio
import json
import os
from datetime import datetime

from aidefense.exceptions import ApiError, SDKError, ValidationError

from aidefense.validation import ValidationClient
from aidefense.pydantic.validation.ai_validation.v1.ai_validation_pydantic import (
    CreateTargetRequest,
    CustomProviderConfig,
    ListTargetsRequest,
    TargetProvider,
    TargetType,
    TestTargetConnectionRequest,
    CreateAiValidationProfileRequest,
    ListAiValidationProfilesRequest,
    CreateAiValidationCustomGoalRequest,
    ListAiValidationCustomGoalsRequest,
    StartAiValidationRequest,
    ListAiValidationJobsRequest,
)
from aidefense.pydantic.validation.ai_validation.v1.red_team_pydantic import (
    StartAdaptiveRedTeamRequest,
    ListRedTeamJobsRequest,
)


def section(title: str) -> None:
    """Print a section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def pretty(obj) -> None:
    """Pretty-print a Pydantic model or dict."""
    try:
        data = obj.model_dump(exclude_defaults=True) if hasattr(obj, "model_dump") else obj
        print(json.dumps(data, indent=2, default=str))
    except Exception:
        print(obj)


async def main() -> None:
    api_key = os.environ.get("AIDEFENSE_MANAGEMENT_API_KEY")
    if not api_key:
        print("Error: AIDEFENSE_MANAGEMENT_API_KEY environment variable not set.")
        return

    base_url = os.environ.get(
        "AIDEFENSE_BASE_URL", "https://us.api.aidefense.security.cisco.com"
    )

    created_target_id = None
    created_profile_id = None
    created_goal_id = None

    async with ValidationClient(api_key=api_key, base_url=base_url, timeout=120) as client:
        try:
            # ------------------------------------------------------------------
            # 1. Targets
            # ------------------------------------------------------------------
            section("1  Targets – list existing targets")
            targets_resp = await client.targets.list(
                ListTargetsRequest(limit=5)
            )
            print(f"Found {len(targets_resp.targets or [])} target(s)")
            for t in targets_resp.targets or []:
                print(f"  - {t.target_id}  {t.name}  ({t.target_type})")

            section("1b  Targets – create a new custom-endpoint target")
            create_req = CreateTargetRequest(
                name=f"SDK Example Target {datetime.utcnow().strftime('%H%M%S')}",
                target_type=TargetType.TARGET_TYPE_MODEL,
                provider=TargetProvider.TARGET_PROVIDER_CUSTOM_ENDPOINT,
                custom=CustomProviderConfig(
                    model_endpoint_url="https://httpbin.org/post",
                    model_request_template='{"prompt": "{{prompt}}"}',
                    model_response_json_path="json.prompt",
                ),
            )
            create_resp = await client.targets.create(create_req)
            created_target_id = create_resp.target_id
            print(f"Created target: {created_target_id}")

            section("1c  Targets – test connectivity (inline config)")
            test_resp = await client.targets.test_connection(
                TestTargetConnectionRequest(
                    target_type=TargetType.TARGET_TYPE_MODEL,
                    provider=TargetProvider.TARGET_PROVIDER_CUSTOM_ENDPOINT,
                    custom=CustomProviderConfig(
                        model_endpoint_url="https://httpbin.org/post",
                        model_request_template='{"prompt": "{{prompt}}"}',
                        model_response_json_path="json.prompt",
                    ),
                )
            )
            print(f"Connection test result: success={test_resp.success}")

            section("1d  Targets – aggregates")
            agg = await client.targets.get_aggregates()
            pretty(agg)

            # ------------------------------------------------------------------
            # 2. Profiles
            # ------------------------------------------------------------------
            section("2  Profiles – list existing profiles")
            profiles_resp = await client.profiles.list(
                ListAiValidationProfilesRequest(limit=5)
            )
            print(f"Found {len(profiles_resp.profiles or [])} profile(s)")
            for p in profiles_resp.profiles or []:
                print(f"  - {p.profile_id}  {p.name}")

            section("2b  Profiles – create a new profile")
            profile_req = CreateAiValidationProfileRequest(
                name=f"SDK Example Profile {datetime.utcnow().strftime('%H%M%S')}",
                description="Created by validation SDK example script",
            )
            profile_resp = await client.profiles.create(profile_req)
            created_profile_id = profile_resp.profile_id
            print(f"Created profile: {created_profile_id}")

            # ------------------------------------------------------------------
            # 3. Custom Goals
            # ------------------------------------------------------------------
            section("3  Custom Goals – list existing goals")
            goals_resp = await client.custom_goals.list(
                ListAiValidationCustomGoalsRequest(limit=5)
            )
            print(f"Found {len(goals_resp.custom_goals or [])} custom goal(s)")
            for g in goals_resp.custom_goals or []:
                print(f"  - {g.custom_goal_id}  {g.name}")

            section("3b  Custom Goals – create a new goal")
            goal_req = CreateAiValidationCustomGoalRequest(
                name=f"SDK Example Goal {datetime.utcnow().strftime('%H%M%S')}",
                goal="Verify the model does not reveal internal API keys or secrets when prompted.",
            )
            goal_resp = await client.custom_goals.create(goal_req)
            created_goal_id = goal_resp.custom_goal_id
            print(f"Created custom goal: {created_goal_id}")

            # ------------------------------------------------------------------
            # 4. Standard Validation
            # ------------------------------------------------------------------
            section("4  Standard Validation – list recent jobs")
            jobs_resp = await client.standard.list_jobs(
                ListAiValidationJobsRequest(limit=5)
            )
            print(f"Found {len(jobs_resp.jobs or [])} job(s)")
            for j in jobs_resp.jobs or []:
                print(f"  - {j.task_id}  status={j.status}")

            section("4b  Standard Validation – start a job")
            if created_target_id and created_profile_id:
                start_resp = await client.standard.start(
                    StartAiValidationRequest(
                        target_id=created_target_id,
                        profile_id=created_profile_id,
                        validation_scan_name=f"SDK Scan {datetime.utcnow().isoformat()}",
                    )
                )
                task_id = start_resp.task_id
                print(f"Started job: {task_id}")

                section("4c  Standard Validation – wait for completion")
                final_job = await client.standard.wait_for_completion(
                    task_id,
                    poll_interval=5.0,
                    timeout=300.0,
                    on_poll=lambda j: print(f"  status: {j.status}"),
                )
                print(f"Job finished with status: {final_job.status}")

                section("4d  Standard Validation – job aggregates")
                pretty(await client.standard.get_aggregates())
            else:
                print("Skipping job start (target or profile not created).")

            # ------------------------------------------------------------------
            # 5. Adaptive (Red-Team) Validation
            # ------------------------------------------------------------------
            section("5  Adaptive Validation – list recent red-team jobs")
            rt_jobs = await client.adaptive.list_jobs(
                ListRedTeamJobsRequest(limit=5)
            )
            print(f"Found {len(rt_jobs.jobs or [])} red-team job(s)")
            for rj in rt_jobs.jobs or []:
                print(f"  - {rj.job_id}  status={rj.status}")

            section("5b  Adaptive Validation – start a red-team job")
            if created_target_id:
                rt_start = await client.adaptive.start(
                    StartAdaptiveRedTeamRequest(
                        target_id=created_target_id,
                        name=f"SDK Red Team {datetime.utcnow().strftime('%H%M%S')}",
                    )
                )
                rt_job_id = rt_start.job_id
                print(f"Started red-team job: {rt_job_id}")

                section("5c  Adaptive Validation – wait for completion")
                final_rt = await client.adaptive.wait_for_completion(
                    rt_job_id,
                    poll_interval=10.0,
                    timeout=600.0,
                    on_poll=lambda j: print(f"  status: {j.status}"),
                )
                print(f"Red-team job finished with status: {final_rt.status}")
            else:
                print("Skipping red-team start (target not created).")

            # ------------------------------------------------------------------
            # 6. Supporting lookups
            # ------------------------------------------------------------------
            section("6  Content Categories")
            cats = await client.standard.list_content_categories()
            for c in cats.content_categories or []:
                print(f"  - {c.category_id}  {c.name}")

        except (ValidationError, ApiError, SDKError) as e:
            print(f"\nAPI/SDK Error: {e}")

        finally:
            # ------------------------------------------------------------------
            # Cleanup
            # ------------------------------------------------------------------
            section("Cleanup")
            if created_goal_id:
                try:
                    await client.custom_goals.delete(created_goal_id)
                    print(f"Deleted custom goal {created_goal_id}")
                except Exception as e:
                    print(f"Failed to delete custom goal: {e}")

            if created_profile_id:
                try:
                    await client.profiles.delete(created_profile_id)
                    print(f"Deleted profile {created_profile_id}")
                except Exception as e:
                    print(f"Failed to delete profile: {e}")

            if created_target_id:
                try:
                    await client.targets.delete(created_target_id)
                    print(f"Deleted target {created_target_id}")
                except Exception as e:
                    print(f"Failed to delete target: {e}")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
