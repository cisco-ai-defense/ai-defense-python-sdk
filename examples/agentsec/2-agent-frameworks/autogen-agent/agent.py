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
import logging
import os
import sys
import time
import threading
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
            async with streamablehttp_client(_mcp_url, timeout=MCP_TIMEOUT) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    return next((c.text for c in (result.content or []) if hasattr(c, "text")), "No answer")
        
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
    thread.join(timeout=MCP_TIMEOUT)
    
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
        
        response_text = _sync_call_mcp_tool('fetch', {'url': url})
        
        elapsed = time.time() - start
        logger.info(f"Got response ({len(response_text)} chars) in {elapsed:.1f}s")
        return response_text
    except Exception as e:
        logger.exception(f"Tool error: {type(e).__name__}: {e}")
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
    
    logger.debug(f"Creating LLMConfig: api_type={api_type}, model={model}")
    
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
        logger.debug(f"Azure config: base_url={config.get('base_url')}")
        
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
        logger.debug(f"Bedrock config: region={config.get('aws_region')}")
        
    elif api_type == 'vertex_ai':
        # Google Vertex AI (native AG2 support via ADC)
        config_entry.update({
            'api_type': 'google',  # AG2 uses 'google' api_type for Vertex AI
            'vertex_ai': True,     # Enable Vertex AI mode
            'project_id': config.get('project', ''),
            'location': config.get('location', 'us-central1'),
            # Disable response validation to handle newer FinishReason values
            # (e.g., reason 15 for tool calls) that the SDK doesn't recognize yet.
            'response_validation': False,
        })
        logger.debug(f"Vertex AI config: project={config.get('project')}, location={config.get('location')}")
        
    else:
        # Default: OpenAI
        config_entry['api_key'] = config.get('api_key', '')
        logger.debug(f"OpenAI config: model={model}")
    
    return LLMConfig(config_list=[config_entry])


def create_agents(llm_config):
    """Create the UserProxy and Assistant agents."""
    logger.debug("Creating agents")
    
    # Assistant agent - the AI that answers questions
    assistant = AssistantAgent(
        name="assistant",
        llm_config=llm_config,
        system_message="""You are a helpful research assistant.
You have a tool called fetch_url that can retrieve the contents of a web page.
When someone asks about a website, use fetch_url to get the actual content and then summarize it.
When done, end your reply with TASK_COMPLETE.""",
    )
    logger.debug("Assistant agent created")
    
    # User proxy agent - represents the human user
    user_proxy = UserProxyAgent(
        name="user_proxy",
        human_input_mode="NEVER",  # Don't ask for human input
        max_consecutive_auto_reply=3,
        is_termination_msg=lambda x: (x.get("content") or "").rstrip().endswith("TASK_COMPLETE"),
        code_execution_config=False,  # Disable code execution
    )
    logger.debug("User proxy agent created")
    
    # Register the fetch_url tool (MCP_SERVER_URL points to fetch server)
    if _mcp_url:
        @user_proxy.register_for_execution()
        @assistant.register_for_llm(name="fetch_url", description="Fetch the contents of a URL. Use this when the user asks to fetch a webpage.")
        def fetch_url_tool(url: str) -> str:
            """Fetch the contents of a URL."""
            return fetch_url(url)
        logger.debug("fetch_url tool registered")
    
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
        logger.debug("MCP_SERVER_URL not set, MCP tools disabled")
        return
    
    logger.info(f"MCP URL configured: {mcp_url}")


async def run_conversation(initial_message: str = None):
    """Run the AutoGen agent conversation."""
    global _provider
    
    logger.debug("run_conversation started")
    
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
    logger.info(f"Using model: {model}")
    
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
            logger.debug("Starting conversation")
            start = time.time()
            
            # Initiate chat
            chat_result = user_proxy.initiate_chat(
                assistant,
                message=initial_message,
                max_turns=5,
            )
            
            elapsed = time.time() - start
            logger.debug(f"Conversation completed in {elapsed:.1f}s")
            
            # Get the final response
            if chat_result and hasattr(chat_result, 'chat_history') and chat_result.chat_history:
                for msg in reversed(chat_result.chat_history):
                    content = msg.get('content', '')
                    if content and msg.get('role') == 'assistant':
                        print(f"\n{'='*60}", flush=True)
                        print("Final Answer:", flush=True)
                        print("="*60, flush=True)
                        print(content.replace("TASK_COMPLETE", "").strip(), flush=True)
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
                logger.debug("Starting conversation")
                
                chat_result = user_proxy.initiate_chat(
                    assistant,
                    message=user_input,
                    max_turns=5,
                )
                
                if chat_result and hasattr(chat_result, 'chat_history') and chat_result.chat_history:
                    for msg in reversed(chat_result.chat_history):
                        content = msg.get('content', '')
                        if content and msg.get('role') == 'assistant':
                            print(f"\nAssistant: {content.replace('TASK_COMPLETE', '').strip()}\n", flush=True)
                            break
                    
            except SecurityPolicyError as e:
                print(f"\n[BLOCKED] {e.decision.action}: {e.decision.reasons}\n", flush=True)
            
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!", flush=True)
            break


def main():
    """Entry point."""
    logger.debug("main() started")
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
    logger.debug(f"Initial message: {initial_message}")
    
    loop = asyncio.new_event_loop()
    loop.set_exception_handler(exception_handler)
    try:
        logger.debug("Starting event loop")
        loop.run_until_complete(run_conversation(initial_message))
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception as e:
            logger.debug(f"Error during async generator shutdown: {e}")
        loop.close()


if __name__ == "__main__":
    main()
