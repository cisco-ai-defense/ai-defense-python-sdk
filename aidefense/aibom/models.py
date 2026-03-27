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

"""Pydantic models for AIBOM Report Manager Service v1 API."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import Field

from aidefense.models.base import AIDefenseModel
from aidefense.management.models.common import Paging, SortOrder


# --------------------
# Enums
# --------------------

class BomStatus(str, Enum):
    """Status of a Bill of Materials (BOM) analysis."""
    BOM_STATUS_UNSPECIFIED = "BOM_STATUS_UNSPECIFIED"
    BOM_STATUS_COMPLETED = "BOM_STATUS_COMPLETED"
    BOM_STATUS_COMPLETED_WITH_ERRORS = "BOM_STATUS_COMPLETED_WITH_ERRORS"
    BOM_STATUS_FAILED = "BOM_STATUS_FAILED"
    BOM_STATUS_SKIPPED = "BOM_STATUS_SKIPPED"


class ComponentCategory(str, Enum):
    """Category of component in a BOM."""
    COMPONENT_CATEGORY_UNSPECIFIED = "COMPONENT_CATEGORY_UNSPECIFIED"
    COMPONENT_CATEGORY_MODEL = "COMPONENT_CATEGORY_MODEL"
    COMPONENT_CATEGORY_AGENT = "COMPONENT_CATEGORY_AGENT"
    COMPONENT_CATEGORY_DATA = "COMPONENT_CATEGORY_DATA"
    COMPONENT_CATEGORY_PROMPT = "COMPONENT_CATEGORY_PROMPT"
    COMPONENT_CATEGORY_TOOL = "COMPONENT_CATEGORY_TOOL"
    COMPONENT_CATEGORY_CHAIN = "COMPONENT_CATEGORY_CHAIN"
    COMPONENT_CATEGORY_EMBEDDING = "COMPONENT_CATEGORY_EMBEDDING"
    COMPONENT_CATEGORY_MEMORY = "COMPONENT_CATEGORY_MEMORY"
    COMPONENT_CATEGORY_OTHER = "COMPONENT_CATEGORY_OTHER"


class SourceKind(str, Enum):
    """Type of source being analyzed."""
    SOURCE_KIND_UNSPECIFIED = "SOURCE_KIND_UNSPECIFIED"
    SOURCE_KIND_LOCAL_PATH = "SOURCE_KIND_LOCAL_PATH"
    SOURCE_KIND_CONTAINER = "SOURCE_KIND_CONTAINER"
    SOURCE_KIND_OTHER = "SOURCE_KIND_OTHER"


class SortBy(str, Enum):
    """Field to sort BOM results by."""
    SORT_BY_UNSPECIFIED = "SORT_BY_UNSPECIFIED"
    SORT_BY_SUBMITTED_AT = "SORT_BY_SUBMITTED_AT"
    SORT_BY_LAST_GENERATED_AT = "SORT_BY_LAST_GENERATED_AT"
    SORT_BY_ASSETS_DISCOVERED = "SORT_BY_ASSETS_DISCOVERED"


# --------------------
# Request Models
# --------------------

class SourceInput(AIDefenseModel):
    """Input source for analysis.

    Args:
        name: Name of the source.
        path: Path to the source.
    """
    name: str = Field(..., description="Source name")
    path: str = Field(..., description="Path to the source")


class CreateAnalysisRequest(AIDefenseModel):
    """Request to create an analysis report.

    Args:
        run_id: Unique identifier for the analysis run.
        analyzer_version: Version of the analyzer that performed the scan.
        submitted_at: RFC3339 timestamp when the analysis was submitted.
        source_kind: Type of source being analyzed.
        sources: List of source inputs for analysis.
        env: Environment variables or context (optional).
        report: Raw report JSON data (optional).
    """
    run_id: str = Field(..., description="Unique run identifier")
    analyzer_version: str = Field(..., description="Version of the analyzer")
    submitted_at: Optional[datetime] = Field(..., description="RFC3339 timestamp of submission")
    source_kind: SourceKind = Field(..., description="Type of source being analyzed")
    sources: List[SourceInput] = Field(default_factory=list, description="List of sources")
    env: Optional[Dict[str, Any]] = Field(None, description="Environment context")
    report: Optional[Dict[str, Any]] = Field(None, description="Raw report JSON data")


# --------------------
# Response Models
# --------------------

class CreateAnalysisResponse(AIDefenseModel):
    """Response from creating an analysis.

    Args:
        analysis_id: Unique identifier for the created analysis.
        status: Status of the analysis submission (e.g., 'accepted').
        message: Optional status message.
    """
    analysis_id: str = Field(..., description="Analysis identifier")
    status: str = Field(..., description="Status (e.g. 'accepted')")
    message: Optional[str] = Field(None, description="Status message")


class AssetTypeCounts(AIDefenseModel):
    """Counts of different asset types in a BOM.

    Args:
        models: Number of models.
        embeddings: Number of embeddings.
        prompts: Number of prompts.
        agents: Number of agents.
        tools: Number of tools.
        chains: Number of chains.
    """
    models: int = Field(default=0, description="Number of models")
    embeddings: int = Field(default=0, description="Number of embeddings")
    prompts: int = Field(default=0, description="Number of prompts")
    agents: int = Field(default=0, description="Number of agents")
    tools: int = Field(default=0, description="Number of tools")
    chains: int = Field(default=0, description="Number of chains")


class BomDetailSummary(AIDefenseModel):
    """Summary information for a BOM detail.

    Args:
        total_assets: Total number of assets discovered.
        last_generated_at: Timestamp when summary was last generated.
        asset_types: Breakdown of asset types.
    """
    total_assets: int = Field(default=0, description="Total assets discovered")
    last_generated_at: Optional[datetime] = Field(None, description="Last generation timestamp")
    asset_types: Optional[AssetTypeCounts] = Field(None, description="Asset type breakdown")


class BomDetail(AIDefenseModel):
    """Detailed BOM information.

    Args:
        analysis_id: Unique identifier of the analysis.
        source_name: Name of the source analyzed.
        source_kind: Type of source.
        generated_at: Timestamp when BOM was generated.
        summary: Summary details of the BOM.
        status: Current status of the BOM.
    """
    analysis_id: str = Field(..., description="Analysis identifier")
    source_name: str = Field(..., description="Source name")
    source_kind: SourceKind = Field(..., description="Type of source")
    generated_at: Optional[datetime] = Field(None, description="Generation timestamp")
    summary: Optional[BomDetailSummary] = Field(None, description="BOM summary")
    status: BomStatus = Field(..., description="BOM status")


class ComponentRow(AIDefenseModel):
    """A component entry in a BOM component list.

    Args:
        name: Name of the component.
        details: Additional details about the component.
        category: Category of the component.
        file_path: File path where component is located.
        line_number: Line number in the file.
        framework: Framework or library name.
        last_generated_at: Last generation timestamp.
    """
    name: str = Field(..., description="Component name")
    details: str = Field(default="", description="Component details")
    category: ComponentCategory = Field(..., description="Component category")
    file_path: str = Field(default="", description="File path location")
    line_number: int = Field(default=0, description="Line number in file")
    framework: str = Field(default="", description="Framework/library name")
    last_generated_at: Optional[datetime] = Field(None, description="Last generation timestamp")


class BomSummaryItem(AIDefenseModel):
    """Summary item for a BOM in a list response.

    Args:
        analysis_id: Unique identifier of the analysis.
        source_name: Name of the analyzed source.
        source_kind: Type of source.
        assets_discovered: Number of assets discovered.
        last_generated_at: Timestamp of last generation.
        status: Current BOM status.
    """
    analysis_id: str = Field(..., description="Analysis identifier")
    source_name: str = Field(..., description="Source name")
    source_kind: SourceKind = Field(..., description="Type of source")
    assets_discovered: int = Field(default=0, description="Number of assets discovered")
    last_generated_at: Optional[datetime] = Field(None, description="Last generation timestamp")
    status: BomStatus = Field(..., description="BOM status")


class ListBomsResponse(AIDefenseModel):
    """Response containing a paginated list of BOMs.

    Args:
        items: List of BOM summary items.
        paging: Pagination information.
    """
    items: List[BomSummaryItem] = Field(default_factory=list, description="BOM items")
    paging: Optional[Paging] = Field(None, description="Pagination info")


class ListBomComponentsResponse(AIDefenseModel):
    """Response containing a paginated list of BOM components.

    Args:
        items: List of component rows.
        paging: Pagination information.
    """
    items: List[ComponentRow] = Field(default_factory=list, description="Component items")
    paging: Optional[Paging] = Field(None, description="Pagination info")


class BomSummaryStats(AIDefenseModel):
    """Summary statistics for BOMs.

    Args:
        total_boms: Total number of BOMs.
        completed: Number of completed BOMs.
        completed_with_errors: Number of completed BOMs with errors.
        failed: Number of failed BOMs.
        total_assets: Total number of assets across all BOMs.
    """
    total_boms: int = Field(default=0, description="Total BOMs")
    completed: int = Field(default=0, description="Completed BOMs")
    completed_with_errors: int = Field(default=0, description="Completed with errors")
    failed: int = Field(default=0, description="Failed BOMs")
    total_assets: int = Field(default=0, description="Total assets")


class GetBomSummaryResponse(AIDefenseModel):
    """Response containing BOM summary statistics.

    Args:
        summary: BOM summary statistics.
    """
    summary: Optional[BomSummaryStats] = Field(None, description="Summary statistics")


# --------------------
# Query Parameter Models (for list/filter operations)
# --------------------

class ListBomsRequest(AIDefenseModel):
    """Query parameters for listing BOMs.

    Args:
        search: Search term to filter BOMs by.
        status: Filter by BOM status.
        source_kind: Filter by source kind.
        from_time: Start timestamp (RFC3339) for filtering.
        to_time: End timestamp (RFC3339) for filtering.
        sort_by: Field to sort results by.
        order: Sort order (ascending or descending).
        limit: Maximum number of results to return.
        offset: Number of results to skip for pagination.
    """
    search: Optional[str] = Field(None, description="Search filter")
    status: Optional[BomStatus] = Field(None, description="Status filter")
    source_kind: Optional[SourceKind] = Field(None, description="Source kind filter")
    from_time: Optional[str] = Field(None, alias="from", description="Start timestamp")
    to_time: Optional[str] = Field(None, alias="to", description="End timestamp")
    sort_by: Optional[SortBy] = Field(None, description="Sort field")
    order: Optional[SortOrder] = Field(None, description="Sort order")
    limit: Optional[int] = Field(None, description="Result limit")
    offset: Optional[int] = Field(None, description="Result offset")


class ListBomComponentsRequest(AIDefenseModel):
    """Query parameters for listing BOM components.

    Args:
        search: Search term to filter components by.
        component_type: Filter by component category.
        framework: Filter by framework name.
        limit: Maximum number of results to return.
        offset: Number of results to skip for pagination.
    """
    search: Optional[str] = Field(None, description="Search filter")
    component_type: Optional[ComponentCategory] = Field(
        None,
        alias="type",
        description="Component category filter"
    )
    framework: Optional[str] = Field(None, description="Framework filter")
    limit: Optional[int] = Field(None, description="Result limit")
    offset: Optional[int] = Field(None, description="Result offset")


class BomsSummaryRequest(AIDefenseModel):
    """Query parameters for getting BOMs summary.

    Args:
        search: Search term to filter BOMs by.
        status: Filter by BOM status.
        source_kind: Filter by source kind.
        from_time: Start timestamp (RFC3339) for filtering.
        to_time: End timestamp (RFC3339) for filtering.
    """
    search: Optional[str] = Field(None, description="Search filter")
    status: Optional[BomStatus] = Field(None, description="Status filter")
    source_kind: Optional[SourceKind] = Field(None, description="Source kind filter")
    from_time: Optional[str] = Field(None, alias="from", description="Start timestamp")
    to_time: Optional[str] = Field(None, alias="to", description="End timestamp")
