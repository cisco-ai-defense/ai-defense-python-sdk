#!/usr/bin/env bash
# =============================================================================
# Invoke AgentCore - Direct Code Deploy Mode
# =============================================================================
# This script invokes the deployed agent via the AgentCore CLI.
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

# Load environment variables from shared examples/.env (preserve name if set by parent e.g. --new-resources)
_SAVED_DIRECT_AGENT="${AGENTCORE_DIRECT_AGENT_NAME:-}"
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
[ -n "$_SAVED_DIRECT_AGENT" ] && export AGENTCORE_DIRECT_AGENT_NAME="$_SAVED_DIRECT_AGENT"

export AWS_REGION="${AWS_REGION:-us-west-2}"

PROMPT="${1:-Hello! Check payments health and summarize some logs.}"

echo "=============================================="
echo "Invoking AgentCore (Direct Deploy)"
echo "=============================================="
echo "Prompt: $PROMPT"
echo ""

AGENT_NAME="${AGENTCORE_DIRECT_AGENT_NAME:-agentcore_sre_direct}"
poetry run agentcore invoke --agent "$AGENT_NAME" "{\"prompt\":\"${PROMPT}\"}"
