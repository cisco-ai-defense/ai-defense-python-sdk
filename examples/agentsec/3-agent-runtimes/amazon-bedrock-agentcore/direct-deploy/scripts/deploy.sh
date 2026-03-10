#!/usr/bin/env bash
# =============================================================================
# Deploy AgentCore - Direct Code Deploy Mode
# =============================================================================
# This script deploys the agent to AWS using AgentCore's direct code deployment.
# The code is uploaded and executed directly in the AgentCore runtime.
#
# Prerequisites:
#   - AWS CLI configured (aws configure or aws sso login)
#   - bedrock-agentcore CLI installed (pip install bedrock-agentcore-starter-toolkit)
#   - Poetry dependencies installed (cd .. && poetry install)
#
# Usage:
#   ./scripts/deploy.sh
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

# Set defaults
export AWS_REGION="${AWS_REGION:-us-west-2}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-$AWS_REGION}"
export PYTHONPATH="$ROOT_DIR"

echo "=============================================="
echo "AgentCore Direct Code Deploy"
echo "=============================================="
echo "Region: $AWS_REGION"
echo "Root: $ROOT_DIR"
echo ""


# Agent name (override with AGENTCORE_DIRECT_AGENT_NAME for new resource names)
AGENT_NAME="${AGENTCORE_DIRECT_AGENT_NAME:-agentcore_sre_direct}"

# Configure the agent for direct_code_deploy (without -c to avoid container mode)
echo "Configuring agent: $AGENT_NAME"
poetry run agentcore configure \
    -e direct-deploy/agentcore_app.py \
    -n "$AGENT_NAME" \
    --disable-otel \
    -dt direct_code_deploy \
    -rt PYTHON_3_11 \
    -r "$AWS_REGION" \
    -ni

# Deploy the agent
echo ""
echo "Deploying agent: $AGENT_NAME"
poetry run agentcore deploy -a "$AGENT_NAME" -auc

echo ""
echo "=============================================="
echo "Deploy complete!"
echo "Run ./scripts/invoke.sh \"Your message\" to test"
echo "=============================================="
