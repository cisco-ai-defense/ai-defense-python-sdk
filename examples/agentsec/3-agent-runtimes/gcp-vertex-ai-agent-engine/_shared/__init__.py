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
