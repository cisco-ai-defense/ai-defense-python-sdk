"""
FastAPI application for Cloud Run deployment with LangChain Agent.

This file provides a REST API for the SRE agent when deployed to Cloud Run.
Cloud Run provides serverless container deployment with automatic scaling.

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

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from _shared.agent_factory import invoke_agent

app = FastAPI(
    title="Vertex AI SRE Agent - Cloud Run",
    description="LangChain-based SRE Agent with Cisco AI Defense protection, deployed on Cloud Run",
    version="1.0.0",
)


class InvokeRequest(BaseModel):
    """Request model for agent invocation."""
    prompt: str


class InvokeResponse(BaseModel):
    """Response model for agent invocation."""
    result: str
    status: str = "success"


@app.get("/health")
def health():
    """Health check endpoint for Cloud Run."""
    return {"status": "healthy", "service": "sre-agent-cloud-run"}


@app.post("/invoke", response_model=InvokeResponse)
def invoke(request: InvokeRequest):
    """
    Invoke the SRE agent with a prompt.
    
    The LangChain agent will decide which tools to use based on the prompt.
    All requests are protected by Cisco AI Defense through agentsec.
    
    Example prompts:
    - "Check the health of the payments service"
    - "Show me recent logs for the auth service"
    - "Fetch https://example.com and summarize it"
    """
    try:
        result = invoke_agent(request.prompt)
        return InvokeResponse(result=result, status="success")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def root():
    """Root endpoint with API information."""
    return {
        "service": "Vertex AI SRE Agent",
        "deployment": "Cloud Run",
        "agent": "LangChain with tool calling",
        "protection": "Cisco AI Defense (agentsec)",
        "tools": [
            "check_service_health - Check service health status",
            "get_recent_logs - Get recent log entries",
            "calculate_capacity - Calculate capacity metrics",
            "fetch_url - Fetch URL content via MCP (if configured)",
        ],
        "endpoints": {
            "/health": "Health check",
            "/invoke": "POST - Invoke agent with prompt",
        },
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
