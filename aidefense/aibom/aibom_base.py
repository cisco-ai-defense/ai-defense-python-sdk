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


from typing import Optional

from aidefense.aibom.models import (
    BomsSummaryRequest,
    CreateAnalysisRequest,
    CreateAnalysisResponse,
    GetBomSummaryResponse,
    ListBomComponentsRequest,
    ListBomComponentsResponse,
    ListBomsRequest,
    ListBomsResponse,
    BomDetail,
)
from aidefense.aibom.routes import (
    analysis,
    bom_by_id,
    bom_components,
    boms,
    boms_summary,
)
from aidefense.config import Config
from aidefense.management.auth import ManagementAuth
from aidefense.management.base_client import BaseClient
from aidefense.request_handler import HttpMethod


class AiBom(BaseClient):
    """
    Base client for AIBOM service.
    """
    def __init__(self, api_key: str, config: Optional[Config] = None, request_handler = None):
        """
        Initialize an AIBOM client instance.

        Args:
              api_key (str): Your Cisco AI Defense API key for authentication.
              config (Config, optional): SDK-level configuration for endpoints, logging, retries, etc.
                 If not provided, a default Config instance is created.
              request_handler: Optional custom request handler for API requests.
        """
        super().__init__(ManagementAuth(api_key), config, request_handler)

    def create_analysis(self, req: CreateAnalysisRequest) -> CreateAnalysisResponse:
        """
        Create a new BOM analysis for the specified application.

        Args:
            req (CreateAnalysisRequest): The request object containing analysis parameters.
        Returns:
            CreateAnalysisResponse: The response object containing analysis details.
        """
        response = self.make_request(
            method=HttpMethod.POST,
            path=analysis(),
            data=req.to_body_dict(),
        )

        result = CreateAnalysisResponse.model_validate(response)

        self.config.logger.debug(f"Created analysis: {result}")

        return result


    def list_boms(self, req: ListBomsRequest) -> ListBomsResponse:
        """
        List all BOMs for the specified application.

        Args:
            req (ListBomsRequest): The request object containing listing parameters.
        Returns:
            ListBomsResponse: The response object containing a list of BOMs.
        """
        response = self.make_request(
            method=HttpMethod.GET,
            path=boms(),
            params=req.to_params(),
        )

        result = ListBomsResponse.model_validate(response)

        self.config.logger.debug(f"Listed BOMs: {result}")

        return result

    def get_bom(self, analysis_id: str) -> BomDetail:
        """
        Get details of a specific BOM by analysis ID.

        Args:
            analysis_id (str): The ID of the analysis whose BOM details are to be retrieved.
        Returns:
            BomDetail: The response object containing BOM details.
        """
        response = self.make_request(
            method=HttpMethod.GET,
            path=bom_by_id(analysis_id),
        )

        result = BomDetail.model_validate(response)

        self.config.logger.debug(f"Retrieved BOM details for analysis {analysis_id}: {result}")

        return result


    def delete_bom(self, analysis_id: str) -> None:
        """
        Delete a specific BOM by analysis ID.

        Args:
            analysis_id (str): The ID of the analysis whose BOM is to be deleted.
        Returns:
            None
        """
        self.make_request(
            method=HttpMethod.DELETE,
            path=bom_by_id(analysis_id),
        )

        self.config.logger.debug(f"Deleted BOM for analysis {analysis_id}")


    def list_bom_components(self, analysis_id: str, req: ListBomComponentsRequest) -> ListBomComponentsResponse:
        """
        List all components in a specific BOM by analysis ID.

        Args:
            analysis_id (str): The ID of the analysis whose BOM components are to be listed.
            req (ListBomComponentsRequest): The request object containing listing parameters.
        Returns:
            ListBomComponentsResponse: The response object containing a list of BOM components.
        """
        response = self.make_request(
            method=HttpMethod.GET,
            path=bom_components(analysis_id),
            params=req.to_params(),
         )

        result = ListBomComponentsResponse.model_validate(response)

        self.config.logger.debug(f"Listed BOM components for analysis {analysis_id}: {result}")

        return result


    def get_bom_summary(self, req: BomsSummaryRequest) -> GetBomSummaryResponse:
        """
        Get a summary of BOMs for a specific application.

        Args:
            req (BomsSummaryRequest): The request object containing summary parameters.
        Returns:
            GetBomSummaryResponse: The response object containing the BOM summary.
        """
        response = self.make_request(
            method=HttpMethod.GET,
            path=boms_summary(),
            params=req.to_params(),
        )

        result = GetBomSummaryResponse.model_validate(response)

        self.config.logger.debug(f"Retrieved BOM summary: {result}")

        return result
