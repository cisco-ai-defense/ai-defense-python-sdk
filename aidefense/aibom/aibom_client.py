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


from contextlib import contextmanager
import os
from typing import List, Optional, Sequence
from pathlib import Path

from tempfile import NamedTemporaryFile

from aidefense.aibom.aibom_base import AiBom
from aidefense.aibom.models import CreateAnalysisResponse, CreateAnalysisRequest, SourceInput, SourceKind
from aidefense.config import Config
import json

try:
    # cisco-aibom is an optional dependency; keep module importable without it.
    from aibom.cli import analyze
except ModuleNotFoundError:
    analyze = None

DEFAULT_REPORT_FORMAT = "json"
DEFAULT_LOG_LEVEL = "WARNING"

class AiBomClient:
    """Client for interacting with the AI BOM API."""

    _client: AiBom

    def __init__(self, api_key: str, config: Optional[Config] = None):
        self._client = AiBom(api_key=api_key, config=config)

    def analyze(self, sources: List[str], output_file: Optional[Path] = None, **kwargs) -> dict:
        """Create a new analysis for the given sources.

        Args:
            sources (List[str]): List of source identifiers (e.g., repository URLs, file paths).
            output_file (Optional[Path]): Optional path to save the analysis results as JSON.

        Returns:
            dict: The analysis results as a dictionary.
        """
        if analyze is None:
            raise ModuleNotFoundError(
                "Optional dependency 'cisco-aibom' is required for AiBomClient.analyze(). "
                "Install it with: poetry install --extras aibom"
            )

        source_list = self._validate_and_normalize_sources(sources)

        with self._resolve_output_path(output_file) as out_path:
            analyze(
                sources=source_list,
                output_format=DEFAULT_REPORT_FORMAT,
                output_file=out_path,
                log_level=DEFAULT_LOG_LEVEL,
                images_file=None,
                custom_catalog=None,
                post_url=None,
                **kwargs,
            )
            return json.loads(out_path.read_text(encoding="utf-8"))

    def submit_report_file(self, raw_data: dict = None, file_path: Path = None) -> CreateAnalysisResponse:
        """Submit an analysis report to the AIBOM service.
        Args:
            raw_data (dict): The analysis report data as a dictionary. Optional if file_path is provided.
            file_path (Path): Path to the analysis report JSON file. Optional if raw_data is provided.
        Returns:
            CreateAnalysisResponse: The response from the AIBOM service after submitting the report.
        """

        if raw_data is None and file_path:
            raw_bytes = Path(file_path).read_bytes()
            raw_data = json.loads(raw_bytes)
        elif raw_data is None and not file_path:
            raise ValueError("Either raw_data or file_path must be provided")

        report_metadata = raw_data.get("aibom_analysis", {}).get("metadata", {})

        analysis_sources = raw_data.get("aibom_analysis", {}).get("sources", {})

        source_kinds = set()
        sources: List[SourceInput] = []

        for key in analysis_sources:
            source = analysis_sources[key]
            source_kind = source.get("summary", {}).get("source_kind")
            if source_kind not in ["local-path", "container"]:
                raise ValueError(f"Unsupported source_kind: {source_kind}")
            source_kinds.add(source_kind)
            sources.append(SourceInput(name=key, path=key))

        return self._client.create_analysis(
            req=CreateAnalysisRequest(
                run_id=report_metadata.get("run_id"),
                analyzer_version=report_metadata.get("analyzer_version"),
                submitted_at=report_metadata.get("submitted_at"),
                source_kind=self._get_source_kind(source_kinds),
                sources=sources,
                report=raw_data,
            ),
        )
    def analyze_and_submit(self, sources: List[str], output_file: Optional[Path] = None, **kwargs) -> CreateAnalysisResponse:
        """Convenience method to run analyze and directly submit the report.
        Args:
            sources (List[str]): List of source identifiers (e.g., repository URLs, file paths).
            output_file (Optional[Path]): Optional path to save the analysis results as JSON before submitting.
        Returns:
            CreateAnalysisResponse: The response from the AIBOM service after submitting the report.
        """
        analyze_result = self.analyze(sources=sources, output_file=output_file, **kwargs)
        return self.submit_report_file(raw_data=analyze_result)

    @staticmethod
    def _get_source_kind(source_kinds: set) -> SourceKind:
        if len(source_kinds) == 1:
            kind = source_kinds.pop()
            if kind == "local-path":
                return SourceKind.SOURCE_KIND_LOCAL_PATH
            elif kind == "container":
                return SourceKind.SOURCE_KIND_CONTAINER
        return SourceKind.SOURCE_KIND_OTHER

    def _validate_and_normalize_sources(self, sources: Sequence[os.PathLike]) -> list[str]:
        if not sources:
            raise ValueError("sources must not be empty")
        normalized = [str(Path(s).expanduser().resolve()) for s in sources]
        return normalized


    @contextmanager
    def _resolve_output_path(self, output_file: Optional[os.PathLike]):
        if output_file:
            yield Path(output_file).expanduser().resolve()
            return

        tmp = NamedTemporaryFile(suffix=".json", delete=False)
        tmp_path = Path(tmp.name)
        try:
            print(f"⚠️ No output file specified, using temporary file: {tmp_path}")
            yield tmp_path
        finally:
            tmp.close()
            tmp_path.unlink(missing_ok=True)

