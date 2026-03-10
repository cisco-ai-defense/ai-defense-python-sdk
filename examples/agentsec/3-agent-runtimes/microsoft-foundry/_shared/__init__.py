"""Shared components for Microsoft Azure AI Foundry examples.

This package provides a common agent implementation that can be used
across different deployment modes (Foundry Agent App, Azure Functions, Container).

The agent is protected by agentsec (Cisco AI Defense) for both LLM and MCP calls.
Protection is initialized at import time when agent_factory is imported.
"""

from .agent_factory import invoke_agent, get_client
from .mcp_tools import fetch_url, get_mcp_tools

__all__ = ["invoke_agent", "get_client", "fetch_url", "get_mcp_tools"]
