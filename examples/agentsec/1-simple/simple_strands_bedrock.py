#!/usr/bin/env python3
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
# Reads mode from environment: AGENTSEC_LLM_INTEGRATION_MODE (api/gateway)
agentsec.protect(
    api_mode_llm="on_monitor",
    api_mode_fail_open_llm=True,
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

