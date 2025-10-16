"""
Utility functions for displaying scan results in the AI Defense Python SDK examples.
"""
from typing import List

from aidefense.modelscan.models import (
    Technique,
    Severity,
    ScanStatus,
    AnalysisResult,
    FileInfo
)


def format_severity(severity: Severity) -> str:
    """Format severity with appropriate emoji and color."""
    if severity == Severity.CRITICAL:
        return f"🔴 {severity.value}"
    elif severity == Severity.HIGH:
        return f"🟠 {severity.value}"
    elif severity == Severity.MEDIUM:
        return f"🟡 {severity.value}"
    elif severity == Severity.LOW:
        return f"🔵 {severity.value}"
    else:
        return f"⚪ {severity.value}"


def print_threats(techniques: List[Technique], indent: int = 0) -> None:
    """Recursively print threat information from the hierarchical structure."""
    indent_str = "  " * indent
    for technique in techniques:
        print(f"{indent_str}🔍 {technique.technique_name} ({technique.technique_id})")
        
        for sub_technique in technique.items:
            print(f"{indent_str}  │")
            print(f"{indent_str}  ├─ 🎯 {sub_technique.sub_technique_name} ({sub_technique.sub_technique_id})")
            print(f"{indent_str}  │  ├─ Severity: {format_severity(sub_technique.max_severity)}")
            
            if sub_technique.description:
                print(f"{indent_str}  │  ├─ Description: {sub_technique.description}")
                
            if sub_technique.indicators:
                print(f"{indent_str}  │  ├─ Indicators:")
                for indicator in sub_technique.indicators:
                    print(f"{indent_str}  │  │  • {indicator}")
            
            if sub_technique.items:
                print(f"{indent_str}  │  └─ Detections:")
                for threat in sub_technique.items:
                    print(f"{indent_str}  │     • {threat.threat_type.value}: {threat.description}")
                    if threat.details:
                        print(f"{indent_str}  │       Details: {threat.details}")
            print(f"{indent_str}  │")


def print_file_info(file_info: FileInfo) -> None:
    """Print information about a scanned file and its threats."""
    # Determine status icon
    if file_info.status == ScanStatus.SKIPPED:
        status_icon = "⏭️"
    elif file_info.threats.items:
        status_icon = "⚠️"
    else:
        status_icon = "✅"

    print(f"\n{status_icon} {file_info.name} ({file_info.size} bytes)")
    print(f"  Status: {file_info.status.value}")

    if file_info.reason:
        print(f"  Reason: {file_info.reason}")

    # Display threat information if available
    if file_info.threats.items:
        print("\n  🚨 Threats Detected:")
        print("  " + "-" * 45)
        print_threats(file_info.threats.items, indent=2)
    elif file_info.status == ScanStatus.COMPLETED:
        print("  ✅ No threats detected")


def print_analysis_results(analysis_results: AnalysisResult, scan_id: str = None) -> None:
    """Print analysis results with pagination information.
    
    Args:
        analysis_results: The analysis results to display
        scan_id: Optional scan ID to display in the results
    """
    total_files = analysis_results.paging.total
    print(f"📂 Files Analyzed: {len(analysis_results.items)} of {total_files}")
    print("=" * 50)

    for item in analysis_results.items:
        print_file_info(item)

    # Handle pagination if there are more results
    paging = analysis_results.paging
    if paging.offset + len(analysis_results.items) < paging.total:
        remaining = paging.total - (paging.offset + len(analysis_results.items))
        print(f"\n📄 {remaining} more files available. Use file_offset to retrieve additional results.")
