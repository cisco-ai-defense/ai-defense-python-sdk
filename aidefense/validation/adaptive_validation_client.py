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

"""Adaptive (red team) validation client for the AI Defense Validation API."""

from typing import Optional

from ..management.auth import ManagementAuth
from ..management.base_client import BaseClient
from ..config import Config
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


class AdaptiveValidationClient(BaseClient):
    """
    Client for running and managing adaptive (red-team) validation jobs.

    Adaptive validation uses an AI attacker that iteratively probes the target,
    learning from each response to discover weaknesses.
    """

    def __init__(
        self,
        auth: ManagementAuth,
        config: Optional[Config] = None,
        request_handler=None,
    ):
        super().__init__(auth, config, request_handler)

    # ------------------------------------------------------------------
    # Job lifecycle
    # ------------------------------------------------------------------

    def start(
        self, request: StartAdaptiveRedTeamRequest
    ) -> StartRedTeamJobResponse:
        """
        Start a new adaptive red-team validation job.

        Args:
            request: Red-team start request including target configuration,
                industry, goals, and optional constraints.

        Returns:
            StartRedTeamJobResponse: Contains the created job ID.

        Raises:
            ValidationError, ApiError, SDKError
        """
        data = request.model_dump(exclude_defaults=True)
        response = self.make_request("POST", red_team_adaptive(), data=data)
        return self._parse_response(
            StartRedTeamJobResponse, response, "start adaptive validation response"
        )

    def get_job(self, job_id: str) -> GetRedTeamJobResponse:
        """
        Get details of a red-team job.

        Args:
            job_id: The job identifier.

        Returns:
            GetRedTeamJobResponse: Full job details and config.

        Raises:
            ValidationError, ApiError, SDKError
        """
        self._ensure_uuid(job_id, "job_id")
        response = self.make_request("GET", red_team_job(job_id))
        return self._parse_response(
            GetRedTeamJobResponse, response, "get red team job response"
        )

    def list_jobs(
        self, request: ListRedTeamJobsRequest
    ) -> ListRedTeamJobsResponse:
        """
        List red-team jobs with optional filtering and pagination.

        Args:
            request: List request with optional filters, sort, limit, offset.

        Returns:
            ListRedTeamJobsResponse: Paginated list of red-team jobs.

        Raises:
            ValidationError, ApiError, SDKError
        """
        params = request.model_dump(exclude_defaults=True)
        response = self.make_request("GET", red_team_jobs(), params=params)
        return self._parse_response(
            ListRedTeamJobsResponse, response, "list red team jobs response"
        )

    def update_job(
        self, job_id: str, request: UpdateRedTeamJobRequest
    ) -> UpdateRedTeamJobResponse:
        """
        Update a red-team job (e.g. rename or change description).

        Args:
            job_id: The job identifier.
            request: Fields to update.

        Returns:
            UpdateRedTeamJobResponse: The update response.

        Raises:
            ValidationError, ApiError, SDKError
        """
        self._ensure_uuid(job_id, "job_id")
        data = request.model_dump(exclude_defaults=True)
        response = self.make_request("PATCH", red_team_job(job_id), data=data)
        return self._parse_response(
            UpdateRedTeamJobResponse, response, "update red team job response"
        )

    def pause_job(self, job_id: str) -> PauseRedTeamJobResponse:
        """
        Pause a running red-team job.

        Args:
            job_id: The job identifier.

        Returns:
            PauseRedTeamJobResponse: Updated job status.

        Raises:
            ValidationError, ApiError, SDKError
        """
        self._ensure_uuid(job_id, "job_id")
        response = self.make_request("POST", red_team_job_pause(job_id))
        return self._parse_response(
            PauseRedTeamJobResponse, response, "pause red team job response"
        )

    def resume_job(
        self,
        job_id: str,
        options: Optional[ResumeRedTeamJobOptions] = None,
    ) -> ResumeRedTeamJobResponse:
        """
        Resume a paused red-team job.

        Args:
            job_id: The job identifier.
            options: Optional resume options.

        Returns:
            ResumeRedTeamJobResponse: Updated job status.

        Raises:
            ValidationError, ApiError, SDKError
        """
        self._ensure_uuid(job_id, "job_id")
        data = options.model_dump(exclude_defaults=True) if options else None
        response = self.make_request(
            "POST", red_team_job_resume(job_id), data=data
        )
        return self._parse_response(
            ResumeRedTeamJobResponse, response, "resume red team job response"
        )

    def cancel_job(self, job_id: str) -> CancelRedTeamJobResponse:
        """
        Cancel a running or paused red-team job.

        Args:
            job_id: The job identifier.

        Returns:
            CancelRedTeamJobResponse: Updated job status.

        Raises:
            ValidationError, ApiError, SDKError
        """
        self._ensure_uuid(job_id, "job_id")
        response = self.make_request("POST", red_team_job_cancel(job_id))
        return self._parse_response(
            CancelRedTeamJobResponse, response, "cancel red team job response"
        )

    def restart_job(
        self,
        job_id: str,
        options: Optional[RestartRedTeamJobOptions] = None,
    ) -> RestartRedTeamJobResponse:
        """
        Restart a completed, cancelled, or failed red-team job.

        Args:
            job_id: The job identifier.
            options: Optional restart options.

        Returns:
            RestartRedTeamJobResponse: Updated job status.

        Raises:
            ValidationError, ApiError, SDKError
        """
        self._ensure_uuid(job_id, "job_id")
        data = options.model_dump(exclude_defaults=True) if options else None
        response = self.make_request(
            "POST", red_team_job_restart(job_id), data=data
        )
        return self._parse_response(
            RestartRedTeamJobResponse, response, "restart red team job response"
        )

    def delete_job(self, job_id: str) -> DeleteRedTeamJobResponse:
        """
        Delete a red-team job and its associated data.

        Args:
            job_id: The job identifier.

        Returns:
            DeleteRedTeamJobResponse: Deletion confirmation.

        Raises:
            ValidationError, ApiError, SDKError
        """
        self._ensure_uuid(job_id, "job_id")
        response = self.make_request("DELETE", red_team_job(job_id))
        return self._parse_response(
            DeleteRedTeamJobResponse, response, "delete red team job response"
        )

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    def get_report(self, job_id: str) -> GetRedTeamReportResponse:
        """
        Get the report for a completed red-team job.

        Args:
            job_id: The job identifier.

        Returns:
            GetRedTeamReportResponse: The job report with findings and recommendations.

        Raises:
            ValidationError, ApiError, SDKError
        """
        self._ensure_uuid(job_id, "job_id")
        response = self.make_request("GET", red_team_job_report(job_id))
        return self._parse_response(
            GetRedTeamReportResponse, response, "get red team report response"
        )
