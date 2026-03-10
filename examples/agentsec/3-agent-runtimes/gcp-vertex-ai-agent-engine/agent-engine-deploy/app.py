"""
Vertex AI Agent Engine entry point with LangChain Agent.

This file is the entry point when deploying to Vertex AI Agent Engine (managed mode).
Agent Engine is Google's fully managed service for running agents.

The agent uses LangChain with tool calling to:
- Check service health (check_service_health)
- Get recent logs (get_recent_logs)
- Calculate capacity metrics (calculate_capacity)
- Fetch webpage content via MCP (fetch_url) - if MCP_SERVER_URL is set

agentsec protection is applied through the shared agent_factory module,
protecting both LLM calls and MCP tool calls.
"""

import os
import sys

# Ensure the parent directory is importable
_agent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _agent_dir not in sys.path:
    sys.path.insert(0, _agent_dir)

from _shared.agent_factory import invoke_agent


def handle_request(request: dict) -> dict:
    """
    Handle an Agent Engine request.
    
    This is the main entry point for Agent Engine invocations.
    The LangChain agent will decide which tools to use based on the prompt.
    All requests go through agentsec protection via the agent_factory.
    
    Expected format: {"prompt": "..."}
    Returns: {"result": "...", "status": "success|error"}
    """
    prompt = request.get("prompt", "Hello! How can I help you today?")
    
    try:
        result = invoke_agent(prompt)
        return {
            "result": result,
            "status": "success",
        }
    except Exception as e:
        return {
            "result": str(e),
            "status": "error",
        }


# For local testing
if __name__ == "__main__":
    import json

    # Test prompts that exercise different tools
    test_prompts = [
        # Local tool: check_service_health
        "Check the health of the payments service",
        # Local tool: get_recent_logs
        "Show me recent logs for the auth service",
        # Local tool: calculate_capacity
        "I have 60% usage with 15% monthly growth. What's the capacity outlook?",
        # MCP tool: fetch_url (only works if MCP_SERVER_URL is set)
        "Fetch https://example.com and tell me what it's about",
    ]
    
    print("\n" + "="*70)
    print("GCP Vertex AI Agent Engine - Local Test")
    print("="*70)
    print(f"MCP_SERVER_URL: {os.getenv('MCP_SERVER_URL', 'NOT SET')}")
    print("="*70)
    
    for prompt in test_prompts:
        print(f"\n{'='*60}")
        print(f"Prompt: {prompt}")
        print('='*60)
        response = handle_request({"prompt": prompt})
        print(json.dumps(response, indent=2))
