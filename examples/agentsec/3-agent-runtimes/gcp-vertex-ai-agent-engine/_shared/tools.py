"""
Demo tools for the SRE agent using LangChain @tool decorator.

These tools demonstrate how agent tools work with agentsec protection.
In a real deployment, these would connect to actual monitoring systems.

The LangChain @tool decorator enables the agent to reason about when to use
each tool based on its docstring and parameter types.
"""

import random
from datetime import datetime
from typing import Dict, Any

from langchain_core.tools import tool


@tool
def check_service_health(service_name: str) -> str:
    """
    Check the health status of a service.
    
    Use this tool when you need to check if a service is running properly.
    
    Args:
        service_name: Name of the service to check (e.g., 'payments', 'auth', 'database')
        
    Returns:
        A string describing the health status of the service
    """
    # Demo implementation - would connect to real monitoring in production
    statuses = ["healthy", "healthy", "healthy", "degraded", "unhealthy"]
    status = random.choice(statuses)
    
    result = {
        "service": service_name,
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "latency_ms": random.randint(10, 500) if status != "unhealthy" else None,
        "error_rate": round(random.uniform(0, 0.1) if status == "healthy" else random.uniform(0.1, 0.5), 4),
    }
    
    print(f"[TOOL CALL] check_service_health(service_name='{service_name}')", flush=True)
    print(f"[TOOL] Result: {result}", flush=True)
    
    return f"Service '{service_name}' is {status}. Latency: {result['latency_ms']}ms, Error rate: {result['error_rate']}"


@tool
def get_recent_logs(service_name: str, limit: int = 10) -> str:
    """
    Get recent log entries for a service.
    
    Use this tool when you need to see recent logs or troubleshoot issues.
    
    Args:
        service_name: Name of the service to get logs from
        limit: Maximum number of log entries to return (default: 10)
        
    Returns:
        A string containing recent log entries
    """
    log_levels = ["INFO", "INFO", "INFO", "WARN", "ERROR"]
    messages = [
        "Request processed successfully",
        "Connection established",
        "Cache hit for key xyz",
        "Slow query detected (>100ms)",
        "Connection timeout to database",
        "Health check passed",
        "Configuration reloaded",
    ]
    
    logs = []
    for i in range(min(limit, 10)):
        logs.append({
            "timestamp": datetime.now().isoformat(),
            "level": random.choice(log_levels),
            "message": random.choice(messages),
            "service": service_name,
        })
    
    print(f"[TOOL CALL] get_recent_logs(service_name='{service_name}', limit={limit})", flush=True)
    print(f"[TOOL] Retrieved {len(logs)} log entries", flush=True)
    
    log_lines = [f"[{log['level']}] {log['timestamp']} - {log['message']}" for log in logs]
    return f"Recent logs for {service_name}:\n" + "\n".join(log_lines)


@tool
def calculate_capacity(current_usage: float, growth_rate: float, target_utilization: float = 0.7) -> str:
    """
    Calculate capacity planning metrics and provide recommendations.
    
    Use this tool for capacity planning and resource scaling decisions.
    
    Args:
        current_usage: Current resource usage as a decimal (0-1, e.g., 0.5 for 50%)
        growth_rate: Monthly growth rate as a decimal (e.g., 0.1 for 10% monthly growth)
        target_utilization: Target utilization threshold (default: 0.7 for 70%)
        
    Returns:
        A string with capacity planning analysis and recommendations
    """
    if current_usage >= target_utilization:
        months_until_full = 0
    else:
        import math
        months_until_full = math.log(target_utilization / current_usage) / math.log(1 + growth_rate)
    
    recommendation = "Scale now" if months_until_full < 3 else "Monitor" if months_until_full < 6 else "Stable"
    
    result = {
        "current_usage": f"{current_usage * 100:.1f}%",
        "target_utilization": f"{target_utilization * 100:.1f}%",
        "growth_rate": f"{growth_rate * 100:.1f}% monthly",
        "months_until_target": round(months_until_full, 1),
        "recommendation": recommendation,
    }
    
    print(f"[TOOL CALL] calculate_capacity(current_usage={current_usage}, growth_rate={growth_rate}, target_utilization={target_utilization})", flush=True)
    print(f"[TOOL] Result: {result}", flush=True)
    
    return (
        f"Capacity Analysis:\n"
        f"- Current usage: {result['current_usage']}\n"
        f"- Target utilization: {result['target_utilization']}\n"
        f"- Growth rate: {result['growth_rate']}\n"
        f"- Months until target: {result['months_until_target']}\n"
        f"- Recommendation: {result['recommendation']}"
    )


# Export list of all tools for the agent
TOOLS = [check_service_health, get_recent_logs, calculate_capacity]
