#!/usr/bin/env bash
# =============================================================================
# Deploy to Azure AI Foundry - Container Deployment
# =============================================================================
# This script builds and deploys the agent as a container to Azure AI Foundry
# using Azure Container Registry (ACR).
#
# Prerequisites:
#   - Azure CLI installed (az)
#   - Azure ML CLI extension (az extension add -n ml)
#   - Docker installed and running
#   - Logged in to Azure (az login)
#   - Environment variables configured in examples/.env
#
# Usage:
#   ./scripts/deploy.sh
#
# Environment Variables Required:
#   AZURE_SUBSCRIPTION_ID - Azure subscription ID
#   AZURE_RESOURCE_GROUP - Resource group name
#   AZURE_AI_FOUNDRY_PROJECT - AI Foundry project/workspace name
#   AZURE_ACR_NAME - Azure Container Registry name
#   AZURE_ACR_LOGIN_SERVER - ACR login server (e.g., myacr.azurecr.io)
#   AZURE_OPENAI_ENDPOINT - Azure OpenAI endpoint
#   AZURE_OPENAI_API_KEY - Azure OpenAI API key
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd "$DEPLOY_DIR/.." && pwd)"

cd "$ROOT_DIR"

# Load environment variables from shared examples/agentsec/.env
# Path: microsoft-foundry/ -> 3-agent-runtimes/ -> agentsec/
# Preserve endpoint names if set by parent (e.g. --new-resources timestamped names)
_SAVED_CONTAINER_ENDPOINT="${CONTAINER_ENDPOINT_NAME:-}"
AGENTSEC_EXAMPLES_DIR="$(cd "$ROOT_DIR/../.." && pwd)"
if [ -f "$AGENTSEC_EXAMPLES_DIR/.env" ]; then
    set -a
    source "$AGENTSEC_EXAMPLES_DIR/.env"
    set +a
fi
[ -n "$_SAVED_CONTAINER_ENDPOINT" ] && export CONTAINER_ENDPOINT_NAME="$_SAVED_CONTAINER_ENDPOINT"

# Validate required environment variables
: "${AZURE_SUBSCRIPTION_ID:?AZURE_SUBSCRIPTION_ID is required}"
: "${AZURE_RESOURCE_GROUP:?AZURE_RESOURCE_GROUP is required}"
: "${AZURE_AI_FOUNDRY_PROJECT:?AZURE_AI_FOUNDRY_PROJECT is required}"
: "${AZURE_ACR_NAME:?AZURE_ACR_NAME is required}"
: "${AZURE_ACR_LOGIN_SERVER:?AZURE_ACR_LOGIN_SERVER is required}"

# Configuration
IMAGE_NAME="${IMAGE_NAME:-foundry-sre-agent}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
ENDPOINT_NAME="${CONTAINER_ENDPOINT_NAME:-${ENDPOINT_NAME:-foundry-sre-container}}"
DEPLOYMENT_NAME="${DEPLOYMENT_NAME:-default}"
INSTANCE_TYPE="${INSTANCE_TYPE:-Standard_DS3_v2}"
INSTANCE_COUNT="${INSTANCE_COUNT:-1}"

FULL_IMAGE_NAME="$AZURE_ACR_LOGIN_SERVER/$IMAGE_NAME:$IMAGE_TAG"

echo "=============================================="
echo "Azure AI Foundry - Container Deployment"
echo "=============================================="
echo "Subscription: $AZURE_SUBSCRIPTION_ID"
echo "Resource Group: $AZURE_RESOURCE_GROUP"
echo "Workspace: $AZURE_AI_FOUNDRY_PROJECT"
echo "ACR: $AZURE_ACR_LOGIN_SERVER"
echo "Image: $FULL_IMAGE_NAME"
echo "Endpoint: $ENDPOINT_NAME"
echo ""

# Set Azure subscription
echo "Setting Azure subscription..."
az account set --subscription "$AZURE_SUBSCRIPTION_ID"

# Copy agentsec source to the build context (it's not on PyPI)
# Remove copy on exit (success or failure) so it doesn't shadow repo aidefense for MCP tests
cleanup_on_exit() {
    rm -rf "$ROOT_DIR/aidefense" 2>/dev/null || true
    # Remove generated YAML files that may contain credentials
    rm -f "$DEPLOY_DIR/deployment.yaml" "$DEPLOY_DIR/endpoint.yaml" 2>/dev/null || true
}
trap cleanup_on_exit EXIT

echo "Copying aidefense SDK source to build context..."
# Path: agentsec/ -> examples/ -> repo-root/aidefense/
AIDEFENSE_SRC="$AGENTSEC_EXAMPLES_DIR/../../aidefense"
if [ -d "$AIDEFENSE_SRC" ]; then
    rm -rf "$ROOT_DIR/aidefense" 2>/dev/null || true
    cp -R "$AIDEFENSE_SRC" "$ROOT_DIR/aidefense"
    echo "Copied aidefense from $AIDEFENSE_SRC to $ROOT_DIR/aidefense"
else
    echo "ERROR: aidefense source not found at $AIDEFENSE_SRC"
    exit 1
fi

# Login to ACR
echo "Logging in to ACR..."
az acr login --name "$AZURE_ACR_NAME"

# Build and push the container image using ACR Build
echo "Building and pushing container image..."
az acr build \
    --registry "$AZURE_ACR_NAME" \
    --image "$IMAGE_NAME:$IMAGE_TAG" \
    --file foundry-container/Dockerfile \
    .

# Create endpoint configuration YAML
cat > "$DEPLOY_DIR/endpoint.yaml" << EOF
\$schema: https://azuremlsdk2.blob.core.windows.net/latest/managedOnlineEndpoint.schema.json
name: $ENDPOINT_NAME
auth_mode: key
EOF

# Create deployment configuration YAML
# NOTE: For custom containers (BYOC), the model section is optional.
# Azure ML inference server (azmlinfsrv) uses "/" for liveness/readiness and "/score" for scoring.
# Use unique environment name per endpoint to avoid "Cannot override existing endpoint: InferenceLiveness".
cat > "$DEPLOY_DIR/deployment.yaml" << EOF
\$schema: https://azuremlschemas.azureedge.net/latest/managedOnlineDeployment.schema.json
name: $DEPLOYMENT_NAME
endpoint_name: $ENDPOINT_NAME
environment:
  name: foundry-container-env-${ENDPOINT_NAME}
  image: $FULL_IMAGE_NAME
  inference_config:
    liveness_route:
      port: 5001
      path: /
    readiness_route:
      port: 5001
      path: /
    scoring_route:
      port: 5001
      path: /score
instance_type: $INSTANCE_TYPE
instance_count: $INSTANCE_COUNT
request_settings:
  request_timeout_ms: 120000
  max_concurrent_requests_per_instance: 1
environment_variables:
  AZURE_OPENAI_ENDPOINT: "$AZURE_OPENAI_ENDPOINT"
  AZURE_OPENAI_API_KEY: "$AZURE_OPENAI_API_KEY"
  AZURE_OPENAI_DEPLOYMENT_NAME: "${AZURE_OPENAI_DEPLOYMENT_NAME:-gpt-4o}"
  AZURE_OPENAI_API_VERSION: "${AZURE_OPENAI_API_VERSION:-2024-08-01-preview}"
  AGENTSEC_LLM_INTEGRATION_MODE: "${AGENTSEC_LLM_INTEGRATION_MODE:-api}"
  AGENTSEC_MCP_INTEGRATION_MODE: "${AGENTSEC_MCP_INTEGRATION_MODE:-api}"
  AGENTSEC_API_MODE_LLM: "${AGENTSEC_API_MODE_LLM:-monitor}"
  AGENTSEC_API_MODE_MCP: "${AGENTSEC_API_MODE_MCP:-monitor}"
  AI_DEFENSE_API_MODE_LLM_ENDPOINT: "${AI_DEFENSE_API_MODE_LLM_ENDPOINT:-}"
  AI_DEFENSE_API_MODE_LLM_API_KEY: "${AI_DEFENSE_API_MODE_LLM_API_KEY:-}"
  MCP_SERVER_URL: "${MCP_SERVER_URL:-}"
EOF

# Create or update endpoint
echo "Creating/updating endpoint..."
if az ml online-endpoint show --name "$ENDPOINT_NAME" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --workspace-name "$AZURE_AI_FOUNDRY_PROJECT" &>/dev/null; then
    echo "Endpoint exists, updating..."
else
    echo "Creating new endpoint..."
    az ml online-endpoint create \
        --file "$DEPLOY_DIR/endpoint.yaml" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --workspace-name "$AZURE_AI_FOUNDRY_PROJECT"
fi

# Create or update deployment
echo "Creating/updating deployment..."
if az ml online-deployment show --name "$DEPLOYMENT_NAME" --endpoint-name "$ENDPOINT_NAME" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --workspace-name "$AZURE_AI_FOUNDRY_PROJECT" &>/dev/null; then
    echo "Deployment exists, updating..."
    az ml online-deployment update \
        --file "$DEPLOY_DIR/deployment.yaml" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --workspace-name "$AZURE_AI_FOUNDRY_PROJECT"
else
    echo "Creating new deployment..."
    az ml online-deployment create \
        --file "$DEPLOY_DIR/deployment.yaml" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --workspace-name "$AZURE_AI_FOUNDRY_PROJECT" \
        --all-traffic
fi

# Get endpoint URL
ENDPOINT_URL=$(az ml online-endpoint show \
    --name "$ENDPOINT_NAME" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --workspace-name "$AZURE_AI_FOUNDRY_PROJECT" \
    --query "scoring_uri" -o tsv)

echo ""
echo "=============================================="
echo "Deployment complete!"
echo "=============================================="
echo "Image: $FULL_IMAGE_NAME"
echo "Endpoint URL: $ENDPOINT_URL"
echo ""
echo "Run ./scripts/invoke.sh \"Your message\" to test"
echo "=============================================="
