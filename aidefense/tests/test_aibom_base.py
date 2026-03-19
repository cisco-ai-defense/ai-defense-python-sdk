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

"""Tests for AiBom base client.

Covers:
- Client initialization with API key and config
- create_analysis request/response handling
- list_boms with pagination and filters
- get_bom detail retrieval
- delete_bom deletion
- list_bom_components with filtering
- get_bom_summary statistics
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generator, Optional
from unittest.mock import MagicMock

import pytest

from aidefense.aibom.aibom_base import AiBom
from aidefense.aibom.models import (
    BomStatus,
    BomSummaryItem,
    BomsSummaryRequest,
    ComponentCategory,
    ComponentRow,
    CreateAnalysisRequest,
    ListBomComponentsRequest,
    ListBomsRequest,
    SourceInput,
    SourceKind,
)
from aidefense.config import Config
from aidefense.request_handler import HttpMethod

TEST_API_KEY = "0123456789" * 6 + "0123"


@dataclass(frozen=True)
class ListBomsCase:
    """Parameterized case for list_boms tests."""

    name: str
    search: Optional[str] = None
    status: Optional[BomStatus] = None
    source_kind: Optional[SourceKind] = None
    limit: Optional[int] = None
    offset: Optional[int] = None


@dataclass(frozen=True)
class ComponentFilterCase:
    """Parameterized case for component filtering."""

    name: str
    search: Optional[str] = None
    component_type: Optional[ComponentCategory] = None
    limit: Optional[int] = None


@pytest.fixture(autouse=True)
def reset_config_singleton() -> Generator[None, None, None]:
    """Reset Config singleton before each test."""
    Config._instance = None
    yield
    Config._instance = None


@pytest.fixture
def aibom_client() -> Generator[AiBom, None, None]:
    """Create an AiBom client with mocked make_request."""
    client = AiBom(api_key=TEST_API_KEY)
    client.make_request = MagicMock()
    yield client


class TestAiBomInitialization:
    """Client instantiation and configuration handling."""

    def test_init_with_api_key_only(self) -> None:
        """AiBom can initialize with just an API key."""
        client = AiBom(api_key=TEST_API_KEY)
        assert client is not None
        assert client.config is not None

    def test_init_with_custom_config(self) -> None:
        """AiBom initializes with a custom Config instance."""
        custom_config = Config()
        client = AiBom(api_key=TEST_API_KEY, config=custom_config)
        assert client.config is not None

    def test_init_with_custom_request_handler(self) -> None:
        """AiBom accepts a custom request handler."""
        mock_handler = MagicMock()
        client = AiBom(api_key=TEST_API_KEY, request_handler=mock_handler)
        assert client is not None


class TestAiBomCreateAnalysis:
    """Analysis creation with request validation and response parsing."""

    def test_create_analysis_posts_request_and_deserializes_response(
        self,
        aibom_client: AiBom,
    ) -> None:
        """create_analysis builds a POST request and validates the response."""
        client = aibom_client
        analysis_request = CreateAnalysisRequest(
            run_id="run-123",
            analyzer_version="1.2.3",
            submitted_at="2026-03-19T12:00:00Z",
            source_kind=SourceKind.SOURCE_KIND_LOCAL_PATH,
            sources=[
                SourceInput(name="app.py", path="/app/src/app.py"),
                SourceInput(name="config.py", path="/app/src/config.py"),
            ],
        )
        expected_response = {
            "analysis_id": "analysis-456",
            "status": "accepted",
            "message": "queued for processing",
        }
        client.make_request.return_value = expected_response

        result = client.create_analysis(req=analysis_request)

        client.make_request.assert_called_once()
        call_args = client.make_request.call_args
        assert call_args.kwargs["method"] == HttpMethod.POST
        assert "analysis" in call_args.kwargs["path"]
        assert result.analysis_id == "analysis-456"
        assert result.status == "accepted"
        assert result.message == "queued for processing"

    def test_create_analysis_with_report_data(
        self,
        aibom_client: AiBom,
    ) -> None:
        """create_analysis includes optional report data in the request."""
        client = aibom_client
        report_data: dict[str, Any] = {"components": [{"name": "model-1"}]}
        analysis_request = CreateAnalysisRequest(
            run_id="run-789",
            analyzer_version="2.0.0",
            submitted_at="2026-03-19T13:00:00Z",
            source_kind=SourceKind.SOURCE_KIND_CONTAINER,
            sources=[SourceInput(name="image", path="app:latest")],
            report=report_data,
        )
        client.make_request.return_value = {
            "analysis_id": "analysis-789",
            "status": "accepted",
        }

        result = client.create_analysis(req=analysis_request)

        call_args = client.make_request.call_args
        assert call_args.kwargs["data"]["report"] == report_data
        assert result.analysis_id == "analysis-789"

    def test_create_analysis_with_environment_context(
        self,
        aibom_client: AiBom,
    ) -> None:
        """create_analysis preserves environment context in the request."""
        client = aibom_client
        env_context: dict[str, Any] = {
            "python_version": "3.11",
            "framework": "fastapi",
        }
        analysis_request = CreateAnalysisRequest(
            run_id="run-env",
            analyzer_version="1.1.0",
            submitted_at="2026-03-19T14:00:00Z",
            source_kind=SourceKind.SOURCE_KIND_LOCAL_PATH,
            sources=[SourceInput(name="src", path="/workspace/src")],
            env=env_context,
        )
        client.make_request.return_value = {
            "analysis_id": "analysis-env",
            "status": "accepted",
        }

        result = client.create_analysis(req=analysis_request)

        call_args = client.make_request.call_args
        assert call_args.kwargs["data"]["env"] == env_context
        assert result.analysis_id == "analysis-env"


class TestAiBomListBoms:
    """BOM listing with filters, pagination, and sorting."""

    @pytest.mark.parametrize(
        "case",
        [
            ListBomsCase(name="no-filters", search=None, limit=10),
            ListBomsCase(name="by-status", status=BomStatus.BOM_STATUS_COMPLETED),
            ListBomsCase(
                name="by-source-kind",
                source_kind=SourceKind.SOURCE_KIND_CONTAINER,
            ),
            ListBomsCase(
                name="paginated",
                limit=50,
                offset=100,
            ),
        ],
        ids=lambda case: case.name,
    )
    def test_list_boms_passes_filters_and_params(
        self,
        aibom_client: AiBom,
        case: ListBomsCase,
    ) -> None:
        """list_boms correctly translates query parameters."""
        client = aibom_client
        list_request = ListBomsRequest(
            search=case.search,
            status=case.status,
            source_kind=case.source_kind,
            limit=case.limit,
            offset=case.offset,
        )

        mock_items = [
            BomSummaryItem(
                analysis_id=f"analysis-{i}",
                source_name=f"source-{i}",
                source_kind=SourceKind.SOURCE_KIND_LOCAL_PATH,
                assets_discovered=i * 10,
                status=BomStatus.BOM_STATUS_COMPLETED,
            )
            for i in range(3)
        ]
        client.make_request.return_value = {
            "items": [item.model_dump() for item in mock_items],
            "paging": {"count": 3, "total": 3, "limit": 10, "offset": 0},
        }

        result = client.list_boms(req=list_request)

        client.make_request.assert_called_once()
        call_args = client.make_request.call_args
        assert call_args.kwargs["method"] == HttpMethod.GET
        assert "boms" in call_args.kwargs["path"]
        assert result.items is not None
        assert len(result.items) == 3
        assert result.items[0].analysis_id == "analysis-0"


class TestAiBomGetBom:
    """Individual BOM detail retrieval."""

    def test_get_bom_returns_detail_by_analysis_id(
        self,
        aibom_client: AiBom,
    ) -> None:
        """get_bom retrieves a BOM detail by analysis ID."""
        client = aibom_client
        analysis_id = "analysis-123"

        client.make_request.return_value = {
            "analysis_id": analysis_id,
            "source_name": "my-app",
            "source_kind": "SOURCE_KIND_LOCAL_PATH",
            "generated_at": "2026-03-19T12:00:00Z",
            "status": "BOM_STATUS_COMPLETED",
            "summary": {
                "total_assets": 42,
                "asset_types": {"models": 5, "agents": 3, "tools": 10},
            },
        }

        result = client.get_bom(analysis_id=analysis_id)

        client.make_request.assert_called_once()
        call_args = client.make_request.call_args
        assert call_args.kwargs["method"] == HttpMethod.GET
        assert analysis_id in call_args.kwargs["path"]
        assert result.analysis_id == analysis_id
        assert result.source_name == "my-app"
        assert result.summary.total_assets == 42

    def test_get_bom_with_incomplete_summary(
        self,
        aibom_client: AiBom,
    ) -> None:
        """get_bom handles BOMs with no or partial summary data."""
        client = aibom_client
        client.make_request.return_value = {
            "analysis_id": "analysis-minimal",
            "source_name": "minimal",
            "source_kind": "SOURCE_KIND_OTHER",
            "status": "BOM_STATUS_SKIPPED",
        }

        result = client.get_bom(analysis_id="analysis-minimal")

        assert result.analysis_id == "analysis-minimal"
        assert result.summary is None


class TestAiBomDeleteBom:
    """BOM deletion."""

    def test_delete_bom_sends_delete_request(
        self,
        aibom_client: AiBom,
    ) -> None:
        """delete_bom sends a DELETE request for the given analysis ID."""
        client = aibom_client
        analysis_id = "analysis-todelete"

        client.delete_bom(analysis_id=analysis_id)

        client.make_request.assert_called_once()
        call_args = client.make_request.call_args
        assert call_args.kwargs["method"] == HttpMethod.DELETE
        assert analysis_id in call_args.kwargs["path"]

    def test_delete_bom_returns_none(
        self,
        aibom_client: AiBom,
    ) -> None:
        """delete_bom returns None."""
        client = aibom_client
        client.make_request.return_value = None

        result = client.delete_bom(analysis_id="analysis-123")

        assert result is None


class TestAiBomListBomComponents:
    """BOM component listing and filtering."""

    @pytest.mark.parametrize(
        "case",
        [
            ComponentFilterCase(
                name="model-components",
                component_type=ComponentCategory.COMPONENT_CATEGORY_MODEL,
            ),
            ComponentFilterCase(
                name="agent-components",
                component_type=ComponentCategory.COMPONENT_CATEGORY_AGENT,
            ),
            ComponentFilterCase(
                name="search-by-name",
                search="openai",
                limit=25,
            ),
            ComponentFilterCase(
                name="no-filters",
                limit=100,
            ),
        ],
        ids=lambda case: case.name,
    )
    def test_list_bom_components_with_filters(
        self,
        aibom_client: AiBom,
        case: ComponentFilterCase,
    ) -> None:
        """list_bom_components applies filters and pagination."""
        client = aibom_client
        analysis_id = "analysis-456"
        component_request = ListBomComponentsRequest(
            search=case.search,
            component_type=case.component_type,
            limit=case.limit,
        )

        mock_items = [
            ComponentRow(
                name=f"component-{i}",
                category=case.component_type or ComponentCategory.COMPONENT_CATEGORY_OTHER,
                file_path=f"/app/src/component_{i}.py",
                line_number=i * 10,
                framework="fastapi",
            )
            for i in range(2)
        ]
        client.make_request.return_value = {
            "items": [item.model_dump() for item in mock_items],
            "paging": {"count": 2, "total": 2, "limit": case.limit or 10, "offset": 0},
        }

        result = client.list_bom_components(
            analysis_id=analysis_id,
            req=component_request,
        )

        client.make_request.assert_called_once()
        call_args = client.make_request.call_args
        assert call_args.kwargs["method"] == HttpMethod.GET
        assert analysis_id in call_args.kwargs["path"]
        assert result.items is not None
        assert len(result.items) == 2
        assert result.items[0].name == "component-0"

    def test_list_bom_components_empty_result(
        self,
        aibom_client: AiBom,
    ) -> None:
        """list_bom_components handles empty result sets."""
        client = aibom_client
        client.make_request.return_value = {"items": [], "paging": {"count": 0, "total": 0, "offset": 0}}

        result = client.list_bom_components(
            analysis_id="analysis-empty",
            req=ListBomComponentsRequest(),
        )

        assert result.items == []


class TestAiBomGetBomSummary:
    """BOM summary statistics."""

    def test_get_bom_summary_returns_aggregated_stats(
        self,
        aibom_client: AiBom,
    ) -> None:
        """get_bom_summary returns aggregated BOM statistics."""
        client = aibom_client
        summary_request = BomsSummaryRequest()

        client.make_request.return_value = {
            "summary": {
                "total_boms": 50,
                "completed": 40,
                "completed_with_errors": 7,
                "failed": 3,
                "total_assets": 1250,
            }
        }

        result = client.get_bom_summary(req=summary_request)

        client.make_request.assert_called_once()
        call_args = client.make_request.call_args
        assert call_args.kwargs["method"] == HttpMethod.GET
        assert result.summary is not None
        assert result.summary.total_boms == 50
        assert result.summary.completed == 40
        assert result.summary.total_assets == 1250

    def test_get_bom_summary_with_filtered_request(
        self,
        aibom_client: AiBom,
    ) -> None:
        """get_bom_summary accepts filtering parameters."""
        client = aibom_client
        summary_request = BomsSummaryRequest(
            status=BomStatus.BOM_STATUS_COMPLETED,
            source_kind=SourceKind.SOURCE_KIND_CONTAINER,
        )

        client.make_request.return_value = {
            "summary": {
                "total_boms": 20,
                "completed": 20,
                "completed_with_errors": 0,
                "failed": 0,
                "total_assets": 450,
            }
        }

        result = client.get_bom_summary(req=summary_request)

        call_args = client.make_request.call_args
        assert call_args.kwargs["params"] is not None
        assert result.summary.total_boms == 20


class TestAiBomEnumHandling:
    """Enum serialization and deserialization in requests/responses."""

    def test_source_kind_enum_in_response(
        self,
        aibom_client: AiBom,
    ) -> None:
        """Response parsing correctly deserializes SourceKind enums."""
        client = aibom_client

        client.make_request.return_value = {
            "analysis_id": "analysis-enum",
            "source_name": "test-source",
            "source_kind": "SOURCE_KIND_CONTAINER",
            "status": "BOM_STATUS_COMPLETED",
        }

        result = client.get_bom(analysis_id="analysis-enum")

        assert result.source_kind == SourceKind.SOURCE_KIND_CONTAINER

    def test_bom_status_enum_in_response(
        self,
        aibom_client: AiBom,
    ) -> None:
        """Response parsing correctly deserializes BomStatus enums."""
        client = aibom_client

        client.make_request.return_value = {
            "analysis_id": "analysis-status",
            "source_name": "test",
            "source_kind": "SOURCE_KIND_LOCAL_PATH",
            "status": "BOM_STATUS_COMPLETED_WITH_ERRORS",
        }

        result = client.get_bom(analysis_id="analysis-status")

        assert result.status == BomStatus.BOM_STATUS_COMPLETED_WITH_ERRORS

    def test_component_category_enum_in_response(
        self,
        aibom_client: AiBom,
    ) -> None:
        """Response parsing correctly deserializes ComponentCategory enums."""
        client = aibom_client

        client.make_request.return_value = {
            "items": [
                {
                    "name": "gpt-4",
                    "category": "COMPONENT_CATEGORY_MODEL",
                    "file_path": "/app/models.py",
                    "line_number": 42,
                }
            ],
            "paging": {"count": 1, "total": 1, "offset": 0},
        }

        result = client.list_bom_components(
            analysis_id="analysis-cat",
            req=ListBomComponentsRequest(),
        )

        assert result.items[0].category == ComponentCategory.COMPONENT_CATEGORY_MODEL
