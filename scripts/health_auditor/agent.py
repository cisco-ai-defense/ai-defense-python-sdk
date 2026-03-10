#!/usr/bin/env python3.11
"""Model-assisted scoring and reporting for codebase health findings.

This agent:
- Uses OpenAI SDK pointed to Ollama (local model) for scoring
- Relies on agentsec monkeypatching for AI Defense inspection
- Writes per-service Markdown reports to reports/
- Writes a manifest for MCP-based publishing
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

# agentsec must be imported before OpenAI SDK usage
import agentsec

agentsec.protect()  # monkeypatch OpenAI SDK for AI Defense inspection

from openai import OpenAI

SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

MIN_SEVERITY_BY_RULE = {
    "SEC-SECRET-001": "P1",
    "SEC-INJECT-004": "P1",
    "SEC-AUTHZ-003": "P1",
}

MAX_SEVERITY_BY_CATEGORY = {
    "maintainability": "P2",
    "test_gaps": "P2",
}


@dataclass
class Finding:
    rule_id: str
    category: str
    file_path: str
    code_snippet: str
    evidence: str
    service: str


@dataclass
class ScoredFinding:
    finding: Finding
    severity: str
    confidence: float
    rationale: List[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Health Auditor Agent")
    parser.add_argument("--repo", default=".", help="Path to repo root")
    parser.add_argument(
        "--services",
        default="",
        help="Comma-separated list of services (optional)",
    )
    parser.add_argument(
        "--findings-dir",
        default="",
        help="Directory with per-service findings JSON files",
    )
    parser.add_argument(
        "--findings-json",
        default="",
        help="Single JSON file containing findings list or dict by service",
    )
    parser.add_argument(
        "--model",
        default="qwen2.5:7b",
        help="Model name (Ollama local model)",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        help="Ollama OpenAI-compatible base URL",
    )
    parser.add_argument(
        "--reports-dir",
        default="reports",
        help="Output directory for markdown reports",
    )
    return parser.parse_args()


def discover_services(repo_path: Path) -> List[str]:
    services = []
    for p in repo_path.iterdir():
        if p.is_dir() and not p.name.startswith("."):
            services.append(p.name)
    return sorted(services)


def load_findings(
    services: List[str],
    findings_dir: Optional[Path],
    findings_json: Optional[Path],
) -> List[Finding]:
    findings: List[Finding] = []

    if findings_json and findings_json.exists():
        data = json.loads(findings_json.read_text())
        if isinstance(data, dict):
            for svc, items in data.items():
                findings.extend(_parse_findings(items, svc))
        elif isinstance(data, list):
            findings.extend(_parse_findings(data, "unknown"))
        else:
            raise ValueError("Unsupported findings JSON format")
        return findings

    if findings_dir and findings_dir.exists():
        for svc in services:
            path = findings_dir / f"{svc}.json"
            if path.exists():
                data = json.loads(path.read_text())
                findings.extend(_parse_findings(data, svc))
        return findings

    return findings


def _parse_findings(items: Iterable[Dict[str, Any]], service: str) -> List[Finding]:
    out: List[Finding] = []
    for item in items:
        out.append(
            Finding(
                rule_id=item.get("rule_id", "UNKNOWN"),
                category=item.get("category", "unknown"),
                file_path=item.get("file_path", ""),
                code_snippet=item.get("code_snippet", ""),
                evidence=item.get("evidence", ""),
                service=service,
            )
        )
    return out


def enforce_bounds(scored: ScoredFinding) -> ScoredFinding:
    # Enforce min severity by rule
    min_sev = MIN_SEVERITY_BY_RULE.get(scored.finding.rule_id)
    if min_sev and SEVERITY_ORDER[scored.severity] > SEVERITY_ORDER[min_sev]:
        scored.severity = min_sev

    # Enforce max severity by category
    max_sev = MAX_SEVERITY_BY_CATEGORY.get(scored.finding.category)
    if max_sev and SEVERITY_ORDER[scored.severity] < SEVERITY_ORDER[max_sev]:
        scored.severity = max_sev

    return scored


def build_prompt(finding: Finding) -> str:
    return (
        "You are scoring a code health finding. "
        "Return JSON only with keys: severity, confidence, rationale.\n\n"
        "Severity must be one of P0, P1, P2, P3. "
        "Confidence is 0-1. Rationale is 1-3 short bullets.\n\n"
        f"rule_id: {finding.rule_id}\n"
        f"category: {finding.category}\n"
        f"service: {finding.service}\n"
        f"file_path: {finding.file_path}\n"
        f"evidence: {finding.evidence}\n"
        f"code_snippet: {finding.code_snippet}\n"
    )


def score_with_model(client: OpenAI, model: str, finding: Finding) -> ScoredFinding:
    prompt = build_prompt(finding)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    content = resp.choices[0].message.content or "{}"

    try:
        data = json.loads(content)
        severity = data.get("severity", "P3")
        confidence = float(data.get("confidence", 0.5))
        rationale = data.get("rationale", [])
        if not isinstance(rationale, list):
            rationale = [str(rationale)]
    except Exception:
        severity = "P3"
        confidence = 0.5
        rationale = ["Model output parse failed; defaulted severity"]

    scored = ScoredFinding(
        finding=finding,
        severity=severity,
        confidence=confidence,
        rationale=rationale,
    )
    return enforce_bounds(scored)


def group_by_service(items: List[ScoredFinding]) -> Dict[str, List[ScoredFinding]]:
    grouped: Dict[str, List[ScoredFinding]] = {}
    for item in items:
        grouped.setdefault(item.finding.service, []).append(item)
    return grouped


def summarize_counts(items: List[ScoredFinding]) -> Dict[str, int]:
    counts = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    for item in items:
        counts[item.severity] += 1
    return counts


def render_markdown(service: str, items: List[ScoredFinding]) -> str:
    counts = summarize_counts(items)
    lines = [
        f"# Health Audit Report — {service}",
        "",
        f"**Summary:** P0={counts['P0']} | P1={counts['P1']} | P2={counts['P2']} | P3={counts['P3']}",
        "",
    ]

    for sev in ["P0", "P1", "P2", "P3"]:
        sev_items = [i for i in items if i.severity == sev]
        if not sev_items:
            continue
        lines.append(f"## {sev} Findings")
        for i in sev_items:
            f = i.finding
            lines.append(f"- **{f.rule_id}** `{f.file_path}`")
            if f.evidence:
                lines.append(f"  - Evidence: {f.evidence}")
            if f.code_snippet:
                lines.append(f"  - Snippet: `{f.code_snippet[:120]}`")
            if i.rationale:
                lines.append("  - Rationale:")
                for r in i.rationale[:3]:
                    lines.append(f"    - {r}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def write_reports(grouped: Dict[str, List[ScoredFinding]], reports_dir: Path) -> List[Path]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    output_paths: List[Path] = []
    for service, items in grouped.items():
        content = render_markdown(service, items)
        out_path = reports_dir / f"{service}.md"
        out_path.write_text(content)
        output_paths.append(out_path)
    return output_paths


def write_manifest(output_paths: List[Path], reports_dir: Path) -> Path:
    manifest = {"reports": [str(p) for p in output_paths]}
    manifest_path = reports_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return manifest_path


def run_audit(
    repo: Path,
    services: List[str],
    findings_dir: Optional[Path],
    findings_json: Optional[Path],
    model: str,
    base_url: str,
    reports_dir: Path,
) -> List[Path]:
    if not services:
        services = discover_services(repo)

    findings = load_findings(services, findings_dir, findings_json)
    if not findings:
        raise ValueError("No findings loaded. Provide --findings-json or --findings-dir.")

    client = OpenAI(base_url=base_url, api_key="ollama")

    scored: List[ScoredFinding] = []
    for f in findings:
        scored.append(score_with_model(client, model, f))

    grouped = group_by_service(scored)
    output_paths = write_reports(grouped, reports_dir)
    write_manifest(output_paths, reports_dir)
    return output_paths


def main() -> int:
    args = parse_args()
    repo_path = Path(args.repo).resolve()

    services = [s.strip() for s in args.services.split(",") if s.strip()]
    findings_dir = Path(args.findings_dir) if args.findings_dir else None
    findings_json = Path(args.findings_json) if args.findings_json else None
    try:
        output_paths = run_audit(
            repo=repo_path,
            services=services,
            findings_dir=findings_dir,
            findings_json=findings_json,
            model=args.model,
            base_url=args.base_url,
            reports_dir=Path(args.reports_dir),
        )
    except ValueError as exc:
        print(str(exc))
        return 1

    print(f"Wrote {len(output_paths)} reports to {args.reports_dir}")
    print(f"Wrote manifest to {Path(args.reports_dir) / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
