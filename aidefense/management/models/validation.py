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

"""Validation models for the AI Defense Management/Validation APIs."""

from enum import Enum, IntEnum
from typing import List, Optional
from datetime import datetime
from pydantic import Field
from ...models.base import AIDefenseModel


class AssetType(str, Enum):
    UNKNOWN = "UNKNOWN"
    APPLICATION = "APPLICATION"
    MODEL = "MODEL"
    EXTERNAL = "EXTERNAL"


class AWSRegion(IntEnum):
    """
    The region that the Bedrock request will be handled from.

    Default = "AWS_REGION_UNSPECIFIED".
    Allowed values: [
        "AWS_REGION_UNSPECIFIED",
        "AWS_REGION_US_EAST_1",
        "AWS_REGION_US_WEST_2",
        "AWS_REGION_EU_CENTRAL_1",
        "AWS_REGION_AP_NORTHEAST_1",
    ].
    """

    AWS_REGION_UNSPECIFIED = 0
    AWS_REGION_US_EAST_1 = 1
    AWS_REGION_US_WEST_2 = 2
    AWS_REGION_EU_CENTRAL_1 = 3
    AWS_REGION_AP_NORTHEAST_1 = 4


class ExternalApiProvider(str, Enum):
    EXTERNAL_API_PROVIDER_AZURE_OPENAI = "EXTERNAL_API_PROVIDER_AZURE_OPENAI"
    EXTERNAL_API_PROVIDER_OPENAI = "EXTERNAL_API_PROVIDER_OPENAI"


class JobStatus(str, Enum):
    JOB_CREATED = "JOB_CREATED"
    JOB_IN_PROGRESS = "JOB_IN_PROGRESS"
    JOB_COMPLETED = "JOB_COMPLETED"
    JOB_FAILED = "JOB_FAILED"


class Header(AIDefenseModel):
    key: str
    value: str


class StartAiValidationRequest(AIDefenseModel):
    asset_type: Optional[AssetType] = Field(None, description="Asset type to validate")
    application_id: Optional[str] = Field(
        None, description="Application ID if asset is application"
    )
    ai_asset_name: Optional[str] = Field(None, description="Asset name (for model)")
    validation_scan_name: Optional[str] = Field(
        None, description="Name for the validation run"
    )
    model_provider: Optional[str] = Field(None, description="Model provider name")
    headers: Optional[List[Header]] = Field(
        None, description="Headers for external model calls"
    )
    model_endpoint_url_model_id: Optional[str] = Field(
        None, description="Endpoint URL or model ID"
    )
    model_request_template: Optional[str] = Field(
        None, description="Request template for model"
    )
    model_response_json_path: Optional[str] = Field(
        None, description="Response JSON path"
    )
    description: Optional[str] = Field(None, description="Description of the test")
    aws_region: Optional[AWSRegion] = Field(
        AWSRegion.AWS_REGION_UNSPECIFIED,
        description="The region that the Bedrock request will be handled from.",
    )
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    stop_sequences: Optional[List[str]] = None
    additional_config: Optional[str] = None
    external_api_provider: Optional[ExternalApiProvider] = None


class StartAiValidationResponse(AIDefenseModel):
    task_id: str = Field(description="Task ID of the started validation job")


class GetAiValidationJobResponse(AIDefenseModel):
    task_id: Optional[str] = None
    tenant_id: Optional[str] = None
    config_id: Optional[str] = None
    run_count: Optional[int] = None
    status: Optional[JobStatus] = None
    progress: Optional[int] = None
    total_num_prompts: Optional[int] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class AiValidationConfigResponseDetails(AIDefenseModel):
    config_id: Optional[str] = None
    tenant_id: Optional[str] = None
    asset_type: Optional[AssetType] = None
    application_id: Optional[str] = None
    ai_asset_name: Optional[str] = None
    validation_scan_name: Optional[str] = None
    model_provider: Optional[str] = None
    model_endpoint_url_model_id: Optional[str] = None
    model_request_template: Optional[str] = None
    model_response_json_path: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ListAllAiValidationConfigResponse(AIDefenseModel):
    config: List[AiValidationConfigResponseDetails] = Field(default_factory=list)


class GetAiValidationConfigResponse(AiValidationConfigResponseDetails):
    """Alias model for single config response."""

    pass
