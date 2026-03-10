#!/usr/bin/env python3.11
"""Streamlit UI for the Codebase Health Auditor."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import List, Optional

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.health_auditor.agent import run_audit


def _parse_services(text: str) -> List[str]:
    return [s.strip() for s in text.split(",") if s.strip()]


def _write_uploaded_json(upload, repo_root: Path) -> Optional[Path]:
    if upload is None:
        return None
    data = upload.read()
    if not data:
        return None
    tmp_dir = repo_root / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / "_findings_upload.json"
    tmp_path.write_bytes(data)
    return tmp_path


st.set_page_config(page_title="Codebase Health Auditor", layout="wide")

st.title("Codebase Health Auditor")

st.markdown(
    "Generate per-service health audit reports using a local model (Ollama) "
    "with agentsec inspection. Reports are written to the repo and a manifest "
    "is created for MCP publishing."
)

with st.sidebar:
    st.header("Model")
    model = st.text_input("Model", value="qwen2.5:7b")
    base_url = st.text_input("Base URL", value="http://localhost:11434/v1")

    st.header("Repo")
    repo = st.text_input("Repo path", value=".")
    reports_dir = st.text_input("Reports dir", value="reports")

    st.header("Services")
    services_text = st.text_input(
        "Comma-separated services (leave empty to auto-discover)", value=""
    )

    st.header("Confluence")
    confluence_space_key = st.text_input(
        "Space key (personal space key)", value="~7120206c00c240e8d44dfba665d4e4395c7207"
    )
    confluence_parent_title = st.text_input(
        "Parent page title", value="Agent Reports"
    )

st.subheader("Findings input")
col1, col2 = st.columns(2)
with col1:
    uploaded = st.file_uploader("Upload findings JSON", type=["json"])
with col2:
    findings_path_text = st.text_input(
        "Or path to findings JSON", value=""
    )

run = st.button("Run audit")

st.subheader("Existing reports")
manifest_path = Path(reports_dir) / "manifest.json"
if manifest_path.exists():
    try:
        manifest = json.loads(manifest_path.read_text())
        report_paths = manifest.get("reports", [])
    except Exception:
        report_paths = []
    if report_paths:
        for p in report_paths:
            st.write(p)
    else:
        st.info("Manifest found but no reports listed.")
else:
    st.info("No manifest found yet. Run an audit to generate reports.")

st.subheader("Publish request")
publish_request_path = Path(reports_dir) / "publish_request.json"
if st.button("Request publish to Confluence"):
    if not manifest_path.exists():
        st.error("No manifest found. Run an audit first.")
    else:
        payload = {
            "manifest_path": str(manifest_path),
            "space_key": confluence_space_key.strip(),
            "parent_title": confluence_parent_title.strip(),
        }
        publish_request_path.write_text(json.dumps(payload, indent=2))
        st.success(f"Publish request written to {publish_request_path}")
        st.info(
            "Ask the assistant to publish via MCP using the publish request file."
        )

if run:
    services = _parse_services(services_text)
    findings_json = None

    repo_root = Path(repo).resolve()
    if uploaded is not None:
        findings_json = _write_uploaded_json(uploaded, repo_root)
    elif findings_path_text.strip():
        findings_json = Path(findings_path_text.strip())

    if findings_json is None:
        st.error("Provide findings JSON via upload or path.")
        st.stop()

    try:
        output_paths = run_audit(
            repo=repo_root,
            services=services,
            findings_dir=None,
            findings_json=findings_json,
            model=model,
            base_url=base_url,
            reports_dir=Path(reports_dir),
        )
    except Exception as exc:
        st.error(str(exc))
        st.stop()

    st.success(f"Wrote {len(output_paths)} reports to {reports_dir}")
    st.markdown("### Output")
    for p in output_paths:
        st.write(str(p))

    manifest_path = Path(reports_dir) / "manifest.json"
    if manifest_path.exists():
        st.markdown("### Manifest")
        st.code(manifest_path.read_text(), language="json")
