#!/usr/bin/env python3
"""
LangGraph Agent with agentsec Security + MCP Tools + Multi-Provider Support
============================================================================

A complete example demonstrating:
- agentsec protecting LLM calls (inspected by AI Defense)
- Multi-provider support (Bedrock, Azure, Vertex AI, OpenAI)
- MCP tool integration (fetch_url from remote MCP server)
- Interactive conversation mode

Usage:
    python agent.py                    # Interactive mode
    python agent.py "Your question"    # Single question mode
    
    # Use different providers:
    CONFIG_FILE=config-azure.yaml python agent.py
    CONFIG_FILE=config-vertex.yaml python agent.py
"""

import asyncio
import logging
import os
import sys
import time
import warnings
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Configurable timeout from environment
MCP_TIMEOUT = int(os.getenv("MCP_TIMEOUT", "60"))

# Load shared .env file (before agentsec.protect())
from dotenv import load_dotenv
shared_env = Path(__file__).parent.parent.parent / ".env"
if shared_env.exists():
    load_dotenv(shared_env)

# =============================================================================
# MINIMAL agentsec integration: Just 2 lines!
# =============================================================================
from aidefense.runtime import agentsec
config_path = str(Path(__file__).parent.parent.parent / "agentsec.yaml")
# Allow integration test script to override YAML integration mode via env vars
_protect_kwargs = {}
if os.getenv("AGENTSEC_LLM_INTEGRATION_MODE"):
    _protect_kwargs["llm_integration_mode"] = os.getenv("AGENTSEC_LLM_INTEGRATION_MODE")
if os.getenv("AGENTSEC_MCP_INTEGRATION_MODE"):
    _protect_kwargs["mcp_integration_mode"] = os.getenv("AGENTSEC_MCP_INTEGRATION_MODE")
agentsec.protect(config=config_path, **_protect_kwargs)

# That's it! Now import your frameworks normally
#
# Alternative: Configure inline (for quick testing):
#   agentsec.protect(api_mode={"llm": {"mode": "monitor"}})
from aidefense.runtime.agentsec.exceptions import SecurityPolicyError

print(f"[agentsec] Patched: {agentsec.get_patched_clients()}")

# =============================================================================
# Import shared provider infrastructure
# =============================================================================
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from _shared import load_config, create_provider, validate_url, URLValidationError

# =============================================================================
# Import agent libraries (AFTER agentsec.protect())
# =============================================================================
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession
from langchain_core.tools import tool

# Suppress LangGraph deprecation warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from langgraph.prebuilt import create_react_agent

# =============================================================================
# MCP Session (global for tool access)
# =============================================================================

_mcp_session = None

# =============================================================================
# Tool Definitions
# =============================================================================

@tool
async def fetch_url(url: str) -> str:
    """
    Fetch the contents of a URL.
    
    Args:
        url: The URL to fetch (e.g., 'https://example.com')
    
    Returns:
        The text content of the URL
    """
    logger.info(f"fetch_url called: url={url}")
    
    # Validate URL to prevent SSRF attacks
    try:
        validate_url(url)
    except URLValidationError as e:
        logger.warning(f"URL validation failed: {e}")
        return f"Error: Invalid URL - {e}"
    
    global _mcp_session
    if _mcp_session is None:
        logger.warning("MCP not connected")
        return "Error: MCP not connected"
    
    try:
        start = time.time()
        result = await _mcp_session.call_tool('fetch', {'url': url})
        content = next((c.text for c in (result.content or []) if hasattr(c, "text")), "No content")
        elapsed = time.time() - start
        logger.info(f"Got response ({len(content)} chars) in {elapsed:.1f}s")
        return content
    except Exception as e:
        logger.exception(f"Tool error: {type(e).__name__}: {e}")
        return f"Error: {e}"


# =============================================================================
# Main Application
# =============================================================================

async def run_agent(initial_message: str = None):
    """Run the LangGraph Agent with MCP tools."""
    global _mcp_session
    
    logger.debug("run_agent started")
    
    # Load configuration and create provider
    try:
        config = load_config()
        provider = create_provider(config)
        print(f"[provider] Using: {config.get('provider', 'unknown')} / {provider.model_id}")
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        print("Create a config.yaml or set CONFIG_FILE environment variable")
        return
    except Exception as e:
        print(f"[ERROR] Failed to initialize provider: {e}")
        import traceback
        traceback.print_exc()
        return
    
    mcp_url = os.getenv("MCP_SERVER_URL")
    model_id = provider.model_id
    
    logger.debug(f"MCP URL: {mcp_url}")
    logger.debug(f"Model ID: {model_id}")
    
    # -------------------------------------------------------------------------
    # Connect to MCP if URL configured
    # -------------------------------------------------------------------------
    mcp_context = None
    session_context = None
    
    if mcp_url:
        logger.info(f"Connecting to MCP server: {mcp_url}")
        try:
            mcp_context = streamablehttp_client(mcp_url, timeout=MCP_TIMEOUT)
            logger.debug("MCP context created")
            read, write, _ = await mcp_context.__aenter__()
            logger.debug("MCP context entered")
            session_context = ClientSession(read, write)
            _mcp_session = await session_context.__aenter__()
            logger.debug("MCP session created")
            await _mcp_session.initialize()
            logger.debug("MCP session initialized")
            tools_list = await _mcp_session.list_tools()
            logger.info(f"MCP connected. Tools: {[t.name for t in tools_list.tools]}")
        except Exception as e:
            logger.warning(f"MCP connection failed: {e}")
            _mcp_session = None
    
    # -------------------------------------------------------------------------
    # Create LLM instance from provider
    # -------------------------------------------------------------------------
    logger.info(f"Creating LLM with model: {model_id}")
    
    llm = provider.get_langchain_llm()
    logger.debug("LLM created")
    
    # -------------------------------------------------------------------------
    # Create ReAct agent with tools
    # -------------------------------------------------------------------------
    # Use fetch_url tool (MCP_SERVER_URL points to fetch server)
    # Register tools if MCP URL is configured (tool calls create fresh connections)
    tools = [fetch_url] if mcp_url else []
    logger.debug(f"MCP URL: {mcp_url}, Tools: {[t.name if hasattr(t, 'name') else str(t) for t in tools]}")
    
    # Create the ReAct agent graph (suppress deprecation warning)
    logger.debug("Creating ReAct agent")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        agent = create_react_agent(
            model=llm,
            tools=tools,
        )
    logger.debug("ReAct agent created")
    
    print("\n" + "=" * 60, flush=True)
    print("  LangGraph Agent + agentsec + MCP", flush=True)
    print("=" * 60, flush=True)
    
    # System prompt for fetch tool
    system_prompt = """You are a helpful assistant with access to the fetch_url tool.

CRITICAL INSTRUCTIONS:
1. When asked to fetch a URL, ALWAYS use the fetch_url tool
2. After fetching, summarize the content for the user

Tool usage: fetch_url(url='https://example.com')
"""

    # -------------------------------------------------------------------------
    # Handle single message mode
    # -------------------------------------------------------------------------
    if initial_message:
        print(f"\nYou: {initial_message}", flush=True)
        try:
            logger.debug("Calling agent.ainvoke()")
            start = time.time()
            result = await agent.ainvoke(
                {"messages": [("system", system_prompt), ("user", initial_message)]}
            )
            elapsed = time.time() - start
            logger.debug(f"agent.ainvoke() returned in {elapsed:.1f}s")
            # Extract the final response
            response = result["messages"][-1].content
            print(f"\nAgent: {response}", flush=True)
        except SecurityPolicyError as e:
            print(f"\n[BLOCKED] {e.decision.action}: {e.decision.reasons}", flush=True)
        except Exception as e:
            print(f"\n[ERROR] {type(e).__name__}: {e}", flush=True)
            import traceback
            traceback.print_exc()
        
        # Cleanup and return
        await cleanup_mcp(session_context, mcp_context)
        return
    
    # -------------------------------------------------------------------------
    # Interactive mode
    # -------------------------------------------------------------------------
    print("\nType your message (or 'quit' to exit)", flush=True)
    print("Try: 'Fetch https://example.com and tell me what it's for'\n", flush=True)
    
    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                print("Goodbye!", flush=True)
                break
            
            print("\nAgent: ", end="", flush=True)
            try:
                logger.debug("Calling agent.ainvoke()")
                result = await agent.ainvoke(
                    {"messages": [("system", system_prompt), ("user", user_input)]}
                )
                # Extract the final response
                response = result["messages"][-1].content
                print(response, flush=True)
            except SecurityPolicyError as e:
                print(f"\n[BLOCKED] {e.decision.action}: {e.decision.reasons}", flush=True)
            print(flush=True)
            
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!", flush=True)
            break
    
    # Cleanup
    await cleanup_mcp(session_context, mcp_context)


async def cleanup_mcp(session_context, mcp_context):
    """Clean up MCP connections gracefully."""
    try:
        if session_context:
            await session_context.__aexit__(None, None, None)
    except Exception as e:
        # Log cleanup errors at debug level (expected during shutdown)
        logger.debug(f"MCP session cleanup: {type(e).__name__}")
    try:
        if mcp_context:
            await mcp_context.__aexit__(None, None, None)
    except Exception as e:
        logger.debug(f"MCP context cleanup: {type(e).__name__}")


def main():
    """Entry point."""
    logger.debug("main() started")
    import warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    
    # Suppress asyncio shutdown errors from MCP library
    def exception_handler(loop, context):
        if "exception" in context:
            exc = context["exception"]
            if isinstance(exc, (RuntimeError, asyncio.CancelledError)):
                return  # Suppress MCP cleanup errors
        loop.default_exception_handler(context)
    
    # Get initial message from command line if provided
    initial_message = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    logger.debug(f"Initial message: {initial_message}")
    
    loop = asyncio.new_event_loop()
    loop.set_exception_handler(exception_handler)
    try:
        logger.debug("Starting event loop")
        loop.run_until_complete(run_agent(initial_message))
    finally:
        # Suppress shutdown errors
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception as e:
            logger.debug(f"Error during async generator shutdown: {e}")
        loop.close()


if __name__ == "__main__":
    main()
