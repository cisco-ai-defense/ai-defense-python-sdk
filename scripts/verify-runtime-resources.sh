#!/usr/bin/env bash
#
# Verify that runtime resources from the last --new-resources run exist in each CSP.
# Run after: ./scripts/run-integration-tests.sh --runtimes --deploy --new-resources
#
# Usage: ./scripts/verify-runtime-resources.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LAST_RESOURCES_FILE="$SCRIPT_DIR/.last_new_resources_run"
ENV_FILE="$PROJECT_DIR/examples/agentsec/.env"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

if [ ! -f "$LAST_RESOURCES_FILE" ]; then
    echo -e "${RED}No .last_new_resources_run found. Run with --runtimes --deploy --new-resources first.${NC}"
    exit 1
fi

set -a
source "$LAST_RESOURCES_FILE"
[ -f "$ENV_FILE" ] && source "$ENV_FILE"
set +a

PASS=0
FAIL=0

check() {
    if [ $? -eq 0 ]; then
        echo -e "  ${GREEN}✓${NC} $1"
        PASS=$((PASS + 1))
        return 0
    else
        echo -e "  ${RED}✗${NC} $1"
        FAIL=$((FAIL + 1))
        return 1
    fi
}

echo -e "${BLUE}=============================================="
echo "  Verifying runtime resources in each CSP"
echo -e "==============================================${NC}"
echo "  Suffix AWS: $RESOURCE_SUFFIX_AWS  Azure: $RESOURCE_SUFFIX_AZURE  GCP: $RESOURCE_SUFFIX"
echo ""

# AWS (skip if no AWS resource names from this run, e.g. single-CSP run was Azure only)
echo -e "${BLUE}--- AWS Bedrock / Lambda ---${NC}"
if [ -z "${FUNCTION_NAME:-}" ]; then
    echo -e "  ${YELLOW}skip${NC} no AWS resource names in .last_new_resources_run"
elif command -v aws &>/dev/null; then
    export AWS_REGION="${AWS_REGION:-us-east-1}"
    aws lambda get-function --function-name "${FUNCTION_NAME}" --region "$AWS_REGION" &>/dev/null
    check "Lambda: $FUNCTION_NAME"
else
    echo -e "  ${YELLOW}skip${NC} aws CLI not found"
fi
echo ""

# GCP (skip if no GCP resource name, e.g. single-CSP run was not GCP)
echo -e "${BLUE}--- GCP Vertex AI Agent Engine ---${NC}"
GCP_RESOURCE_FILE="$PROJECT_DIR/examples/agentsec/3-agent-runtimes/gcp-vertex-ai-agent-engine/agent-engine-deploy/scripts/.agent_resource"
if [ -z "${AGENT_ENGINE_NAME:-}" ]; then
    echo -e "  ${YELLOW}skip${NC} no GCP resource name in .last_new_resources_run"
elif [ -f "$GCP_RESOURCE_FILE" ] && [ -n "${GOOGLE_CLOUD_PROJECT:-}" ] && [ -n "${GOOGLE_CLOUD_LOCATION:-}" ]; then
    GCP_RESOURCE=$(cat "$GCP_RESOURCE_FILE")
    if command -v gcloud &>/dev/null; then
        # List reasoning engines and grep for our resource ID (last segment of full path)
        ENGINE_ID="${GCP_RESOURCE##*/}"
        LIST=$(gcloud alpha ai reasoning-engines list --project="${GOOGLE_CLOUD_PROJECT}" --region="${GOOGLE_CLOUD_LOCATION}" --format="value(name)" 2>/dev/null) || true
        if echo "$LIST" | grep -q "$ENGINE_ID"; then
            check "Reasoning engine: $AGENT_ENGINE_NAME"
        else
            echo -e "  ${RED}✗${NC} Reasoning engine not found: $AGENT_ENGINE_NAME"
            FAIL=$((FAIL + 1))
        fi
    else
        echo -e "  ${YELLOW}skip${NC} gcloud not found"
    fi
else
    echo -e "  ${YELLOW}skip${NC} .agent_resource or GCP env missing"
fi
echo ""

# Azure (skip if no Azure resource names, e.g. single-CSP run was not Azure)
echo -e "${BLUE}--- Azure ML + Function App ---${NC}"
if [ -z "${AGENT_ENDPOINT_NAME:-}" ] && [ -z "${AZURE_FUNCTION_APP_NAME:-}" ]; then
    echo -e "  ${YELLOW}skip${NC} no Azure resource names in .last_new_resources_run"
elif command -v az &>/dev/null && [ -n "${AZURE_RESOURCE_GROUP:-}" ] && [ -n "${AZURE_AI_FOUNDRY_PROJECT:-}" ]; then
    az account set --subscription "${AZURE_SUBSCRIPTION_ID}" &>/dev/null || true
    az ml online-endpoint show --name "${AGENT_ENDPOINT_NAME}" --resource-group "$AZURE_RESOURCE_GROUP" --workspace-name "$AZURE_AI_FOUNDRY_PROJECT" &>/dev/null
    check "ML endpoint (agent): $AGENT_ENDPOINT_NAME"

    az ml online-endpoint show --name "${CONTAINER_ENDPOINT_NAME}" --resource-group "$AZURE_RESOURCE_GROUP" --workspace-name "$AZURE_AI_FOUNDRY_PROJECT" &>/dev/null
    check "ML endpoint (container): $CONTAINER_ENDPOINT_NAME"

    az functionapp show --name "${AZURE_FUNCTION_APP_NAME}" --resource-group "$AZURE_RESOURCE_GROUP" &>/dev/null
    check "Function App: $AZURE_FUNCTION_APP_NAME"
else
    echo -e "  ${YELLOW}skip${NC} az CLI not found or Azure env not set"
fi
echo ""

echo -e "${BLUE}=============================================="
echo "  Verification summary"
echo -e "==============================================${NC}"
echo -e "  ${GREEN}Pass: $PASS${NC}  ${RED}Fail: $FAIL${NC}"
if [ $FAIL -gt 0 ]; then
    exit 1
fi
exit 0
