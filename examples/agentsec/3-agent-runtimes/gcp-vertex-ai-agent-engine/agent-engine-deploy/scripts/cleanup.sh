#!/usr/bin/env bash
# Cleanup Agent Engine deployment
#
# This script deletes the deployed Agent Engine agent from Vertex AI.
#
# Usage:
#   ./cleanup.sh
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
PROJECT="${GOOGLE_CLOUD_PROJECT:?Error: GOOGLE_CLOUD_PROJECT not set}"
LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
AGENT_NAME="${AGENT_ENGINE_NAME:-sre-agent-engine}"

echo "=============================================="
echo "Cleaning up Agent Engine deployment"
echo "=============================================="
echo "Project:  $PROJECT"
echo "Location: $LOCATION"
echo "Agent:    $AGENT_NAME"
echo ""

# Check for saved resource name
RESOURCE_FILE="/tmp/agent_engine_resource.txt"
if [ ! -f "$RESOURCE_FILE" ]; then
    echo "No saved resource found. Agent may not be deployed."
    exit 0
fi

RESOURCE_NAME=$(cat "$RESOURCE_FILE")

cd "$PROJECT_DIR"

# Ensure dependencies
if [ -f "poetry.lock" ]; then
    poetry install --quiet 2>/dev/null || poetry install
    PYTHON_CMD="poetry run python"
else
    PYTHON_CMD="python"
fi

# Create cleanup script
cat > /tmp/cleanup_agent_engine.py <<EOF
"""
Delete deployed Agent Engine agent.
"""
from google.cloud import aiplatform

# Initialize
aiplatform.init(project="$PROJECT", location="$LOCATION")
client = aiplatform.vertexai.AgentEngineClient()

resource_name = "$RESOURCE_NAME"

print(f"Deleting agent: {resource_name}")

try:
    client.agent_engines.delete(name=resource_name)
    print("Agent deleted successfully!")
    
except Exception as e:
    print(f"Error deleting agent: {e}")
    import traceback
    traceback.print_exc()
EOF

# Execute cleanup
$PYTHON_CMD /tmp/cleanup_agent_engine.py

# Clean up temp files
rm -f /tmp/cleanup_agent_engine.py
rm -f "$RESOURCE_FILE"

echo ""
echo "Cleanup complete!"
