#!/usr/bin/env bash
# =============================================================================
# Deploy to Azure Functions
# =============================================================================
# This script deploys the agent as an Azure Function App.
#
# Prerequisites:
#   - Azure CLI installed (az)
#   - Azure Functions Core Tools installed (func)
#   - Logged in to Azure (az login)
#   - Environment variables configured in examples/.env
#
# Usage:
#   ./scripts/deploy.sh
#
# Environment Variables Required:
#   AZURE_SUBSCRIPTION_ID - Azure subscription ID
#   AZURE_RESOURCE_GROUP - Resource group name
#   AZURE_FUNCTION_APP_NAME - Function app name
#   AZURE_STORAGE_ACCOUNT - Storage account name
#   AZURE_OPENAI_ENDPOINT - Azure OpenAI endpoint
#   AZURE_OPENAI_API_KEY - Azure OpenAI API key
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd "$DEPLOY_DIR/.." && pwd)"

cd "$DEPLOY_DIR"

# Load environment variables from shared examples/agentsec/.env
# Path: microsoft-foundry/ -> 3-agent-runtimes/ -> agentsec/
# Preserve function app name if set by parent (e.g. --new-resources timestamped name for new deployment)
_SAVED_FUNCTION_APP_NAME="${AZURE_FUNCTION_APP_NAME:-}"
AGENTSEC_EXAMPLES_DIR="$(cd "$ROOT_DIR/../.." && pwd)"
if [ -f "$AGENTSEC_EXAMPLES_DIR/.env" ]; then
    set -a
    source "$AGENTSEC_EXAMPLES_DIR/.env"
    set +a
fi
[ -n "$_SAVED_FUNCTION_APP_NAME" ] && export AZURE_FUNCTION_APP_NAME="$_SAVED_FUNCTION_APP_NAME"

# Validate required environment variables
: "${AZURE_SUBSCRIPTION_ID:?AZURE_SUBSCRIPTION_ID is required}"
: "${AZURE_RESOURCE_GROUP:?AZURE_RESOURCE_GROUP is required}"
: "${AZURE_FUNCTION_APP_NAME:?AZURE_FUNCTION_APP_NAME is required}"
: "${AZURE_STORAGE_ACCOUNT:?AZURE_STORAGE_ACCOUNT is required}"

# Configuration
LOCATION="${AZURE_LOCATION:-eastus}"
PYTHON_VERSION="${PYTHON_VERSION:-3.11}"

echo "=============================================="
echo "Azure Functions Deployment"
echo "=============================================="
echo "Subscription: $AZURE_SUBSCRIPTION_ID"
echo "Resource Group: $AZURE_RESOURCE_GROUP"
echo "Function App: $AZURE_FUNCTION_APP_NAME"
echo "Storage Account: $AZURE_STORAGE_ACCOUNT"
echo "Location: $LOCATION"
echo ""

# Azure Functions Core Tools required for publish
if ! command -v func &>/dev/null; then
    echo "ERROR: Azure Functions Core Tools (func) not found. Install and ensure 'func' is in PATH."
    echo "  macOS (Homebrew): brew tap azure/functions && brew install azure-functions-core-tools@4"
    echo "  Or: https://docs.microsoft.com/en-us/azure/azure-functions/functions-run-local"
    exit 1
fi

# Set Azure subscription
echo "Setting Azure subscription..."
az account set --subscription "$AZURE_SUBSCRIPTION_ID"

# Copy agentsec source to the deployment directory (it's not on PyPI)
echo "Copying aidefense SDK source..."
# Path: microsoft-foundry/ -> 3-agent-runtimes/ -> agentsec/ -> examples/ -> repo-root/aidefense/
AIDEFENSE_SRC="$AGENTSEC_EXAMPLES_DIR/../../aidefense"
if [ -d "$AIDEFENSE_SRC" ]; then
    rm -rf "$DEPLOY_DIR/aidefense" 2>/dev/null || true
    cp -R "$AIDEFENSE_SRC" "$DEPLOY_DIR/aidefense"
    echo "Copied aidefense from $AIDEFENSE_SRC to $DEPLOY_DIR/aidefense"
else
    echo "ERROR: aidefense source not found at $AIDEFENSE_SRC"
    exit 1
fi

# Copy shared code
echo "Copying shared code..."
rm -rf "$DEPLOY_DIR/_shared" 2>/dev/null || true
cp -R "$ROOT_DIR/_shared" "$DEPLOY_DIR/"

# Create resource group if it doesn't exist
if ! az group show --name "$AZURE_RESOURCE_GROUP" &>/dev/null; then
    echo "Creating resource group..."
    az group create --name "$AZURE_RESOURCE_GROUP" --location "$LOCATION"
fi

# Create storage account if it doesn't exist
if ! az storage account show --name "$AZURE_STORAGE_ACCOUNT" --resource-group "$AZURE_RESOURCE_GROUP" &>/dev/null; then
    echo "Creating storage account..."
    az storage account create \
        --name "$AZURE_STORAGE_ACCOUNT" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --location "$LOCATION" \
        --sku Standard_LRS
fi

# Create function app if it doesn't exist
if ! az functionapp show --name "$AZURE_FUNCTION_APP_NAME" --resource-group "$AZURE_RESOURCE_GROUP" &>/dev/null; then
    echo "Creating function app..."
    az functionapp create \
        --name "$AZURE_FUNCTION_APP_NAME" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --storage-account "$AZURE_STORAGE_ACCOUNT" \
        --consumption-plan-location "$LOCATION" \
        --runtime python \
        --runtime-version "$PYTHON_VERSION" \
        --functions-version 4 \
        --os-type Linux
fi

# Configure app settings
echo "Configuring app settings..."
az functionapp config appsettings set \
    --name "$AZURE_FUNCTION_APP_NAME" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --settings \
        "AZURE_OPENAI_ENDPOINT=$AZURE_OPENAI_ENDPOINT" \
        "AZURE_OPENAI_API_KEY=$AZURE_OPENAI_API_KEY" \
        "AZURE_OPENAI_DEPLOYMENT_NAME=${AZURE_OPENAI_DEPLOYMENT_NAME:-gpt-4o}" \
        "AZURE_OPENAI_API_VERSION=${AZURE_OPENAI_API_VERSION:-2024-08-01-preview}" \
        "AGENTSEC_LLM_INTEGRATION_MODE=${AGENTSEC_LLM_INTEGRATION_MODE:-api}" \
        "AGENTSEC_MCP_INTEGRATION_MODE=${AGENTSEC_MCP_INTEGRATION_MODE:-api}" \
        "AGENTSEC_LOG_LEVEL=${AGENTSEC_LOG_LEVEL:-DEBUG}" \
        "AGENTSEC_API_MODE_LLM=${AGENTSEC_API_MODE_LLM:-monitor}" \
        "AGENTSEC_API_MODE_MCP=${AGENTSEC_API_MODE_MCP:-monitor}" \
        "AI_DEFENSE_API_MODE_LLM_ENDPOINT=${AI_DEFENSE_API_MODE_LLM_ENDPOINT:-}" \
        "AI_DEFENSE_API_MODE_LLM_API_KEY=${AI_DEFENSE_API_MODE_LLM_API_KEY:-}" \
        "MCP_SERVER_URL=${MCP_SERVER_URL:-}" \
    --output none

# Deploy using Azure Functions Core Tools
echo "Deploying function app..."
func azure functionapp publish "$AZURE_FUNCTION_APP_NAME" --python

# Get function URL
FUNCTION_URL="https://${AZURE_FUNCTION_APP_NAME}.azurewebsites.net/api/invoke"

echo ""
echo "=============================================="
echo "Deployment complete!"
echo "=============================================="
echo "Function URL: $FUNCTION_URL"
echo ""
echo "Run ./scripts/invoke.sh \"Your message\" to test"
echo "=============================================="
