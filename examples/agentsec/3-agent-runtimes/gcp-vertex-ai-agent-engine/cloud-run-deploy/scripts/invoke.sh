#!/usr/bin/env bash
# =============================================================================
# Invoke the Cloud Run SRE agent with AI Defense protection
# =============================================================================
#
# Usage:
#   ./invoke.sh "Check the health of my services"
#   ./invoke.sh                                    # Uses default prompt
#   ./invoke.sh --local "Test prompt"              # Run locally (not deployed)
#
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$(dirname "$DEPLOY_DIR")"
EXAMPLES_DIR="$(dirname "$PROJECT_DIR")"

# Load environment (check multiple locations)
ENV_FILE=""
if [ -f "$EXAMPLES_DIR/.env" ]; then
    ENV_FILE="$EXAMPLES_DIR/.env"
elif [ -f "$EXAMPLES_DIR/../.env" ]; then
    ENV_FILE="$EXAMPLES_DIR/../.env"
fi

if [ -n "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE" 2>/dev/null || true
    set +a
fi

# Configuration
PROJECT="${GOOGLE_CLOUD_PROJECT:?Error: GOOGLE_CLOUD_PROJECT not set. Please set it in .env or export it.}"
LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
SERVICE_NAME="${CLOUD_RUN_SERVICE:-sre-agent-cloudrun}"

# Default prompt
PROMPT="${1:-What are 2 benefits of using AI for SRE tasks? Reply briefly.}"

# Check for local mode
if [ "$PROMPT" = "--local" ]; then
    PROMPT="${2:-What are 2 benefits of using AI for SRE tasks? Reply briefly.}"
    
    echo "=============================================="
    echo "Running locally (not deployed)"
    echo "=============================================="
    cd "$PROJECT_DIR"
    
    poetry install --quiet 2>/dev/null || poetry install
    
    export PYTHONPATH="$PROJECT_DIR"
    export GOOGLE_CLOUD_PROJECT="$PROJECT"
    export GOOGLE_CLOUD_LOCATION="$LOCATION"
    export GOOGLE_GENAI_USE_VERTEXAI="True"
    
    echo "Prompt: $PROMPT"
    echo "----------------------------------------------"
    
    poetry run python -c "
import sys
sys.path.insert(0, '$PROJECT_DIR')
from _shared.agent_factory import invoke_agent

prompt = '''$PROMPT'''
result = invoke_agent(prompt)
print(result)
"
    exit 0
fi

# Get service URL
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --platform managed \
    --region "$LOCATION" \
    --format 'value(status.url)' 2>/dev/null || echo "")

if [ -z "$SERVICE_URL" ]; then
    echo "Error: Cloud Run service '$SERVICE_NAME' not found in $LOCATION"
    echo ""
    echo "Deploy first with: ./deploy.sh"
    exit 1
fi

echo "=============================================="
echo "Invoking Cloud Run Service"
echo "=============================================="
echo "Service: $SERVICE_NAME"
echo "URL:     $SERVICE_URL"
echo "Prompt:  $PROMPT"
echo "----------------------------------------------"

# Get identity token for authenticated request
TOKEN=$(gcloud auth print-identity-token 2>/dev/null || echo "")

# Invoke the service and capture response
if [ -n "$TOKEN" ]; then
    RESPONSE=$(curl -s -X POST "$SERVICE_URL/invoke" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"prompt\": \"$PROMPT\"}")
else
    RESPONSE=$(curl -s -X POST "$SERVICE_URL/invoke" \
        -H "Content-Type: application/json" \
        -d "{\"prompt\": \"$PROMPT\"}")
fi

# Pretty print if possible
if command -v python3 &> /dev/null; then
    echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
else
    echo "$RESPONSE"
fi

echo ""
echo "----------------------------------------------"
echo "To view AI Defense logs:"
echo "  gcloud run services logs read $SERVICE_NAME --region $LOCATION --limit 50"
