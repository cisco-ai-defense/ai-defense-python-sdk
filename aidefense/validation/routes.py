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
"""Internal route helpers for the AI Defense Validation API.

These helpers centralize relative API paths used by the validation clients.
They are intentionally kept internal so that end users do not override or
depend on these paths directly.

All paths returned here are relative. `_Api.request()` is responsible
for adding the base URL and API version.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Top-level resource names
# ---------------------------------------------------------------------------
AI_VALIDATION = "ai-validation"
RED_TEAM = "red-team"

# ===========================================================================
# Standard Validation (ai_validation.proto)
# ===========================================================================

# --- Jobs ------------------------------------------------------------------


def ai_validation_start() -> str:
    return f"{AI_VALIDATION}/start"


def ai_validation_start_multi() -> str:
    return f"{ai_validation_start()}/multi"


def ai_validation_jobs() -> str:
    return f"{AI_VALIDATION}/jobs"


def ai_validation_job_pause(job_id: str) -> str:
    return f"{ai_validation_jobs()}/{job_id}/pause"


def ai_validation_job_resume(job_id: str) -> str:
    return f"{ai_validation_jobs()}/{job_id}/resume"


def ai_validation_job_cancel(job_id: str) -> str:
    return f"{ai_validation_jobs()}/{job_id}/cancel"


def ai_validation_job_restart(job_id: str) -> str:
    return f"{ai_validation_jobs()}/{job_id}/restart"


def ai_validation_job(task_id: str) -> str:
    """Uses singular /job/ per proto definition (GetAiValidationJob RPC)."""
    return f"{AI_VALIDATION}/job/{task_id}"


def ai_validation_job_delete(task_id: str) -> str:
    return f"{ai_validation_jobs()}/{task_id}"


def ai_validation_jobs_aggregates() -> str:
    return f"{ai_validation_jobs()}/aggregates"


def ai_validation_job_results_summary(task_id: str) -> str:
    return f"{ai_validation_jobs()}/{task_id}/results/summary"


# --- Results ---------------------------------------------------------------


def ai_validation_results(task_id: str) -> str:
    return f"{AI_VALIDATION}/results/{task_id}"


def ai_validation_results_detail(task_id: str) -> str:
    return f"{AI_VALIDATION}/results-detail/{task_id}"


def ai_validation_result(task_id: str, attack_id: str) -> str:
    return f"{ai_validation_results(task_id)}/{attack_id}"


def ai_validation_attack_error_detail(task_id: str, attack_id: str) -> str:
    """Uses singular /job/ per proto definition (GetAttackErrorDetail RPC)."""
    return f"{ai_validation_job(task_id)}/attack/{attack_id}/error-detail"


# --- Config ----------------------------------------------------------------


def ai_validation_config() -> str:
    return f"{AI_VALIDATION}/config"


def ai_validation_config_by_task(task_id: str) -> str:
    return f"{ai_validation_config()}/{task_id}"


# --- Targets ---------------------------------------------------------------


def ai_validation_targets() -> str:
    return f"{AI_VALIDATION}/targets"


def ai_validation_target(target_id: str) -> str:
    return f"{ai_validation_targets()}/{target_id}"


def ai_validation_targets_aggregates() -> str:
    return f"{ai_validation_targets()}/aggregates"


def ai_validation_targets_test() -> str:
    return f"{ai_validation_targets()}/test"


def ai_validation_targets_aws_accounts() -> str:
    return f"{ai_validation_targets()}/aws-accounts"


# --- Profiles --------------------------------------------------------------


def ai_validation_profiles() -> str:
    return f"{AI_VALIDATION}/profiles"


def ai_validation_profile(profile_id: str) -> str:
    return f"{ai_validation_profiles()}/{profile_id}"


def ai_validation_profiles_by_goal(goal_id: str) -> str:
    return f"{ai_validation_profiles()}/goals/{goal_id}"


# --- Custom Goals ----------------------------------------------------------


def ai_validation_custom_goals() -> str:
    return f"{AI_VALIDATION}/custom-goals"


def ai_validation_custom_goal(custom_goal_id: str) -> str:
    return f"{ai_validation_custom_goals()}/{custom_goal_id}"


# --- Other -----------------------------------------------------------------


def ai_validation_data_model_id() -> str:
    return f"{AI_VALIDATION}/data/modelid"


def ai_validation_asset_names() -> str:
    return f"{AI_VALIDATION}/asset_names"


def ai_validation_content_categories() -> str:
    return f"{AI_VALIDATION}/content-categories"


# ===========================================================================
# Red Team (red_team.proto)
# ===========================================================================


def red_team_adaptive() -> str:
    return f"{RED_TEAM}/adaptive"


def red_team_jobs() -> str:
    return f"{RED_TEAM}/jobs"


def red_team_job(job_id: str) -> str:
    return f"{red_team_jobs()}/{job_id}"


def red_team_job_pause(job_id: str) -> str:
    return f"{red_team_job(job_id)}/pause"


def red_team_job_resume(job_id: str) -> str:
    return f"{red_team_job(job_id)}/resume"


def red_team_job_cancel(job_id: str) -> str:
    return f"{red_team_job(job_id)}/cancel"


def red_team_job_restart(job_id: str) -> str:
    return f"{red_team_job(job_id)}/restart"


def red_team_job_report(job_id: str) -> str:
    return f"{red_team_job(job_id)}/report"


__all__ = [
    # Resources
    "AI_VALIDATION",
    "RED_TEAM",
    # Jobs
    "ai_validation_start",
    "ai_validation_start_multi",
    "ai_validation_jobs",
    "ai_validation_job_pause",
    "ai_validation_job_resume",
    "ai_validation_job_cancel",
    "ai_validation_job_restart",
    "ai_validation_job",
    "ai_validation_job_delete",
    "ai_validation_jobs_aggregates",
    "ai_validation_job_results_summary",
    # Results
    "ai_validation_results",
    "ai_validation_results_detail",
    "ai_validation_result",
    "ai_validation_attack_error_detail",
    # Config
    "ai_validation_config",
    "ai_validation_config_by_task",
    # Targets
    "ai_validation_targets",
    "ai_validation_target",
    "ai_validation_targets_aggregates",
    "ai_validation_targets_test",
    "ai_validation_targets_aws_accounts",
    # Profiles
    "ai_validation_profiles",
    "ai_validation_profile",
    "ai_validation_profiles_by_goal",
    # Custom Goals
    "ai_validation_custom_goals",
    "ai_validation_custom_goal",
    # Other
    "ai_validation_data_model_id",
    "ai_validation_asset_names",
    "ai_validation_content_categories",
    # Red Team
    "red_team_adaptive",
    "red_team_jobs",
    "red_team_job",
    "red_team_job_pause",
    "red_team_job_resume",
    "red_team_job_cancel",
    "red_team_job_restart",
    "red_team_job_report",
]
