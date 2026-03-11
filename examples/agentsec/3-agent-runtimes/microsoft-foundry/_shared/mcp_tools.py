"""MCP-backed tools for the Azure AI Foundry Agent using LangChain @tool decorator.

These tools connect to an external MCP server and are automatically protected
by agentsec's MCP patcher for request/response inspection.

The agentsec MCP patcher intercepts `mcp.client.session.ClientSession.call_tool()`
to inspect tool calls via AI Defense before and after execution.

Usage:
    Set MCP_SERVER_URL environment variable to enable MCP tools:
    MCP_SERVER_URL=https://remote.mcpservers.org/fetch/mcp
    
    Optional: Set MCP_TIMEOUT to configure timeout (default: 60 seconds)
    MCP_TIMEOUT=60
    
Example:
    from _shared.mcp_tools import fetch_url, get_mcp_tools
    
    # Check if MCP is configured
    mcp_tools = get_mcp_tools()
    if mcp_tools:
        result = fetch_url.invoke({"url": "https://example.com"})
"""

import asyncio
import logging
import os
import time

from langchain_core.tools import tool

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
    
    This function handles event loop management carefully to work in various
    contexts (Azure Functions, Azure ML, etc.) where there may or may not
    be an existing event loop.
    
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
    
    # Handle event loop management carefully for different execution contexts
    # Azure Functions and Azure ML may have existing event loops
    try:
        # Check if there's already a running loop (e.g., in async context)
        loop = asyncio.get_running_loop()
        # We're in an async context - use nest_asyncio to allow nested loops
        try:
            import nest_asyncio
            nest_asyncio.apply()
        except ImportError:
            pass
        # Create a new loop in a thread to avoid blocking the running loop
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, _async_call())
            return future.result(timeout=mcp_timeout + 60)
    except RuntimeError:
        # No running loop - we can use asyncio.run() directly
        return asyncio.run(_async_call())


@tool
def fetch_url(url: str) -> str:
    """Fetch the contents of a URL using an external MCP server.
    
    Use this tool when you need to fetch webpage content, read a website,
    or get information from a URL. This tool connects to an MCP server
    that can retrieve webpage contents.
    
    The MCP call is protected by AI Defense for both request and response.
    
    Args:
        url: The URL to fetch (e.g., 'https://example.com', 'https://news.ycombinator.com')
    
    Returns:
        The text content of the URL
    """
    mcp_url, mcp_timeout = _get_mcp_config()
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
        logger.error(f"MCP call timed out after {mcp_timeout}s")
        return f"Error: MCP call timed out after {mcp_timeout} seconds"
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
        List of MCP tool functions (LangChain @tool decorated) if configured,
        empty list otherwise
    """
    mcp_url, mcp_timeout = _get_mcp_config()
    
    if mcp_url:
        logger.info(f"MCP enabled: server={mcp_url}, timeout={mcp_timeout}s")
        return [fetch_url]
    else:
        logger.info("MCP disabled (MCP_SERVER_URL not set)")
        return []
