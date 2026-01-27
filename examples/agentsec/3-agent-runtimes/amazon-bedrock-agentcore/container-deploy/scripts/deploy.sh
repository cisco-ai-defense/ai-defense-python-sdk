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
export ECR_URI="${ECR_URI:-422940237045.dkr.ecr.us-west-2.amazonaws.com/bedrock-agentcore-my_agent}"

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

# Configure the agent for container deployment
echo "Configuring agent for container deployment..."
poetry run agentcore configure -c \
    -e container-deploy/agentcore_app.py \
    -rf container-deploy/requirements.txt \
    -n agentcore_sre_container \
    --ecr "$ECR_URI" \
    --disable-otel \
    -dt container \
    -r "$AWS_REGION" \
    -ni

# Deploy the agent (builds in cloud with CodeBuild, pushes, and registers)
echo ""
echo "Building and deploying container..."
poetry run agentcore deploy -a agentcore_sre_container -auc

echo ""
echo "=============================================="
echo "Deploy complete!"
echo "Run ./scripts/invoke.sh \"Your message\" to test"
echo "=============================================="
