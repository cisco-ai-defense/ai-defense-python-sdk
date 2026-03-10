#!/usr/bin/env bash
# =============================================================================
# Deploy AgentCore - Container Deploy Mode
# =============================================================================
# This script deploys the agent to AWS using AgentCore's container deployment.
# It builds a Docker image, pushes to ECR, and registers with AgentCore.
#
# Prerequisites:
#   - AWS CLI configured (aws configure or aws sso login)
#   - Docker installed and running
#   - ECR repository created (see ECR_URI in .env)
#   - bedrock-agentcore CLI installed
#   - Poetry dependencies installed (cd .. && poetry install)
#
# Usage:
#   ./scripts/deploy.sh
#
# Environment Variables:
#   ECR_URI - ECR repository URI for the container image
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd "$DEPLOY_DIR/.." && pwd)"

cd "$ROOT_DIR"

# Load environment variables from shared examples/.env (preserve name if set by parent e.g. --new-resources)
_SAVED_CONTAINER_AGENT="${AGENTCORE_CONTAINER_AGENT_NAME:-}"
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
[ -n "$_SAVED_CONTAINER_AGENT" ] && export AGENTCORE_CONTAINER_AGENT_NAME="$_SAVED_CONTAINER_AGENT"

# Set defaults - Container deploy requires ECR in the same region
# Default to us-west-2 where the existing ECR repo lives
export AWS_REGION="${AWS_REGION:-us-west-2}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-$AWS_REGION}"
export PYTHONPATH="$ROOT_DIR"

# Get AWS account ID for ECR URI
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "422940237045")}"

# ECR URI must be in the same region as the agent
# Default to existing repo in us-west-2
export ECR_URI="${ECR_URI:-${AWS_ACCOUNT_ID}.dkr.ecr.us-west-2.amazonaws.com/bedrock-agentcore-my_agent}"

# Extract region from ECR URI and ensure agent region matches
ECR_REGION=$(echo "$ECR_URI" | sed -n 's|.*\.ecr\.\([^.]*\)\.amazonaws\.com.*|\1|p')
if [ -n "$ECR_REGION" ] && [ "$ECR_REGION" != "$AWS_REGION" ]; then
    echo "WARNING: ECR region ($ECR_REGION) differs from AWS_REGION ($AWS_REGION)"
    echo "Setting AWS_REGION to match ECR region for container deployment"
    export AWS_REGION="$ECR_REGION"
    export AWS_DEFAULT_REGION="$ECR_REGION"
fi

echo "=============================================="
echo "AgentCore Container Deploy"
echo "=============================================="
echo "Region: $AWS_REGION"
echo "ECR: $ECR_URI"
echo "Root: $ROOT_DIR"
echo ""

# Copy aidefense SDK source to the build context (includes agentsec at aidefense/runtime/agentsec)
echo "Copying aidefense SDK source to build context..."
AIDEFENSE_SRC="$ROOT_DIR/../../../../aidefense"
if [ -d "$AIDEFENSE_SRC" ]; then
    cp -R "$AIDEFENSE_SRC" "$ROOT_DIR/"
    echo "Copied aidefense from $AIDEFENSE_SRC"
else
    echo "ERROR: aidefense SDK source not found at $AIDEFENSE_SRC"
    exit 1
fi

# Copy Dockerfile to root (agentcore CLI expects it at root level)
echo "Copying Dockerfile to root..."
cp "$DEPLOY_DIR/Dockerfile" "$ROOT_DIR/Dockerfile"

# Copy .env file to root for container to use
echo "Copying .env to root..."
if [ -f "$EXAMPLES_DIR/.env" ]; then
    cp "$EXAMPLES_DIR/.env" "$ROOT_DIR/.env"
    echo "Copied .env from $EXAMPLES_DIR/.env"
fi

# Agent name (override with AGENTCORE_CONTAINER_AGENT_NAME for new resource names)
AGENT_NAME="${AGENTCORE_CONTAINER_AGENT_NAME:-agentcore_sre_container}"

# Configure the agent for container deployment
echo "Configuring agent: $AGENT_NAME"
poetry run agentcore configure -c \
    -e container-deploy/agentcore_app.py \
    -rf container-deploy/requirements.txt \
    -n "$AGENT_NAME" \
    --ecr "$ECR_URI" \
    --disable-otel \
    -dt container \
    -r "$AWS_REGION" \
    -ni

# Deploy the agent (builds in cloud with CodeBuild, pushes, and registers)
echo ""
echo "Building and deploying container: $AGENT_NAME"
poetry run agentcore deploy -a "$AGENT_NAME" -auc

echo ""
echo "=============================================="
echo "Deploy complete!"
echo "Run ./scripts/invoke.sh \"Your message\" to test"
echo "=============================================="
