#!/usr/bin/env python3
"""
Azure OpenAI client + MCP tool call with agentsec protection.

Demonstrates both LLM and MCP inspection in a single script:
  1. LLM call via Azure OpenAI chat.completions (inspected by AI Defense)
  2. MCP tool call via session.call_tool (inspected by AI Defense)

Usage:
    python azure_openai_mcp_example.py

Environment variables are loaded from ../.env:
    AZURE_OPENAI_API_KEY: Your Azure OpenAI API key
    AZURE_OPENAI_ENDPOINT: Your Azure OpenAI endpoint
    AZURE_OPENAI_DEPLOYMENT_NAME: Deployment name (e.g., gpt-4o)
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
    print(f"Loaded environment from {env_file}")

from aidefense.runtime import agentsec
config_path = str(Path(__file__).parent.parent / "agentsec.yaml")
agentsec.protect(
    config=config_path,
    llm_integration_mode=os.getenv("AGENTSEC_LLM_INTEGRATION_MODE", "api"),
    mcp_integration_mode=os.getenv("AGENTSEC_MCP_INTEGRATION_MODE", "api"),
    api_mode={
        "llm": {"mode": "monitor"},
        "mcp": {"mode": "monitor"},
    },
)


async def main() -> None:
    """Demonstrate Azure OpenAI + MCP with agentsec protection."""

    patched = agentsec.get_patched_clients()
    print(f"Patched clients: {patched}")
    print()

    # --- LLM call ---
    from openai import AzureOpenAI

    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

    if not api_key or not endpoint:
        raise ValueError("AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT must be set in ../.env")

    client = AzureOpenAI(
        api_key=api_key,
        azure_endpoint=endpoint,
        api_version=api_version,
    )

    print(f"[LLM] Making Azure OpenAI call (inspected by Cisco AI Defense)...")
    response = client.chat.completions.create(
        model=deployment,
        messages=[{"role": "user", "content": "Say hello in exactly 3 words."}],
    )
    print(f"[LLM] Response: {response.choices[0].message.content}")
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
