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

"""Security inspectors for LLM and MCP interactions."""

# API Mode Inspectors
from .api_llm import LLMInspector
from .api_mcp import MCPInspector

# Gateway Mode Inspectors
from .gateway_llm import GatewayClient
from .gateway_mcp import MCPGatewayInspector

__all__ = ["LLMInspector", "MCPInspector", "GatewayClient", "MCPGatewayInspector"]

# Re-export for convenience
inspect_llm = LLMInspector
inspect_mcp = MCPInspector
