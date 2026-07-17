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

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from .client import _Api

from aidefense.pydantic.validation.ai_validation.v1.ai_validation_pydantic import (
    JobStatus,
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

_TERMINAL_STATUSES = frozenset({
    JobStatus.JOB_COMPLETED,
    JobStatus.JOB_FAILED,
    JobStatus.JOB_CANCELLED,
})


class StandardValidation:
    """
    Run and manage standard (non-adaptive) validation jobs.

    All methods are coroutines — call them with ``await``.
    """

    def __init__(self, api: _Api):
        self._api = api

    # ------------------------------------------------------------------
    # Job lifecycle
    # ------------------------------------------------------------------

    async def start(
        self, request: StartAiValidationRequest
    ) -> StartAiValidationResponse:
        """Start a new standard validation job."""
        data = request.model_dump(exclude_defaults=True)
        response = await self._api.request("POST", ai_validation_start(), data=data)
        return self._api.parse(
            StartAiValidationResponse, response, "start validation response"
        )

    async def start_multi(
        self, request: StartAiValidationRequest
    ) -> StartAiValidationResponse:
        """Start a multi-target standard validation job."""
        data = request.model_dump(exclude_defaults=True)
        response = await self._api.request("POST", ai_validation_start_multi(), data=data)
        return self._api.parse(
            StartAiValidationResponse, response, "start multi validation response"
        )

    async def get_job(self, task_id: str) -> GetAiValidationJobResponse:
        """Get details of a validation job."""
        self._api.ensure_uuid(task_id, "task_id")
        response = await self._api.request("GET", ai_validation_job(task_id))
        return self._api.parse(
            GetAiValidationJobResponse, response, "get job response"
        )

    async def list_jobs(
        self, request: ListAiValidationJobsRequest
    ) -> ListAiValidationJobsResponse:
        """List validation jobs with optional filtering and pagination."""
        params = request.model_dump(exclude_defaults=True)
        response = await self._api.request("GET", ai_validation_jobs(), params=params)
        return self._api.parse(
            ListAiValidationJobsResponse, response, "list jobs response"
        )

    async def pause_job(self, job_id: str) -> PauseAiValidationJobResponse:
        """Pause a running validation job.

        Note: This endpoint may not be available on all deployments.
        """
        self._api.ensure_uuid(job_id, "job_id")
        response = await self._api.request("POST", ai_validation_job_pause(job_id))
        return self._api.parse(
            PauseAiValidationJobResponse, response, "pause job response"
        )

    async def resume_job(
        self,
        job_id: str,
        options: Optional[ResumeAiValidationJobOptions] = None,
    ) -> ResumeAiValidationJobResponse:
        """Resume a paused validation job.

        Note: This endpoint may not be available on all deployments.
        """
        self._api.ensure_uuid(job_id, "job_id")
        data = options.model_dump(exclude_defaults=True) if options else None
        response = await self._api.request(
            "POST", ai_validation_job_resume(job_id), data=data
        )
        return self._api.parse(
            ResumeAiValidationJobResponse, response, "resume job response"
        )

    async def cancel_job(self, job_id: str) -> CancelAiValidationJobResponse:
        """Cancel a running or paused validation job.

        Note: This endpoint may not be available on all deployments.
        """
        self._api.ensure_uuid(job_id, "job_id")
        response = await self._api.request("POST", ai_validation_job_cancel(job_id))
        return self._api.parse(
            CancelAiValidationJobResponse, response, "cancel job response"
        )

    async def restart_job(
        self,
        job_id: str,
        options: Optional[RestartAiValidationJobOptions] = None,
    ) -> RestartAiValidationJobResponse:
        """Restart a completed, cancelled, or failed validation job.

        Note: This endpoint may not be available on all deployments.
        """
        self._api.ensure_uuid(job_id, "job_id")
        data = options.model_dump(exclude_defaults=True) if options else None
        response = await self._api.request(
            "POST", ai_validation_job_restart(job_id), data=data
        )
        return self._api.parse(
            RestartAiValidationJobResponse, response, "restart job response"
        )

    async def delete_job(self, task_id: str) -> DeleteAiValidationJobResponse:
        """Delete a validation job and its associated data."""
        self._api.ensure_uuid(task_id, "task_id")
        response = await self._api.request("DELETE", ai_validation_job_delete(task_id))
        return self._api.parse(
            DeleteAiValidationJobResponse, response, "delete job response"
        )

    async def get_aggregates(self) -> GetAiValidationJobAggregatesResponse:
        """Get aggregate counts for validation jobs grouped by status."""
        response = await self._api.request("GET", ai_validation_jobs_aggregates())
        return self._api.parse(
            GetAiValidationJobAggregatesResponse,
            response,
            "get job aggregates response",
        )

    async def get_results_summary(
        self, task_id: str
    ) -> GetJobResultsSummaryResponse:
        """Get a summary of results for a job including severity counts."""
        self._api.ensure_uuid(task_id, "task_id")
        response = await self._api.request(
            "GET", ai_validation_job_results_summary(task_id)
        )
        return self._api.parse(
            GetJobResultsSummaryResponse, response, "get job results summary response"
        )

    # ------------------------------------------------------------------
    # Polling helper
    # ------------------------------------------------------------------

    async def wait_for_completion(
        self,
        task_id: str,
        *,
        poll_interval: float = 10.0,
        timeout: float = 3600.0,
        on_poll: Optional[Callable[[GetAiValidationJobResponse], None]] = None,
    ) -> GetAiValidationJobResponse:
        """Poll a job until it reaches a terminal state (JOB_COMPLETED, JOB_FAILED, JOB_CANCELLED).

        Args:
            task_id: The job/task ID to poll.
            poll_interval: Seconds between each poll. Defaults to 10.
            timeout: Maximum seconds to wait before raising TimeoutError. Defaults to 3600.
            on_poll: Optional callback invoked after each poll with the latest job response.

        Returns:
            The final ``GetAiValidationJobResponse`` in a terminal state.

        Raises:
            TimeoutError: If the job does not finish within *timeout* seconds.
        """
        self._api.ensure_uuid(task_id, "task_id")
        elapsed = 0.0
        while True:
            job = await self.get_job(task_id)
            if on_poll is not None:
                on_poll(job)
            if job.status in _TERMINAL_STATUSES:
                return job
            if elapsed >= timeout:
                raise TimeoutError(
                    f"Job {task_id} did not complete within {timeout}s (last status: {job.status})"
                )
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    async def list_results(
        self, task_id: str, request: ListAiValidationResultsRequest
    ) -> ListAiValidationResultsResponse:
        """List validation results for a job."""
        self._api.ensure_uuid(task_id, "task_id")
        params = request.model_dump(exclude_defaults=True)
        response = await self._api.request(
            "GET", ai_validation_results(task_id), params=params
        )
        return self._api.parse(
            ListAiValidationResultsResponse, response, "list results response"
        )

    async def list_results_detail(
        self, task_id: str, request: ListAiValidationResultsDetailRequest
    ) -> ListAiValidationResultsDetailResponse:
        """List detailed validation results including prompt/response pairs."""
        self._api.ensure_uuid(task_id, "task_id")
        params = request.model_dump(exclude_defaults=True)
        response = await self._api.request(
            "GET", ai_validation_results_detail(task_id), params=params
        )
        return self._api.parse(
            ListAiValidationResultsDetailResponse,
            response,
            "list results detail response",
        )

    async def get_result(
        self, task_id: str, attack_id: str
    ) -> GetAiValidationResultResponse:
        """Get a single validation result by task and attack IDs."""
        self._api.ensure_uuid(task_id, "task_id")
        response = await self._api.request(
            "GET", ai_validation_result(task_id, attack_id)
        )
        return self._api.parse(
            GetAiValidationResultResponse, response, "get result response"
        )

    async def get_attack_error_detail(
        self, task_id: str, attack_id: str
    ) -> GetAiValidationResultErrorDetailResponse:
        """Get error details for a specific failed attack attempt."""
        self._api.ensure_uuid(task_id, "task_id")
        response = await self._api.request(
            "GET", ai_validation_attack_error_detail(task_id, attack_id)
        )
        return self._api.parse(
            GetAiValidationResultErrorDetailResponse,
            response,
            "get attack error detail response",
        )

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    async def get_config(self) -> GetAiValidationConfigResponse:
        """Get the current validation configuration."""
        response = await self._api.request("GET", ai_validation_config())
        return self._api.parse(
            GetAiValidationConfigResponse, response, "get config response"
        )

    async def get_config_by_task(self, task_id: str) -> GetAiValidationConfigResponse:
        """Get the validation configuration used for a specific job."""
        self._api.ensure_uuid(task_id, "task_id")
        response = await self._api.request("GET", ai_validation_config_by_task(task_id))
        return self._api.parse(
            GetAiValidationConfigResponse, response, "get config by task response"
        )

    async def update_config(
        self, request: UpdateAiValidationConfigRequest
    ) -> UpdateAiValidationConfigResponse:
        """Update the validation configuration."""
        data = request.model_dump(exclude_defaults=True)
        response = await self._api.request("PUT", ai_validation_config(), data=data)
        return self._api.parse(
            UpdateAiValidationConfigResponse, response, "update config response"
        )

    # ------------------------------------------------------------------
    # Supporting lookups
    # ------------------------------------------------------------------

    async def list_data_for_model_id(
        self, request: ListAiValidationDataForModelIdRequest
    ) -> ListAiValidationDataForModelIdResponse:
        """List validation data available for a given model ID."""
        params = request.model_dump(exclude_defaults=True)
        response = await self._api.request(
            "GET", ai_validation_data_model_id(), params=params
        )
        return self._api.parse(
            ListAiValidationDataForModelIdResponse,
            response,
            "list data for model id response",
        )

    async def list_asset_names(
        self, request: ListAiAssetNamesRequest
    ) -> ListAiAssetNamesResponse:
        """List asset names available for validation."""
        params = request.model_dump(exclude_defaults=True)
        response = await self._api.request(
            "GET", ai_validation_asset_names(), params=params
        )
        return self._api.parse(
            ListAiAssetNamesResponse, response, "list asset names response"
        )

    async def list_content_categories(self) -> ListContentCategoriesResponse:
        """List available content categories for validation."""
        response = await self._api.request("GET", ai_validation_content_categories())
        return self._api.parse(
            ListContentCategoriesResponse,
            response,
            "list content categories response",
        )
