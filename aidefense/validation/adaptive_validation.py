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

"""Adaptive (red team) validation resource for the AI Defense Validation API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .client import _Api

from ._generated.ai_validation.v1.red_team_pydantic import (
    StartAdaptiveRedTeamRequest,
    StartRedTeamJobResponse,
    GetRedTeamJobResponse,
    ListRedTeamJobsRequest,
    ListRedTeamJobsResponse,
    UpdateRedTeamJobRequest,
    UpdateRedTeamJobResponse,
    PauseRedTeamJobResponse,
    ResumeRedTeamJobResponse,
    CancelRedTeamJobResponse,
    RestartRedTeamJobResponse,
    DeleteRedTeamJobResponse,
    GetRedTeamReportResponse,
    ResumeRedTeamJobOptions,
    RestartRedTeamJobOptions,
)
from .routes import (
    red_team_adaptive,
    red_team_jobs,
    red_team_job,
    red_team_job_pause,
    red_team_job_resume,
    red_team_job_cancel,
    red_team_job_restart,
    red_team_job_report,
)


class AdaptiveValidation:
    """
    Run and manage adaptive (red-team) validation jobs.

    Adaptive validation uses an AI attacker that iteratively probes the target,
    learning from each response to discover weaknesses.
    """

    def __init__(self, api: _Api):
        self._api = api

    # ------------------------------------------------------------------
    # Job lifecycle
    # ------------------------------------------------------------------

    def start(
        self, request: StartAdaptiveRedTeamRequest
    ) -> StartRedTeamJobResponse:
        """Start a new adaptive red-team validation job."""
        data = request.model_dump(exclude_defaults=True)
        response = self._api.request("POST", red_team_adaptive(), data=data)
        return self._api.parse(
            StartRedTeamJobResponse, response, "start adaptive validation response"
        )

    def get_job(self, job_id: str) -> GetRedTeamJobResponse:
        """Get details of a red-team job."""
        self._api.ensure_uuid(job_id, "job_id")
        response = self._api.request("GET", red_team_job(job_id))
        return self._api.parse(
            GetRedTeamJobResponse, response, "get red team job response"
        )

    def list_jobs(
        self, request: ListRedTeamJobsRequest
    ) -> ListRedTeamJobsResponse:
        """List red-team jobs with optional filtering and pagination."""
        params = request.model_dump(exclude_defaults=True)
        response = self._api.request("GET", red_team_jobs(), params=params)
        return self._api.parse(
            ListRedTeamJobsResponse, response, "list red team jobs response"
        )

    def update_job(
        self, job_id: str, request: UpdateRedTeamJobRequest
    ) -> UpdateRedTeamJobResponse:
        """Update a red-team job (e.g. rename or change description)."""
        self._api.ensure_uuid(job_id, "job_id")
        data = request.model_dump(exclude_defaults=True)
        response = self._api.request("PATCH", red_team_job(job_id), data=data)
        return self._api.parse(
            UpdateRedTeamJobResponse, response, "update red team job response"
        )

    def pause_job(self, job_id: str) -> PauseRedTeamJobResponse:
        """Pause a running red-team job."""
        self._api.ensure_uuid(job_id, "job_id")
        response = self._api.request("POST", red_team_job_pause(job_id))
        return self._api.parse(
            PauseRedTeamJobResponse, response, "pause red team job response"
        )

    def resume_job(
        self,
        job_id: str,
        options: Optional[ResumeRedTeamJobOptions] = None,
    ) -> ResumeRedTeamJobResponse:
        """Resume a paused red-team job."""
        self._api.ensure_uuid(job_id, "job_id")
        data = options.model_dump(exclude_defaults=True) if options else None
        response = self._api.request(
            "POST", red_team_job_resume(job_id), data=data
        )
        return self._api.parse(
            ResumeRedTeamJobResponse, response, "resume red team job response"
        )

    def cancel_job(self, job_id: str) -> CancelRedTeamJobResponse:
        """Cancel a running or paused red-team job."""
        self._api.ensure_uuid(job_id, "job_id")
        response = self._api.request("POST", red_team_job_cancel(job_id))
        return self._api.parse(
            CancelRedTeamJobResponse, response, "cancel red team job response"
        )

    def restart_job(
        self,
        job_id: str,
        options: Optional[RestartRedTeamJobOptions] = None,
    ) -> RestartRedTeamJobResponse:
        """Restart a completed, cancelled, or failed red-team job."""
        self._api.ensure_uuid(job_id, "job_id")
        data = options.model_dump(exclude_defaults=True) if options else None
        response = self._api.request(
            "POST", red_team_job_restart(job_id), data=data
        )
        return self._api.parse(
            RestartRedTeamJobResponse, response, "restart red team job response"
        )

    def delete_job(self, job_id: str) -> DeleteRedTeamJobResponse:
        """Delete a red-team job and its associated data."""
        self._api.ensure_uuid(job_id, "job_id")
        response = self._api.request("DELETE", red_team_job(job_id))
        return self._api.parse(
            DeleteRedTeamJobResponse, response, "delete red team job response"
        )

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    def get_report(self, job_id: str) -> GetRedTeamReportResponse:
        """Get the report for a completed red-team job."""
        self._api.ensure_uuid(job_id, "job_id")
        response = self._api.request("GET", red_team_job_report(job_id))
        return self._api.parse(
            GetRedTeamReportResponse, response, "get red team report response"
        )
