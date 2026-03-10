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

"""Base client for the AI-BOM (AI Bill of Materials) API."""

from typing import Optional

from aidefense.config import Config
from aidefense.management.auth import ManagementAuth
from aidefense.management.base_client import BaseClient
from aidefense.request_handler import HttpMethod

from .models import (
    CreateAnalysisRequest,
    CreateAnalysisResponse,
    ListBomsRequest,
    ListBomsResponse,
    GetBomSummaryRequest,
    GetBomSummaryResponse,
    BomDetail,
    ListBomComponentsRequest,
    ListBomComponentsResponse,
)
from .routes import (
    aibom_analysis,
    aibom_boms,
    aibom_boms_summary,
    aibom_bom_by_id,
    aibom_bom_components,
)


class AIBom(BaseClient):
    """
    Client for AI-BOM (AI Bill of Materials) operations with Cisco AI Defense.

    The AIBom class provides methods to manage AI-BOM analyses: list BOMs,
    create analyses, retrieve BOM details, list components, and delete BOMs.

    Typical usage:
        ```python
        from aidefense.aibom import AIBom

        client = AIBom(api_key="YOUR_MANAGEMENT_API_KEY")

        # List BOMs
        response = client.list_boms(ListBomsRequest(limit=10))
        for item in response.items:
            print(f"{item.analysis_id}: {item.source_name}")

        # Get BOM detail
        bom = client.get_bom(analysis_id="analysis-uuid")
        ```
    """

    def __init__(
        self,
        api_key: str,
        config: Optional[Config] = None,
        request_handler=None,
    ):
        """
        Initialize an AIBom client instance.

        Args:
            api_key: Your Cisco AI Defense API key for authentication.
            config: Optional SDK configuration.
            request_handler: Optional custom request handler.
        """
        super().__init__(ManagementAuth(api_key), config, request_handler)

    def list_boms(self, req: ListBomsRequest) -> ListBomsResponse:
        """
        List AI-BOMs with optional filters and pagination.

        Args:
            req: ListBomsRequest with search, status, source_kind, date range, sort, limit, offset.

        Returns:
            ListBomsResponse with items and paging.
        """
        params = req.to_params()
        res = self.make_request(
            method=HttpMethod.GET,
            path=aibom_boms(),
            params=params,
        )
        return ListBomsResponse.model_validate(res)

    def get_bom_summary(self, req: GetBomSummaryRequest) -> GetBomSummaryResponse:
        """
        Get aggregated BOM summary statistics with optional filters.

        Args:
            req: GetBomSummaryRequest with search, status, source_kind, date range.

        Returns:
            GetBomSummaryResponse with summary stats.
        """
        params = req.to_params()
        res = self.make_request(
            method=HttpMethod.GET,
            path=aibom_boms_summary(),
            params=params,
        )
        return GetBomSummaryResponse.model_validate(res)

    def create_analysis(self, req: CreateAnalysisRequest) -> CreateAnalysisResponse:
        """
        Submit an AI-BOM analysis report.

        Args:
            req: CreateAnalysisRequest with run_id, sources, report, etc.

        Returns:
            CreateAnalysisResponse with analysis_id and status.
        """
        res = self.make_request(
            method=HttpMethod.POST,
            path=aibom_analysis(),
            data=req.to_body_dict(),
        )
        return CreateAnalysisResponse.model_validate(res)

    def get_bom(self, analysis_id: str) -> BomDetail:
        """
        Get full BOM detail by analysis ID.

        Args:
            analysis_id: The analysis identifier (UUID).

        Returns:
            BomDetail with source, summary, and status.
        """
        res = self.make_request(
            method=HttpMethod.GET,
            path=aibom_bom_by_id(analysis_id),
        )
        return BomDetail.model_validate(res)

    def delete_bom(self, analysis_id: str, reason: str = "") -> None:
        """
        Soft delete an AI-BOM by analysis ID.

        Args:
            analysis_id: The analysis identifier (UUID).
            reason: Optional reason for deletion.
        """
        data = {"reason": reason} if reason else None
        self.make_request(
            method=HttpMethod.DELETE,
            path=aibom_bom_by_id(analysis_id),
            data=data,
        )
        self.config.logger.debug(f"Deleted BOM {analysis_id}")

    def list_bom_components(
        self,
        analysis_id: str,
        req: ListBomComponentsRequest,
    ) -> ListBomComponentsResponse:
        """
        List components of an AI-BOM with optional filters.

        Args:
            analysis_id: The analysis identifier (UUID).
            req: ListBomComponentsRequest with search, type, framework, limit, offset.

        Returns:
            ListBomComponentsResponse with items and paging.
        """
        params = req.to_params()
        # Ensure analysis_id is not sent as a param (it's in the path)
        params.pop("analysis_id", None)
        params.pop("analysisId", None)
        res = self.make_request(
            method=HttpMethod.GET,
            path=aibom_bom_components(analysis_id),
            params=params,
        )
        return ListBomComponentsResponse.model_validate(res)
