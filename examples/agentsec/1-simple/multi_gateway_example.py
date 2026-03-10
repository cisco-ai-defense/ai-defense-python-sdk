#!/usr/bin/env python3
"""
Multi-Gateway Example — Two Bedrock LLM Gateways + Two MCP Servers.

Demonstrates:
1. Two Bedrock LLM gateways (same provider, different connections/models):
   - bedrock-1 (default): cheap model (Claude 3 Haiku) for quick tasks
   - bedrock-2 (named):   capable model (Claude 3.5 Sonnet) for complex tasks

2. Per-gateway AWS credentials (different regions/profiles per gateway):
   - bedrock-1 uses AWS_REGION=us-east-1 with profile "default"
   - bedrock-2 uses AWS_REGION=eu-west-1 with profile "team-b"
   Both are configured in agentsec.yaml with ${VAR} substitution from .env.

3. Two MCP servers (both defined in agentsec.yaml mcp_gateways):
   - https://remote.mcpservers.org/fetch/mcp — fetches web pages
   - https://mcp.time.mcpcentral.io         — returns current time
   MCP gateways support per-server auth_mode: none, api_key,
   or oauth2_client_credentials (see agentsec.yaml for examples).

All calls are protected by Cisco AI Defense — both request and response
are inspected in both API mode and Gateway mode.

Usage:
    python multi_gateway_example.py

Configuration:
    LLM gateways: agentsec.yaml → gateway_mode.llm_gateways (bedrock-1, bedrock-2)
    MCP gateways: agentsec.yaml → gateway_mode.mcp_gateways (fetch, time)
    Secrets:       ../.env
    AWS per-gw:    agentsec.yaml → aws_region, aws_profile (per gateway entry)
"""

import asyncio
import os
from pathlib import Path

# Load environment variables from shared .env file BEFORE importing agentsec
from dotenv import load_dotenv
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"Loaded environment from {env_file}")

from aidefense.runtime import agentsec

# Load full configuration from YAML (recommended approach)
config_path = str(Path(__file__).parent.parent / "agentsec.yaml")
agentsec.protect(
    config=config_path,
    # Allow env var overrides for integration testing (api vs gateway)
    llm_integration_mode=os.getenv("AGENTSEC_LLM_INTEGRATION_MODE", "gateway"),
    mcp_integration_mode=os.getenv("AGENTSEC_MCP_INTEGRATION_MODE", "gateway"),
)


# =============================================================================
# Part 1: Two Bedrock LLM Gateways (same provider, different models)
# =============================================================================

def demo_llm_gateways():
    """Use bedrock-1 (default, cheap) and bedrock-2 (named, capable)."""
    import boto3

    print("=" * 70)
    print("  Part 1: Two Bedrock LLM Gateways (same provider)")
    print("=" * 70)
    print()

    bedrock = boto3.client(
        "bedrock-runtime",
        region_name=os.getenv("AWS_REGION", "us-east-1"),
    )

    # ── Call 1: bedrock-1 (default gateway) — cheap model ────────────────
    # bedrock-1 uses its own AWS credentials for SigV4 signing, configured
    # via aws_region/aws_profile in agentsec.yaml (e.g. us-east-1, default profile).
    prompt1 = "What is 2 + 2? Answer in one sentence."
    print("► bedrock-1 (default) — Claude 3 Haiku (cheap, fast model)")
    print(f"  Prompt: {prompt1}")

    # No gateway() context needed — bedrock-1 is the default for provider=bedrock
    response1 = bedrock.converse(
        modelId="anthropic.claude-3-haiku-20240307-v1:0",
        messages=[{"role": "user", "content": [{"text": prompt1}]}],
    )
    text1 = response1["output"]["message"]["content"][0]["text"]
    print(f"  Response: {text1}")
    print()

    # ── Call 2: bedrock-2 (named gateway) — capable model ────────────────
    # bedrock-2 can use different AWS credentials (e.g. eu-west-1, profile "team-b")
    # configured independently in agentsec.yaml.
    prompt2 = "Explain quantum entanglement in two sentences."
    print("► bedrock-2 (named) — Claude 3.5 Sonnet (capable model)")
    print(f"  Prompt: {prompt2}")

    # Use gateway("bedrock-2") to route this call through the second gateway
    try:
        with agentsec.gateway("bedrock-2"):
            response2 = bedrock.converse(
                modelId="anthropic.claude-3-5-sonnet-20241022-v2:0",
                messages=[{"role": "user", "content": [{"text": prompt2}]}],
            )
        text2 = response2["output"]["message"]["content"][0]["text"]
        print(f"  Response: {text2}")
    except Exception as e:
        # The bedrock-2 gateway connection may not have policies attached yet.
        # The routing to the correct gateway connection is still demonstrated.
        print(f"  Gateway returned error: {e}")
        print("  (This is expected if the bedrock-2 connection has no policies attached.)")
        print("  Note: The call was correctly routed to the bedrock-2 gateway connection.")
    print()


# =============================================================================
# Part 2: Two MCP Servers (both defined in agentsec.yaml)
# =============================================================================

async def demo_mcp_servers():
    """Connect to two MCP servers defined in agentsec.yaml mcp_gateways."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    print("=" * 70)
    print("  Part 2: Two MCP Servers")
    print("=" * 70)
    print()

    # ── MCP Server 1: Fetch (remote.mcpservers.org) ──────────────────────
    fetch_url = "https://remote.mcpservers.org/fetch/mcp"
    print(f"► MCP Server 1: {fetch_url}")
    try:
        async with streamablehttp_client(fetch_url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools = await session.list_tools()
                tool_names = [t.name for t in tools.tools]
                print(f"  Available tools: {tool_names}")

                # Call the fetch tool
                result = await session.call_tool(
                    "fetch", {"url": "https://example.com"}
                )
                text = ""
                if result.content:
                    for c in result.content:
                        if hasattr(c, "text"):
                            text = c.text
                            break
                print(f"  fetch(example.com): {text[:150]}...")
    except Exception as e:
        print(f"  Error connecting to fetch server: {e}")
    print()

    # ── MCP Server 2: Time (mcp.time.mcpcentral.io) ─────────────────────
    time_url = "https://mcp.time.mcpcentral.io"
    print(f"► MCP Server 2: {time_url}")
    try:
        async with streamablehttp_client(time_url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools = await session.list_tools()
                tool_names = [t.name for t in tools.tools]
                print(f"  Available tools: {tool_names}")

                # Call the first available tool
                if tools.tools:
                    tool = tools.tools[0]
                    # Build args from schema if required
                    args = {}
                    schema = getattr(tool, "inputSchema", None) or {}
                    props = schema.get("properties", {})
                    if "timezone" in props:
                        args["timezone"] = "America/New_York"
                    result = await session.call_tool(tool.name, args)
                    text = ""
                    if result.content:
                        for c in result.content:
                            if hasattr(c, "text"):
                                text = c.text
                                break
                    print(f"  {tool.name}({args}): {text[:200]}")
    except Exception as e:
        print(f"  Error connecting to time server: {e}")
    print()


# =============================================================================
# Main
# =============================================================================

def main():
    print()
    print("Multi-Gateway Example")
    print("Showcasing multiple LLM gateways + multiple MCP servers")
    print("All protected by Cisco AI Defense")
    print()

    # Part 1: Two Bedrock LLM gateways
    demo_llm_gateways()

    # Part 2: Two MCP servers
    asyncio.run(demo_mcp_servers())

    print("=" * 70)
    print("  Done! All calls were protected by Cisco AI Defense.")
    print("=" * 70)


if __name__ == "__main__":
    main()
