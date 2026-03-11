"""
Agent Factory for Microsoft Azure AI Foundry with agentsec (Cisco AI Defense) protection.

This module provides a LangChain-based agent that can reason about when to use
tools, similar to how Amazon Bedrock AgentCore uses Strands Agent.

agentsec.protect() is called BEFORE importing the AI library to ensure
all calls are properly intercepted and inspected by Cisco AI Defense.

ARCHITECTURE:
    User Prompt → LangChain Agent → AzureChatOpenAI (LLM)
                         ↓
                   Tool Calling
                         ↓
             ┌──────────┴───────────┐
             │     Local Tools      │    MCP Tools
             │  - check_service_    │    - fetch_url() 
             │    health()          │      ↓
             │  - get_recent_logs() │    MCP Server
             │  - calculate_        │    (agentsec protected)
             │    capacity()        │
             └──────────┬───────────┘
                        ↓
                   Final Response

INTEGRATION MODES:
- API Mode: Requests are inspected via Cisco AI Defense API (pre/post call)
- Gateway Mode: Requests are routed through Cisco AI Defense Gateway

Both modes provide LLM request/response protection and MCP request/response protection.
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# =============================================================================
# Load environment variables from shared .env file
# =============================================================================
from dotenv import load_dotenv

# Try to load from examples/agentsec/.env (shared env file)
# Path: _shared/ -> microsoft-foundry/ -> 3-agent-runtimes/ -> agentsec/
_shared_env = Path(__file__).parent.parent.parent.parent / ".env"
if _shared_env.exists():
    load_dotenv(_shared_env)

# =============================================================================
# Configure agentsec via agentsec.yaml (BEFORE importing any AI library)
# =============================================================================
from aidefense.runtime import agentsec

# Resolve agentsec.yaml path (container vs local development)
_yaml_paths = [
    Path("/app/agentsec.yaml"),  # Container deployment
    Path(__file__).parent.parent.parent.parent / "agentsec.yaml",  # examples/agentsec/agentsec.yaml
]

_yaml_config = None
for _yp in _yaml_paths:
    if _yp.exists():
        _yaml_config = str(_yp)
        break

# All gateway/API mode settings (URLs, keys, modes, fail-open, retry, etc.)
# are defined in agentsec.yaml. Secrets are referenced via ${VAR_NAME} and
# resolved from the environment (populated by load_dotenv above).
# Allow integration test scripts to override YAML integration mode via env vars
_protect_kwargs = {}
if os.getenv("AGENTSEC_LLM_INTEGRATION_MODE"):
    _protect_kwargs["llm_integration_mode"] = os.getenv("AGENTSEC_LLM_INTEGRATION_MODE")
if os.getenv("AGENTSEC_MCP_INTEGRATION_MODE"):
    _protect_kwargs["mcp_integration_mode"] = os.getenv("AGENTSEC_MCP_INTEGRATION_MODE")

agentsec.protect(
    config=_yaml_config,
    auto_dotenv=False,  # We already loaded .env manually
    **_protect_kwargs,
)

print(f"[agentsec] Patched: {agentsec.get_patched_clients()}")

# =============================================================================
# Import LangChain libraries (AFTER agentsec.protect())
# =============================================================================
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage

# Import our tools
from .tools import TOOLS
from .mcp_tools import get_mcp_tools

# =============================================================================
# Agent Configuration
# =============================================================================

# System prompt for the SRE agent
SYSTEM_PROMPT = """You are an SRE (Site Reliability Engineering) helper agent.

You have access to the following capabilities:
- Check service health status (check_service_health)
- Get recent log entries (get_recent_logs)
- Calculate capacity planning metrics (calculate_capacity)
- Fetch webpage content from URLs (fetch_url) - Use this when asked to fetch or read a URL

When asked to check a service, USE the check_service_health tool.
When asked to view logs, USE the get_recent_logs tool.
When asked about capacity or scaling, USE the calculate_capacity tool.
When asked to fetch a URL or read webpage content, ALWAYS use the fetch_url tool.

Be helpful, concise, and technically accurate.
After using a tool, summarize the results clearly for the user."""

# Global agent state (singleton pattern for cold start optimization)
_llm_with_tools = None
_tools_dict = None
_nest_asyncio_applied = False


def _get_agent():
    """Get or create the LangChain agent with tools.
    
    Uses a singleton pattern to reuse the agent across invocations,
    which is important for Azure Functions cold start optimization.
    
    Returns:
        Tuple of (llm_with_tools, tools_dict)
    """
    global _llm_with_tools, _tools_dict
    
    if _llm_with_tools is None:
        # Get Azure OpenAI configuration from environment
        azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        api_key = os.environ.get("AZURE_OPENAI_API_KEY")
        
        if not azure_endpoint or not api_key:
            raise ValueError(
                "Azure OpenAI credentials not configured. "
                "Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY environment variables."
            )
        
        # Model/deployment configuration
        # Azure OpenAI uses deployment names instead of model names
        # The deployment name should match your Azure OpenAI resource deployment
        deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
        
        print(f"[agent] Creating LangChain agent with Azure OpenAI", flush=True)
        print(f"[agent] Endpoint: {azure_endpoint}", flush=True)
        print(f"[agent] Deployment: {deployment_name}, API Version: {api_version}", flush=True)
        
        # Create the Azure OpenAI LLM
        llm = AzureChatOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=api_key,
            api_version=api_version,
            azure_deployment=deployment_name,
            temperature=0.7,
            max_tokens=1024,
        )
        
        # Combine local tools + MCP tools (if configured)
        local_tools = TOOLS  # [check_service_health, get_recent_logs, calculate_capacity]
        mcp_tools = get_mcp_tools()  # Returns [fetch_url] if MCP_SERVER_URL is set
        all_tools = local_tools + mcp_tools
        
        # Build tools dictionary for execution
        _tools_dict = {t.name: t for t in all_tools}
        
        # Bind tools to LLM (modern LangChain 1.0+ approach)
        if all_tools:
            _llm_with_tools = llm.bind_tools(all_tools)
            print(f"[agent] Tools bound: {list(_tools_dict.keys())}", flush=True)
        else:
            _llm_with_tools = llm
            print("[agent] No tools available", flush=True)
    
    return _llm_with_tools, _tools_dict


def _run_agent_loop(
    llm_with_tools,
    tools_dict: Dict[str, Any],
    messages: List,
    max_iterations: int = 10
) -> str:
    """
    Run the agentic loop with tool calling.
    
    This is the modern LangChain pattern that handles:
    1. Invoking the LLM
    2. Checking for tool calls
    3. Executing tools
    4. Adding results to messages
    5. Looping until final answer
    
    Args:
        llm_with_tools: LLM with tools bound
        tools_dict: Dictionary mapping tool names to tool functions
        messages: List of messages (conversation history)
        max_iterations: Maximum number of agent iterations
        
    Returns:
        Final response text from the agent
    """
    for iteration in range(max_iterations):
        print(f"[agent] Iteration {iteration + 1}/{max_iterations}", flush=True)
        
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
            
            print(f"[agent] Tool call: {tool_name}({tool_args})", flush=True)
            
            # Execute the tool
            if tool_name in tools_dict:
                try:
                    result = tools_dict[tool_name].invoke(tool_args)
                except Exception as e:
                    result = f"Error executing tool: {e}"
                    print(f"[agent] Tool error: {e}", flush=True)
            else:
                result = f"Unknown tool: {tool_name}"
            
            # Add tool result to messages
            messages.append(ToolMessage(content=str(result), tool_call_id=tool_id))
    
    # Max iterations reached
    return "I've reached the maximum number of iterations. Here's what I found so far: " + (
        messages[-1].content if messages else "Unable to complete the request."
    )


def invoke_agent(prompt: str, model: str = None) -> str:
    """
    Invoke the SRE agent with a prompt.
    
    The agent will:
    1. Receive the prompt
    2. Decide which tools to use (if any)
    3. Execute tools as needed
    4. Return a final response
    
    Both LLM calls and MCP tool calls are protected by agentsec (Cisco AI Defense).
    
    Args:
        prompt: The user's prompt/question
        model: Optional model name (not used, kept for API compatibility)
        
    Returns:
        The agent's response text
    """
    global _nest_asyncio_applied
    
    # Enable nested event loops (required for sync tool calling async MCP)
    # Applied on first invocation to avoid side effects when module is imported
    if not _nest_asyncio_applied:
        try:
            import nest_asyncio
            nest_asyncio.apply()
            _nest_asyncio_applied = True
        except ImportError:
            pass  # nest_asyncio not installed, may have issues with MCP tools
    
    # Get the agent (creates if needed)
    llm_with_tools, tools_dict = _get_agent()
    
    # Build messages with system prompt
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]
    
    # Run the agent loop
    print(f"[agent] Processing: {prompt[:100]}{'...' if len(prompt) > 100 else ''}", flush=True)
    result = _run_agent_loop(llm_with_tools, tools_dict or {}, messages)
    
    print(f"[agent] Response: {result[:200]}{'...' if len(result) > 200 else ''}", flush=True)
    return result


def get_client():
    """Get the initialized LangChain LLM (for compatibility)."""
    llm_with_tools, _ = _get_agent()
    return llm_with_tools
