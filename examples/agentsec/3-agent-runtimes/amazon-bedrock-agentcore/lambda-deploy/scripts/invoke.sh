#!/usr/bin/env bash
# =============================================================================
# Invoke AgentCore - Lambda Deploy Mode
# =============================================================================
# This script invokes the Lambda function via AWS CLI.
#
# Usage:
#   ./scripts/invoke.sh                    # Default greeting
#   ./scripts/invoke.sh "Your message"     # Custom message
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd "$DEPLOY_DIR/.." && pwd)"

cd "$ROOT_DIR"

# Load environment variables from shared examples/.env
EXAMPLES_DIR="$(cd "$ROOT_DIR/.." && pwd)"
if [ -f "$EXAMPLES_DIR/.env" ]; then
    set -a
    source "$EXAMPLES_DIR/.env"
    set +a
elif [ -f "$ROOT_DIR/.env" ]; then
    set -a
    source "$ROOT_DIR/.env"
    set +a
fi

export AWS_REGION="${AWS_REGION:-us-west-2}"
export FUNCTION_NAME="${FUNCTION_NAME:-agentcore-sre-lambda}"

PROMPT="${1:-Hello! Check payments health and summarize some logs.}"

echo "=============================================="
echo "Invoking AgentCore (Lambda Deploy)"
echo "=============================================="
echo "Function: $FUNCTION_NAME"
echo "Prompt: $PROMPT"
echo ""

# Create build directory if it doesn't exist
mkdir -p build

# Invoke the Lambda function
aws lambda invoke \
    --function-name "$FUNCTION_NAME" \
    --region "$AWS_REGION" \
    --cli-binary-format raw-in-base64-out \
    --payload "{\"prompt\":\"${PROMPT}\"}" \
    build/lambda_response.json

echo ""
echo "Response:"
cat build/lambda_response.json
echo ""
