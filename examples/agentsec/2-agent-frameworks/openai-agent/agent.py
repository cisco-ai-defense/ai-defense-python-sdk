#!/usr/bin/env python3
"""
OpenAI Agent with agentsec Security + MCP Tools
================================================

A combined example demonstrating:
- agentsec protecting LLM calls (inspected by AI Defense)
- OpenAI SDK for OpenAI and Azure OpenAI (native SDK - no LiteLLM)
- MCP tool integration (fetch_url from remote MCP server)
- Interactive conversation mode

Note: This example uses the OpenAI SDK directly, which only supports:
- OpenAI models
- Azure OpenAI models (via the same SDK with Azure configuration)

For other providers (Bedrock, Gemini), see strands-agent, crewai-agent, or autogen-agent.

Usage:
    python agent.py                    # Interactive mode
    python agent.py "Your question"    # Single question mode
    
    # Use different providers:
    CONFIG_FILE=config-openai.yaml python agent.py   # OpenAI (default)
    CONFIG_FILE=config-azure.yaml python agent.py    # Azure OpenAI
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Load shared .env file (before agentsec.protect())
from dotenv import load_dotenv
shared_env = Path(__file__).parent.parent / "_shared" / ".env"
if shared_env.exists():
    load_dotenv(shared_env)

# =============================================================================
# MINIMAL agentsec integration: Just 2 lines!
# =============================================================================
from aidefense.runtime import agentsec
agentsec.protect()  # Reads config from .env, patches clients

# That's it! Now import your frameworks normally
#
# Alternative: Configure Gateway mode programmatically (provider-specific):
#   agentsec.protect(
#       llm_integration_mode="gateway",
#       providers={"openai": {"gateway_url": "https://gateway.../conn", "gateway_api_key": "key"}},
#       auto_dotenv=False,
#   )
from agentsec.exceptions import SecurityPolicyError

print(f"[agentsec] LLM: {os.getenv('AGENTSEC_API_MODE_LLM', 'monitor')} | Integration: {os.getenv('AGENTSEC_LLM_INTEGRATION_MODE', 'api')} | Patched: {agentsec.get_patched_clients()}")

# =============================================================================
# Import shared provider infrastructure
# =============================================================================
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from _shared import load_config, create_provider

# =============================================================================
# Import agent libraries (AFTER agentsec.protect())
# =============================================================================
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

# =============================================================================
# MCP Tool Definition
# =============================================================================

_mcp_session = None
_mcp_url = None


def _sync_call_mcp_tool(tool_name: str, arguments: dict) -> str:
    """Synchronously call an MCP tool by creating a fresh MCP connection."""
    import threading
    
    result_container = {"result": None, "error": None}
    
    def run_in_thread():
        async def _async_call():
            async with streamablehttp_client(_mcp_url, timeout=120) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    return result.content[0].text if result.content else "No answer"
        
        # Create a new event loop in this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result_container["result"] = loop.run_until_complete(_async_call())
        except Exception as e:
            result_container["error"] = e
        finally:
            loop.close()
    
    # Run in a separate thread to avoid event loop conflicts
    thread = threading.Thread(target=run_in_thread)
    thread.start()
    thread.join(timeout=120)
    
    if result_container["error"]:
        raise result_container["error"]
    return result_container["result"] or "No answer"


def fetch_url(url: str) -> str:
    """
    Fetch the contents of a URL.
    
    Args:
        url: The URL to fetch (e.g., 'https://example.com')
    
    Returns:
        The text content of the URL
    """
    global _mcp_url
    print(f"[DEBUG] fetch_url called: url={url}", flush=True)
    if _mcp_url is None:
        print("[DEBUG] MCP URL not set!", flush=True)
        return "Error: MCP not configured"
    
    try:
        print(f"[TOOL CALL] fetch_url(url='{url}')", flush=True)
        start = time.time()
        
        response_text = _sync_call_mcp_tool('fetch', {'url': url})
        
        elapsed = time.time() - start
        print(f"[TOOL] Got response ({len(response_text)} chars) in {elapsed:.1f}s", flush=True)
        return response_text
    except Exception as e:
        print(f"[TOOL ERROR] {type(e).__name__}: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return f"Error: {e}"


# OpenAI function tool definitions
FETCH_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Fetch the contents of a URL. Use this when the user asks to fetch or get content from a webpage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to fetch (e.g., 'https://example.com')"
                    }
                },
                "required": ["url"]
            }
        }
    }
]


def get_tools():
    """Get fetch tools (MCP_SERVER_URL points to fetch server)."""
    if not _mcp_url:
        return None
    return FETCH_TOOLS


def get_system_prompt():
    """Get system prompt for fetch tool."""
    return """You are a helpful assistant with access to the fetch_url tool.

CRITICAL INSTRUCTIONS:
1. When the user asks to fetch content from a URL, ALWAYS use the fetch_url tool.
2. After fetching, summarize the content for the user.

Tool: fetch_url(url='https://example.com')"""


# =============================================================================
# Agent Implementation
# =============================================================================

class OpenAIAgent:
    """Simple OpenAI agent with function calling support."""
    
    def __init__(self, model: str = None, client=None):
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.client = client  # Accept pre-configured client from provider
        self.messages = [
            {"role": "system", "content": get_system_prompt()}
        ]
        print(f"[DEBUG] OpenAIAgent initialized with model: {self.model}", flush=True)
    
    def _process_tool_calls(self, tool_calls) -> list:
        """Process tool calls and return results."""
        results = []
        for tool_call in tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)
            print(f"[DEBUG] Processing tool call: {func_name}({func_args})", flush=True)
            
            if func_name == "fetch_url":
                result = fetch_url(**func_args)
            else:
                result = f"Unknown function: {func_name}"
            
            results.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "content": result
            })
        return results
    
    def chat(self, user_message: str) -> str:
        """Send a message and get a response, handling tool calls if needed."""
        print(f"[DEBUG] chat() called with: {user_message[:50]}...", flush=True)
        
        # Add user message
        self.messages.append({"role": "user", "content": user_message})
        
        # First call - may trigger tool use
        print("[DEBUG] Making LLM call...", flush=True)
        start = time.time()
        response = self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            tools=get_tools(),  # Only include tools if MCP is configured
            tool_choice="auto" if _mcp_url else None,
        )
        elapsed = time.time() - start
        print(f"[DEBUG] LLM call completed in {elapsed:.1f}s", flush=True)
        
        assistant_message = response.choices[0].message
        
        # Check if the model wants to use tools
        if assistant_message.tool_calls:
            print(f"[DEBUG] Model requested {len(assistant_message.tool_calls)} tool call(s)", flush=True)
            
            # Add assistant's message with tool calls
            self.messages.append({
                "role": "assistant",
                "content": assistant_message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in assistant_message.tool_calls
                ]
            })
            
            # Process tool calls and add results
            tool_results = self._process_tool_calls(assistant_message.tool_calls)
            self.messages.extend(tool_results)
            
            # Second call with tool results
            print("[DEBUG] Making follow-up LLM call with tool results...", flush=True)
            start = time.time()
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
            )
            elapsed = time.time() - start
            print(f"[DEBUG] Follow-up LLM call completed in {elapsed:.1f}s", flush=True)
            
            assistant_message = response.choices[0].message
        
        # Add final response to history
        self.messages.append({
            "role": "assistant",
            "content": assistant_message.content
        })
        
        return assistant_message.content
    
    def reset(self):
        """Reset conversation history."""
        self.messages = [
            {"role": "system", "content": get_system_prompt()}
        ]


# =============================================================================
# Main Application
# =============================================================================

async def setup_mcp():
    """Set up MCP connection if configured."""
    global _mcp_session, _mcp_url
    
    mcp_url = os.getenv("MCP_SERVER_URL")
    _mcp_url = mcp_url
    
    if not mcp_url:
        print("[DEBUG] MCP_SERVER_URL not set, MCP tools disabled", flush=True)
        return None, None
    
    print(f"[mcp] Connecting to {mcp_url}...", flush=True)
    try:
        mcp_context = streamablehttp_client(mcp_url, timeout=60)
        print("[DEBUG] MCP context created", flush=True)
        read, write, _ = await mcp_context.__aenter__()
        print("[DEBUG] MCP context entered", flush=True)
        session_context = ClientSession(read, write)
        _mcp_session = await session_context.__aenter__()
        print("[DEBUG] MCP session created", flush=True)
        await _mcp_session.initialize()
        print("[DEBUG] MCP session initialized", flush=True)
        tools_list = await _mcp_session.list_tools()
        print(f"[mcp] Connected! Tools: {[t.name for t in tools_list.tools]}", flush=True)
        return mcp_context, session_context
    except Exception as e:
        print(f"[mcp] Connection failed: {e}", flush=True)
        _mcp_session = None
        # Keep _mcp_url set so tools can still attempt fresh connections
        # (MCP server may be temporarily unavailable or become available later)
        return None, None


async def run_agent(initial_message: str = None):
    """Run the OpenAI Agent with MCP tools."""
    print("[DEBUG] run_agent started", flush=True)
    
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
    
    # Set up MCP connection
    mcp_context, session_context = await setup_mcp()
    
    # Create agent with provider's client
    model = provider.model_id
    client = provider.get_openai_client()
    print(f"[agent] Creating OpenAI Agent with model: {model}", flush=True)
    agent = OpenAIAgent(model=model, client=client)
    
    print("\n" + "=" * 60, flush=True)
    print("  OpenAI Agent + agentsec + MCP", flush=True)
    print("=" * 60, flush=True)
    
    # Single message mode
    if initial_message:
        print(f"\nYou: {initial_message}", flush=True)
        try:
            print("[DEBUG] Calling agent.chat()...", flush=True)
            start = time.time()
            response = agent.chat(initial_message)
            elapsed = time.time() - start
            print(f"[DEBUG] agent.chat() returned in {elapsed:.1f}s", flush=True)
            print(f"\nAgent: {response}", flush=True)
        except SecurityPolicyError as e:
            print(f"\n[BLOCKED] {e.decision.action}: {e.decision.reasons}", flush=True)
        except Exception as e:
            print(f"\n[ERROR] {type(e).__name__}: {e}", flush=True)
            import traceback
            traceback.print_exc()
        
        # Cleanup
        await cleanup_mcp(mcp_context, session_context)
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
            if user_input.lower() == "reset":
                agent.reset()
                print("[Conversation reset]", flush=True)
                continue
            
            try:
                print("[DEBUG] Calling agent.chat()...", flush=True)
                response = agent.chat(user_input)
                print(f"\nAgent: {response}\n", flush=True)
            except SecurityPolicyError as e:
                print(f"\n[BLOCKED] {e.decision.action}: {e.decision.reasons}\n", flush=True)
            
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!", flush=True)
            break
    
    # Cleanup
    await cleanup_mcp(mcp_context, session_context)


async def cleanup_mcp(mcp_context, session_context):
    """Clean up MCP connections."""
    try:
        if session_context:
            await session_context.__aexit__(None, None, None)
    except Exception as e:
        # Log cleanup errors at debug level (expected during shutdown)
        print(f"[DEBUG] MCP session cleanup: {type(e).__name__}", flush=True)
    try:
        if mcp_context:
            await mcp_context.__aexit__(None, None, None)
    except Exception as e:
        print(f"[DEBUG] MCP context cleanup: {type(e).__name__}", flush=True)


def main():
    """Entry point."""
    print("[DEBUG] main() started", flush=True)
    import warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    
    # Suppress asyncio shutdown errors
    def exception_handler(loop, context):
        if "exception" in context:
            exc = context["exception"]
            if isinstance(exc, (RuntimeError, asyncio.CancelledError)):
                return  # Suppress cleanup errors
        loop.default_exception_handler(context)
    
    # Get initial message from command line if provided
    initial_message = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    print(f"[DEBUG] Initial message: {initial_message}", flush=True)
    
    loop = asyncio.new_event_loop()
    loop.set_exception_handler(exception_handler)
    try:
        print("[DEBUG] Starting event loop...", flush=True)
        loop.run_until_complete(run_agent(initial_message))
    finally:
        # Suppress shutdown errors
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
        loop.close()


if __name__ == "__main__":
    main()

