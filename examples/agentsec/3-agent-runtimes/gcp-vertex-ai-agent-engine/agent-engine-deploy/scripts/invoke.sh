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

# Load environment
if [ -f "$PROJECT_DIR/../../../.env" ]; then
    source "$PROJECT_DIR/../../../.env"
fi

# Configuration
PROJECT="${GOOGLE_CLOUD_PROJECT:?Error: GOOGLE_CLOUD_PROJECT not set. Please set it in .env or export it.}"
LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
AGENT_NAME="${AGENT_ENGINE_NAME:-sre-agent-protected}"

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
echo "Invoking Agent Engine: $AGENT_NAME"
echo "Project: $PROJECT"
echo "Location: $LOCATION"
echo ""
echo "Prompt: $PROMPT"
echo "----------------------------------------"

# Note: The actual invocation depends on how the agent was deployed.
# This is a placeholder for the Agent Engine API call.

echo ""
echo "To invoke the deployed agent, use the Agent Builder SDK:"
echo ""
echo "from vertexai.agents import Agent"
echo "agent = Agent.get(name='$AGENT_NAME', project='$PROJECT', location='$LOCATION')"
echo "response = agent.invoke({'prompt': '$PROMPT'})"
echo "print(response)"
echo ""
echo "Or use --local flag to test locally:"
echo "  ./invoke.sh --local \"$PROMPT\""
