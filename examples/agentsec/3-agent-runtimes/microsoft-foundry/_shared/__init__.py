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

"""Shared components for Microsoft Azure AI Foundry examples.

This package provides a common agent implementation that can be used
across different deployment modes (Foundry Agent App, Azure Functions, Container).

The agent is protected by agentsec (Cisco AI Defense) for both LLM and MCP calls.
Protection is initialized at import time when agent_factory is imported.
"""

from .agent_factory import invoke_agent, get_client
from .mcp_tools import fetch_url, get_mcp_tools

__all__ = ["invoke_agent", "get_client", "fetch_url", "get_mcp_tools"]
