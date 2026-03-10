"""Lambda Handler for AWS Lambda Deploy with agentsec protection.

This module provides a Lambda handler that demonstrates agentsec protection
for LLM calls (Bedrock) and MCP tool calls from within a Lambda function.

Supports both local tools and MCP tools (when MCP_SERVER_URL is configured).

Usage:
    # Deploy to AWS Lambda (includes _shared module)
    ./scripts/deploy.sh
    
    # Invoke the Lambda function
    ./scripts/invoke.sh "Check payments health"
    
    # Test MCP tool (requires MCP_SERVER_URL in Lambda env)
    ./scripts/invoke.sh "Fetch https://example.com and summarize it"

Note: agentsec protection is configured in _shared/agent_factory.py
      The deploy script includes _shared in the Lambda package.
"""

import json
import os
import sys

# Add current directory to path for _shared imports (Lambda deployment structure)
LAMBDA_TASK_ROOT = os.environ.get("LAMBDA_TASK_ROOT", os.path.dirname(__file__))
if LAMBDA_TASK_ROOT not in sys.path:
    sys.path.insert(0, LAMBDA_TASK_ROOT)

# Import the protected agent (agentsec.protect() is called on import)
# This includes both local tools AND MCP tools (if MCP_SERVER_URL is set)
from _shared import get_agent
from aidefense.runtime import agentsec


# =============================================================================
# Lambda Handler
# =============================================================================
def _extract_prompt(event):
    """Extract the prompt from various Lambda event formats."""
    if isinstance(event, dict):
        if "prompt" in event:
            return event["prompt"]
        
        body = event.get("body")
        if body is not None:
            if isinstance(body, (dict, list)):
                return json.dumps(body)
            try:
                payload = json.loads(body)
                return payload.get("prompt", body)
            except Exception:
                return body
    
    return str(event)


def handler(event, context):
    """Lambda handler function.
    
    Both Bedrock LLM calls and MCP tool calls are protected by agentsec.
    """
    prompt = _extract_prompt(event)
    
    print(f"[lambda] Received prompt: {prompt}")
    print(f"[agentsec] Patched clients: {agentsec.get_patched_clients()}")
    
    # Call the Strands agent (Bedrock + MCP calls are protected by agentsec!)
    result = get_agent()(prompt)
    
    response_body = {"result": str(result)}
    
    # If invoked via API Gateway, return HTTP response format
    if isinstance(event, dict) and ("httpMethod" in event or "requestContext" in event):
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(response_body),
        }
    
    return response_body
