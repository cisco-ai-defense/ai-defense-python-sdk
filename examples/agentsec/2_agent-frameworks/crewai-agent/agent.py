#!/usr/bin/env python3
"""
CrewAI Agent with agentsec Security + MCP Tools + Multi-Provider Support
=========================================================================

A combined example demonstrating:
- agentsec protecting LLM calls via SecurityLLM wrapper
- Multi-provider support (Bedrock, Azure, Vertex AI, OpenAI)
- MCP tool integration (fetch_url from remote MCP server)
- Multi-agent crew collaboration (Researcher + Writer)

Usage:
    python agent.py                    # Interactive mode
    python agent.py "Your question"    # Single question mode
    
    # Use different providers:
    CONFIG_FILE=config-azure.yaml python agent.py
    CONFIG_FILE=config-vertex.yaml python agent.py
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
    from crewai import Agent, Task, Crew, Process
except ImportError as e:
    print(f"[ERROR] CrewAI not installed: {e}")
    print("Install with: pip install crewai")
    sys.exit(1)

from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

# =============================================================================
# MCP Tool Definition
# =============================================================================

_mcp_url = None


def _sync_call_mcp_tool(tool_name: str, arguments: dict, max_retries: int = 3) -> str:
    """Synchronously call an MCP tool by creating a fresh MCP connection in a thread.
    
    Includes retry logic for transient connection errors.
    """
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
    
    last_error = None
    for attempt in range(max_retries):
        result_container = {"result": None, "error": None}
        
        thread = threading.Thread(target=run_in_thread)
        thread.start()
        thread.join(timeout=120)
        
        if result_container["result"] is not None:
            return result_container["result"]
        
        if result_container["error"]:
            last_error = result_container["error"]
            error_name = type(last_error).__name__
            # Check if it's a retryable connection error
            is_retryable = any(err in str(type(last_error).__mro__) or err in error_name 
                              for err in ['ConnectError', 'TimeoutError', 'ConnectionError'])
            if not is_retryable and 'ExceptionGroup' not in error_name:
                # Non-retryable error, raise immediately
                raise last_error
            
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2  # 2s, 4s backoff
                print(f"[MCP] Connection error, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})...", flush=True)
                time.sleep(wait_time)
    
    if last_error:
        raise last_error
    return "No answer"


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
        error_name = type(e).__name__
        error_msg = str(e)
        # Only log brief info for connection errors (don't print full traceback)
        if 'ConnectError' in error_name or 'ExceptionGroup' in error_name or 'TimeoutError' in error_name:
            print(f"[TOOL] MCP connection failed after retries: {error_name}", flush=True)
        else:
            print(f"[TOOL] Unexpected error: {error_name}: {error_msg}", flush=True)
            import traceback
            traceback.print_exc()
        return f"Error fetching URL: {error_name}"


# =============================================================================
# CrewAI Agent and Crew Setup
# =============================================================================

# Global provider instance
_provider = None


def create_llm_from_provider():
    """Create the LLM instance for CrewAI using the configured provider."""
    global _provider
    
    if _provider is None:
        raise ValueError("Provider not initialized. Call setup first.")
    
    llm = _provider.get_crewai_llm()
    print(f"[DEBUG] Created LLM from provider: {_provider.model_id}", flush=True)
    return llm


def create_crew(model_id: str):
    """Create the Researcher + Writer crew."""
    print(f"[DEBUG] Creating crew with model: {model_id}", flush=True)
    
    # Create the LLM instance from provider
    llm = create_llm_from_provider()
    
    # Researcher agent - uses fetch_url to get information
    researcher = Agent(
        role="Technical Researcher",
        goal="Research URLs to find accurate technical information",
        backstory="""You are an expert technical researcher. When given research from a URL fetch,
        analyze the content and extract the most relevant information to answer the question.""",
        verbose=True,
        allow_delegation=False,
        tools=[],  # Tool will be used via task description
        llm=llm,
    )
    print("[DEBUG] Researcher agent created", flush=True)
    
    # Writer agent - summarizes research findings
    writer = Agent(
        role="Technical Writer",
        goal="Summarize technical research into clear, concise explanations",
        backstory="""You are a skilled technical writer who takes research 
        findings and transforms them into clear, well-structured explanations 
        that are easy to understand.""",
        verbose=True,
        allow_delegation=False,
        llm=llm,
    )
    print("[DEBUG] Writer agent created", flush=True)
    
    return researcher, writer


def create_tasks(researcher, writer, question: str):
    """Create tasks for the crew."""
    print(f"[DEBUG] Creating tasks for question: {question}", flush=True)
    
    # Research task
    research_task = Task(
        description=f"""Analyze the following question and any fetched URL content:
        
        Question: {question}
        
        Provide accurate technical information based on the fetched content.
        Focus on extracting specific details that answer the question.""",
        expected_output="Detailed technical information answering the question",
        agent=researcher,
    )
    
    # Writing task
    writing_task = Task(
        description="""Take the research findings and write a clear, concise summary.
        
        Your summary should:
        1. Answer the original question directly
        2. Include key technical details
        3. Be well-organized and easy to understand
        4. Be 2-3 paragraphs maximum""",
        expected_output="A clear, concise summary of the technical topic",
        agent=writer,
    )
    
    return [research_task, writing_task]


# =============================================================================
# Main Application
# =============================================================================

def do_mcp_research(question: str) -> str:
    """Call fetch_url tool to fetch content from URL in question."""
    import re
    # Extract URL from question or use example.com
    urls = re.findall(r'https?://[^\s]+', question)
    url = urls[0] if urls else "https://example.com"
    return fetch_url(url)


async def setup_mcp():
    """Set up MCP connection if configured."""
    global _mcp_url
    
    mcp_url = os.getenv("MCP_SERVER_URL")
    _mcp_url = mcp_url
    
    if not mcp_url:
        print("[DEBUG] MCP_SERVER_URL not set, MCP tools disabled", flush=True)
        return
    
    print(f"[mcp] MCP URL configured: {mcp_url}", flush=True)


async def run_crew(initial_message: str = None):
    """Run the CrewAI crew."""
    global _provider
    
    print("[DEBUG] run_crew started", flush=True)
    
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
    
    # Set up MCP connection
    await setup_mcp()
    
    # Get model ID from provider
    model_id = _provider.model_id
    print(f"[agent] Using model: {model_id}", flush=True)
    
    # Create agents
    researcher, writer = create_crew(model_id)
    
    print("\n" + "=" * 60, flush=True)
    print("  CrewAI Crew + agentsec + MCP", flush=True)
    print("=" * 60, flush=True)
    
    # Single message mode
    if initial_message:
        print(f"\nQuestion: {initial_message}", flush=True)
        try:
            # First, fetch URL content if MCP is configured
            if _mcp_url:
                print(f"\n[DEBUG] Fetching URL content via MCP...", flush=True)
                research = do_mcp_research(initial_message)
                print(f"[DEBUG] Content retrieved: {len(research)} chars", flush=True)
            else:
                research = "No MCP connection available."
            
            # Create tasks with the research context
            tasks = create_tasks(researcher, writer, initial_message)
            
            # Create and run crew
            print("[DEBUG] Creating crew...", flush=True)
            crew = Crew(
                agents=[researcher, writer],
                tasks=tasks,
                process=Process.sequential,
                verbose=True,
            )
            
            print("[DEBUG] Running crew...", flush=True)
            start = time.time()
            result = crew.kickoff()
            elapsed = time.time() - start
            print(f"[DEBUG] Crew completed in {elapsed:.1f}s", flush=True)
            
            print(f"\n{'='*60}", flush=True)
            print("Final Answer:", flush=True)
            print("="*60, flush=True)
            print(result, flush=True)
            
        except SecurityPolicyError as e:
            print(f"\n[BLOCKED] {e.decision.action}: {e.decision.reasons}", flush=True)
        except Exception as e:
            print(f"\n[ERROR] {type(e).__name__}: {e}", flush=True)
            import traceback
            traceback.print_exc()
        return
    
    # Interactive mode
    print("\nType your question (or 'quit' to exit)", flush=True)
    print("Try: 'Fetch https://example.com and tell me what it's for'\n", flush=True)
    
    while True:
        try:
            user_input = input("Question: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                print("Goodbye!", flush=True)
                break
            
            try:
                # Get research first
                if _mcp_url:
                    research = do_mcp_research(user_input)
                
                # Create and run crew
                tasks = create_tasks(researcher, writer, user_input)
                crew = Crew(
                    agents=[researcher, writer],
                    tasks=tasks,
                    process=Process.sequential,
                    verbose=True,
                )
                result = crew.kickoff()
                print(f"\nAnswer: {result}\n", flush=True)
                
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
        loop.run_until_complete(run_crew(initial_message))
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
        loop.close()


if __name__ == "__main__":
    main()

