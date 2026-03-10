"""
Azure ML Inference Entry Script for Foundry Agent App.

Azure ML managed endpoints expect a main.py with init() and run() functions.
This script wraps our agent for Azure ML compatibility.

Note: agentsec protection is initialized at import time when _shared is imported.
"""

import os
import sys
import json

# Azure ML sets the app root to /var/azureml-app
APP_ROOT = os.environ.get("AZUREML_APP_ROOT", "/var/azureml-app")
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

# Import the agent factory (protection is initialized at import time)
from _shared import invoke_agent
from aidefense.runtime.agentsec import get_patched_clients


def init():
    """
    Called once when the container starts.
    agentsec protection is already initialized when _shared was imported.
    """
    print(f"[main.py] Initializing Foundry Agent App...", flush=True)
    print(f"[main.py] PYTHONPATH: {sys.path}", flush=True)
    print(f"[agentsec] Patched clients: {get_patched_clients()}", flush=True)
    print(f"[main.py] Initialization complete.", flush=True)


def run(raw_data):
    """
    Called for each scoring request.
    
    Args:
        raw_data: JSON string with the request payload
        
    Returns:
        JSON response with the agent's result
    """
    try:
        # Parse the input
        data = json.loads(raw_data)
        
        # Handle Azure ML's "data" wrapper
        if "data" in data:
            data = data["data"]
        
        # Extract the prompt
        prompt = data.get("prompt", data.get("message", data.get("input")))
        
        if not prompt:
            return json.dumps({"error": "prompt field is required"})
        
        print(f"[main.py] Received prompt: {prompt}", flush=True)
        print(f"[agentsec] Patched clients: {get_patched_clients()}", flush=True)
        
        # Invoke the agent (LLM + MCP calls are protected by agentsec!)
        result = invoke_agent(prompt)
        
        return json.dumps({"result": result})
        
    except Exception as e:
        print(f"[main.py] Error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return json.dumps({"error": str(e)})
