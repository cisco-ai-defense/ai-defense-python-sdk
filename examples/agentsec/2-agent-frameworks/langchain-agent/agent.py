#!/usr/bin/env python3
"""
LangChain Agent with agentsec Security + MCP Tools + Multi-Provider Support
============================================================================

A complete example demonstrating:
- agentsec protecting LLM calls (inspected by AI Defense)
- Multi-provider support (Bedrock, Azure, Vertex AI, OpenAI)
- MCP tool integration (fetch_url from remote MCP server)
- Interactive conversation mode

This example uses the MODERN LangChain approach (LangChain 1.0+):
- LCEL (LangChain Expression Language) chains
- Native tool calling via `llm.bind_tools()`
- Simple agentic loop (no deprecated AgentExecutor)

This is different from the LangGraph example which uses state graphs for
more complex agent orchestration.

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
from typing import List, Dict, Any

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
# Import LangChain libraries (AFTER agentsec.protect())
# =============================================================================
# NOTE: We use the MODERN LangChain 1.0+ approach with LCEL and native tool calling.
# This replaces the deprecated AgentExecutor pattern.
# =============================================================================
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage

# =============================================================================
# MCP Session (global for tool access)
# =============================================================================

_mcp_session = None

# =============================================================================
# Tool Definitions
# =============================================================================

@tool
def fetch_url(url: str) -> str:
    """
    Fetch the contents of a URL.
    
    Args:
        url: The URL to fetch (e.g., 'https://example.com')
    
    Returns:
        The text content of the URL
    """
    logger.info(f"fetch_url called: url='{url}'")
    
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
    
    # Run async MCP call in sync context
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    async def _call_mcp():
        start = time.time()
        result = await _mcp_session.call_tool('fetch', {'url': url})
        content = next((c.text for c in (result.content or []) if hasattr(c, "text")), "No content")
        elapsed = time.time() - start
        logger.info(f"Got response ({len(content)} chars) in {elapsed:.1f}s")
        return content
    
    try:
        return loop.run_until_complete(_call_mcp())
    except Exception as e:
        logger.exception(f"Tool error: {type(e).__name__}: {e}")
        return f"Error: {e}"


# =============================================================================
# Modern LangChain Agent Loop (LCEL + Tool Calling)
# =============================================================================
# This is the modern LangChain 1.0+ approach:
# 1. Bind tools to LLM with llm.bind_tools()
# 2. Invoke LLM and check for tool calls
# 3. Execute tools and add results to messages
# 4. Loop until LLM provides final answer (no tool calls)
# =============================================================================

def run_agent_loop(llm_with_tools, tools_dict: Dict[str, Any], messages: List, max_iterations: int = 10) -> str:
    """
    Run the agentic loop with tool calling.
    
    This is the modern LangChain pattern that replaces AgentExecutor.
    """
    for iteration in range(max_iterations):
        logger.debug(f"Agent iteration {iteration + 1}/{max_iterations}")
        
        # Invoke LLM
        response = llm_with_tools.invoke(messages)
        messages.append(response)
        
        # Check if LLM wants to call tools
        if not response.tool_calls:
            # No tool calls - return the final response
            return response.content
        
        # Execute each tool call
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call["id"]
            
            logger.debug(f"Tool call: {tool_name}({tool_args})")
            
            # Execute the tool
            if tool_name in tools_dict:
                try:
                    result = tools_dict[tool_name].invoke(tool_args)
                except Exception as e:
                    result = f"Error executing tool: {e}"
            else:
                result = f"Unknown tool: {tool_name}"
            
            # Add tool result to messages
            messages.append(ToolMessage(content=str(result), tool_call_id=tool_id))
    
    # Max iterations reached
    return "I've reached the maximum number of iterations. Here's what I found so far: " + messages[-1].content if messages else "Unable to complete the request."


# =============================================================================
# Main Application
# =============================================================================

async def run_agent(initial_message: str = None):
    """Run the LangChain Agent with MCP tools."""
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
            read, write, _ = await mcp_context.__aenter__()
            session_context = ClientSession(read, write)
            _mcp_session = await session_context.__aenter__()
            await _mcp_session.initialize()
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
    # Setup Tools and Bind to LLM (Modern LangChain 1.0+ Pattern)
    # -------------------------------------------------------------------------
    # NOTE: This uses the modern LangChain approach with native tool calling.
    # Instead of the deprecated AgentExecutor, we use:
    # 1. llm.bind_tools() to enable tool calling
    # 2. A simple agentic loop that handles tool execution
    # -------------------------------------------------------------------------
    
    # Define tools (fetch_url if MCP connected, otherwise empty)
    # Register tools if MCP URL is configured (tool calls create fresh connections)
    tools = [fetch_url] if mcp_url else []
    tools_dict = {t.name: t for t in tools}
    
    logger.debug(f"Tools: {list(tools_dict.keys())}")
    
    # Bind tools to LLM (modern LangChain 1.0+ approach)
    if tools:
        llm_with_tools = llm.bind_tools(tools)
        logger.debug("Tools bound to LLM")
    else:
        llm_with_tools = llm
        logger.debug("No tools to bind (MCP not connected)")
    
    print("\n" + "=" * 60, flush=True)
    print("  LangChain Agent + agentsec + MCP", flush=True)
    print("  (Modern LCEL + Tool Calling Pattern)", flush=True)
    print("=" * 60, flush=True)
    
    # System message for the agent
    system_message = SystemMessage(content="""You are a helpful assistant with access to the fetch_url tool.

CRITICAL INSTRUCTIONS:
1. When the user asks to fetch a URL or asks about a webpage, ALWAYS use the fetch_url tool.
2. NEVER guess what a page contains - always use the tool to get actual content.
3. After fetching, summarize the results clearly for the user.

Tool usage: fetch_url(url='https://example.com')""")
    
    # -------------------------------------------------------------------------
    # Handle single message mode
    # -------------------------------------------------------------------------
    if initial_message:
        print(f"\nYou: {initial_message}", flush=True)
        try:
            start = time.time()
            messages = [system_message, HumanMessage(content=initial_message)]
            response = run_agent_loop(llm_with_tools, tools_dict, messages)
            elapsed = time.time() - start
            logger.debug(f"Agent completed in {elapsed:.1f}s")
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
    
    # Keep conversation history for multi-turn (with max limit to prevent memory growth)
    MAX_HISTORY_MESSAGES = 20  # Keep last N messages (plus system message)
    conversation_messages = [system_message]
    
    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                print("Goodbye!", flush=True)
                break
            
            try:
                # Add user message to conversation
                conversation_messages.append(HumanMessage(content=user_input))
                
                # Run agent loop
                response = run_agent_loop(llm_with_tools, tools_dict, conversation_messages.copy())
                
                # Add assistant response to conversation history
                conversation_messages.append(AIMessage(content=response))
                
                # Trim history if it exceeds max limit (keep system message + last N messages)
                if len(conversation_messages) > MAX_HISTORY_MESSAGES + 1:
                    conversation_messages = [system_message] + conversation_messages[-(MAX_HISTORY_MESSAGES):]
                
                print(f"\nAgent: {response}", flush=True)
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
    
    # Enable nested event loops (required for sync tool calling async MCP)
    # Applied in main() to avoid side effects when module is imported
    import nest_asyncio
    nest_asyncio.apply()
    
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
