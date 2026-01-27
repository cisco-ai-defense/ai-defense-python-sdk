"""
Agent Factory for GCP Vertex AI with agentsec (Cisco AI Defense) protection.

This module provides a LangChain-based agent that can reason about when to use
tools, similar to how Amazon Bedrock AgentCore uses Strands Agent.

agentsec.protect() is called BEFORE importing the AI library to ensure
all calls are properly intercepted and inspected by Cisco AI Defense.

ARCHITECTURE:
    User Prompt → LangChain Agent → ChatVertexAI (LLM)
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

SUPPORTED LIBRARIES:
- `vertexai` (google-cloud-aiplatform) - via langchain-google-vertexai
- `google-genai` (google-genai) - Modern unified SDK (set GOOGLE_AI_SDK=google_genai)

Set GOOGLE_AI_SDK=google_genai to use the modern SDK, otherwise defaults to vertexai.
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# =============================================================================
# Load environment variables from shared .env file
# =============================================================================
from dotenv import load_dotenv

# Try to load from examples/.env (shared env file)
_shared_env = Path(__file__).parent.parent.parent.parent / ".env"
if _shared_env.exists():
    load_dotenv(_shared_env)

# Determine which SDK to use
GOOGLE_AI_SDK = os.getenv("GOOGLE_AI_SDK", "vertexai")  # "vertexai" or "google_genai"

# =============================================================================
# Configure agentsec protection (BEFORE importing any AI library)
# =============================================================================
from aidefense.runtime import agentsec

# Build provider config based on which SDK we're using
providers_config = {
    "vertexai": {
        "gateway_url": os.getenv("AGENTSEC_VERTEXAI_GATEWAY_URL"),
        "gateway_api_key": os.getenv("AGENTSEC_VERTEXAI_GATEWAY_API_KEY"),
    },
    "google_genai": {
        "gateway_url": os.getenv("AGENTSEC_GOOGLE_GENAI_GATEWAY_URL") or os.getenv("AGENTSEC_VERTEXAI_GATEWAY_URL"),
        "gateway_api_key": os.getenv("AGENTSEC_GOOGLE_GENAI_GATEWAY_API_KEY") or os.getenv("AGENTSEC_VERTEXAI_GATEWAY_API_KEY"),
    },
}

agentsec.protect(
    # AI Defense integration mode: "api" or "gateway"
    llm_integration_mode=os.getenv("AGENTSEC_LLM_INTEGRATION_MODE", "api"),
    mcp_integration_mode=os.getenv("AGENTSEC_MCP_INTEGRATION_MODE", "api"),
    
    # API mode configuration (LLM)
    api_mode_llm=os.getenv("AGENTSEC_API_MODE_LLM", "on_monitor"),
    api_mode_llm_endpoint=os.getenv("AI_DEFENSE_API_MODE_LLM_ENDPOINT"),
    api_mode_llm_api_key=os.getenv("AI_DEFENSE_API_MODE_LLM_API_KEY"),
    api_mode_fail_open_llm=True,
    
    # API mode configuration (MCP)
    api_mode_mcp=os.getenv("AGENTSEC_API_MODE_MCP", "on_monitor"),
    api_mode_mcp_endpoint=os.getenv("AI_DEFENSE_API_MODE_MCP_ENDPOINT"),
    api_mode_mcp_api_key=os.getenv("AI_DEFENSE_API_MODE_MCP_API_KEY"),
    api_mode_fail_open_mcp=True,
    
    # Gateway mode configuration (LLM)
    providers=providers_config,
    
    # Gateway mode configuration (MCP)
    gateway_mode_mcp_url=os.getenv("AGENTSEC_MCP_GATEWAY_URL"),
    gateway_mode_mcp_api_key=os.getenv("AGENTSEC_MCP_GATEWAY_API_KEY"),
    gateway_mode_fail_open_mcp=True,
    
    # Disable auto .env loading since we did it manually
    auto_dotenv=False,
)

print(f"[agentsec] SDK: {GOOGLE_AI_SDK} | LLM: {os.getenv('AGENTSEC_API_MODE_LLM', 'on_monitor')} | "
      f"MCP: {os.getenv('AGENTSEC_API_MODE_MCP', 'on_monitor')} | "
      f"Integration: LLM={os.getenv('AGENTSEC_LLM_INTEGRATION_MODE', 'api')}, MCP={os.getenv('AGENTSEC_MCP_INTEGRATION_MODE', 'api')} | "
      f"Patched: {agentsec.get_patched_clients()}")

# =============================================================================
# Import LangChain libraries (AFTER agentsec.protect())
# =============================================================================
from langchain_google_vertexai import ChatVertexAI
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
    which is important for Lambda-like cold start optimization.
    
    Returns:
        Tuple of (llm_with_tools, tools_dict)
    """
    global _llm_with_tools, _tools_dict
    
    if _llm_with_tools is None:
        # Get project and location from environment
        project = os.environ["GOOGLE_CLOUD_PROJECT"]
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        model_name = os.getenv("VERTEX_AI_MODEL", "gemini-2.0-flash-001")
        
        print(f"[agent] Creating LangChain agent with model: {model_name}", flush=True)
        print(f"[agent] Project: {project}, Location: {location}", flush=True)
        
        # Create the LLM
        llm = ChatVertexAI(
            model=model_name,
            project=project,
            location=location,
            temperature=0.7,
            max_output_tokens=1024,
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
        import nest_asyncio
        nest_asyncio.apply()
        _nest_asyncio_applied = True
    
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
