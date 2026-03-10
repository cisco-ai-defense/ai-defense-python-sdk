#!/usr/bin/env bash
# =============================================================================
# Invoke the GKE SRE agent with AI Defense protection
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
CLUSTER_NAME="${GKE_CLUSTER:-sre-agent-cluster}"

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

# Get cluster credentials
echo "Getting cluster credentials..."
gcloud container clusters get-credentials "$CLUSTER_NAME" \
    --region "$LOCATION" \
    --project "$PROJECT" \
    2>/dev/null || {
    echo "Error: Could not get cluster credentials for '$CLUSTER_NAME'"
    echo ""
    echo "Setup cluster first with: ./deploy.sh setup"
    exit 1
}

# Get service external IP
EXTERNAL_IP=$(kubectl get service sre-agent-service -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")

if [ -z "$EXTERNAL_IP" ]; then
    echo "External IP not yet assigned. Using port-forward instead..."
    
    # Start port-forward in background
    kubectl port-forward service/sre-agent-service 8080:80 &
    PF_PID=$!
    sleep 3
    
    cleanup() {
        kill $PF_PID 2>/dev/null || true
    }
    trap cleanup EXIT
    
    SERVICE_URL="http://localhost:8080"
else
    SERVICE_URL="http://$EXTERNAL_IP"
fi

echo "=============================================="
echo "Invoking GKE Service"
echo "=============================================="
echo "Cluster: $CLUSTER_NAME"
echo "URL:     $SERVICE_URL"
echo "Prompt:  $PROMPT"
echo "----------------------------------------------"

# Invoke the service and capture response
RESPONSE=$(curl -s -X POST "$SERVICE_URL/invoke" \
    -H "Content-Type: application/json" \
    -d "{\"prompt\": \"$PROMPT\"}")

# Pretty print if possible
if command -v python3 &> /dev/null; then
    echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
else
    echo "$RESPONSE"
fi

echo ""
echo "----------------------------------------------"
echo "To view AI Defense logs:"
echo "  kubectl logs -l app=sre-agent --tail=100"
