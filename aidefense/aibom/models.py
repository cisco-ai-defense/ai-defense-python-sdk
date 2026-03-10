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

"""Pydantic models for the AI-BOM API."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import Field

from aidefense.models.base import AIDefenseModel

# Reuse Paging from management common
from aidefense.management.models.common import Paging


# --------------------
# Enums
# --------------------

class BomStatus(str, Enum):
    """Status of an AI-BOM analysis."""
    BOM_STATUS_UNSPECIFIED = "BOM_STATUS_UNSPECIFIED"
    BOM_STATUS_COMPLETED = "BOM_STATUS_COMPLETED"
    BOM_STATUS_COMPLETED_WITH_ERRORS = "BOM_STATUS_COMPLETED_WITH_ERRORS"
    BOM_STATUS_FAILED = "BOM_STATUS_FAILED"
    BOM_STATUS_SKIPPED = "BOM_STATUS_SKIPPED"


class SourceKind(str, Enum):
    """Source type for an AI-BOM analysis."""
    SOURCE_KIND_UNSPECIFIED = "SOURCE_KIND_UNSPECIFIED"
    SOURCE_KIND_LOCAL_PATH = "SOURCE_KIND_LOCAL_PATH"
    SOURCE_KIND_CONTAINER = "SOURCE_KIND_CONTAINER"
    SOURCE_KIND_OTHER = "SOURCE_KIND_OTHER"


class ComponentCategory(str, Enum):
    """Category of an AI-BOM component."""
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


class SortBy(str, Enum):
    """Sort field for listing BOMs."""
    SORT_BY_UNSPECIFIED = "SORT_BY_UNSPECIFIED"
    SORT_BY_SUBMITTED_AT = "SORT_BY_SUBMITTED_AT"
    SORT_BY_LAST_GENERATED_AT = "SORT_BY_LAST_GENERATED_AT"
    SORT_BY_ASSETS_DISCOVERED = "SORT_BY_ASSETS_DISCOVERED"


class BomSortOrder(str, Enum):
    """Sort order for list operations."""
    SORT_ORDER_UNSPECIFIED = "SortOrder_Unspecified"
    ASC = "asc"
    DESC = "desc"


# --------------------
# Request/Response Models
# --------------------

class SourceInput(AIDefenseModel):
    """Source input for an AI-BOM analysis.

    Args:
        name: Name of the source.
        path: Path to the source (local path, container ref, etc.).
    """
    name: str = Field(..., description="Source name")
    path: str = Field(..., description="Source path")


class CreateAnalysisRequest(AIDefenseModel):
    """Request for creating an AI-BOM analysis.

    Args:
        run_id: Run identifier.
        analyzer_version: Version of the analyzer.
        submitted_at: RFC3339 timestamp when submitted.
        source_kind: Type of source (local path, container, etc.).
        sources: List of source inputs.
        env: Optional environment config (Struct).
        report: Raw report JSON as dict.
        report_sha256: Optional integrity hash of the report.
    """
    run_id: str = Field(default="", alias="run_id", description="Run identifier")
    analyzer_version: str = Field(default="", alias="analyzer_version", description="Analyzer version")
    submitted_at: str = Field(default="", alias="submitted_at", description="RFC3339 submission timestamp")
    source_kind: SourceKind = Field(..., alias="source_kind", description="Source type")
    sources: List[SourceInput] = Field(default_factory=list, description="Source inputs")
    env: Optional[Dict[str, Any]] = Field(None, description="Environment config")
    report: Optional[Dict[str, Any]] = Field(None, description="Raw report JSON")
    report_sha256: Optional[str] = Field(None, alias="report_sha256", description="Report integrity hash")


class CreateAnalysisResponse(AIDefenseModel):
    """Response from creating an AI-BOM analysis.

    Args:
        analysis_id: Unique analysis identifier.
        status: Acceptance status (e.g., accepted).
        message: Optional message.
    """
    analysis_id: str = Field(..., alias="analysis_id", description="Analysis identifier")
    status: str = Field(default="", description="Status")
    message: str = Field(default="", alias="message", description="Optional message")


# --------------------
# Summary Models
# --------------------

class BomSummaryStats(AIDefenseModel):
    """Aggregated BOM summary statistics.

    Args:
        total_boms: Total number of BOMs.
        completed: Count of completed BOMs.
        completed_with_errors: Count of completed-with-errors BOMs.
        failed: Count of failed BOMs.
        total_assets: Total assets discovered.
    """
    total_boms: int = Field(default=0, alias="total_boms", description="Total BOMs")
    completed: int = Field(default=0, description="Completed count")
    completed_with_errors: int = Field(default=0, alias="completed_with_errors", description="Completed with errors")
    failed: int = Field(default=0, description="Failed count")
    total_assets: int = Field(default=0, alias="total_assets", description="Total assets")


class BomSummaryItem(AIDefenseModel):
    """Summary item for a single BOM in list results.

    Args:
        analysis_id: Analysis identifier.
        source_name: Name of the source.
        source_kind: Type of source.
        assets_discovered: Number of assets discovered.
        last_generated_at: When the BOM was last generated.
        status: BOM status.
    """
    analysis_id: str = Field(..., alias="analysis_id", description="Analysis identifier")
    source_name: str = Field(default="", alias="source_name", description="Source name")
    source_kind: SourceKind = Field(default=SourceKind.SOURCE_KIND_UNSPECIFIED, alias="source_kind", description="Source type")
    assets_discovered: int = Field(default=0, alias="assets_discovered", description="Assets discovered")
    last_generated_at: Optional[datetime] = Field(None, alias="last_generated_at", description="Last generated timestamp")
    status: BomStatus = Field(default=BomStatus.BOM_STATUS_UNSPECIFIED, description="BOM status")


# --------------------
# Detail Models
# --------------------

class AssetTypeCounts(AIDefenseModel):
    """Counts of asset types in a BOM.

    Args:
        models: Number of models.
        embeddings: Number of embeddings.
        prompts: Number of prompts.
        agents: Number of agents.
        tools: Number of tools.
        chains: Number of chains.
    """
    models: int = Field(default=0, description="Models count")
    embeddings: int = Field(default=0, description="Embeddings count")
    prompts: int = Field(default=0, description="Prompts count")
    agents: int = Field(default=0, description="Agents count")
    tools: int = Field(default=0, description="Tools count")
    chains: int = Field(default=0, description="Chains count")


class BomDetailSummary(AIDefenseModel):
    """Summary within a BOM detail.

    Args:
        total_assets: Total assets.
        last_generated_at: Last generated timestamp.
        asset_types: Counts by asset type.
    """
    total_assets: int = Field(default=0, alias="total_assets", description="Total assets")
    last_generated_at: Optional[datetime] = Field(None, alias="last_generated_at", description="Last generated")
    asset_types: Optional[AssetTypeCounts] = Field(None, alias="asset_types", description="Asset type counts")


class BomDetail(AIDefenseModel):
    """Full BOM detail.

    Args:
        analysis_id: Analysis identifier.
        source_name: Source name.
        source_kind: Source type.
        generated_at: When the BOM was generated.
        summary: BOM summary.
        status: BOM status.
    """
    analysis_id: str = Field(..., alias="analysis_id", description="Analysis identifier")
    source_name: str = Field(default="", alias="source_name", description="Source name")
    source_kind: SourceKind = Field(default=SourceKind.SOURCE_KIND_UNSPECIFIED, alias="source_kind", description="Source type")
    generated_at: Optional[datetime] = Field(None, alias="generated_at", description="Generation timestamp")
    summary: Optional[BomDetailSummary] = Field(None, description="BOM summary")
    status: BomStatus = Field(default=BomStatus.BOM_STATUS_UNSPECIFIED, description="BOM status")


# --------------------
# List Models
# --------------------

class ListBomsRequest(AIDefenseModel):
    """Request for listing BOMs.

    Args:
        search: Search string.
        status: Filter by BOM status.
        source_kind: Filter by source kind.
        from_: Start of date range.
        to: End of date range.
        sort_by: Sort field.
        order: Sort order.
        limit: Page size.
        offset: Pagination offset.
    """
    search: Optional[str] = Field(None, description="Search string")
    status: Optional[BomStatus] = Field(None, description="Filter by status")
    source_kind: Optional[SourceKind] = Field(None, alias="source_kind", description="Filter by source kind")
    from_: Optional[datetime] = Field(None, alias="from", description="Date range start")
    to: Optional[datetime] = Field(None, description="Date range end")
    sort_by: Optional[SortBy] = Field(None, alias="sort_by", description="Sort field")
    order: Optional[BomSortOrder] = Field(None, description="Sort order")
    limit: int = Field(default=25, description="Page size")
    offset: int = Field(default=0, description="Pagination offset")


class ListBomsResponse(AIDefenseModel):
    """Response from listing BOMs.

    Args:
        items: List of BOM summary items.
        paging: Pagination info.
    """
    items: List[BomSummaryItem] = Field(default_factory=list, description="BOM items")
    paging: Optional[Paging] = Field(None, description="Pagination")


class GetBomSummaryRequest(AIDefenseModel):
    """Request for BOM summary stats.

    Args:
        search: Search string.
        status: Filter by status.
        source_kind: Filter by source kind.
        from_: Date range start.
        to: Date range end.
    """
    search: Optional[str] = Field(None, description="Search string")
    status: Optional[BomStatus] = Field(None, description="Filter by status")
    source_kind: Optional[SourceKind] = Field(None, alias="source_kind", description="Filter by source kind")
    from_: Optional[datetime] = Field(None, alias="from", description="Date range start")
    to: Optional[datetime] = Field(None, description="Date range end")


class GetBomSummaryResponse(AIDefenseModel):
    """Response from BOM summary.

    Args:
        summary: Aggregated BOM stats.
    """
    summary: Optional[BomSummaryStats] = Field(None, description="Summary stats")


class ListBomComponentsRequest(AIDefenseModel):
    """Request for listing BOM components.

    Args:
        analysis_id: Analysis identifier (also in path).
        search: Search string.
        component_type: Filter by component category.
        framework: Filter by framework.
        limit: Page size.
        offset: Pagination offset.
    """
    analysis_id: str = Field(..., alias="analysis_id", description="Analysis identifier")
    search: Optional[str] = Field(None, description="Search string")
    component_type: Optional[ComponentCategory] = Field(None, alias="type", description="Filter by category")
    framework: Optional[str] = Field(None, description="Filter by framework")
    limit: int = Field(default=25, description="Page size")
    offset: int = Field(default=0, description="Pagination offset")


class ComponentRow(AIDefenseModel):
    """A single component row in list results.

    Args:
        name: Component name.
        details: Component details.
        category: Component category.
        file_path: File path.
        line_number: Line number.
        framework: Framework.
        last_generated_at: Last generated timestamp.
    """
    name: str = Field(default="", description="Component name")
    details: str = Field(default="", description="Details")
    category: ComponentCategory = Field(default=ComponentCategory.COMPONENT_CATEGORY_UNSPECIFIED, description="Category")
    file_path: str = Field(default="", alias="file_path", description="File path")
    line_number: int = Field(default=0, alias="line_number", description="Line number")
    framework: str = Field(default="", description="Framework")
    last_generated_at: Optional[datetime] = Field(None, alias="last_generated_at", description="Last generated")


class ListBomComponentsResponse(AIDefenseModel):
    """Response from listing BOM components.

    Args:
        items: List of components.
        paging: Pagination info.
    """
    items: List[ComponentRow] = Field(default_factory=list, description="Components")
    paging: Optional[Paging] = Field(None, description="Pagination")


class DeleteBomRequest(AIDefenseModel):
    """Request for deleting a BOM.

    Args:
        analysis_id: Analysis identifier.
        reason: Reason for deletion.
    """
    analysis_id: str = Field(..., alias="analysis_id", description="Analysis identifier")
    reason: str = Field(default="", description="Deletion reason")
