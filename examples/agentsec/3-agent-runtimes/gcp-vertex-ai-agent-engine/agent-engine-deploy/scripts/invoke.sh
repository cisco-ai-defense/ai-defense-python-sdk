#!/usr/bin/env bash
# Invoke the Agent Engine deployment
#
# Usage:
#   ./invoke.sh "Check the health of my services"
#   ./invoke.sh --local "What's the status of the API?"
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$(dirname "$DEPLOY_DIR")"

# Load environment (preserve AGENT_ENGINE_NAME if set by parent e.g. --new-resources)
_SAVED_AGENT_ENGINE_NAME="${AGENT_ENGINE_NAME:-}"
if [ -f "$PROJECT_DIR/../../../.env" ]; then
    source "$PROJECT_DIR/../../../.env"
fi
[ -n "$_SAVED_AGENT_ENGINE_NAME" ] && export AGENT_ENGINE_NAME="$_SAVED_AGENT_ENGINE_NAME"

# Configuration
PROJECT="${GOOGLE_CLOUD_PROJECT:?Error: GOOGLE_CLOUD_PROJECT not set. Please set it in .env or export it.}"
LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
AGENT_NAME="${AGENT_ENGINE_NAME:-sre-agent-engine}"

# Default prompt
PROMPT="${1:-How can you help me with SRE tasks?}"

# Check for local mode
if [ "$PROMPT" = "--local" ]; then
    PROMPT="${2:-How can you help me with SRE tasks?}"
    
    echo "Running locally..."
    cd "$PROJECT_DIR"
    
    if [ -f "poetry.lock" ]; then
        poetry install --quiet 2>/dev/null || poetry install
        PYTHON_CMD="poetry run python"
    else
        PYTHON_CMD="python"
    fi
    
    export PYTHONPATH="$PROJECT_DIR"
    export GOOGLE_CLOUD_PROJECT="$PROJECT"
    export GOOGLE_CLOUD_LOCATION="$LOCATION"
    export GOOGLE_GENAI_USE_VERTEXAI="True"
    
    $PYTHON_CMD -c "
import json
import sys
sys.path.insert(0, '$PROJECT_DIR')
from _shared.agent_factory import invoke_agent

prompt = '''$PROMPT'''
print(f'Prompt: {prompt}')
print('-' * 40)
result = invoke_agent(prompt)
print(result)
"
    exit 0
fi

# Invoke deployed Agent Engine
echo "Invoking Vertex AI Agent Engine: $AGENT_NAME"
echo "Project: $PROJECT"
echo "Location: $LOCATION"
echo ""
echo "Prompt: $PROMPT"
echo "=========================================="

cd "$PROJECT_DIR"

# Ensure dependencies
if [ -f "poetry.lock" ]; then
    poetry install --quiet 2>/dev/null || poetry install
    PYTHON_CMD="poetry run python"
else
    PYTHON_CMD="python"
fi

# Check for saved resource name
RESOURCE_FILE="/tmp/agent_engine_resource.txt"
if [ -f "$RESOURCE_FILE" ]; then
    RESOURCE_NAME=$(cat "$RESOURCE_FILE")
else
    RESOURCE_NAME=""
fi

# Create invoke script
cat > /tmp/invoke_agent_engine.py <<EOF
"""
Invoke deployed Agent Engine agent.
"""
import sys
import vertexai

# Initialize
client = vertexai.Client(project="$PROJECT", location="$LOCATION")

# Get resource name
resource_name = "$RESOURCE_NAME"
if not resource_name:
    # Try to find agent by display name
    print("Looking for agent: $AGENT_NAME")
    # Note: Listing agents and finding by name would go here
    print("Error: Agent resource not found. Please deploy first with ./deploy.sh")
    sys.exit(1)

print(f"Using agent: {resource_name}")
print("")

try:
    # Get the deployed agent
    remote_agent = client.agent_engines.get(name=resource_name)
    
    # Invoke the agent using the query method
    prompt = """$PROMPT"""
    response = remote_agent.query(prompt=prompt)
    
    print("Response:")
    print("-" * 60)
    print(response)
    print("")
    
except Exception as e:
    print(f"Error invoking agent: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF

# Execute invocation
$PYTHON_CMD /tmp/invoke_agent_engine.py

# Clean up
rm -f /tmp/invoke_agent_engine.py
