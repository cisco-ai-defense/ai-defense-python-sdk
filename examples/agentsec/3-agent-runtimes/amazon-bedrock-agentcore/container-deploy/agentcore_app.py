"""AgentCore App for Container Deploy.

This module provides the AgentCore entrypoint for Docker container deployment.
The BedrockAgentCoreApp wraps the agent and exposes it via the AgentCore runtime.

Usage:
    # Deploy via agentcore CLI (builds and pushes Docker image)
    ./scripts/deploy.sh
    
    # Invoke the deployed agent
    ./scripts/invoke.sh "Check payments health"

Note: agentsec protection is configured in _shared/agent_factory.py
"""

import os
import sys

# Add parent directory to path for imports
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from bedrock_agentcore import BedrockAgentCoreApp

# Import the protected agent (agentsec.protect() is called on import)
from _shared import get_agent

# Create AgentCore app wrapper
app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload: dict):
    """AgentCore entrypoint - invoked when the agent receives a request.
    
    Args:
        payload: Request payload, expected to have a "prompt" key
        
    Returns:
        Dict with "result" key containing the agent's response
    """
    if not isinstance(payload, dict):
        payload = {"prompt": str(payload)}
    
    user_message = payload.get("prompt", "Hello! How can I help you today?")
    
    # Call the Strands agent (protected by agentsec)
    result = get_agent()(user_message)
    
    return {"result": str(result)}


if __name__ == "__main__":
    # Container runtime - listen on PORT env var (set by AgentCore)
    port = int(os.getenv("PORT", "8080"))
    print(f"Starting AgentCore container on port {port}...")
    app.run(host="0.0.0.0", port=port)
