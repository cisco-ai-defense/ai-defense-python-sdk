#!/usr/bin/env bash
# Deploy SRE agent to Vertex AI Agent Engine
#
# Follows the official deployment guide:
# https://cloud.google.com/agent-builder/agent-engine/deploy
#
# Vertex AI Agent Engine is Google's fully managed service for running agents.
# This script deploys from source files using the Vertex AI Python SDK.
#
# NOTE: Includes 10-minute timeout for SDK create() operation to prevent hanging.
#       The SDK polls for agent readiness and may hang indefinitely waiting for
#       health checks. Timeout ensures clean exit even if agent takes long to start.
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - Vertex AI API enabled: gcloud services enable aiplatform.googleapis.com
#   - Generative Language API enabled: gcloud services enable generativelanguage.googleapis.com
#     (Vertex AI delegates Gemini calls to this backend; without it the agent gets
#      403 ACCESS_TOKEN_SCOPE_INSUFFICIENT from generativelanguage.googleapis.com)
#   - Python 3.11+ with google-cloud-aiplatform package
#
# Usage:
#   ./deploy.sh              # Deploy to Vertex AI Agent Engine
#   ./deploy.sh test         # Run local test instead
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$(dirname "$DEPLOY_DIR")"

# Load environment (preserve AGENT_ENGINE_NAME if set by parent e.g. --new-resources)
_SAVED_AGENT_ENGINE_NAME="${AGENT_ENGINE_NAME:-}"
if [ -f "$PROJECT_DIR/../../../.env" ]; then
    source "$PROJECT_DIR/../../../.env"
fi
[ -n "$_SAVED_AGENT_ENGINE_NAME" ] && export AGENT_ENGINE_NAME="$_SAVED_AGENT_ENGINE_NAME"

# Configuration
PROJECT="${GOOGLE_CLOUD_PROJECT:?Error: GOOGLE_CLOUD_PROJECT not set. Please set it in .env or export it.}"
LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
AGENT_NAME="${AGENT_ENGINE_NAME:-sre-agent-engine}"
SERVICE_ACCOUNT="${AGENT_ENGINE_SA:-}"

echo "=============================================="
echo "Deploying to Vertex AI Agent Engine"
echo "=============================================="
echo "Project:  $PROJECT"
echo "Location: $LOCATION"
echo "Agent:    $AGENT_NAME"
echo ""

# Check for test mode
if [ "${1:-}" = "test" ]; then
    echo "Running local test..."
    cd "$PROJECT_DIR"
    
    # Ensure dependencies are installed
    if [ -f "poetry.lock" ]; then
        poetry install --quiet 2>/dev/null || poetry install
        PYTHON_CMD="poetry run python"
    else
        PYTHON_CMD="python"
    fi
    
    export PYTHONPATH="$PROJECT_DIR"
    export GOOGLE_CLOUD_PROJECT="$PROJECT"
    export GOOGLE_CLOUD_LOCATION="$LOCATION"
    export GOOGLE_GENAI_USE_VERTEXAI="True"
    
    $PYTHON_CMD "$DEPLOY_DIR/app.py"
    exit 0
fi

# Ensure gcloud is configured
gcloud config set project "$PROJECT" --quiet

# Vertex AI Agent Engine SDK uses Application Default Credentials (ADC). Fail fast with a clear message.
if ! gcloud auth application-default print-access-token &>/dev/null; then
    echo "ERROR: Application Default Credentials (ADC) not set. The Agent Engine SDK requires ADC."
    echo "Run in this terminal: gcloud auth application-default login"
    echo "See: https://cloud.google.com/docs/authentication/external/set-up-adc"
    exit 1
fi

echo "Deploying agent using Vertex AI Agent Engine SDK..."
echo "This may take 3-5 minutes..."
echo ""

# Prepare deployment directory
# Copy _shared and aidefense into agent-engine-deploy for deployment (required by Agent Engine SDK)
echo "Preparing source packages..."
if [ -d "$DEPLOY_DIR/_shared" ]; then
    rm -rf "$DEPLOY_DIR/_shared"
fi
cp -r "$PROJECT_DIR/_shared" "$DEPLOY_DIR/_shared"

if [ -d "$DEPLOY_DIR/aidefense" ]; then
    rm -rf "$DEPLOY_DIR/aidefense"
fi
# Copy aidefense SDK from repository root
# PROJECT_DIR is gcp-vertex-ai-agent-engine, go up 4 levels to reach the SDK root
SDK_ROOT="$(cd "$PROJECT_DIR/../../../../" && pwd)"
cp -r "$SDK_ROOT/aidefense" "$DEPLOY_DIR/aidefense"

# Change to agent-engine-deploy directory so source packages are correctly rooted
cd "$DEPLOY_DIR"

# Ensure dependencies are installed (use project root's poetry)
if [ -f "$PROJECT_DIR/poetry.lock" ]; then
    cd "$PROJECT_DIR"
    poetry install --quiet 2>/dev/null || poetry install
    PYTHON_CMD="poetry run python"
    cd "$DEPLOY_DIR"
else
    PYTHON_CMD="python"
fi

# Build environment variables JSON
# Note: GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION are reserved and automatically provided by Agent Engine
ENV_VARS_JSON="{"
ENV_VARS_JSON="${ENV_VARS_JSON}\"GOOGLE_GENAI_USE_VERTEXAI\": \"True\","
# SDK to use in the deployed container.
# Priority: GOOGLE_AI_SDK_DEPLOYMENT > GOOGLE_AI_SDK > google_genai
GOOGLE_AI_SDK="${GOOGLE_AI_SDK_DEPLOYMENT:-${GOOGLE_AI_SDK:-google_genai}}"
ENV_VARS_JSON="${ENV_VARS_JSON}\"GOOGLE_AI_SDK\": \"${GOOGLE_AI_SDK}\","
# Note: agentsec configuration (integration modes, gateway URLs, API keys, etc.)
# is now loaded from agentsec.yaml at runtime. Only secrets referenced by the YAML
# via ${VAR_NAME} and non-agentsec env vars need to be passed here.
if [ -n "${AI_DEFENSE_API_MODE_LLM_API_KEY:-}" ]; then
    ENV_VARS_JSON="${ENV_VARS_JSON}\"AI_DEFENSE_API_MODE_LLM_API_KEY\": \"${AI_DEFENSE_API_MODE_LLM_API_KEY}\""
fi
if [ -n "${AI_DEFENSE_API_MODE_MCP_API_KEY:-}" ]; then
    ENV_VARS_JSON="${ENV_VARS_JSON}, \"AI_DEFENSE_API_MODE_MCP_API_KEY\": \"${AI_DEFENSE_API_MODE_MCP_API_KEY}\""
fi

# Add MCP configuration if set
if [ -n "${MCP_SERVER_URL:-}" ]; then
    ENV_VARS_JSON="${ENV_VARS_JSON}, \"MCP_SERVER_URL\": \"${MCP_SERVER_URL}\""
fi

ENV_VARS_JSON="${ENV_VARS_JSON}}"

# Build service account config
SERVICE_ACCOUNT_CONFIG=""
if [ -n "$SERVICE_ACCOUNT" ]; then
    SERVICE_ACCOUNT_CONFIG=", \"service_account\": \"$SERVICE_ACCOUNT\""
fi

# Create deployment script
cat > /tmp/deploy_agent_engine.py <<PYTHON_EOF
"""
Deploy agent to Vertex AI Agent Engine using the official SDK.
Follows: https://cloud.google.com/agent-builder/agent-engine/deploy
"""
import os
import sys
import json

# Add project directory to path
sys.path.insert(0, "$DEPLOY_DIR")

import vertexai

# Initialize Vertex AI client
print("Creating Vertex AI client...")
client = vertexai.Client(project="$PROJECT", location="$LOCATION")

# Parse environment variables
env_vars = json.loads('''$ENV_VARS_JSON''')

# Configure deployment
config = {
    "display_name": "$AGENT_NAME",
    "description": "SRE Agent with Cisco AI Defense (agentsec) protection - LangChain based agent with tool calling",
    "source_packages": ["_shared", "agent_engine_entry", "aidefense"],
    "entrypoint_module": "agent_engine_entry.entry",
    "entrypoint_object": "agent",
    "requirements_file": "agent_engine_entry/requirements.txt",
    "class_methods": [
        {
            "name": "query",
            "api_mode": "",  # Synchronous
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The user prompt for the agent"
                    }
                },
                "required": ["prompt"]
            }
        }
    ],
    "env_vars": env_vars,
    "agent_framework": "langchain",
    "min_instances": 1,
    "max_instances": 10,
    "resource_limits": {"cpu": "4", "memory": "4Gi"},
    "container_concurrency": 9$SERVICE_ACCOUNT_CONFIG
}

print(f"Deploying agent: {config['display_name']}")
print(f"Framework: {config['agent_framework']}")
print(f"Entry point: {config['entrypoint_module']}.{config['entrypoint_object']}")
print(f"Source packages: {config['source_packages']}")
print("")
print("Initiating deployment... (this may take 5-15 minutes for first-time deployments)")
print("The SDK is uploading source code and building the container image...")
print("")

# Deploy the agent with timeout handling
try:
    import sys
    import signal
    
    # Set up timeout handler (10 minutes max wait after deployment starts)
    def timeout_handler(signum, frame):
        print("")
        print("⚠️  Deployment operation timed out waiting for agent to become ready.")
        print("   The agent may still be starting up. Check GCP console for status.")
        print("")
        print("To check agent status:")
        print("  gcloud alpha ai reasoning-engines list --region=$LOCATION --project=$PROJECT")
        sys.exit(0)
    
    # Set timeout for 10 minutes (600 seconds)
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(600)
    
    sys.stdout.flush()
    remote_agent = client.agent_engines.create(config=config)
    
    # Cancel alarm if we got here
    signal.alarm(0)
    
    print("Deployment request accepted by GCP, container is being built...")
    
    # Get resource information
    resource_name = remote_agent.api_resource.name
    print("")
    print("=" * 60)
    print("Deployment Complete!")
    print("=" * 60)
    print(f"Agent Name: {config['display_name']}")
    print(f"Resource: {resource_name}")
    print(f"Location: $LOCATION")
    print("")
    print("To invoke the agent:")
    print("  ./scripts/invoke.sh \"Check the health of the payments service\"")
    print("")
    
    # Save resource name for invoke script
    with open("/tmp/agent_engine_resource.txt", "w") as f:
        f.write(resource_name)
    
    # Explicitly exit successfully
    sys.exit(0)
    
except Exception as e:
    signal.alarm(0)  # Cancel alarm on error
    print(f"Error deploying agent: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYTHON_EOF

# Execute deployment (with unbuffered output)
$PYTHON_CMD -u /tmp/deploy_agent_engine.py

# Clean up
rm -f /tmp/deploy_agent_engine.py
rm -rf "$DEPLOY_DIR/_shared"
rm -rf "$DEPLOY_DIR/aidefense"
echo "Cleaned up temporary files."
