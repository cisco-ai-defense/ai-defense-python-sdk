"""MCP-backed tools for the SRE agent.

These tools connect to an external MCP server (e.g., DeepWiki) and are
automatically protected by agentsec's MCP patcher for request/response inspection.

The agentsec MCP patcher intercepts `mcp.client.session.ClientSession.call_tool()`
to inspect tool calls via AI Defense before and after execution.

Usage:
    Set MCP_SERVER_URL environment variable to enable MCP tools:
    MCP_SERVER_URL=https://mcp.deepwiki.com/mcp
"""

import asyncio
import os
import time
from strands import tool

# Global MCP URL - set from environment
_mcp_url = os.getenv("MCP_SERVER_URL")


def _sync_call_mcp_tool(tool_name: str, arguments: dict) -> str:
    """Synchronously call an MCP tool by creating a fresh MCP connection.
    
    This function creates a new event loop and MCP connection for each call,
    which works well with Strands' synchronous tool execution model.
    
    The actual MCP call (session.call_tool) is intercepted by agentsec's
    MCP patcher for AI Defense inspection.
    
    Args:
        tool_name: Name of the MCP tool to call (e.g., 'fetch')
        arguments: Arguments to pass to the tool
        
    Returns:
        Text result from the MCP tool
    """
    global _mcp_url
    
    if not _mcp_url:
        return "Error: MCP_SERVER_URL not configured"
    
    # Import MCP client here to ensure agentsec has patched it
    from mcp.client.streamable_http import streamablehttp_client
    from mcp import ClientSession
    
    async def _async_call():
        async with streamablehttp_client(_mcp_url, timeout=120) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                # This call is INTERCEPTED by agentsec for AI Defense inspection!
                result = await session.call_tool(tool_name, arguments)
                return result.content[0].text if result.content else "No answer"
    
    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_async_call())
    finally:
        loop.close()


@tool
def fetch_url(url: str) -> str:
    """Fetch the contents of a URL using MCP.
    
    This tool connects to an external MCP server to fetch webpage content.
    The MCP call is protected by AI Defense for both request and response.
    
    Args:
        url: The URL to fetch (e.g., 'https://example.com')
    
    Returns:
        The text content of the URL
    """
    global _mcp_url
    print(f"[MCP TOOL] fetch_url called: url={url}", flush=True)
    
    if _mcp_url is None:
        print("[MCP TOOL] MCP_SERVER_URL not set!", flush=True)
        return "Error: MCP not configured. Set MCP_SERVER_URL environment variable."
    
    try:
        print(f"[MCP TOOL] Calling MCP server at {_mcp_url}...", flush=True)
        start = time.time()
        
        # Call the MCP server's 'fetch' tool
        # This is where agentsec intercepts for AI Defense inspection
        response_text = _sync_call_mcp_tool('fetch', {'url': url})
        
        elapsed = time.time() - start
        print(f"[MCP TOOL] Got response ({len(response_text)} chars) in {elapsed:.1f}s", flush=True)
        return response_text
    except Exception as e:
        print(f"[MCP TOOL ERROR] {type(e).__name__}: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return f"Error fetching URL: {e}"


def get_mcp_tools():
    """Get MCP tools if MCP_SERVER_URL is configured.
    
    Returns:
        List of MCP tools if configured, empty list otherwise
    """
    global _mcp_url
    _mcp_url = os.getenv("MCP_SERVER_URL")
    
    if _mcp_url:
        print(f"[MCP] Enabled with server: {_mcp_url}", flush=True)
        return [fetch_url]
    else:
        print("[MCP] Disabled (MCP_SERVER_URL not set)", flush=True)
        return []
