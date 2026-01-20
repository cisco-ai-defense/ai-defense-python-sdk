#!/usr/bin/env bash
# =============================================================================
# Deploy AgentCore - Lambda Deploy Mode
# =============================================================================
# This script deploys the agent to AWS Lambda.
# It creates a deployment package, IAM role, and Lambda function.
#
# Prerequisites:
#   - AWS CLI configured (aws configure or aws sso login)
#   - Poetry dependencies installed (cd .. && poetry install)
#
# Usage:
#   ./scripts/deploy.sh
#
# Environment Variables:
#   FUNCTION_NAME - Lambda function name (default: agentcore-sre-lambda)
#   ROLE_NAME - IAM role name (default: agentcore-lambda-role)
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
export ROLE_NAME="${ROLE_NAME:-agentcore-lambda-role}"
export FUNCTION_NAME="${FUNCTION_NAME:-agentcore-sre-lambda}"

echo "=============================================="
echo "AgentCore Lambda Deploy"
echo "=============================================="
echo "Region: $AWS_REGION"
echo "Function: $FUNCTION_NAME"
echo "Role: $ROLE_NAME"
echo "Root: $ROOT_DIR"
echo ""

# Create build directory
rm -rf build && mkdir -p build/lambda

# Install dependencies for Lambda (x86_64 platform)
echo "Installing dependencies for Lambda..."
poetry run pip install -r "$DEPLOY_DIR/requirements.txt" \
    --platform manylinux2014_x86_64 \
    --implementation cp \
    --python-version 311 \
    --only-binary=:all: \
    --target build/lambda

# Copy aidefense SDK source (includes agentsec at aidefense/runtime/agentsec)
echo "Copying aidefense SDK source..."
AIDEFENSE_SRC="$ROOT_DIR/../../../../aidefense"
if [ -d "$AIDEFENSE_SRC" ]; then
    cp -R "$AIDEFENSE_SRC" build/lambda/
else
    echo "ERROR: aidefense SDK source not found at $AIDEFENSE_SRC"
    exit 1
fi

# Copy _shared module (agent factory, tools, MCP tools)
echo "Copying _shared module..."
SHARED_DIR="$ROOT_DIR/_shared"
if [ -d "$SHARED_DIR" ]; then
    cp -R "$SHARED_DIR" build/lambda/
else
    echo "ERROR: _shared module not found at $SHARED_DIR"
    exit 1
fi

# Copy the Lambda handler (uses _shared module)
echo "Copying application code..."
cp "$DEPLOY_DIR/lambda_handler.py" build/lambda/

# Copy .env if it exists (for runtime configuration)
if [ -f "$EXAMPLES_DIR/.env" ]; then
    cp "$EXAMPLES_DIR/.env" build/lambda/
elif [ -f "$ROOT_DIR/.env" ]; then
    cp "$ROOT_DIR/.env" build/lambda/
fi

# Create deployment package
echo "Creating deployment package..."
cd build/lambda && zip -r ../lambda_package.zip . >/dev/null
cd "$ROOT_DIR"

echo "Package size: $(du -h build/lambda_package.zip | cut -f1)"

# Create or get IAM role
echo ""
echo "Configuring IAM role..."
ROLE_ARN="$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text 2>/dev/null || true)"

if [ -z "$ROLE_ARN" ] || [ "$ROLE_ARN" = "None" ]; then
    echo "Creating IAM role: $ROLE_NAME"
    ROLE_ARN="$(aws iam create-role --role-name "$ROLE_NAME" \
        --assume-role-policy-document "file://$DEPLOY_DIR/lambda_trust_policy.json" \
        --query 'Role.Arn' --output text)"
    
    # Attach required policies
    aws iam attach-role-policy --role-name "$ROLE_NAME" \
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
    aws iam attach-role-policy --role-name "$ROLE_NAME" \
        --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess
    
    echo "Waiting for role to propagate..."
    sleep 10
else
    echo "Using existing role: $ROLE_NAME"
fi

# Create or update Lambda function
echo ""
echo "Deploying Lambda function..."
if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$AWS_REGION" >/dev/null 2>&1; then
    echo "Updating existing function..."
    aws lambda update-function-code \
        --function-name "$FUNCTION_NAME" \
        --zip-file fileb://build/lambda_package.zip \
        --region "$AWS_REGION"
    
    aws lambda wait function-updated \
        --function-name "$FUNCTION_NAME" \
        --region "$AWS_REGION"
    
    aws lambda update-function-configuration \
        --function-name "$FUNCTION_NAME" \
        --handler lambda_handler.handler \
        --runtime python3.11 \
        --timeout 60 \
        --memory-size 512 \
        --region "$AWS_REGION"
else
    echo "Creating new function..."
    aws lambda create-function \
        --function-name "$FUNCTION_NAME" \
        --runtime python3.11 \
        --handler lambda_handler.handler \
        --role "$ROLE_ARN" \
        --zip-file fileb://build/lambda_package.zip \
        --timeout 60 \
        --memory-size 512 \
        --region "$AWS_REGION"
fi

echo ""
echo "=============================================="
echo "Deploy complete!"
echo "Function ARN: $(aws lambda get-function --function-name "$FUNCTION_NAME" --query 'Configuration.FunctionArn' --output text)"
echo ""
echo "Run ./scripts/invoke.sh \"Your message\" to test"
echo "=============================================="
