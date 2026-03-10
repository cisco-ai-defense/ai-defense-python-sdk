#!/usr/bin/env bash
# =============================================================================
# Invoke Azure Function
# =============================================================================
# This script invokes the deployed Azure Function.
#
# Prerequisites:
#   - Azure CLI installed (az)
#   - Function app deployed via deploy.sh
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
# Preserve function app name if set by parent (e.g. --new-resources timestamped name)
_SAVED_FUNCTION_APP_NAME="${AZURE_FUNCTION_APP_NAME:-}"
AGENTSEC_EXAMPLES_DIR="$(cd "$ROOT_DIR/../.." && pwd)"
if [ -f "$AGENTSEC_EXAMPLES_DIR/.env" ]; then
    set -a
    source "$AGENTSEC_EXAMPLES_DIR/.env"
    set +a
fi
[ -n "$_SAVED_FUNCTION_APP_NAME" ] && export AZURE_FUNCTION_APP_NAME="$_SAVED_FUNCTION_APP_NAME"

# Validate required environment variables
: "${AZURE_FUNCTION_APP_NAME:?AZURE_FUNCTION_APP_NAME is required}"

# Get prompt from argument
PROMPT="${1:-Hello! What can you help me with?}"

echo "=============================================="
echo "Invoking Azure Function"
echo "=============================================="
echo "Function App: $AZURE_FUNCTION_APP_NAME"
echo "Prompt: $PROMPT"
echo ""

# Get function key
FUNCTION_KEY=$(az functionapp keys list \
    --name "$AZURE_FUNCTION_APP_NAME" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --query "functionKeys.default" -o tsv)

# Function URL
FUNCTION_URL="https://${AZURE_FUNCTION_APP_NAME}.azurewebsites.net/api/invoke?code=$FUNCTION_KEY"

# Invoke function with HTTP status code checking
RESPONSE_FILE=$(mktemp)
HTTP_CODE=$(curl -s -o "$RESPONSE_FILE" -w "%{http_code}" -X POST "$FUNCTION_URL" \
    -H "Content-Type: application/json" \
    -d "{\"prompt\": \"$PROMPT\"}")

RESPONSE=$(cat "$RESPONSE_FILE")
rm -f "$RESPONSE_FILE"

echo "=============================================="
echo "Response (HTTP $HTTP_CODE):"
echo "=============================================="

if [ "$HTTP_CODE" != "200" ]; then
    echo "ERROR: HTTP status code $HTTP_CODE"
    echo ""
fi

if [ -z "$RESPONSE" ]; then
    echo "(empty response)"
else
    echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
fi

# Exit with error if HTTP status is not 200
if [ "$HTTP_CODE" != "200" ]; then
    exit 1
fi
