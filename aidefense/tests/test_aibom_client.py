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

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Mapping, Sequence, TypedDict, Union
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

pytest.importorskip("aibom.cli")

from aidefense.aibom.aibom_client import (
	DEFAULT_LOG_LEVEL,
	DEFAULT_REPORT_FORMAT,
	AiBomClient,
)
from aidefense.aibom.models import CreateAnalysisResponse, SourceKind
from aidefense.config import Config


TEST_API_KEY = "0123456789" * 6 + "0123"
SourceValue = Union[str, os.PathLike[str]]


class ReportMetadata(TypedDict):
	run_id: str
	analyzer_version: str
	submitted_at: str


class ReportSourceSummary(TypedDict):
	source_kind: str


class ReportSourceEntry(TypedDict):
	summary: ReportSourceSummary


class ReportAnalysis(TypedDict):
	metadata: ReportMetadata
	sources: dict[str, ReportSourceEntry]


class RawReport(TypedDict):
	aibom_analysis: ReportAnalysis


@dataclass(frozen=True)
class AnalyzeCase:
	name: str
	sources: Sequence[SourceValue]
	extra_kwargs: dict[str, Any]


@pytest.fixture(autouse=True)
def reset_config_singleton():
	"""Reset Config singleton before each test."""
	Config._instance = None
	yield
	Config._instance = None


@pytest.fixture
def client_and_service() -> Generator[tuple[AiBomClient, MagicMock], None, None]:
	"""Create an AiBomClient with a mocked underlying service client."""
	with patch("aidefense.aibom.aibom_client.AiBom") as mock_aibom_cls:
		service = MagicMock()
		mock_aibom_cls.return_value = service
		yield AiBomClient(api_key=TEST_API_KEY), service


def build_report(source_kinds: Mapping[str, str]) -> RawReport:
	return {
		"aibom_analysis": {
			"metadata": {
				"run_id": "run-123",
				"analyzer_version": "1.2.3",
				"submitted_at": "2026-03-19T12:00:00Z",
			},
			"sources": {
				source_name: {"summary": {"source_kind": source_kind}}
				for source_name, source_kind in source_kinds.items()
			},
		}
	}


class TestAiBomClientAnalyze:
	"""Analyze execution, source normalization, and temp-file handling."""

	@pytest.mark.parametrize(
		"case",
		[
			AnalyzeCase(
				name="single-path-string",
				sources=[".", "../ai-defense-python-sdk"],
				extra_kwargs={"include_tests": True},
			),
			AnalyzeCase(
				name="mixed-pathlike-inputs",
				sources=[Path("README.md"), Path("aidefense")],
				extra_kwargs={"max_depth": 4, "follow_symlinks": False},
			),
		],
		ids=lambda case: case.name,
	)
	def test_analyze_normalizes_sources_and_reads_json_result(
		self,
		client_and_service: tuple[AiBomClient, MagicMock],
		tmp_path: Path,
		case: AnalyzeCase,
	):
		client, _ = client_and_service
		output_file = tmp_path / "analysis.json"
		expected_result = {
			"ok": True,
			"source_count": len(case.sources),
		}

		def fake_analyze(**kwargs):
			assert kwargs["sources"] == [
				str(Path(source).expanduser().resolve())
				for source in case.sources
			]
			assert kwargs["output_format"] == DEFAULT_REPORT_FORMAT
			assert kwargs["output_file"] == output_file.resolve()
			assert kwargs["log_level"] == DEFAULT_LOG_LEVEL
			assert kwargs["images_file"] is None
			assert kwargs["custom_catalog"] is None
			assert kwargs["post_url"] is None
			for key, value in case.extra_kwargs.items():
				assert kwargs[key] == value
			Path(kwargs["output_file"]).write_text(
				json.dumps(expected_result),
				encoding="utf-8",
			)

		with patch("aidefense.aibom.aibom_client.analyze", side_effect=fake_analyze) as mock_analyze:
			result = client.analyze(case.sources, output_file=output_file, **case.extra_kwargs)

		mock_analyze.assert_called_once()
		assert result == expected_result

	def test_analyze_rejects_empty_sources(
		self,
		client_and_service: tuple[AiBomClient, MagicMock],
	):
		client, _ = client_and_service

		with pytest.raises(ValueError, match="sources must not be empty"):
			client.analyze([])

	def test_analyze_without_output_file_uses_and_removes_temporary_file(
		self,
		client_and_service: tuple[AiBomClient, MagicMock],
	):
		client, _ = client_and_service
		expected_result = {"status": "generated"}
		captured_output: Path | None = None

		def fake_analyze(**kwargs):
			nonlocal captured_output
			captured_output = Path(kwargs["output_file"])
			assert captured_output.exists()
			captured_output.write_text(json.dumps(expected_result), encoding="utf-8")

		with patch("aidefense.aibom.aibom_client.analyze", side_effect=fake_analyze):
			result = client.analyze([Path("aidefense")])

		assert result == expected_result
		assert captured_output is not None
		assert not captured_output.exists()


class TestAiBomClientSubmitReport:
	"""Report submission request building and validation."""

	def test_submit_report_file_builds_local_path_request_from_raw_data(
		self,
		client_and_service: tuple[AiBomClient, MagicMock],
	):
		client, service = client_and_service
		raw_report = build_report({"src/app.py": "local-path"})
		expected_response = CreateAnalysisResponse(
			analysis_id="analysis-1",
			status="accepted",
			message="queued",
		)
		service.create_analysis.return_value = expected_response

		result = client.submit_report_file(raw_data=raw_report)

		request = service.create_analysis.call_args.kwargs["req"]
		assert result == expected_response
		assert request.run_id == "run-123"
		assert request.analyzer_version == "1.2.3"
		assert request.submitted_at == datetime(2026, 3, 19, 12, 0, tzinfo=timezone.utc)
		assert request.source_kind == SourceKind.SOURCE_KIND_LOCAL_PATH
		assert [(source.name, source.path) for source in request.sources] == [
			("src/app.py", "src/app.py")
		]
		assert request.report == raw_report

	def test_submit_report_file_reads_report_from_file(
		self,
		client_and_service: tuple[AiBomClient, MagicMock],
		tmp_path: Path,
	):
		client, service = client_and_service
		report_file = tmp_path / "analysis.json"
		report_file.write_text(
			json.dumps(build_report({"image:latest": "container"})),
			encoding="utf-8",
		)
		expected_response = CreateAnalysisResponse(
			analysis_id="analysis-2",
			status="accepted",
		)
		service.create_analysis.return_value = expected_response

		result = client.submit_report_file(file_path=report_file)

		request = service.create_analysis.call_args.kwargs["req"]
		assert result == expected_response
		assert request.source_kind == SourceKind.SOURCE_KIND_CONTAINER
		assert [(source.name, source.path) for source in request.sources] == [
			("image:latest", "image:latest")
		]

	def test_submit_report_file_maps_mixed_source_kinds_to_other(
		self,
		client_and_service: tuple[AiBomClient, MagicMock],
	):
		client, service = client_and_service
		service.create_analysis.return_value = CreateAnalysisResponse(
			analysis_id="analysis-3",
			status="accepted",
		)

		client.submit_report_file(
			raw_data=build_report(
				{
					"src/app.py": "local-path",
					"image:latest": "container",
				}
			)
		)

		request = service.create_analysis.call_args.kwargs["req"]
		assert request.source_kind == SourceKind.SOURCE_KIND_OTHER

	def test_submit_report_file_requires_raw_data_or_file_path(
		self,
		client_and_service: tuple[AiBomClient, MagicMock],
	):
		client, _ = client_and_service

		with pytest.raises(ValueError, match="Either raw_data or file_path must be provided"):
			client.submit_report_file()

	def test_submit_report_file_rejects_empty_raw_data_missing_mandatory_fields(
		self,
		client_and_service: tuple[AiBomClient, MagicMock],
	):
		client, service = client_and_service

		with pytest.raises(ValidationError, match="run_id|analyzer_version"):
			client.submit_report_file(raw_data={})

		service.create_analysis.assert_not_called()

	def test_submit_report_file_rejects_unsupported_source_kind(
		self,
		client_and_service: tuple[AiBomClient, MagicMock],
	):
		client, _ = client_and_service

		with pytest.raises(ValueError, match="Unsupported source_kind: git"):
			client.submit_report_file(raw_data=build_report({"repo": "git"}))


class TestAiBomClientConvenienceMethods:
	"""Simple chaining behavior for high-level helpers."""

	def test_analyze_and_submit_passes_analyze_result_to_submit(
		self,
		client_and_service: tuple[AiBomClient, MagicMock],
		tmp_path: Path,
	):
		client, _ = client_and_service
		analyze_result = build_report({"src/app.py": "local-path"})
		expected_response = CreateAnalysisResponse(
			analysis_id="analysis-4",
			status="accepted",
		)
		output_file = tmp_path / "analysis.json"

		with patch.object(client, "analyze", return_value=analyze_result) as mock_analyze:
			with patch.object(client, "submit_report_file", return_value=expected_response) as mock_submit:
				result = client.analyze_and_submit(
					sources=[Path("aidefense")],
					output_file=output_file,
					include_tests=True,
				)

		mock_analyze.assert_called_once_with(
			sources=[Path("aidefense")],
			output_file=output_file,
			include_tests=True,
		)
		mock_submit.assert_called_once_with(raw_data=analyze_result)
		assert result == expected_response
