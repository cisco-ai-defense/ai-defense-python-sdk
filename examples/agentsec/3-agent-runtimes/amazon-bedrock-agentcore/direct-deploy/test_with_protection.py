#!/usr/bin/env python3
"""Test AgentCore with agentsec protection.

This script demonstrates how agentsec protects calls to AgentCore agents.
The protection happens on the CLIENT side - when you call InvokeAgentRuntime,
agentsec intercepts the call and inspects it via AI Defense.

Both REQUEST and RESPONSE are inspected through the patched boto3 client.

Usage:
    # From the agentcore example directory
    poetry run python direct-deploy/test_with_protection.py "Check payments health"
"""

import json
import logging
import os
import sys
import uuid
from pathlib import Path

# Enable DEBUG logging for agentsec to capture inspection logs
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logging.getLogger("agentsec").setLevel(logging.DEBUG)

# Load shared .env file
from dotenv import load_dotenv
_shared_env = Path(__file__).parent.parent.parent.parent / ".env"
if _shared_env.exists():
    load_dotenv(_shared_env)

# =============================================================================
# Configure agentsec via agentsec.yaml (BEFORE importing boto3)
# =============================================================================
from aidefense.runtime import agentsec

# Resolve agentsec.yaml path
_yaml_paths = [
    Path("/app/agentsec.yaml"),  # Container deployment
    Path(__file__).parent.parent.parent.parent / "agentsec.yaml",  # examples/agentsec/agentsec.yaml
]

_yaml_config = None
for _yp in _yaml_paths:
    if _yp.exists():
        _yaml_config = str(_yp)
        break

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
# Now import boto3 (AFTER agentsec.protect())
# =============================================================================
import boto3
from botocore.config import Config


def invoke_agent_with_boto3(prompt: str, agent_name: str = "agentcore_sre_direct"):
    """Invoke the AgentCore agent using boto3 (protected by agentsec).
    
    This method uses the boto3 SDK directly, ensuring both REQUEST and RESPONSE
    go through agentsec's patched client for full AI Defense inspection.
    
    Args:
        prompt: The prompt to send to the agent
        agent_name: The agent name to use (default: agentcore_sre_direct)
    """
    import yaml
    config_file = Path(__file__).parent.parent / ".bedrock_agentcore.yaml"
    
    with open(config_file) as f:
        config = yaml.safe_load(f)
        # Use specified agent name, not default_agent from config
        agent_config = config.get("agents", {}).get(agent_name, {})
        if not agent_config:
            raise ValueError(f"Agent '{agent_name}' not found in config. Available: {list(config.get('agents', {}).keys())}")
        agent_arn = agent_config.get("bedrock_agentcore", {}).get("agent_arn")
        session_id = agent_config.get("bedrock_agentcore", {}).get("agent_session_id")
        if not session_id:
            session_id = str(uuid.uuid4())
    
    print(f"\n[client] Agent ARN: {agent_arn}")
    print(f"[client] Session: {session_id}")
    print(f"[client] Prompt: {prompt}")
    print("-" * 60)
    
    # Create AgentCore client
    client = boto3.client(
        "bedrock-agentcore",
        region_name=os.getenv("AWS_REGION", "us-west-2"),
        config=Config(
            retries={'max_attempts': 3}
        )
    )
    
    # This call is protected by agentsec!
    # agentsec will intercept InvokeAgentRuntime and inspect both:
    # - REQUEST: Before sending to AgentCore (prompt injection detection)
    # - RESPONSE: After receiving from AgentCore (output validation)
    response = client.invoke_agent_runtime(
        agentRuntimeArn=agent_arn,
        runtimeSessionId=session_id,  
        payload=json.dumps({"prompt": prompt}).encode("utf-8"),
    )
    
    # Parse response
    result = json.loads(response["payload"].read())
    print(f"\n[agent] Response: {result.get('result', result)}")
    return result


if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Hello, check the health of the payments service"
    # Allow specifying agent via environment variable (for testing different deploy modes)
    agent_name = os.getenv("AGENTCORE_AGENT_NAME", "agentcore_sre_direct")
    
    print("=" * 60)
    print("Testing AgentCore with agentsec protection (boto3 direct)")
    print("=" * 60)
    print(f"  Agent: {agent_name}")
    
    # Direct boto3 call - both request AND response are protected by agentsec
    print("\n>>> Direct boto3 call (protected by agentsec)")
    print("    Request inspection: YES")
    print("    Response inspection: YES")
    
    try:
        invoke_agent_with_boto3(prompt, agent_name=agent_name)
        print("\n[SUCCESS] Test completed - both request and response were inspected")
    except agentsec.SecurityPolicyError as e:
        print(f"\n[BLOCKED] AI Defense blocked the request: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        print("[INFO] Note: agentsec inspection was still attempted before/after this error")
        sys.exit(1)
