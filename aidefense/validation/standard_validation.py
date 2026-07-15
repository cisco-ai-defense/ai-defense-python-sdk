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

"""Standard validation resource for the AI Defense Validation API.

Covers job lifecycle (start, pause, resume, cancel, restart, delete),
job listing/aggregates, results retrieval, config management, and
supporting lookups (model IDs, asset names, content categories).
"""

from typing import Optional

from ..management.auth import ManagementAuth
from ..management.base_client import BaseClient
from ..config import Config
from ._generated.ai_validation.v1.ai_validation_pydantic import (
    StartAiValidationRequest,
    StartAiValidationResponse,
    GetAiValidationJobResponse,
    PauseAiValidationJobResponse,
    ResumeAiValidationJobResponse,
    CancelAiValidationJobResponse,
    RestartAiValidationJobResponse,
    ListAiValidationJobsRequest,
    ListAiValidationJobsResponse,
    GetAiValidationJobAggregatesResponse,
    DeleteAiValidationJobResponse,
    GetAiValidationConfigResponse,
    UpdateAiValidationConfigRequest,
    UpdateAiValidationConfigResponse,
    ListAiValidationResultsRequest,
    ListAiValidationResultsResponse,
    ListAiValidationResultsDetailRequest,
    ListAiValidationResultsDetailResponse,
    GetAiValidationResultResponse,
    GetAiValidationResultErrorDetailResponse,
    ListAiValidationDataForModelIdRequest,
    ListAiValidationDataForModelIdResponse,
    ListAiAssetNamesRequest,
    ListAiAssetNamesResponse,
    ListContentCategoriesResponse,
    GetJobResultsSummaryResponse,
    ResumeAiValidationJobOptions,
    RestartAiValidationJobOptions,
)
from .routes import (
    ai_validation_start,
    ai_validation_start_multi,
    ai_validation_jobs,
    ai_validation_job,
    ai_validation_job_pause,
    ai_validation_job_resume,
    ai_validation_job_cancel,
    ai_validation_job_restart,
    ai_validation_job_delete,
    ai_validation_jobs_aggregates,
    ai_validation_job_results_summary,
    ai_validation_results,
    ai_validation_results_detail,
    ai_validation_result,
    ai_validation_attack_error_detail,
    ai_validation_config,
    ai_validation_config_by_task,
    ai_validation_data_model_id,
    ai_validation_asset_names,
    ai_validation_content_categories,
)


class StandardValidation(BaseClient):
    """
    Run and manage standard (non-adaptive) validation jobs.

    Standard validation runs a fixed set of attack techniques against a target,
    driven by a validation profile.
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
        self, request: StartAiValidationRequest
    ) -> StartAiValidationResponse:
        """Start a new standard validation job."""
        data = request.model_dump(exclude_defaults=True)
        response = self.make_request("POST", ai_validation_start(), data=data)
        return self._parse_response(
            StartAiValidationResponse, response, "start validation response"
        )

    def start_multi(
        self, request: StartAiValidationRequest
    ) -> StartAiValidationResponse:
        """Start a multi-target standard validation job."""
        data = request.model_dump(exclude_defaults=True)
        response = self.make_request("POST", ai_validation_start_multi(), data=data)
        return self._parse_response(
            StartAiValidationResponse, response, "start multi validation response"
        )

    def get_job(self, task_id: str) -> GetAiValidationJobResponse:
        """Get details of a validation job."""
        response = self.make_request("GET", ai_validation_job(task_id))
        return self._parse_response(
            GetAiValidationJobResponse, response, "get job response"
        )

    def list_jobs(
        self, request: ListAiValidationJobsRequest
    ) -> ListAiValidationJobsResponse:
        """List validation jobs with optional filtering and pagination."""
        params = request.model_dump(exclude_defaults=True)
        response = self.make_request("GET", ai_validation_jobs(), params=params)
        return self._parse_response(
            ListAiValidationJobsResponse, response, "list jobs response"
        )

    def pause_job(self, job_id: str) -> PauseAiValidationJobResponse:
        """Pause a running validation job."""
        response = self.make_request("POST", ai_validation_job_pause(job_id))
        return self._parse_response(
            PauseAiValidationJobResponse, response, "pause job response"
        )

    def resume_job(
        self,
        job_id: str,
        options: Optional[ResumeAiValidationJobOptions] = None,
    ) -> ResumeAiValidationJobResponse:
        """Resume a paused validation job."""
        data = options.model_dump(exclude_defaults=True) if options else None
        response = self.make_request(
            "POST", ai_validation_job_resume(job_id), data=data
        )
        return self._parse_response(
            ResumeAiValidationJobResponse, response, "resume job response"
        )

    def cancel_job(self, job_id: str) -> CancelAiValidationJobResponse:
        """Cancel a running or paused validation job."""
        response = self.make_request("POST", ai_validation_job_cancel(job_id))
        return self._parse_response(
            CancelAiValidationJobResponse, response, "cancel job response"
        )

    def restart_job(
        self,
        job_id: str,
        options: Optional[RestartAiValidationJobOptions] = None,
    ) -> RestartAiValidationJobResponse:
        """Restart a completed, cancelled, or failed validation job."""
        data = options.model_dump(exclude_defaults=True) if options else None
        response = self.make_request(
            "POST", ai_validation_job_restart(job_id), data=data
        )
        return self._parse_response(
            RestartAiValidationJobResponse, response, "restart job response"
        )

    def delete_job(self, task_id: str) -> DeleteAiValidationJobResponse:
        """Delete a validation job and its associated data."""
        response = self.make_request("DELETE", ai_validation_job_delete(task_id))
        return self._parse_response(
            DeleteAiValidationJobResponse, response, "delete job response"
        )

    def get_aggregates(self) -> GetAiValidationJobAggregatesResponse:
        """Get aggregate counts for validation jobs grouped by status."""
        response = self.make_request("GET", ai_validation_jobs_aggregates())
        return self._parse_response(
            GetAiValidationJobAggregatesResponse,
            response,
            "get job aggregates response",
        )

    def get_results_summary(
        self, task_id: str
    ) -> GetJobResultsSummaryResponse:
        """Get a summary of results for a job including severity counts."""
        response = self.make_request(
            "GET", ai_validation_job_results_summary(task_id)
        )
        return self._parse_response(
            GetJobResultsSummaryResponse, response, "get job results summary response"
        )

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    def list_results(
        self, task_id: str, request: ListAiValidationResultsRequest
    ) -> ListAiValidationResultsResponse:
        """List validation results for a job."""
        params = request.model_dump(exclude_defaults=True)
        response = self.make_request(
            "GET", ai_validation_results(task_id), params=params
        )
        return self._parse_response(
            ListAiValidationResultsResponse, response, "list results response"
        )

    def list_results_detail(
        self, task_id: str, request: ListAiValidationResultsDetailRequest
    ) -> ListAiValidationResultsDetailResponse:
        """List detailed validation results including prompt/response pairs."""
        params = request.model_dump(exclude_defaults=True)
        response = self.make_request(
            "GET", ai_validation_results_detail(task_id), params=params
        )
        return self._parse_response(
            ListAiValidationResultsDetailResponse,
            response,
            "list results detail response",
        )

    def get_result(
        self, task_id: str, attack_id: str
    ) -> GetAiValidationResultResponse:
        """Get a single validation result by task and attack IDs."""
        response = self.make_request(
            "GET", ai_validation_result(task_id, attack_id)
        )
        return self._parse_response(
            GetAiValidationResultResponse, response, "get result response"
        )

    def get_attack_error_detail(
        self, task_id: str, attack_id: str
    ) -> GetAiValidationResultErrorDetailResponse:
        """Get error details for a specific failed attack attempt."""
        response = self.make_request(
            "GET", ai_validation_attack_error_detail(task_id, attack_id)
        )
        return self._parse_response(
            GetAiValidationResultErrorDetailResponse,
            response,
            "get attack error detail response",
        )

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    def get_config(self) -> GetAiValidationConfigResponse:
        """Get the current validation configuration."""
        response = self.make_request("GET", ai_validation_config())
        return self._parse_response(
            GetAiValidationConfigResponse, response, "get config response"
        )

    def get_config_by_task(self, task_id: str) -> GetAiValidationConfigResponse:
        """Get the validation configuration used for a specific job."""
        response = self.make_request("GET", ai_validation_config_by_task(task_id))
        return self._parse_response(
            GetAiValidationConfigResponse, response, "get config by task response"
        )

    def update_config(
        self, request: UpdateAiValidationConfigRequest
    ) -> UpdateAiValidationConfigResponse:
        """Update the validation configuration."""
        data = request.model_dump(exclude_defaults=True)
        response = self.make_request("PUT", ai_validation_config(), data=data)
        return self._parse_response(
            UpdateAiValidationConfigResponse, response, "update config response"
        )

    # ------------------------------------------------------------------
    # Supporting lookups
    # ------------------------------------------------------------------

    def list_data_for_model_id(
        self, request: ListAiValidationDataForModelIdRequest
    ) -> ListAiValidationDataForModelIdResponse:
        """List validation data available for a given model ID."""
        params = request.model_dump(exclude_defaults=True)
        response = self.make_request(
            "GET", ai_validation_data_model_id(), params=params
        )
        return self._parse_response(
            ListAiValidationDataForModelIdResponse,
            response,
            "list data for model id response",
        )

    def list_asset_names(
        self, request: ListAiAssetNamesRequest
    ) -> ListAiAssetNamesResponse:
        """List asset names available for validation."""
        params = request.model_dump(exclude_defaults=True)
        response = self.make_request(
            "GET", ai_validation_asset_names(), params=params
        )
        return self._parse_response(
            ListAiAssetNamesResponse, response, "list asset names response"
        )

    def list_content_categories(self) -> ListContentCategoriesResponse:
        """List available content categories for validation."""
        response = self.make_request("GET", ai_validation_content_categories())
        return self._parse_response(
            ListContentCategoriesResponse,
            response,
            "list content categories response",
        )
