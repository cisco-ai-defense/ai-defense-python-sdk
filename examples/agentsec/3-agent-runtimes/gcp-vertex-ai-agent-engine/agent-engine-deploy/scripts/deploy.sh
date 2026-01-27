#!/usr/bin/env bash
# Deploy SRE agent to Vertex AI Agent Engine (managed mode)
#
# Vertex AI Agent Engine is Google's fully managed service for running agents.
# It handles scaling, infrastructure, and provides built-in integrations.
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - Vertex AI API enabled in your project
#   - ADK (Agent Development Kit) configured
#
# Usage:
#   ./deploy.sh              # Deploy to default project
#   ./deploy.sh test         # Run local test instead
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

echo "=============================================="
echo "Deploying to Vertex AI Agent Engine"
echo "=============================================="
echo "Project:  $PROJECT"
echo "Location: $LOCATION"
echo "Agent:    $AGENT_NAME"
echo ""

# Check for test mode
if [ "${1:-}" = "test" ]; then
    echo "Running local test..."
    cd "$PROJECT_DIR"
    
    # Ensure dependencies are installed
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
    
    $PYTHON_CMD "$DEPLOY_DIR/app.py"
    exit 0
fi

# Ensure gcloud is configured
gcloud config set project "$PROJECT" --quiet

# Package the agent for deployment
echo "Packaging agent..."
STAGING_DIR=$(mktemp -d)
cp -r "$PROJECT_DIR/_shared" "$STAGING_DIR/"
cp "$DEPLOY_DIR/app.py" "$STAGING_DIR/"
cp "$DEPLOY_DIR/requirements.txt" "$STAGING_DIR/"

# Create agent config for Agent Engine
cat > "$STAGING_DIR/agent.yaml" <<EOF
name: $AGENT_NAME
description: "SRE Agent with Cisco AI Defense protection"
entry_point: app.handle_request
runtime: python3.11
requirements: requirements.txt
EOF

echo ""
echo "Agent packaged in: $STAGING_DIR"
echo ""
echo "To deploy to Agent Engine, use one of these methods:"
echo ""
echo "1. Vertex AI Console:"
echo "   https://console.cloud.google.com/vertex-ai/agents"
echo ""
echo "2. Agent Builder SDK (Python):"
echo "   from vertexai.agents import Agent"
echo "   agent = Agent.create("
echo "       display_name='$AGENT_NAME',"
echo "       project='$PROJECT',"
echo "       location='$LOCATION',"
echo "       source_dir='$STAGING_DIR',"
echo "   )"
echo ""
echo "3. gcloud CLI (when available):"
echo "   gcloud ai agents create \\"
echo "       --display-name=$AGENT_NAME \\"
echo "       --project=$PROJECT \\"
echo "       --region=$LOCATION \\"
echo "       --source=$STAGING_DIR"
echo ""
echo "For more info: https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/set-up"
