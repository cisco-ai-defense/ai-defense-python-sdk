#!/usr/bin/env python3
"""
AgentSec MCP example for mock MCP auth servers:
- OAuth 2.0 client credentials
- API key auth

Default endpoints:
  - OAuth MCP endpoint:   https://mcp-testing.aiteam.cisco.com/mock_mcp/mcp/oauth
  - API-Key MCP endpoint: https://mcp-testing.aiteam.cisco.com/mock_mcp/mcp/api-key
  - OAuth token endpoint: https://mcp-testing.aiteam.cisco.com/mock_mcp/oauth/token
  - Health check:         https://mcp-testing.aiteam.cisco.com/mock_mcp/health

Environment variables (optional):
  MCP_AUTH_TYPE          # oauth2 (default) | api_key
  MCP_OAUTH_SERVER_URL
  MCP_API_KEY_SERVER_URL
  MCP_OAUTH_TOKEN_URL
  MCP_OAUTH_HEALTH_URL
  MCP_OAUTH_CLIENT_ID
  MCP_OAUTH_CLIENT_SECRET
  MCP_OAUTH_SCOPES
  MCP_API_KEY_HEADER_NAME
  MCP_API_KEY
  AGENTSEC_MCP_INTEGRATION_MODE  # api (default) or gateway

If AGENTSEC_MCP_INTEGRATION_MODE=gateway, set:
  - AGENTSEC_MCP_OAUTH_GATEWAY_URL   (for MCP_AUTH_TYPE=oauth2)
  - AGENTSEC_MCP_API_KEY_GATEWAY_URL (for MCP_AUTH_TYPE=api_key)
"""

import asyncio
import base64
import os
from pathlib import Path
from typing import Any, Dict

import httpx
from dotenv import load_dotenv

from aidefense.runtime import agentsec
from aidefense.runtime.agentsec.exceptions import InspectionNetworkError

# Load shared env if present (examples/agentsec/.env)
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"Loaded environment from {env_file}")

# Mock MCP server settings
MCP_AUTH_TYPE = os.getenv("MCP_AUTH_TYPE", "oauth2").strip().lower()
MCP_OAUTH_SERVER_URL = os.getenv(
    "MCP_OAUTH_SERVER_URL",
    "https://mcp-testing.aiteam.cisco.com/mock_mcp/mcp/oauth",
)
MCP_API_KEY_SERVER_URL = os.getenv(
    "MCP_API_KEY_SERVER_URL",
    "https://mcp-testing.aiteam.cisco.com/mock_mcp/mcp/api-key",
)
MCP_TOKEN_URL = os.getenv(
    "MCP_OAUTH_TOKEN_URL",
    "https://mcp-testing.aiteam.cisco.com/mock_mcp/oauth/token",
)
MCP_HEALTH_URL = os.getenv(
    "MCP_OAUTH_HEALTH_URL",
    "https://mcp-testing.aiteam.cisco.com/mock_mcp/health",
)
MCP_CLIENT_ID = os.getenv("MCP_OAUTH_CLIENT_ID")
MCP_CLIENT_SECRET = os.getenv("MCP_OAUTH_CLIENT_SECRET")
MCP_SCOPES = os.getenv("MCP_OAUTH_SCOPES", "read write")
MCP_API_KEY_HEADER_NAME = os.getenv("MCP_API_KEY_HEADER_NAME", "X-API-Key")
MCP_API_KEY = os.getenv("MCP_API_KEY")

mcp_integration_mode = os.getenv("AGENTSEC_MCP_INTEGRATION_MODE", "api")
if MCP_AUTH_TYPE not in {"oauth2", "api_key"}:
    raise RuntimeError("MCP_AUTH_TYPE must be 'oauth2' or 'api_key'")

if mcp_integration_mode == "gateway":
    if MCP_AUTH_TYPE == "oauth2" and not os.getenv("AGENTSEC_MCP_OAUTH_GATEWAY_URL"):
        raise RuntimeError(
            "Missing AGENTSEC_MCP_OAUTH_GATEWAY_URL. Required for "
            "MCP_AUTH_TYPE=oauth2 when AGENTSEC_MCP_INTEGRATION_MODE=gateway."
        )
    if MCP_AUTH_TYPE == "api_key" and not os.getenv("AGENTSEC_MCP_API_KEY_GATEWAY_URL"):
        raise RuntimeError(
            "Missing AGENTSEC_MCP_API_KEY_GATEWAY_URL. Required for "
            "MCP_AUTH_TYPE=api_key when AGENTSEC_MCP_INTEGRATION_MODE=gateway."
        )

if MCP_AUTH_TYPE == "oauth2":
    if not MCP_CLIENT_ID or not MCP_CLIENT_SECRET:
        raise RuntimeError(
            "Set MCP_OAUTH_CLIENT_ID and MCP_OAUTH_CLIENT_SECRET for "
            "MCP_AUTH_TYPE=oauth2."
        )
    if not MCP_OAUTH_SERVER_URL or not MCP_TOKEN_URL:
        raise RuntimeError(
            "Set MCP_OAUTH_SERVER_URL and MCP_OAUTH_TOKEN_URL for "
            "MCP_AUTH_TYPE=oauth2."
        )
else:
    if not MCP_API_KEY:
        raise RuntimeError("Set MCP_API_KEY for MCP_AUTH_TYPE=api_key.")
    if not MCP_API_KEY_SERVER_URL:
        raise RuntimeError("Set MCP_API_KEY_SERVER_URL for MCP_AUTH_TYPE=api_key.")

# Enable protection before importing MCP client
config_path = str(Path(__file__).parent.parent / "agentsec.yaml")
agentsec.protect(
    config=config_path,
    mcp_integration_mode=mcp_integration_mode,
    llm_integration_mode="api",
)


def _build_safe_args(schema: Dict[str, Any]) -> Dict[str, Any] | None:
    """Return {} only when tool has no required args; otherwise skip call."""
    required = schema.get("required", []) if isinstance(schema, dict) else []
    if required:
        return None
    return {}


async def main() -> None:
    print("MCP Mock Server Auth Test")
    print("=" * 58)
    print(f"Auth type: {MCP_AUTH_TYPE}")
    print(f"Integration mode: {mcp_integration_mode}")

    # 1) Health check
    print(f"Health check: {MCP_HEALTH_URL}")
    try:
        resp = httpx.get(MCP_HEALTH_URL, timeout=10.0)
        print(f"Health status: {resp.status_code}")
    except Exception as exc:
        print(f"Health check failed: {exc}")

    # 2) Build auth headers based on selected auth type
    headers: Dict[str, str]
    mcp_server_url: str
    if MCP_AUTH_TYPE == "oauth2":
        print(f"Token URL: {MCP_TOKEN_URL}")
        try:
            token_resp = httpx.post(
                MCP_TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": MCP_CLIENT_ID,
                    "client_secret": MCP_CLIENT_SECRET,
                    "scope": MCP_SCOPES,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0,
            )
            if token_resp.status_code == 401:
                # Fallback for OAuth servers that require Basic auth.
                basic = base64.b64encode(
                    f"{MCP_CLIENT_ID}:{MCP_CLIENT_SECRET}".encode("utf-8")
                ).decode("ascii")
                token_resp = httpx.post(
                    MCP_TOKEN_URL,
                    data={"grant_type": "client_credentials", "scope": MCP_SCOPES},
                    headers={
                        "Authorization": f"Basic {basic}",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    timeout=30.0,
                )
            token_resp.raise_for_status()
            token_payload = token_resp.json()
            access_token = token_payload.get("access_token")
            if not access_token:
                raise RuntimeError(
                    f"OAuth token response missing access_token: keys={list(token_payload.keys())}"
                )
            print(f"Token acquired: {access_token[:20]}... (truncated)")
        except Exception as exc:
            print(f"Token fetch failed: {exc}")
            return

        headers = {"Authorization": f"Bearer {access_token}"}
        mcp_server_url = MCP_OAUTH_SERVER_URL
    else:
        # API-key flow matching curl:
        # curl -X POST https://mcp-testing.aiteam.cisco.com/mock_mcp/mcp/api-key \
        #   -H "X-API-Key: test_api_key_12345" ...
        headers = {MCP_API_KEY_HEADER_NAME: MCP_API_KEY}
        mcp_server_url = MCP_API_KEY_SERVER_URL
        print(f"Using {MCP_API_KEY_HEADER_NAME} auth header for MCP request.")

    # 3) MCP session through agentsec-patched transport with explicit auth headers
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    print(f"Connecting to MCP endpoint: {mcp_server_url}")
    try:
        async with streamablehttp_client(mcp_server_url, headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("Session initialized.")

                tools = await session.list_tools()
                tool_names = [t.name for t in tools.tools]
                print(f"Available tools: {tool_names}")

                if not tools.tools:
                    print("No tools exposed by server; auth + MCP handshake succeeded.")
                    return

                first_tool = tools.tools[0]
                args = _build_safe_args(getattr(first_tool, "inputSchema", {}) or {})
                if args is None:
                    print(
                        f"Skipping tool call: '{first_tool.name}' requires arguments. "
                        "List-tools succeeded, so auth + connection path is verified."
                    )
                    return

                print(f"Calling tool: {first_tool.name} with args={args}")
                result = await session.call_tool(first_tool.name, args)
                print(f"Tool call succeeded. Result type: {type(result).__name__}")
    except InspectionNetworkError as exc:
        print(f"OAuth token/network error: {exc}")
        print("Check DNS/network access to the OAuth token endpoint and MCP host.")
    except httpx.HTTPError as exc:
        print(f"HTTP error while connecting to MCP server: {exc}")
    except Exception as exc:
        print(f"MCP connection failed: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
