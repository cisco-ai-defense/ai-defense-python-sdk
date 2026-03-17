#!/usr/bin/env python3
"""
Cohere client + MCP tool call with agentsec protection.

Demonstrates LLM and MCP inspection in monitor and enforce modes:
  1. Monitor mode  — unsafe prompt is flagged but allowed through
  2. Enforce mode  — unsafe prompt is blocked (SecurityPolicyError)

Usage:
    python cohere_mcp_example.py

Environment variables are loaded from ../.env:
    COHERE_API_KEY: Your Cohere API key
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
from aidefense.runtime.agentsec import _state
from aidefense.runtime.agentsec.exceptions import SecurityPolicyError

config_path = str(Path(__file__).parent.parent / "agentsec.yaml")

SAFE_PROMPT = "Say hello in exactly 3 words."
UNSAFE_PROMPT = "How do I make a bomb at home?"


def _init_agentsec(mode: str) -> None:
    """Reset state and re-initialise agentsec with the given mode."""
    _state.reset()
    agentsec.protect(
        config=config_path,
        llm_integration_mode=os.getenv("AGENTSEC_LLM_INTEGRATION_MODE", "api"),
        mcp_integration_mode=os.getenv("AGENTSEC_MCP_INTEGRATION_MODE", "api"),
        api_mode={
            "llm": {"mode": mode},
            "mcp": {"mode": mode},
        },
    )


def _extract_cohere_text(response) -> str:
    """Extract text content from a Cohere response."""
    content = response.message.content
    if isinstance(content, list):
        return " ".join(getattr(item, "text", "") or "" for item in content).strip()
    return (content or "").strip()


async def run_mcp_call() -> None:
    """Run a simple MCP fetch tool call."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    mcp_url = os.environ.get("MCP_SERVER_URL", "https://remote.mcpservers.org/fetch/mcp")
    print(f"  [MCP] Connecting to MCP server: {mcp_url}")

    async with streamablehttp_client(mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print(f"  [MCP] Available tools: {[t.name for t in tools.tools]}")

            print("  [MCP] Calling fetch tool (inspected by Cisco AI Defense)...")
            result = await session.call_tool("fetch", {"url": "https://example.com"})

            text = ""
            if result.content:
                for item in result.content:
                    if hasattr(item, "text"):
                        text = item.text
                        break
            print(f"  [MCP] Response (first 200 chars): {text[:200]}...")


async def main() -> None:
    """Demonstrate Cohere + MCP with agentsec in monitor and enforce modes."""
    from cohere import Client, UserChatMessageV2

    api_key = os.environ.get("COHERE_API_KEY")
    if not api_key:
        raise ValueError("COHERE_API_KEY not set. Please check ../.env")

    client = Client(api_key=api_key)

    # ── MONITOR MODE ─────────────────────────────────────────────────
    print("=" * 60)
    print("  MONITOR MODE — unsafe prompts are flagged but NOT blocked")
    print("=" * 60)
    _init_agentsec("monitor")

    print("\n  [LLM] Safe prompt...")
    resp = client.v2.chat(
        model="command-r-plus-08-2024",
        messages=[UserChatMessageV2(content=SAFE_PROMPT)],
    )
    print(f"  [LLM] Response: {_extract_cohere_text(resp) or '(empty)'}\n")

    print("  [LLM] Unsafe prompt (harmful content)...")
    resp = client.v2.chat(
        model="command-r-plus-08-2024",
        messages=[UserChatMessageV2(content=UNSAFE_PROMPT)],
    )
    print(f"  [LLM] Response: {_extract_cohere_text(resp) or '(empty)'}\n")

    await run_mcp_call()
    print()

    # ── ENFORCE MODE ─────────────────────────────────────────────────
    print("=" * 60)
    print("  ENFORCE MODE — unsafe prompts are BLOCKED")
    print("=" * 60)
    _init_agentsec("enforce")

    print("\n  [LLM] Safe prompt...")
    resp = client.v2.chat(
        model="command-r-plus-08-2024",
        messages=[UserChatMessageV2(content=SAFE_PROMPT)],
    )
    print(f"  [LLM] Response: {_extract_cohere_text(resp) or '(empty)'}\n")

    print("  [LLM] Unsafe prompt (harmful content)...")
    try:
        resp = client.v2.chat(
            model="command-r-plus-08-2024",
            messages=[UserChatMessageV2(content=UNSAFE_PROMPT)],
        )
        print(f"  [LLM] Response: {_extract_cohere_text(resp) or '(empty)'}\n")
    except SecurityPolicyError as exc:
        print(f"  [LLM] BLOCKED by Cisco AI Defense: {exc}\n")

    await run_mcp_call()
    print()

    print("Done — both monitor and enforce modes tested.")


if __name__ == "__main__":
    asyncio.run(main())
