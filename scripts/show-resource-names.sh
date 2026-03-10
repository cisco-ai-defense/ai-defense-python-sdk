#!/usr/bin/env bash
#
# Print latest/configured resource names for agent runtime deployments.
# If scripts/.last_new_resources_run exists (from a recent --new-resources run), those names are shown.
# Otherwise uses examples/agentsec/.env and script defaults.
#
# Usage:
#   ./scripts/show-resource-names.sh           # Latest or configured names
#   ./scripts/show-resource-names.sh --live    # Also query Azure for current endpoints/functions (requires az login)
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_DIR/examples/agentsec/.env"
LAST_RESOURCES_FILE="$SCRIPT_DIR/.last_new_resources_run"

# Load .env first for project/resource-group and defaults
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

# Prefer last --new-resources run for resource names (overlay on top of .env)
if [ -f "$LAST_RESOURCES_FILE" ]; then
    echo "=============================================="
    echo "  Latest resource names (from last --new-resources run)"
    echo "=============================================="
    echo "  Source: scripts/.last_new_resources_run"
    echo ""
    set -a
    source "$LAST_RESOURCES_FILE"
    set +a
else
    echo "=============================================="
    echo "  Resource names (from .env and defaults)"
    echo "=============================================="
    echo "  (Run integration tests with --new-resources to write scripts/.last_new_resources_run)"
    echo ""
    AGENT_ENDPOINT_NAME="${AGENT_ENDPOINT_NAME:-foundry-sre-agent}"
    CONTAINER_ENDPOINT_NAME="${CONTAINER_ENDPOINT_NAME:-foundry-sre-container}"
    AZURE_FUNCTION_APP_NAME="${AZURE_FUNCTION_APP_NAME:-aid-sre-agent-func}"
fi

echo "Azure (resource group: ${AZURE_RESOURCE_GROUP:-?}, workspace: ${AZURE_AI_FOUNDRY_PROJECT:-?})"
echo "  Agent App endpoint:    $AGENT_ENDPOINT_NAME"
echo "  Container endpoint:   $CONTAINER_ENDPOINT_NAME"
echo "  Function App:         $AZURE_FUNCTION_APP_NAME"
echo ""

# GCP (from .agent_resource if deployed)
GCP_RESOURCE_FILE="$PROJECT_DIR/examples/agentsec/3-agent-runtimes/gcp-vertex-ai-agent-engine/agent-engine-deploy/scripts/.agent_resource"
if [ -f "$GCP_RESOURCE_FILE" ]; then
    echo "GCP Vertex AI Agent Engine (from last deploy)"
    echo "  Resource: $(cat "$GCP_RESOURCE_FILE")"
    echo "  (Name: ${AGENT_ENGINE_NAME:-sre-agent-engine})"
else
    echo "GCP Vertex AI Agent Engine: not deployed or .agent_resource missing"
    echo "  Default name: ${AGENT_ENGINE_NAME:-sre-agent-engine}"
fi
echo ""

# AWS (from .env or defaults)
echo "AWS Bedrock AgentCore"
echo "  Direct agent:    ${AGENTCORE_DIRECT_AGENT_NAME:-agentcore_sre_direct}"
echo "  Container agent: ${AGENTCORE_CONTAINER_AGENT_NAME:-agentcore_sre_container}"
echo "  Lambda:          ${FUNCTION_NAME:-agentcore-sre-lambda}"
echo ""

# Optional: list live Azure resources
if [ "${1:-}" = "--live" ]; then
    echo "=============================================="
    echo "  Azure live resources (az list)"
    echo "=============================================="
    if [ -z "${AZURE_RESOURCE_GROUP:-}" ] || [ -z "${AZURE_AI_FOUNDRY_PROJECT:-}" ]; then
        echo "  Set AZURE_RESOURCE_GROUP and AZURE_AI_FOUNDRY_PROJECT (e.g. in .env) to list."
    else
        echo ""
        echo "Online endpoints (ML workspace):"
        az ml online-endpoint list \
            --resource-group "$AZURE_RESOURCE_GROUP" \
            --workspace-name "$AZURE_AI_FOUNDRY_PROJECT" \
            --query "[].{name:name, state:provisioning_state}" -o table 2>/dev/null || echo "  (az login or permissions needed)"
        echo ""
        echo "Function Apps:"
        az functionapp list --resource-group "$AZURE_RESOURCE_GROUP" \
            --query "[].{name:name, state:state}" -o table 2>/dev/null || echo "  (az login or permissions needed)"
    fi
fi
