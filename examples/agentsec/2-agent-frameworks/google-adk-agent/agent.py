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
Google ADK agent with Cisco AI Defense (agentsec) protection.

This example demonstrates how to use agentsec with the Google Agent Development
Kit (ADK). ADK uses the google-genai SDK internally for Gemini model calls and
the mcp SDK for MCP tool interactions — both are automatically patched by
agentsec.protect().

agentsec intercepts:
  - LLM calls: AsyncModels.generate_content / generate_content_stream
  - MCP calls: ClientSession.call_tool / get_prompt / read_resource

Usage:
    python agent.py

Gemini authentication (one of the two):
  Option A — Gemini Developer API:
    GOOGLE_API_KEY:             Gemini API key

  Option B — Vertex AI (current .env setup):
    GOOGLE_CLOUD_PROJECT:       GCP project ID  (e.g. gcp-aiteamgcp-nprd-22046)
    GOOGLE_CLOUD_LOCATION:      GCP region       (e.g. us-central1)
    + Application Default Credentials (run: gcloud auth application-default login)

Environment variables (loaded from ../../.env):
    AGENTSEC_API_MODE_LLM:     LLM inspection mode  (monitor | enforce | off)
    AGENTSEC_API_MODE_MCP:     MCP inspection mode   (monitor | enforce | off)
    AI_DEFENSE_API_MODE_LLM_API_KEY: Cisco AI Defense API key
    AI_DEFENSE_API_MODE_LLM_ENDPOINT: AI Defense API endpoint
    MCP_SERVER_URL:             Remote MCP server URL (StreamableHTTP)
"""

import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

env_file = Path(__file__).resolve().parent.parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"Loaded environment from {env_file}", flush=True)

# Auto-enable Vertex AI mode for google-genai SDK when GCP project is configured
if os.environ.get("GOOGLE_CLOUD_PROJECT") and not os.environ.get("GOOGLE_API_KEY"):
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "1")

# ── Enable protection BEFORE importing ADK or any LLM / MCP clients ──
from aidefense.runtime import agentsec
from aidefense.runtime.agentsec.exceptions import SecurityPolicyError

llm_mode = os.environ.get("AGENTSEC_API_MODE_LLM", "monitor")
mcp_mode = os.environ.get("AGENTSEC_API_MODE_MCP", "monitor")
agentsec.protect(
    api_mode={
        "llm": {"mode": llm_mode},
        "mcp": {"mode": mcp_mode},
    },
)

# ── Now import ADK (google-genai and mcp are already patched) ──
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.genai import types

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

APP_NAME = "adk_agentsec_demo"


def _build_mcp_toolset() -> McpToolset | None:
    """Build an MCP toolset from MCP_SERVER_URL if configured."""
    mcp_url = os.environ.get("MCP_SERVER_URL")
    if not mcp_url:
        logger.debug("MCP_SERVER_URL not set — running without MCP tools")
        return None

    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(url=mcp_url),
    )


async def main() -> None:
    """Run a single-turn ADK agent with agentsec protection."""
    patched = agentsec.get_patched_clients()
    print(f"Patched clients: {patched}", flush=True)

    if os.environ.get("GOOGLE_API_KEY"):
        print("Gemini backend: Developer API (GOOGLE_API_KEY)", flush=True)
    elif os.environ.get("GOOGLE_CLOUD_PROJECT"):
        print(
            f"Gemini backend: Vertex AI "
            f"(project={os.environ['GOOGLE_CLOUD_PROJECT']}, "
            f"location={os.environ.get('GOOGLE_CLOUD_LOCATION', 'us-central1')})",
            flush=True,
        )
    else:
        print(
            "WARNING: Neither GOOGLE_API_KEY nor GOOGLE_CLOUD_PROJECT is set. "
            "ADK will fail to initialize the Gemini client.",
            flush=True,
        )

    tools: list = []
    mcp_toolset = _build_mcp_toolset()
    if mcp_toolset is not None:
        tools.append(mcp_toolset)

    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    logger.info(f"Using model: {model}")

    agent = LlmAgent(
        model=model,
        name="secure_assistant",
        instruction=(
            "You are a helpful assistant protected by Cisco AI Defense. "
            "Answer questions concisely. If you have access to tools, use them "
            "when the user's request would benefit from external data."
        ),
        tools=tools,
    )

    session_service = InMemorySessionService()
    runner = Runner(
        app_name=APP_NAME,
        agent=agent,
        session_service=session_service,
    )

    session = await session_service.create_session(
        state={}, app_name=APP_NAME, user_id="demo_user"
    )

    query = "Summarize the benefits of zero-trust security in two sentences."
    print(f"\nUser: {query}", flush=True)

    content = types.Content(role="user", parts=[types.Part(text=query)])

    try:
        events = runner.run_async(
            session_id=session.id,
            user_id=session.user_id,
            new_message=content,
        )
        async for event in events:
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        print(f"Assistant: {part.text}", flush=True)
    except SecurityPolicyError as exc:
        logger.warning(f"Blocked by AI Defense policy: {exc}")
        print(f"\n⛔ Request blocked by Cisco AI Defense: {exc}", flush=True)

    if mcp_toolset is not None:
        await mcp_toolset.close()

    print("\nDone — all calls were inspected by Cisco AI Defense.", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
