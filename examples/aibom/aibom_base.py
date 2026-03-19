#!/usr/bin/env python3
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

"""
Example: Using the AiBom base client methods.

This script demonstrates direct usage of methods from `aidefense.aibom.aibom_base.AiBom`:
1. create_analysis
2. list_boms
3. get_bom
4. list_bom_components
5. get_bom_summary
6. delete_bom (optional)

Required environment variables:
- AIDEFENSE_MANAGEMENT_API_KEY

Optional environment variables:
- AIDEFENSE_MANAGEMENT_BASE_URL (default: https://api.security.cisco.com)
- AIBOM_REPORT_PATH (path to a JSON report file used for create_analysis)
- AIBOM_DELETE_CREATED (set to "true" to delete the created BOM at the end)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from aidefense import Config
from aidefense.aibom.aibom_base import AiBom
from aidefense.aibom.models import (
	BomsSummaryRequest,
	CreateAnalysisRequest,
	ListBomComponentsRequest,
	ListBomsRequest,
	SourceInput,
	SourceKind,
)


def _load_report_from_file(file_path: Path) -> Dict[str, Any]:
	raw_text = file_path.read_text(encoding="utf-8")
	return json.loads(raw_text)


def _extract_source_kind_and_inputs(report: Dict[str, Any]) -> tuple[SourceKind, List[SourceInput]]:
	sources_section = report.get("aibom_analysis", {}).get("sources", {})

	source_kinds: Set[str] = set()
	source_inputs: List[SourceInput] = []

	for source_name, source_data in sources_section.items():
		source_kind = source_data.get("summary", {}).get("source_kind")
		if source_kind in {"local-path", "container"}:
			source_kinds.add(source_kind)

		source_inputs.append(SourceInput(name=source_name, path=source_name))

	if source_kinds == {"local-path"}:
		kind = SourceKind.SOURCE_KIND_LOCAL_PATH
	elif source_kinds == {"container"}:
		kind = SourceKind.SOURCE_KIND_CONTAINER
	else:
		kind = SourceKind.SOURCE_KIND_OTHER

	return kind, source_inputs


def _build_create_analysis_request(report: Dict[str, Any]) -> CreateAnalysisRequest:
	metadata = report.get("aibom_analysis", {}).get("metadata", {})
	source_kind, source_inputs = _extract_source_kind_and_inputs(report)

	return CreateAnalysisRequest(
		run_id=metadata.get("run_id", "sample-run-id"),
		analyzer_version=metadata.get("analyzer_version", "unknown"),
		submitted_at=metadata.get("submitted_at"),
		source_kind=source_kind,
		sources=source_inputs,
		report=report,
	)


def main() -> None:
	management_api_key = os.environ.get("AIDEFENSE_MANAGEMENT_API_KEY")
	management_base_url = os.environ.get(
		"AIDEFENSE_MANAGEMENT_BASE_URL", "https://api.security.cisco.com"
	)

	if not management_api_key:
		print("❌ Error: AIDEFENSE_MANAGEMENT_API_KEY environment variable is not set")
		return

	client = AiBom(
		api_key=management_api_key,
		config=Config(management_base_url=management_base_url),
	)

	created_analysis_id: Optional[str] = None

	try:
		# 1) create_analysis (optional, requires AIBOM_REPORT_PATH)
		report_path = os.environ.get("AIBOM_REPORT_PATH")
		if report_path:
			report_file = Path(report_path).expanduser().resolve()
			if not report_file.exists():
				print(f"❌ AIBOM_REPORT_PATH does not exist: {report_file}")
				return

			print(f"🚀 Creating analysis from report file: {report_file}")
			report_data = _load_report_from_file(report_file)
			create_req = _build_create_analysis_request(report_data)
			create_resp = client.create_analysis(create_req)
			created_analysis_id = create_resp.analysis_id
			print("✅ Analysis created")
			print(create_resp.model_dump_json(indent=2))
		else:
			print("ℹ️ Skipping create_analysis (set AIBOM_REPORT_PATH to enable it)")

		# 2) list_boms
		print("\n🚀 Listing BOMs")
		list_resp = client.list_boms(ListBomsRequest(limit=10, offset=0))
		print(f"✅ Retrieved {len(list_resp.items)} BOM(s)")
		print(list_resp.model_dump_json(indent=2))

		# Use the created analysis_id when available; otherwise use the first listed BOM.
		analysis_id = created_analysis_id
		if not analysis_id and list_resp.items:
			analysis_id = list_resp.items[0].analysis_id

		if not analysis_id:
			print("\nℹ️ No BOM found for get_bom/list_bom_components/delete_bom examples")
		else:
			# 3) get_bom
			print(f"\n🚀 Getting BOM details for analysis_id={analysis_id}")
			bom_resp = client.get_bom(analysis_id)
			print("✅ BOM details")
			print(bom_resp.model_dump_json(indent=2))

			# 4) list_bom_components
			print(f"\n🚀 Listing BOM components for analysis_id={analysis_id}")
			components_resp = client.list_bom_components(
				analysis_id,
				ListBomComponentsRequest(limit=20, offset=0),
			)
			print(f"✅ Retrieved {len(components_resp.items)} component(s)")
			print(components_resp.model_dump_json(indent=2))

		# 5) get_bom_summary
		print("\n🚀 Getting BOM summary")
		summary_resp = client.get_bom_summary(BomsSummaryRequest())
		print("✅ BOM summary")
		print(summary_resp.model_dump_json(indent=2))

		# 6) delete_bom (optional)
		should_delete = os.environ.get("AIBOM_DELETE_CREATED", "false").lower() == "true"
		if should_delete and created_analysis_id:
			print(f"\n🚀 Deleting created BOM: {created_analysis_id}")
			client.delete_bom(created_analysis_id)
			print("✅ Created BOM deleted")
		elif should_delete and not created_analysis_id:
			print("\nℹ️ AIBOM_DELETE_CREATED=true but no BOM was created in this run")
		else:
			print("\nℹ️ Skipping delete_bom (set AIBOM_DELETE_CREATED=true to enable)")

	except Exception as exc:
		print("\n❌ AIBOM base example failed")
		print(f"   {exc}")


if __name__ == "__main__":
	main()
