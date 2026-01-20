#!/usr/bin/env python3
"""
AutoGen Agent with agentsec Security + MCP Tools + Multi-Provider Support
==========================================================================

A combined example demonstrating:
- agentsec protecting LLM calls (inspected by AI Defense)
- Multi-provider support (Bedrock, Azure, Vertex AI, OpenAI) using AG2 native integrations
- MCP tool integration (fetch_url from remote MCP server)
- Multi-agent conversation (UserProxyAgent + AssistantAgent)

Usage:
    python agent.py                    # Interactive mode
    python agent.py "Your question"    # Single question mode
    
    # Use different providers:
    CONFIG_FILE=config-azure.yaml python agent.py
    CONFIG_FILE=config-bedrock.yaml python agent.py
"""

import asyncio
import os
import sys
import time
import threading
from pathlib import Path

# Load shared .env file (before agentsec.protect())
from dotenv import load_dotenv
shared_env = Path(__file__).parent.parent.parent / ".env"
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
from aidefense.runtime.agentsec.exceptions import SecurityPolicyError

print(f"[agentsec] LLM: {os.getenv('AGENTSEC_API_MODE_LLM', 'monitor')} | Integration: {os.getenv('AGENTSEC_LLM_INTEGRATION_MODE', 'api')} | Patched: {agentsec.get_patched_clients()}")

# =============================================================================
# Import shared provider infrastructure
# =============================================================================
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from _shared import load_config, create_provider

# =============================================================================
# Import agent libraries (AFTER agentsec.protect())
# =============================================================================
try:
    from autogen import ConversableAgent, AssistantAgent, UserProxyAgent, LLMConfig
except ImportError as e:
    print(f"[ERROR] AutoGen not installed properly: {e}")
    print("Install with: pip install ag2[openai,bedrock,vertexai]")
    sys.exit(1)

from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

# =============================================================================
# MCP Tool Definition
# =============================================================================

_mcp_url = None


def _sync_call_mcp_tool(tool_name: str, arguments: dict) -> str:
    """Synchronously call an MCP tool by creating a fresh MCP connection in a thread."""
    result_container = {"result": None, "error": None}
    
    def run_in_thread():
        async def _async_call():
            async with streamablehttp_client(_mcp_url, timeout=120) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    return result.content[0].text if result.content else "No answer"
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result_container["result"] = loop.run_until_complete(_async_call())
        except Exception as e:
            result_container["error"] = e
        finally:
            loop.close()
    
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


# =============================================================================
# AutoGen Agent Setup (Classic API with native provider support)
# =============================================================================

# Global provider instance
_provider = None


def create_llm_config_from_provider():
    """Create LLMConfig using the configured provider.
    
    AG2 supports native integrations for all providers:
    - OpenAI: api_type not needed (default)
    - Azure: api_type='azure'
    - Bedrock: api_type='bedrock' (requires ag2[bedrock])
    - Vertex AI: api_type='vertex_ai' (requires ag2[vertexai], uses ADC)
    """
    global _provider
    
    if _provider is None:
        raise ValueError("Provider not initialized. Call setup first.")
    
    # Get AutoGen config from provider
    config = _provider.get_autogen_config()
    api_type = config.get('api_type')
    model = config.get('model', 'gpt-4o-mini')
    
    print(f"[DEBUG] Creating LLMConfig: api_type={api_type}, model={model}", flush=True)
    
    # Build config_list entry
    config_entry = {'model': model}
    
    if api_type == 'azure':
        # Azure OpenAI
        config_entry.update({
            'api_type': 'azure',
            'api_key': config.get('api_key', ''),
            'base_url': config.get('base_url', ''),
            'api_version': config.get('api_version', '2024-02-01'),
        })
        print(f"[DEBUG] Azure config: base_url={config.get('base_url')}", flush=True)
        
    elif api_type == 'bedrock':
        # AWS Bedrock (native AG2 support)
        config_entry.update({
            'api_type': 'bedrock',
            'aws_region': config.get('aws_region', 'us-east-1'),
        })
        # Add credentials if provided
        if config.get('aws_access_key'):
            config_entry['aws_access_key'] = config['aws_access_key']
        if config.get('aws_secret_key'):
            config_entry['aws_secret_key'] = config['aws_secret_key']
        if config.get('aws_session_token'):
            config_entry['aws_session_token'] = config['aws_session_token']
        if config.get('aws_profile_name'):
            config_entry['aws_profile_name'] = config['aws_profile_name']
        print(f"[DEBUG] Bedrock config: region={config.get('aws_region')}", flush=True)
        
    elif api_type == 'vertex_ai':
        # Google Vertex AI (native AG2 support via ADC)
        config_entry.update({
            'api_type': 'google',  # AG2 uses 'google' api_type for Vertex AI
            'vertex_ai': True,     # Enable Vertex AI mode
            'project_id': config.get('project', ''),
            'location': config.get('location', 'us-central1'),
        })
        print(f"[DEBUG] Vertex AI config: project={config.get('project')}, location={config.get('location')}", flush=True)
        
    else:
        # Default: OpenAI
        config_entry['api_key'] = config.get('api_key', '')
        print(f"[DEBUG] OpenAI config: model={model}", flush=True)
    
    return LLMConfig(config_list=[config_entry])


def create_agents(llm_config):
    """Create the UserProxy and Assistant agents."""
    print("[DEBUG] Creating agents...", flush=True)
    
    # Assistant agent - the AI that answers questions
    assistant = AssistantAgent(
        name="assistant",
        llm_config=llm_config,
        system_message="""You are a helpful assistant with access to the fetch_url tool.

CRITICAL INSTRUCTIONS:
1. When the user asks to fetch a URL, you MUST use the fetch_tool function.
2. After fetching, summarize the content for the user.

Tool: fetch_tool(url='https://example.com')

When you have answered the question, end your response with TERMINATE.""",
    )
    print("[DEBUG] Assistant agent created", flush=True)
    
    # User proxy agent - represents the human user
    user_proxy = UserProxyAgent(
        name="user_proxy",
        human_input_mode="NEVER",  # Don't ask for human input
        max_consecutive_auto_reply=3,
        is_termination_msg=lambda x: (x.get("content") or "").rstrip().endswith("TERMINATE"),
        code_execution_config=False,  # Disable code execution
    )
    print("[DEBUG] User proxy agent created", flush=True)
    
    # Register the fetch_url tool (MCP_SERVER_URL points to fetch server)
    if _mcp_url:
        @user_proxy.register_for_execution()
        @assistant.register_for_llm(description="Fetch the contents of a URL. Use this when the user asks to fetch a webpage.")
        def fetch_tool(url: str) -> str:
            """Fetch the contents of a URL."""
            return fetch_url(url)
        print("[DEBUG] fetch_url tool registered", flush=True)
    
    return assistant, user_proxy


# =============================================================================
# Main Application
# =============================================================================

async def setup_mcp():
    """Set up MCP connection if configured."""
    global _mcp_url
    
    mcp_url = os.getenv("MCP_SERVER_URL")
    _mcp_url = mcp_url
    
    if not mcp_url:
        print("[DEBUG] MCP_SERVER_URL not set, MCP tools disabled", flush=True)
        return
    
    print(f"[mcp] MCP URL configured: {mcp_url}", flush=True)


async def run_conversation(initial_message: str = None):
    """Run the AutoGen agent conversation."""
    global _provider
    
    print("[DEBUG] run_conversation started", flush=True)
    
    # Load configuration and create provider
    try:
        config = load_config()
        _provider = create_provider(config)
        print(f"[provider] Using: {config.get('provider', 'unknown')} / {_provider.model_id}")
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        print("Create a config.yaml or set CONFIG_FILE environment variable")
        return
    except Exception as e:
        print(f"[ERROR] Failed to initialize provider: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Set up MCP connection first
    await setup_mcp()
    
    # Get model from provider
    model = _provider.model_id
    print(f"[agent] Using model: {model}", flush=True)
    
    # Create LLM config and agents
    llm_config = create_llm_config_from_provider()
    assistant, user_proxy = create_agents(llm_config)
    
    print("\n" + "=" * 60, flush=True)
    print("  AutoGen Agents + agentsec + MCP", flush=True)
    print("=" * 60, flush=True)
    
    # Single message mode
    if initial_message:
        print(f"\nYou: {initial_message}", flush=True)
        try:
            print("[DEBUG] Starting conversation...", flush=True)
            start = time.time()
            
            # Initiate chat
            chat_result = user_proxy.initiate_chat(
                assistant,
                message=initial_message,
                max_turns=5,
            )
            
            elapsed = time.time() - start
            print(f"[DEBUG] Conversation completed in {elapsed:.1f}s", flush=True)
            
            # Get the final response
            if chat_result and hasattr(chat_result, 'chat_history') and chat_result.chat_history:
                for msg in reversed(chat_result.chat_history):
                    content = msg.get('content', '')
                    if content and msg.get('role') == 'assistant':
                        print(f"\n{'='*60}", flush=True)
                        print("Final Answer:", flush=True)
                        print("="*60, flush=True)
                        print(content.replace("TERMINATE", "").strip(), flush=True)
                        break
            
        except SecurityPolicyError as e:
            print(f"\n[BLOCKED] {e.decision.action}: {e.decision.reasons}", flush=True)
        except Exception as e:
            print(f"\n[ERROR] {type(e).__name__}: {e}", flush=True)
            import traceback
            traceback.print_exc()
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
            
            try:
                print("[DEBUG] Starting conversation...", flush=True)
                
                chat_result = user_proxy.initiate_chat(
                    assistant,
                    message=user_input,
                    max_turns=5,
                )
                
                if chat_result and hasattr(chat_result, 'chat_history') and chat_result.chat_history:
                    for msg in reversed(chat_result.chat_history):
                        content = msg.get('content', '')
                        if content and msg.get('role') == 'assistant':
                            print(f"\nAssistant: {content.replace('TERMINATE', '').strip()}\n", flush=True)
                            break
                    
            except SecurityPolicyError as e:
                print(f"\n[BLOCKED] {e.decision.action}: {e.decision.reasons}\n", flush=True)
            
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!", flush=True)
            break


def main():
    """Entry point."""
    print("[DEBUG] main() started", flush=True)
    import warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    
    # Suppress asyncio shutdown errors
    def exception_handler(loop, context):
        if "exception" in context:
            exc = context["exception"]
            if isinstance(exc, (RuntimeError, asyncio.CancelledError)):
                return
        loop.default_exception_handler(context)
    
    # Get initial message from command line if provided
    initial_message = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    print(f"[DEBUG] Initial message: {initial_message}", flush=True)
    
    loop = asyncio.new_event_loop()
    loop.set_exception_handler(exception_handler)
    try:
        print("[DEBUG] Starting event loop...", flush=True)
        loop.run_until_complete(run_conversation(initial_message))
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
        loop.close()


if __name__ == "__main__":
    main()
