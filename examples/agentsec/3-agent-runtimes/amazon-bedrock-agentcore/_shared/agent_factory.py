"""Agent factory with agentsec protection.

This module configures agentsec with explicit gateway/API URLs for LLM and MCP,
then creates a Strands agent with demo tools.

The agentsec.protect() call patches botocore to intercept:
- Bedrock calls (InvokeModel, Converse, etc.)
- AgentCore calls (InvokeAgentRuntime)

This works for all AgentCore deployment modes:
- Direct code deploy
- Container deploy
- Lambda deploy
"""

import os
import sys
from pathlib import Path

# Load shared .env file from examples/ directory (before agentsec.protect())
from dotenv import load_dotenv

# Try multiple .env locations in order of priority:
# 1. /app/.env (container deployment)
# 2. examples/.env (local development)
# 3. agentcore/.env (fallback)
_env_paths = [
    Path("/app/.env"),  # Container deployment
    Path(__file__).parent.parent.parent.parent / ".env",  # examples/.env
    Path(__file__).parent.parent / ".env",  # agentcore/.env
]

for _env_path in _env_paths:
    if _env_path.exists():
        load_dotenv(_env_path)
        break

# =============================================================================
# Configure agentsec with explicit gateway/API URLs for LLM and MCP
# =============================================================================
from aidefense.runtime import agentsec


def configure_agentsec():
    """Configure agentsec protection with explicit URLs.
    
    This function should be called BEFORE creating any boto3 clients or agents.
    It configures agentsec with explicit gateway/API URLs for both LLM and MCP.
    
    Reads configuration from environment variables:
    - AGENTSEC_LLM_INTEGRATION_MODE: "api" (inspection) or "gateway" (proxy)
    - AGENTSEC_MCP_INTEGRATION_MODE: "api" (inspection) or "gateway" (proxy)
    - API mode settings: AI_DEFENSE_API_MODE_LLM_ENDPOINT, etc.
    - Gateway mode settings: AGENTSEC_BEDROCK_GATEWAY_URL, etc.
    """
    agentsec.protect(
        # Integration mode: "api" (inspection) or "gateway" (proxy)
        llm_integration_mode=os.getenv("AGENTSEC_LLM_INTEGRATION_MODE", "api"),
        mcp_integration_mode=os.getenv("AGENTSEC_MCP_INTEGRATION_MODE", "api"),
        
        # API Mode Configuration (when integration_mode="api")
        api_mode_llm=os.getenv("AGENTSEC_API_MODE_LLM", "on_monitor"),
        api_mode_mcp=os.getenv("AGENTSEC_API_MODE_MCP", "on_monitor"),
        api_mode_llm_endpoint=os.getenv("AI_DEFENSE_API_MODE_LLM_ENDPOINT"),
        api_mode_llm_api_key=os.getenv("AI_DEFENSE_API_MODE_LLM_API_KEY"),
        api_mode_mcp_endpoint=os.getenv("AI_DEFENSE_API_MODE_MCP_ENDPOINT"),
        api_mode_mcp_api_key=os.getenv("AI_DEFENSE_API_MODE_MCP_API_KEY"),
        
        # Fail-open settings
        api_mode_fail_open_llm=os.getenv("AGENTSEC_API_MODE_FAIL_OPEN_LLM", "true").lower() == "true",
        api_mode_fail_open_mcp=os.getenv("AGENTSEC_API_MODE_FAIL_OPEN_MCP", "true").lower() == "true",
        
        # Gateway Mode Configuration (when integration_mode="gateway")
        providers={
            "bedrock": {
                "gateway_url": os.getenv("AGENTSEC_BEDROCK_GATEWAY_URL"),
                "gateway_api_key": os.getenv("AGENTSEC_BEDROCK_GATEWAY_API_KEY"),
            },
            "agentcore": {
                "gateway_url": os.getenv("AGENTSEC_AGENTCORE_GATEWAY_URL"),
                # No API key needed - AgentCore gateway uses AWS Sig V4 authentication
            },
        },
        gateway_mode_mcp_url=os.getenv("AGENTSEC_MCP_GATEWAY_URL"),
        gateway_mode_mcp_api_key=os.getenv("AGENTSEC_MCP_GATEWAY_API_KEY"),
        gateway_mode_fail_open_llm=os.getenv("AGENTSEC_GATEWAY_MODE_FAIL_OPEN_LLM", "true").lower() == "true",
        gateway_mode_fail_open_mcp=os.getenv("AGENTSEC_GATEWAY_MODE_FAIL_OPEN_MCP", "true").lower() == "true",
        
        auto_dotenv=False,  # We already loaded .env manually
    )
    
    print(f"[agentsec] LLM: {os.getenv('AGENTSEC_API_MODE_LLM', 'on_monitor')} | "
          f"Integration: {os.getenv('AGENTSEC_LLM_INTEGRATION_MODE', 'api')} | "
          f"Patched: {agentsec.get_patched_clients()}")


# Configure agentsec on module import
configure_agentsec()

# =============================================================================
# Now import agent libraries (AFTER agentsec.protect())
# =============================================================================
from strands import Agent
from strands.models import BedrockModel

from .tools import add, check_service_health, summarize_log
from .mcp_tools import get_mcp_tools

# Global agent instance (singleton pattern for Lambda cold start optimization)
_agent = None


def get_agent():
    """Create or reuse the SRE agent with consistent model config.
    
    Uses a singleton pattern to reuse the agent across invocations,
    which is important for Lambda cold start optimization.
    
    Includes both local tools and MCP tools (if MCP_SERVER_URL is configured).
    
    Returns:
        Strands Agent configured with Bedrock model and demo tools
    """
    global _agent
    if _agent is None:
        # Set default AWS region if not configured
        os.environ.setdefault("AWS_REGION", "us-west-2")
        os.environ.setdefault("AWS_DEFAULT_REGION", "us-west-2")
        
        # Get model ID from environment or use default
        model_id = os.getenv(
            "BEDROCK_MODEL_ID",
            "anthropic.claude-3-sonnet-20240229-v1:0",
        )
        
        # Create Bedrock model
        model = BedrockModel(
            model_id=model_id,
            region_name=os.getenv("AWS_REGION"),
        )
        
        # Combine local tools + MCP tools (if configured)
        local_tools = [add, check_service_health, summarize_log]
        mcp_tools = get_mcp_tools()  # Returns [fetch_url] if MCP_SERVER_URL is set
        all_tools = local_tools + mcp_tools
        
        # Update system prompt if MCP tools are available
        if mcp_tools:
            system_prompt = """You are an SRE helper assistant. You can:
- Check service health (check_service_health)
- Summarize logs (summarize_log)
- Perform basic calculations (add)
- Fetch webpage content (fetch_url) - Use this when asked to fetch or get content from a URL

When asked to fetch a URL, ALWAYS use the fetch_url tool."""
        else:
            system_prompt = "You are an SRE helper assistant. You can check service health, summarize logs, and perform basic calculations."
        
        # Create agent with all tools
        _agent = Agent(
            model=model,
            system_prompt=system_prompt,
            tools=all_tools,
        )
        
        tool_names = [t.__name__ if hasattr(t, '__name__') else str(t) for t in all_tools]
        print(f"[agent] Created with model: {model_id}")
        print(f"[agent] Tools: {tool_names}")
    
    return _agent
