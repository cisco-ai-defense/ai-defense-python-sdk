#!/usr/bin/env python3
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
Simple Strands agent using Bedrock Claude model with AI Defense protection.

This example demonstrates:
- Using Strands Agent with AWS Bedrock
- Enabling AI Defense protection for LLM calls
- API mode with enforce inspection

Prerequisites:
- AWS credentials configured (via environment or ~/.aws/credentials)
- AI Defense API key in examples/.env

Usage:
    python simple_strands_bedrock.py
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from examples/.env
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)

# Enable verbose logging
os.environ["AGENTSEC_LOG_LEVEL"] = "DEBUG"

from aidefense.runtime import agentsec

# Enable AI Defense protection for all LLM calls
config_path = str(Path(__file__).parent.parent / "agentsec.yaml")
agentsec.protect(
    config=config_path,  # gateway URLs, API endpoints, timeouts
    llm_integration_mode=os.getenv("AGENTSEC_LLM_INTEGRATION_MODE", "api"),
    mcp_integration_mode=os.getenv("AGENTSEC_MCP_INTEGRATION_MODE", "api"),
    api_mode={
        "llm": {"mode": "monitor"},
        "llm_defaults": {"fail_open": True},
    },
)

from strands import Agent
from strands.models import BedrockModel

# Create Bedrock model (uses default AWS credentials from environment)
# Use Claude 3 Haiku for on-demand (Claude 3.5 Sonnet requires inference profile)
model = BedrockModel(
    model_id="anthropic.claude-3-haiku-20240307-v1:0",
    region_name=os.getenv("AWS_REGION", "us-west-2"),
)

# Create agent
agent = Agent(model=model)


def main():
    """Run the Strands agent with AI Defense protection."""
    response = agent("Plan a healthy dinner menu for a family of four.")
    print(response)


if __name__ == "__main__":
    main()

