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


# Configure the agent for direct_code_deploy (without -c to avoid container mode)
echo "Configuring agent..."
poetry run agentcore configure \
    -e direct-deploy/agentcore_app.py \
    -n agentcore_sre_direct \
    --disable-otel \
    -dt direct_code_deploy \
    -rt PYTHON_3_11 \
    -r "$AWS_REGION" \
    -ni

# Deploy the agent
echo ""
echo "Deploying agent..."
poetry run agentcore deploy -a agentcore_sre_direct -auc

echo ""
echo "=============================================="
echo "Deploy complete!"
echo "Run ./scripts/invoke.sh \"Your message\" to test"
echo "=============================================="
