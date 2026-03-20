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

"""Shared code for AgentCore examples."""

from .agent_factory import get_agent, configure_agentsec
from .tools import add, check_service_health, summarize_log
from .mcp_tools import get_mcp_tools, fetch_url

__all__ = [
    "get_agent",
    "configure_agentsec",
    "add",
    "check_service_health",
    "summarize_log",
    "get_mcp_tools",
    "fetch_url",
]
