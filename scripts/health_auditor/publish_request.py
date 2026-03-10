#!/usr/bin/env python3.11
"""Prepare a publish payload from reports/publish_request.json.

This script is intended to be run by the assistant. It reads the publish
request and manifest, loads report contents, and prints a JSON payload to
stdout for MCP publishing.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare publish payload")
    parser.add_argument(
        "--reports-dir", default="reports", help="Directory containing manifest"
    )
    parser.add_argument(
        "--output", default="", help="Optional file to write payload JSON"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    reports_dir = Path(args.reports_dir)
    request_path = reports_dir / "publish_request.json"
    if not request_path.exists():
        raise SystemExit(f"Missing publish request: {request_path}")

    request = json.loads(request_path.read_text())
    manifest_path = Path(request.get("manifest_path", reports_dir / "manifest.json"))
    if not manifest_path.exists():
        raise SystemExit(f"Missing manifest: {manifest_path}")

    manifest = json.loads(manifest_path.read_text())
    report_paths = [Path(p) for p in manifest.get("reports", [])]

    reports: List[Dict[str, str]] = []
    for path in report_paths:
        if not path.exists():
            continue
        reports.append({
            "path": str(path),
            "title": path.stem,
            "content": path.read_text(),
        })

    payload = {
        "space_key": request.get("space_key", ""),
        "parent_title": request.get("parent_title", "Agent Reports"),
        "reports": reports,
    }

    out = json.dumps(payload, indent=2)
    if args.output:
        Path(args.output).write_text(out)
    else:
        print(out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
