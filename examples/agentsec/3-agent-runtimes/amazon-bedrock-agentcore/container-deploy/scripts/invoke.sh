#!/usr/bin/env bash
# =============================================================================
# Invoke AgentCore - Container Deploy Mode
# =============================================================================
# This script invokes the deployed container agent via the AgentCore CLI.
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

PROMPT="${1:-Hello! Check payments health and summarize some logs.}"

echo "=============================================="
echo "Invoking AgentCore (Container Deploy)"
echo "=============================================="
echo "Prompt: $PROMPT"
echo ""

poetry run agentcore invoke --agent agentcore_sre_container "{\"prompt\":\"${PROMPT}\"}"
