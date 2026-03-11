#!/usr/bin/env bash
# =============================================================================
# Invoke Azure AI Foundry Managed Online Endpoint
# =============================================================================
# This script invokes the deployed agent endpoint.
#
# Prerequisites:
#   - Azure CLI installed (az)
#   - Logged in to Azure (az login)
#   - Endpoint deployed via deploy.sh
#
# Usage:
#   ./scripts/invoke.sh "Check the health of payments service"
#   ./scripts/invoke.sh "Fetch https://example.com and summarize it"
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Load environment variables
# Path: microsoft-foundry/ -> 3-agent-runtimes/ -> agentsec/
AGENTSEC_EXAMPLES_DIR="$(cd "$ROOT_DIR/../.." && pwd)"
if [ -f "$AGENTSEC_EXAMPLES_DIR/.env" ]; then
    set -a
    source "$AGENTSEC_EXAMPLES_DIR/.env"
    set +a
fi

# Configuration
ENDPOINT_NAME="${AGENT_ENDPOINT_NAME:-${ENDPOINT_NAME:-foundry-sre-agent}}"

# Validate required environment variables
: "${AZURE_SUBSCRIPTION_ID:?AZURE_SUBSCRIPTION_ID is required}"
: "${AZURE_RESOURCE_GROUP:?AZURE_RESOURCE_GROUP is required}"
: "${AZURE_AI_FOUNDRY_PROJECT:?AZURE_AI_FOUNDRY_PROJECT is required}"

# Get prompt from argument
PROMPT="${1:-Hello! What can you help me with?}"

echo "=============================================="
echo "Invoking Azure AI Foundry Endpoint"
echo "=============================================="
echo "Endpoint: $ENDPOINT_NAME"
echo "Prompt: $PROMPT"
echo ""

# Set subscription
az account set --subscription "$AZURE_SUBSCRIPTION_ID"

# Invoke endpoint
RESPONSE=$(az ml online-endpoint invoke \
    --name "$ENDPOINT_NAME" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --workspace-name "$AZURE_AI_FOUNDRY_PROJECT" \
    --request-file <(echo "{\"data\": {\"prompt\": \"$PROMPT\"}}")
)

echo "=============================================="
echo "Response:"
echo "=============================================="
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
