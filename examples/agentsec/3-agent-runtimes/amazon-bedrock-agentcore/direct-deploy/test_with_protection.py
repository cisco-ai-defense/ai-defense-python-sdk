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
# Configure agentsec protection (BEFORE importing boto3)
# =============================================================================
from aidefense.runtime import agentsec

agentsec.protect(
    llm_integration_mode=os.getenv("AGENTSEC_LLM_INTEGRATION_MODE", "api"),
    api_mode_llm=os.getenv("AGENTSEC_API_MODE_LLM", "on_monitor"),
    api_mode_llm_endpoint=os.getenv("AI_DEFENSE_API_MODE_LLM_ENDPOINT"),
    api_mode_llm_api_key=os.getenv("AI_DEFENSE_API_MODE_LLM_API_KEY"),
    api_mode_fail_open_llm=True,
    providers={
        "bedrock": {
            "gateway_url": os.getenv("AGENTSEC_BEDROCK_GATEWAY_URL"),
            "gateway_api_key": os.getenv("AGENTSEC_BEDROCK_GATEWAY_API_KEY"),
        },
        "agentcore": {
            "gateway_url": os.getenv("AGENTSEC_AGENTCORE_GATEWAY_URL"),
        },
    },
    auto_dotenv=False,
)

print(f"[agentsec] Mode: {os.getenv('AGENTSEC_API_MODE_LLM', 'on_monitor')} | "
      f"Integration: {os.getenv('AGENTSEC_LLM_INTEGRATION_MODE', 'api')} | "
      f"Patched: {agentsec.get_patched_clients()}")

# =============================================================================
# Now import boto3 (AFTER agentsec.protect())
# =============================================================================
import boto3
from botocore.config import Config


def invoke_agent_with_boto3(prompt: str):
    """Invoke the AgentCore agent using boto3 (protected by agentsec).
    
    This method uses the boto3 SDK directly, ensuring both REQUEST and RESPONSE
    go through agentsec's patched client for full AI Defense inspection.
    """
    import yaml
    config_file = Path(__file__).parent.parent / ".bedrock_agentcore.yaml"
    
    with open(config_file) as f:
        config = yaml.safe_load(f)
        default_agent = config.get("default_agent", "agentcore_sre_direct")
        agent_config = config.get("agents", {}).get(default_agent, {})
        agent_arn = agent_config.get("bedrock_agentcore", {}).get("agent_arn")
        session_id = agent_config.get("bedrock_agentcore", {}).get("agent_session_id")
    
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
    
    print("=" * 60)
    print("Testing AgentCore with agentsec protection (boto3 direct)")
    print("=" * 60)
    
    # Direct boto3 call - both request AND response are protected by agentsec
    print("\n>>> Direct boto3 call (protected by agentsec)")
    print("    Request inspection: YES")
    print("    Response inspection: YES")
    
    try:
        invoke_agent_with_boto3(prompt)
        print("\n[SUCCESS] Test completed - both request and response were inspected")
    except agentsec.SecurityPolicyError as e:
        print(f"\n[BLOCKED] AI Defense blocked the request: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        print("[INFO] Note: agentsec inspection was still attempted before/after this error")
        sys.exit(1)
