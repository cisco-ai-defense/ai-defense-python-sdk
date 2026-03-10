"""Agent factory with agentsec protection.

This module configures agentsec via agentsec.yaml, then creates a Strands
agent with demo tools.

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
# 2. Lambda task root (Lambda deployment)
# 3. examples/.env (local development)
# 4. agentcore/.env (fallback)
_lambda_task_root = os.environ.get("LAMBDA_TASK_ROOT", "")
_env_paths = [
    Path("/app/.env"),  # Container deployment
    *([ Path(_lambda_task_root) / ".env" ] if _lambda_task_root else []),  # Lambda deployment
    Path(__file__).parent.parent.parent.parent / ".env",  # examples/.env
    Path(__file__).parent.parent / ".env",  # agentcore/.env
]

for _env_path in _env_paths:
    if _env_path.exists():
        load_dotenv(_env_path)
        break

# In Lambda, clear profile-based AWS auth vars loaded from .env.
# Lambda uses its IAM execution role automatically; AWS_PROFILE would cause
# "ProfileNotFound" since ~/.aws/credentials doesn't exist in Lambda.
if _lambda_task_root:
    for _var in ("AWS_PROFILE", "AWS_AUTH_METHOD"):
        os.environ.pop(_var, None)

# =============================================================================
# Configure agentsec via agentsec.yaml
# =============================================================================
from aidefense.runtime import agentsec

# Resolve agentsec.yaml path (container vs Lambda vs local development)
_yaml_paths = [
    Path("/app/agentsec.yaml"),  # Container deployment
    *([ Path(_lambda_task_root) / "agentsec.yaml" ] if _lambda_task_root else []),  # Lambda deployment
    Path(__file__).parent.parent.parent.parent / "agentsec.yaml",  # examples/agentsec/agentsec.yaml
]

_yaml_config = None
for _yp in _yaml_paths:
    if _yp.exists():
        _yaml_config = str(_yp)
        break


def configure_agentsec():
    """Configure agentsec protection via agentsec.yaml.
    
    This function should be called BEFORE creating any boto3 clients or agents.
    All gateway/API mode settings (URLs, keys, modes, fail-open, retry, etc.)
    are defined in agentsec.yaml. Secrets are referenced via ${VAR_NAME} and
    resolved from the environment (populated by load_dotenv above).
    """
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
        # Ensure AWS_DEFAULT_REGION is consistent with AWS_REGION
        # (boto3 checks AWS_DEFAULT_REGION first, so they must agree)
        os.environ.setdefault("AWS_DEFAULT_REGION", os.environ["AWS_REGION"])
        
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
