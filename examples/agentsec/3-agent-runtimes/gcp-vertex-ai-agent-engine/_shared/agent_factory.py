"""
Agent Factory for GCP Vertex AI with agentsec (Cisco AI Defense) protection.

This module provides a LangChain-based agent that can reason about when to use
tools, similar to how Amazon Bedrock AgentCore uses Strands Agent.

agentsec.protect() is called BEFORE importing the AI library to ensure
all calls are properly intercepted and inspected by Cisco AI Defense.

ARCHITECTURE:
    User Prompt → LangChain Agent → Gemini LLM
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

SUPPORTED LIBRARIES (controlled by the ``sdk`` field on the vertexai gateway
in agentsec.yaml, which resolves ``${GOOGLE_AI_SDK}`` from the environment):

- google_genai (default for local development):
  Uses ChatGoogleGenerativeAI (langchain-google-genai) with vertexai=True.
  Internally uses google.genai.Client, patched by agentsec's google_genai patcher.
  This is the forward path LangChain is steering toward.

- vertexai (recommended for Agent Engine deployment):
  Uses ChatVertexAI (langchain-google-vertexai) with vertexai.init().
  Internally uses vertexai.GenerativeModel, patched by agentsec's vertexai patcher.
  Avoids the ACCESS_TOKEN_SCOPE_INSUFFICIENT error in Agent Engine where the
  managed SA lacks the generative-language scope that google.genai requires.

Both paths are fully supported by agentsec for gateway and API mode inspection.
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

# =============================================================================
# Configure agentsec protection (LAZY - initialized on first use)
# =============================================================================
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

# Track if agentsec has been initialized
_agentsec_initialized = False

def _initialize_agentsec():
    """
    Initialize agentsec protection lazily via agentsec.yaml.
    This is called on first use to avoid import-time dependencies.
    
    IMPORTANT: This lazy initialization is KEY for Agent Engine deployment.
    It ensures agentsec.protect() is called AFTER requirements are installed
    in the container, not at module import time during build validation.
    
    DO NOT revert to module-level agentsec.protect() call - it will break
    Agent Engine deployments with "No module named 'wrapt'" errors.
    
    All gateway/API mode settings (URLs, keys, modes, fail-open, retry, etc.)
    are defined in agentsec.yaml. Secrets are referenced via ${VAR_NAME} and
    resolved from the environment (populated by load_dotenv above).
    """
    global _agentsec_initialized
    if _agentsec_initialized:
        return
    
    # Import here to defer dependency loading
    from aidefense.runtime import agentsec
    
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
    
    _agentsec_initialized = True

# =============================================================================
# Import LangChain libraries (AFTER agentsec is ready to be initialized)
# =============================================================================
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage

# Import our tools
from .tools import TOOLS
from .mcp_tools import get_mcp_tools

# =============================================================================
# Agent Configuration
# =============================================================================

# System prompt for the SRE agent
SYSTEM_PROMPT = """You are an SRE helper agent. Use check_service_health for service checks, get_recent_logs for logs, calculate_capacity for scaling, and fetch_url for URLs. Be concise and accurate. Summarize tool results for the user."""

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
        
        # Resolve SDK from the agentsec gateway config (set via agentsec.yaml's
        # sdk: ${GOOGLE_AI_SDK}), falling back to the GOOGLE_AI_SDK env var.
        from aidefense.runtime.agentsec._state import get_default_gateway_for_provider
        _gw = get_default_gateway_for_provider("vertexai")
        google_ai_sdk = (_gw.get("sdk") if _gw else None) or os.getenv("GOOGLE_AI_SDK", "google_genai")
        
        print(f"[agent] Creating LangChain agent with model: {model_name}", flush=True)
        print(f"[agent] Project: {project}, Location: {location}", flush=True)
        print(f"[agent] SDK path: {google_ai_sdk}", flush=True)
        
        if google_ai_sdk == "vertexai":
            # Agent Engine safe path: uses vertexai.GenerativeModel internally,
            # which only requires the aiplatform scope (always available in
            # Agent Engine). Patched by agentsec's vertexai patcher.
            import vertexai
            from langchain_google_vertexai import ChatVertexAI
            
            vertexai.init(project=project, location=location)
            llm = ChatVertexAI(
                model_name=model_name,
                temperature=0.7,
                max_output_tokens=1024,
            )
        else:
            # Modern forward path (default): uses google.genai.Client internally.
            # Patched by agentsec's google_genai patcher.
            from langchain_google_genai import ChatGoogleGenerativeAI
            import google.auth
            
            _credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            llm = ChatGoogleGenerativeAI(
                model=model_name,
                vertexai=True,
                project=project,
                location=location,
                credentials=_credentials,
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
    
    # Initialize agentsec protection (lazy, only on first call)
    _initialize_agentsec()
    
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
    # Initialize agentsec protection (lazy, only on first call)
    _initialize_agentsec()
    
    llm_with_tools, _ = _get_agent()
    return llm_with_tools
