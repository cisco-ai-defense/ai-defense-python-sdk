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

"""
Utility functions for displaying MCP scan results in the AI Defense Python SDK examples.
"""
from datetime import datetime
from typing import Optional

from aidefense.mcpscan.models import (
    GetMCPScanStatusResponse,
    GetMCPServerScanSummaryResponse,
    MCPScanStatus,
    MCPScanResult,
    CapabilityScanResult,
)


def format_timestamp(timestamp: Optional[datetime]) -> str:
    """Format a timestamp into a human-readable string.

    Args:
        timestamp: The datetime object to format

    Returns:
        Formatted date-time string or "N/A" if None
    """
    if not timestamp:
        return "N/A"
    return timestamp.strftime("%Y-%m-%d %H:%M:%S %Z")


def format_severity(severity: str) -> str:
    """Format severity with appropriate emoji.

    Args:
        severity: Severity level string

    Returns:
        Formatted severity string with emoji
    """
    severity_upper = severity.upper()
    if severity_upper == "CRITICAL":
        return f"🔴 {severity}"
    elif severity_upper == "HIGH":
        return f"🟠 {severity}"
    elif severity_upper == "MEDIUM":
        return f"🟡 {severity}"
    elif severity_upper == "LOW":
        return f"🔵 {severity}"
    else:
        return f"⚪ {severity}"


def get_status_value(status) -> str:
    """Extract string value from status (handles both enum and string)."""
    if hasattr(status, 'value'):
        return status.value
    return str(status)


def format_status(status) -> str:
    """Format scan status with appropriate emoji.

    Args:
        status: The scan status (enum or string)

    Returns:
        Formatted status string with emoji
    """
    status_str = get_status_value(status)
    status_icons = {
        "QUEUED": "⏳",
        "IN_PROGRESS": "🔄",
        "COMPLETED": "✅",
        "FAILED": "❌",
        "CANCELLED": "🚫",
        "CANCELLING": "⏸️",
    }
    icon = status_icons.get(status_str.upper(), "❓")
    return f"{icon} {status_str}"


def print_capability_result(result: CapabilityScanResult, indent: int = 2) -> None:
    """Print information about a capability scan result.

    Args:
        result: The capability scan result to display
        indent: Number of spaces for indentation
    """
    indent_str = " " * indent

    # Determine status icon
    if result.is_safe:
        status_icon = "✅"
    else:
        status_icon = "⚠️"

    print(f"{indent_str}{status_icon} {result.capability_name}")
    print(f"{indent_str}   ID: {result.capability_id}")
    print(f"{indent_str}   Status: {result.status}")
    print(f"{indent_str}   Severity: {format_severity(result.severity)}")
    print(f"{indent_str}   Analyzer: {result.analyzer_type}")
    print(f"{indent_str}   Findings: {result.total_findings}")

    if result.threat_names:
        print(f"{indent_str}   Threats:")
        for threat in result.threat_names:
            print(f"{indent_str}     • {threat}")

    if result.threat_summary:
        print(f"{indent_str}   Summary: {result.threat_summary}")

    if result.capability_description:
        desc = result.capability_description[:100]
        if len(result.capability_description) > 100:
            desc += "..."
        print(f"{indent_str}   Description: {desc}")


def print_scan_result(result) -> None:
    """Print MCP scan result details.

    Args:
        result: The scan result to display (can be dict or MCPScanResult)
    """
    print("\n🔒 Security Assessment:")
    print("-" * 40)

    # Handle both dict and object
    if isinstance(result, dict):
        is_safe = result.get("is_safe", False)
        capabilities = result.get("capabilities", {})
    else:
        is_safe = result.is_safe
        capabilities = result.capabilities

    if is_safe:
        print("  ✅ Overall Status: SAFE")
    else:
        print("  ⚠️ Overall Status: THREATS DETECTED")

    # Print capabilities
    if capabilities:
        # Handle dict format from API
        if isinstance(capabilities, dict):
            tool_results = capabilities.get("tool_results", {})
        else:
            tool_results = capabilities.tool_results if capabilities.tool_results else {}

        if tool_results:
            print("\n📋 Capabilities Scanned:")
            print("-" * 40)

            safe_count = 0
            threat_count = 0

            for cap_id, cap_results in tool_results.items():
                # Handle both dict and object formats
                if isinstance(cap_results, dict):
                    items = cap_results.get("items", [])
                else:
                    items = cap_results.items if cap_results.items else []

                for item in items:
                    if isinstance(item, dict):
                        name = item.get("capability_name", "Unknown")
                        item_is_safe = item.get("is_safe", True)
                        severity = item.get("severity", "SAFE")
                        threats = item.get("threat_names", [])
                        description = item.get("capability_description", "")
                    else:
                        name = item.capability_name
                        item_is_safe = item.is_safe
                        severity = item.severity
                        threats = item.threat_names or []
                        description = item.capability_description or ""

                    icon = "✅" if item_is_safe else "⚠️"
                    print(f"  {icon} {name}")
                    print(f"      Severity: {format_severity(severity)}")

                    if description:
                        desc = description[:80] + "..." if len(description) > 80 else description
                        print(f"      Description: {desc}")

                    # Get detailed threats from the new 'threats' field
                    if isinstance(item, dict):
                        detailed_threats = item.get("threats", [])
                    else:
                        detailed_threats = getattr(item, "threats", []) or []

                    if detailed_threats:
                        print(f"      Threats:")
                        for threat in detailed_threats:
                            if isinstance(threat, dict):
                                sub_name = threat.get("subTechniqueName") or threat.get("sub_technique_name", "Unknown")
                                threat_severity = threat.get("severity", "")
                                threat_desc = threat.get("description", "")
                            else:
                                sub_name = getattr(threat, "sub_technique_name", "Unknown")
                                threat_severity = getattr(threat, "severity", "")
                                threat_desc = getattr(threat, "description", "")

                            print(f"        • {sub_name}")
                            if threat_severity:
                                print(f"          Severity: {format_severity(threat_severity)}")
                            if threat_desc:
                                print(f"          Description: {threat_desc}")
                    elif threats:
                        # Fallback to threat_names if no detailed threats
                        print(f"      Threats: {', '.join(threats)}")

                    if item_is_safe:
                        safe_count += 1
                    else:
                        threat_count += 1

            print("\n📈 Summary:")
            print(f"  Total capabilities: {safe_count + threat_count}")
            print(f"  Safe: {safe_count}")
            print(f"  With threats: {threat_count}")


def print_scan_status(response: GetMCPScanStatusResponse, debug: bool = False) -> None:
    """Print comprehensive scan status information.

    Args:
        response: The scan status response to display
        debug: If True, print raw response data for debugging
    """
    print("\n📊 Scan Status:")
    print("=" * 50)
    print(f"  Server:     {response.name}")
    print(f"  Scan ID:    {response.scan_id}")
    print(f"  Status:     {format_status(response.status)}")
    print(f"  Created:    {format_timestamp(response.created_at)}")
    print(f"  Completed:  {format_timestamp(response.completed_at)}")

    if response.expires_at:
        print(f"  Expires:    {format_timestamp(response.expires_at)}")

    if response.error_info:
        print(f"\n❌ Error: {response.error_info.message}")
        if response.error_info.remediation_tips:
            print("   Remediation tips:")
            for tip in response.error_info.remediation_tips:
                print(f"     • {tip}")

    if debug and response.result:
        print("\n🔧 Debug - Raw Result:")
        print(f"  {response.result.dict() if hasattr(response.result, 'dict') else response.result}")

    if response.result:
        print_scan_result(response.result)


def print_server_scan_summary(summary: GetMCPServerScanSummaryResponse) -> None:
    if summary.capability_summary:
        cap_sum = summary.capability_summary
        print("Capability Summary:")
        print(f"  Tools:     {cap_sum.tool_count}")
        print(f"  Prompts:   {cap_sum.prompt_count}")
        print(f"  Resources: {cap_sum.resource_count}")

    if summary.scan_threat_summary:
        threat_sum = summary.scan_threat_summary
        print("\nThreat Summary:")
        print(f"  Critical: {threat_sum.critical_count}")
        print(f"  High:     {threat_sum.high_count}")
        print(f"  Medium:   {threat_sum.medium_count}")
        print(f"  Low:      {threat_sum.low_count}")

    if summary.completed_at:
        print(f"\nLast scan completed: {summary.completed_at}")
