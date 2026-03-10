#!/usr/bin/env python3
"""
Direct OAuth2 debug for MCP server auth (without agentsec gateway redirect).

Flow:
1) POST /oauth/token (client credentials) to get bearer token
2) Connect to MCP OAuth endpoint with Authorization: Bearer <token>
3) Initialize session and list tools
"""

import asyncio
import os
from pathlib import Path
from typing import Any, Dict

import httpx
from dotenv import load_dotenv

# Load shared env if present (examples/agentsec/.env)
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"Loaded environment from {env_file}")

MCP_OAUTH_SERVER_URL = os.getenv(
    "MCP_OAUTH_SERVER_URL",
    "https://mcp-testing.aiteam.cisco.com/mock_mcp/mcp/oauth",
)
MCP_TOKEN_URL = os.getenv(
    "MCP_OAUTH_TOKEN_URL",
    "https://mcp-testing.aiteam.cisco.com/mock_mcp/oauth/token",
)
MCP_HEALTH_URL = os.getenv(
    "MCP_OAUTH_HEALTH_URL",
    "https://mcp-testing.aiteam.cisco.com/mock_mcp/health",
)
MCP_CLIENT_ID = os.getenv("MCP_OAUTH_CLIENT_ID", "test-client")
MCP_CLIENT_SECRET = os.getenv("MCP_OAUTH_CLIENT_SECRET", "test-secret")
MCP_SCOPES = os.getenv("MCP_OAUTH_SCOPES", "read write")


def _build_safe_args(schema: Dict[str, Any]) -> Dict[str, Any] | None:
    required = schema.get("required", []) if isinstance(schema, dict) else []
    if required:
        return None
    return {}


def fetch_access_token() -> str:
    data = {"grant_type": "client_credentials", "scope": MCP_SCOPES}
    resp = httpx.post(
        MCP_TOKEN_URL,
        data=data,
        auth=(MCP_CLIENT_ID, MCP_CLIENT_SECRET),
        timeout=30.0,
    )
    resp.raise_for_status()
    payload = resp.json()
    token = payload.get("access_token")
    if not token:
        raise RuntimeError(f"Token response missing access_token: keys={list(payload.keys())}")
    return token


async def main() -> None:
    print("MCP OAuth2 Direct Auth Debug")
    print("=" * 32)
    print(f"Health URL: {MCP_HEALTH_URL}")
    print(f"Token URL:  {MCP_TOKEN_URL}")
    print(f"MCP URL:    {MCP_OAUTH_SERVER_URL}")

    try:
        health = httpx.get(MCP_HEALTH_URL, timeout=10.0)
        print(f"Health status: {health.status_code}")
    except Exception as exc:
        print(f"Health check failed: {exc}")

    try:
        token = fetch_access_token()
        print(f"Token acquired: {token[:20]}... (truncated)")
    except Exception as exc:
        print(f"Token fetch failed: {exc}")
        return

    # Import MCP only after token acquisition for cleaner failure output
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    headers = {"Authorization": f"Bearer {token}"}
    print("Connecting to MCP server with bearer token...")
    try:
        async with streamablehttp_client(MCP_OAUTH_SERVER_URL, headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("Session initialized.")

                tools = await session.list_tools()
                names = [t.name for t in tools.tools]
                print(f"Available tools: {names}")

                if not tools.tools:
                    return

                tool = tools.tools[0]
                args = _build_safe_args(getattr(tool, "inputSchema", {}) or {})
                if args is None:
                    print(f"Skipping call: '{tool.name}' requires args.")
                    return

                print(f"Calling tool: {tool.name} args={args}")
                result = await session.call_tool(tool.name, args)
                print(f"Tool call success: {type(result).__name__}")
    except Exception as exc:
        print(f"MCP auth/call failed: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
