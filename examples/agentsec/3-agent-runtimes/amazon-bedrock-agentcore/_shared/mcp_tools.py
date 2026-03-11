"""MCP-backed tools for the SRE agent.

These tools connect to an external MCP server (e.g., DeepWiki) and are
automatically protected by agentsec's MCP patcher for request/response inspection.

The agentsec MCP patcher intercepts `mcp.client.session.ClientSession.call_tool()`
to inspect tool calls via AI Defense before and after execution.

Usage:
    Set MCP_SERVER_URL environment variable to enable MCP tools:
    MCP_SERVER_URL=https://mcp.deepwiki.com/mcp
    
    Optional: Set MCP_TIMEOUT to configure timeout (default: 60 seconds)
    MCP_TIMEOUT=60
"""

import asyncio
import logging
import os
import time
from strands import tool

# Configure logging
logger = logging.getLogger(__name__)

# MCP configuration - refreshed on get_mcp_tools() call
_mcp_url = None
_mcp_timeout = 60  # Default timeout in seconds


def _get_mcp_config():
    """Get current MCP configuration from environment."""
    global _mcp_url, _mcp_timeout
    _mcp_url = os.getenv("MCP_SERVER_URL")
    _mcp_timeout = int(os.getenv("MCP_TIMEOUT", "60"))
    return _mcp_url, _mcp_timeout


def _sync_call_mcp_tool(tool_name: str, arguments: dict) -> str:
    """Synchronously call an MCP tool by creating a fresh MCP connection.
    
    This function uses asyncio.run() for cleaner event loop management,
    which works well with Strands' synchronous tool execution model.
    
    The actual MCP call (session.call_tool) is intercepted by agentsec's
    MCP patcher for AI Defense inspection.
    
    Args:
        tool_name: Name of the MCP tool to call (e.g., 'fetch')
        arguments: Arguments to pass to the tool
        
    Returns:
        Text result from the MCP tool
    """
    mcp_url, mcp_timeout = _get_mcp_config()
    
    if not mcp_url:
        return "Error: MCP_SERVER_URL not configured"
    
    # Import MCP client here to ensure agentsec has patched it
    from mcp.client.streamable_http import streamablehttp_client
    from mcp import ClientSession
    
    async def _async_call():
        async with streamablehttp_client(mcp_url, timeout=mcp_timeout) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                # This call is INTERCEPTED by agentsec for AI Defense inspection!
                result = await session.call_tool(tool_name, arguments)
                return next((c.text for c in (result.content or []) if hasattr(c, "text")), "No answer")
    
    # Use asyncio.run() for cleaner event loop management
    try:
        return asyncio.run(_async_call())
    except RuntimeError as e:
        # Fall back to creating a new event loop if we're already in an async context
        if "cannot be called from a running event loop" in str(e):
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(_async_call())
            finally:
                loop.close()
        raise


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
    mcp_url, _ = _get_mcp_config()
    logger.info(f"fetch_url called: url={url}")
    
    if mcp_url is None:
        logger.warning("MCP_SERVER_URL not set")
        return "Error: MCP not configured. Set MCP_SERVER_URL environment variable."
    
    try:
        logger.info(f"Calling MCP server at {mcp_url}")
        start = time.time()
        
        # Call the MCP server's 'fetch' tool
        # This is where agentsec intercepts for AI Defense inspection
        response_text = _sync_call_mcp_tool('fetch', {'url': url})
        
        elapsed = time.time() - start
        logger.info(f"Got response ({len(response_text)} chars) in {elapsed:.1f}s")
        return response_text
    except asyncio.TimeoutError:
        logger.error(f"MCP call timed out after {_mcp_timeout}s")
        return f"Error: MCP call timed out after {_mcp_timeout} seconds"
    except ConnectionError as e:
        logger.error(f"MCP connection error: {e}")
        return f"Error: Could not connect to MCP server: {e}"
    except Exception as e:
        logger.exception(f"MCP tool error: {type(e).__name__}: {e}")
        return f"Error fetching URL: {e}"


def get_mcp_tools():
    """Get MCP tools if MCP_SERVER_URL is configured.
    
    This function refreshes the MCP configuration from environment variables.
    
    Returns:
        List of MCP tools if configured, empty list otherwise
    """
    mcp_url, mcp_timeout = _get_mcp_config()
    
    if mcp_url:
        logger.info(f"MCP enabled: server={mcp_url}, timeout={mcp_timeout}s")
        return [fetch_url]
    else:
        logger.info("MCP disabled (MCP_SERVER_URL not set)")
        return []
