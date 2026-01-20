"""Shared agent components for GCP Vertex AI Agent Engine example.

This module provides a LangChain-based agent with tools, similar to how
Amazon Bedrock AgentCore uses Strands Agent.

The agent can:
- Check service health (check_service_health)
- Get recent logs (get_recent_logs)
- Calculate capacity metrics (calculate_capacity)
- Fetch webpage content via MCP (fetch_url) - if MCP_SERVER_URL is set

All LLM calls and MCP tool calls are protected by agentsec (Cisco AI Defense).
"""

from .agent_factory import invoke_agent, get_client
from .tools import TOOLS, check_service_health, get_recent_logs, calculate_capacity
from .mcp_tools import fetch_url, get_mcp_tools, _sync_call_mcp_tool

__all__ = [
    # Agent functions
    "invoke_agent",
    "get_client",
    # Local tools (LangChain @tool decorated)
    "TOOLS",
    "check_service_health",
    "get_recent_logs",
    "calculate_capacity",
    # MCP tools (LangChain @tool decorated)
    "fetch_url",
    "get_mcp_tools",
    "_sync_call_mcp_tool",
]
