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

"""
Agent Engine entry point for Vertex AI Agent Engine deployment.

This module provides the callable agent object that Agent Engine expects.
Follows the official deployment guide:
https://cloud.google.com/agent-builder/agent-engine/deploy
"""
import os
import sys
from pathlib import Path

# Add parent directories to path to access _shared
current_dir = Path(__file__).parent
agent_deploy_dir = current_dir.parent
project_dir = agent_deploy_dir.parent

if str(project_dir) not in sys.path:
    sys.path.insert(0, str(project_dir))

from _shared.agent_factory import invoke_agent as _invoke_agent


class AgentEngineAgent:
    """
    Agent wrapper for Vertex AI Agent Engine.
    
    This class wraps the invoke_agent function to make it compatible
    with Agent Engine's expected interface (query method).
    """
    
    def query(self, prompt: str) -> str:
        """
        Query the agent with a prompt (Agent Engine standard interface).
        
        This method is exposed to Agent Engine and can be called via the API.
        All LLM and MCP calls are protected by agentsec through the agent_factory.
        
        Args:
            prompt: The user prompt for the agent
            
        Returns:
            str: The agent's response
        """
        return _invoke_agent(prompt)
    
    def __call__(self, prompt: str) -> str:
        """Make the agent directly callable."""
        return self.query(prompt)


# Create the agent instance that Agent Engine will use
agent = AgentEngineAgent()
