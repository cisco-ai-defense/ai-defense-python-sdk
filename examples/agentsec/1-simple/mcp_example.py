#!/usr/bin/env python3
"""
MCP (Model Context Protocol) with agentsec protection.

This example demonstrates how agentsec inspects MCP tool calls.
Both the request (tool arguments) and response (tool result) are
inspected by Cisco AI Defense.

Usage:
    pip install mcp
    python mcp_example.py

Environment variables are loaded from ../.env:
    AI_DEFENSE_API_MODE_MCP_API_KEY: Your Cisco AI Defense MCP API key
    AI_DEFENSE_API_MODE_MCP_ENDPOINT: MCP API endpoint URL
"""

import asyncio
import os
from pathlib import Path

# Load environment variables from shared .env file
from dotenv import load_dotenv
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"Loaded environment from {env_file}")

# Enable protection before importing MCP client
from aidefense.runtime import agentsec
agentsec.protect(api_mode_mcp="on_monitor")  # Use monitor mode for this example


async def main() -> None:
    """Demonstrate MCP tool call inspection with agentsec."""
    
    print("MCP Example with agentsec Protection")
    print("=" * 50)
    print()
    
    patched = agentsec.get_patched_clients()
    print(f"Patched clients: {patched}")
    print()
    
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    
    mcp_url = os.environ.get("MCP_SERVER_URL", "https://mcp.deepwiki.com/mcp")
    print(f"Connecting to MCP server: {mcp_url}")
    print()
    
    async with streamablehttp_client(mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # List available tools
            tools = await session.list_tools()
            tool_names = [t.name for t in tools.tools]
            print(f"Available tools: {tool_names}")
            print()
            
            # Make a tool call - this will be inspected by agentsec!
            print("Making tool call (will be inspected by Cisco AI Defense)...")
            print("  Tool: ask_question")
            print("  Args: repo=python/cpython, question='What is Python?'")
            print()
            
            result = await session.call_tool(
                "ask_question",
                {
                    "repoName": "python/cpython",
                    "question": "What is Python?"
                }
            )
            
            # Extract response text
            response_text = ""
            if result.content:
                for content in result.content:
                    if hasattr(content, "text"):
                        response_text = content.text
                        break
            
            print("Response (first 300 chars):")
            print(f"  {response_text[:300]}...")
            print()
            print("Tool call complete! Both request and response were inspected by Cisco AI Defense.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Error: {e}")
        print()
        print("This may happen if the MCP server is temporarily unavailable.")
        print("The example demonstrates the MCP inspection pattern regardless.")
