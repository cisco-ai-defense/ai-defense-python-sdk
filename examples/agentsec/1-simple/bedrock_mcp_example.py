#!/usr/bin/env python3
"""
AWS Bedrock (Strands) + MCP tool call with agentsec protection.

Demonstrates both LLM and MCP inspection in a single script:
  1. LLM call via Strands Agent with Bedrock (inspected by AI Defense)
  2. MCP tool call via session.call_tool (inspected by AI Defense)

Prerequisites:
  - AWS credentials configured (via environment or ~/.aws/credentials)

Usage:
    python bedrock_mcp_example.py

Environment variables are loaded from ../.env:
    AWS_REGION: AWS region (default: us-west-2)
    AI_DEFENSE_API_MODE_LLM_API_KEY: Cisco AI Defense API key
    AI_DEFENSE_API_MODE_LLM_ENDPOINT: LLM API endpoint URL
    AI_DEFENSE_API_MODE_MCP_API_KEY: Cisco AI Defense MCP API key
    AI_DEFENSE_API_MODE_MCP_ENDPOINT: MCP API endpoint URL
    MCP_SERVER_URL: MCP server (default: https://remote.mcpservers.org/fetch/mcp)
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)

from aidefense.runtime import agentsec
config_path = str(Path(__file__).parent.parent / "agentsec.yaml")
agentsec.protect(
    config=config_path,
    llm_integration_mode=os.getenv("AGENTSEC_LLM_INTEGRATION_MODE", "api"),
    mcp_integration_mode=os.getenv("AGENTSEC_MCP_INTEGRATION_MODE", "api"),
    api_mode={
        "llm": {"mode": "monitor"},
        "mcp": {"mode": "monitor"},
        "llm_defaults": {"fail_open": True},
    },
)


async def main() -> None:
    """Demonstrate Bedrock + MCP with agentsec protection."""

    patched = agentsec.get_patched_clients()
    print(f"Patched clients: {patched}")
    print()

    # --- LLM call ---
    from strands import Agent
    from strands.models import BedrockModel

    model = BedrockModel(
        model_id="anthropic.claude-3-haiku-20240307-v1:0",
        region_name=os.getenv("AWS_REGION", "us-west-2"),
    )
    agent = Agent(model=model)

    print("[LLM] Making Bedrock call (inspected by Cisco AI Defense)...")
    response = agent("Say hello in exactly 3 words.")
    print(f"[LLM] Response: {response}")
    print()

    # --- MCP tool call ---
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    mcp_url = os.environ.get("MCP_SERVER_URL", "https://remote.mcpservers.org/fetch/mcp")
    print(f"[MCP] Connecting to MCP server: {mcp_url}")

    async with streamablehttp_client(mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print(f"[MCP] Available tools: {[t.name for t in tools.tools]}")

            print("[MCP] Calling fetch tool (inspected by Cisco AI Defense)...")
            result = await session.call_tool("fetch", {"url": "https://example.com"})

            text = ""
            if result.content:
                for item in result.content:
                    if hasattr(item, "text"):
                        text = item.text
                        break
            print(f"[MCP] Response (first 200 chars): {text[:200]}...")
            print()

    print("Both LLM and MCP calls were inspected by Cisco AI Defense!")


if __name__ == "__main__":
    asyncio.run(main())
