"""
Azure Functions v2 Handler with agentsec protection.

This module provides an Azure Functions HTTP trigger that demonstrates agentsec
protection for LLM calls (Azure OpenAI) and MCP tool calls from within a
serverless function.

Supports both local tools and MCP tools (when MCP_SERVER_URL is configured).

Usage:
    # Local development with Azure Functions Core Tools
    func start
    
    # Deploy to Azure Functions
    ./scripts/deploy.sh
    
    # Invoke the deployed function
    ./scripts/invoke.sh "Check payments health"
    
    # Test MCP tool
    ./scripts/invoke.sh "Fetch https://example.com and summarize it"

Note: agentsec protection is initialized at import time when _shared is imported.
"""

import json
import logging
import os
import sys
import azure.functions as func

# Add current directory to path for _shared imports
FUNCTION_ROOT = os.path.dirname(__file__)
if FUNCTION_ROOT not in sys.path:
    sys.path.insert(0, FUNCTION_ROOT)

# Import the agent factory (protection is initialized at import time)
from _shared import invoke_agent
from aidefense.runtime.agentsec import get_patched_clients

# Create the Azure Functions app
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.route(route="invoke", methods=["POST"])
def invoke(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP trigger function to invoke the SRE agent.
    
    Both Azure OpenAI LLM calls and MCP tool calls are protected by agentsec.
    
    Request body:
        {"prompt": "Check the health of the payments service"}
        
    Response:
        {"result": "The payments service is healthy..."}
    """
    logging.info("[function] Received invoke request")
    logging.info(f"[agentsec] Patched clients: {get_patched_clients()}")
    
    try:
        # Parse request body
        req_body = req.get_json()
        prompt = req_body.get("prompt", req_body.get("message", req_body.get("input")))
        
        if not prompt:
            return func.HttpResponse(
                json.dumps({"error": "prompt field is required"}),
                mimetype="application/json",
                status_code=400
            )
        
        logging.info(f"[function] Processing prompt: {prompt}")
        
        # Invoke the agent (LLM + MCP calls are protected by agentsec!)
        result = invoke_agent(prompt)
        
        return func.HttpResponse(
            json.dumps({"result": result}),
            mimetype="application/json",
            status_code=200
        )
        
    except ValueError as e:
        logging.error(f"[function] Invalid request: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON in request body"}),
            mimetype="application/json",
            status_code=400
        )
    except Exception as e:
        logging.error(f"[function] Error: {e}")
        import traceback
        traceback.print_exc()
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            mimetype="application/json",
            status_code=500
        )


@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint."""
    return func.HttpResponse(
        json.dumps({
            "status": "healthy",
            "patched_clients": get_patched_clients()
        }),
        mimetype="application/json",
        status_code=200
    )
