#!/usr/bin/env python3
"""
Strands Agent with agentsec Security + MCP Tools + Multi-Provider Support
==========================================================================

A combined example demonstrating:
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
from strands import Agent
from strands.tools import tool

# =============================================================================
# MCP Tool Definition
# =============================================================================

_mcp_session = None

# Store MCP connection info for sync access from tool threads
_mcp_url = None


def _sync_call_mcp_tool(tool_name: str, arguments: dict) -> str:
    """Synchronously call an MCP tool by creating a fresh MCP connection."""
    async def _async_call():
        async with streamablehttp_client(_mcp_url, timeout=MCP_TIMEOUT) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                return next((c.text for c in (result.content or []) if hasattr(c, "text")), "No answer")
    
    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_async_call())
    finally:
        loop.close()


@tool
def fetch_url(url: str) -> str:
    """
    Fetch the contents of a URL.
    
    Args:
        url: The URL to fetch (e.g., 'https://example.com')
    
    Returns:
        The text content of the URL
    """
    global _mcp_url
    logger.info(f"fetch_url called: url={url}")
    
    # Validate URL to prevent SSRF attacks
    try:
        validate_url(url)
    except URLValidationError as e:
        logger.warning(f"URL validation failed: {e}")
        return f"Error: Invalid URL - {e}"
    
    if _mcp_url is None:
        logger.warning("MCP URL not set")
        return "Error: MCP not configured"
    
    try:
        logger.info(f"Calling fetch tool for '{url}'")
        start = time.time()
        
        # Create fresh MCP connection in this thread's event loop
        response_text = _sync_call_mcp_tool('fetch', {'url': url})
        
        elapsed = time.time() - start
        logger.info(f"Got response ({len(response_text)} chars) in {elapsed:.1f}s")
        return response_text
    except Exception as e:
        logger.exception(f"Tool error: {type(e).__name__}: {e}")
        return f"Error: {e}"


# =============================================================================
# Main Application
# =============================================================================

async def run_agent(initial_message: str = None):
    """Run the Strands Agent with MCP tools."""
    global _mcp_session, _mcp_url
    
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
    
    # Get model - use native Strands model for each provider
    strands_model = provider.get_strands_model()
    
    if strands_model is not None:
        # Use native Strands model (OpenAI, Azure, Gemini)
        model = strands_model
        model_id = provider.model_id
    else:
        # Use model ID string (Bedrock - Strands creates BedrockModel internally)
        model = provider.get_strands_model_id()
        model_id = model
    
    mcp_url = os.getenv("MCP_SERVER_URL")
    
    # Store MCP URL for sync tool access from other threads
    _mcp_url = mcp_url
    
    logger.debug(f"MCP URL: {mcp_url}")
    logger.debug(f"Model ID: {model_id}")
    
    # Connect to MCP if URL configured
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
    
    # Create agent
    logger.info(f"Creating agent with model: {model_id}")
    
    # Use fetch_url tool (MCP_SERVER_URL points to fetch server)
    # Always register tools if MCP URL is configured (tool calls create their own connections)
    tools = [fetch_url] if mcp_url else []
    logger.debug(f"MCP URL: {mcp_url}, Tools: {[t.__name__ if hasattr(t, '__name__') else str(t) for t in tools]}")
    
    # System prompt for fetch tool
    system_prompt = """You are a helpful assistant with access to the fetch_url tool.

CRITICAL INSTRUCTIONS:
1. When a user asks you to fetch a URL or asks about a webpage, you MUST use the fetch_url tool.
2. ALWAYS use the tool to get actual content rather than guessing what a page contains.
3. After fetching, summarize what you found for the user.

Tool usage: fetch_url(url='https://example.com')
"""
    
    logger.debug("Creating Agent instance")
    agent = Agent(
        model=model,
        system_prompt=system_prompt,
        tools=tools,
    )
    logger.debug("Agent instance created")
    
    print("\n" + "=" * 60, flush=True)
    print("  Strands Agent + agentsec + MCP", flush=True)
    print(f"  Provider: {config.get('provider', 'unknown')} | Model: {model_id}", flush=True)
    print("=" * 60, flush=True)
    
    # Single message mode
    if initial_message:
        print(f"\nYou: {initial_message}", flush=True)
        try:
            logger.debug("Calling agent()")
            start = time.time()
            response = agent(initial_message)
            elapsed = time.time() - start
            logger.debug(f"agent() returned in {elapsed:.1f}s")
            print(f"\nAgent: {response}", flush=True)
        except SecurityPolicyError as e:
            print(f"\n[BLOCKED] {e.decision.action}: {e.decision.reasons}", flush=True)
        except Exception as e:
            print(f"\n[ERROR] {type(e).__name__}: {e}", flush=True)
            import traceback
            traceback.print_exc()
        # Cleanup MCP before returning
        try:
            if session_context:
                await session_context.__aexit__(None, None, None)
        except Exception as e:
            logger.debug(f"MCP session cleanup: {type(e).__name__}")
        try:
            if mcp_context:
                await mcp_context.__aexit__(None, None, None)
        except Exception as e:
            logger.debug(f"MCP context cleanup: {type(e).__name__}")
        return
    
    # Interactive mode
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
                logger.debug("Calling agent()")
                response = agent(user_input)
                print(response, flush=True)
            except SecurityPolicyError as e:
                print(f"\n[BLOCKED] {e.decision.action}: {e.decision.reasons}", flush=True)
            print(flush=True)
            
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!", flush=True)
            break
    
    # Cleanup (log async errors at debug level)
    try:
        if session_context:
            await session_context.__aexit__(None, None, None)
    except Exception as e:
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
