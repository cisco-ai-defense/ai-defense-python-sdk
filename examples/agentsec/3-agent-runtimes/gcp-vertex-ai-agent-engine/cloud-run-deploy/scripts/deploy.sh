#!/usr/bin/env bash
# =============================================================================
# Deploy SRE agent to Cloud Run with Cisco AI Defense protection
# =============================================================================
#
# Cloud Run provides serverless container deployment with:
# - Automatic scaling (including scale-to-zero)
# - Pay-per-request pricing
# - Built-in HTTPS and load balancing
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - Docker installed
#   - Cloud Run API enabled
#
# Usage:
#   ./deploy.sh              # Build and deploy to Cloud Run
#   ./deploy.sh build        # Build Docker image only
#   ./deploy.sh test         # Run local test
#
# Environment Variables:
#   GOOGLE_CLOUD_PROJECT         - GCP project ID
#   GOOGLE_CLOUD_LOCATION        - GCP region (default: us-central1)
#   CLOUD_RUN_SERVICE            - Service name (default: sre-agent-cloudrun)
#   AGENTSEC_LLM_INTEGRATION_MODE - api or gateway (default: api)
#   AGENTSEC_API_MODE_LLM        - off/on_monitor/on_enforce (default: on_monitor)
#   AI_DEFENSE_API_MODE_LLM_ENDPOINT - AI Defense API endpoint
#   AI_DEFENSE_API_MODE_LLM_API_KEY  - AI Defense API key
#
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$(dirname "$DEPLOY_DIR")"
RUNTIMES_DIR="$(dirname "$PROJECT_DIR")"
AGENTSEC_DIR="$(dirname "$RUNTIMES_DIR")"
EXAMPLES_DIR="$(dirname "$AGENTSEC_DIR")"
REPO_ROOT="$(dirname "$EXAMPLES_DIR")"
# Load environment (check multiple locations)
ENV_FILE=""
if [ -f "$AGENTSEC_DIR/.env" ]; then
    ENV_FILE="$AGENTSEC_DIR/.env"
elif [ -f "$EXAMPLES_DIR/.env" ]; then
    ENV_FILE="$EXAMPLES_DIR/.env"
fi

if [ -n "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE" 2>/dev/null || true
    set +a
fi

# Configuration
PROJECT="${GOOGLE_CLOUD_PROJECT:?Error: GOOGLE_CLOUD_PROJECT not set. Please set it in .env or export it.}"
LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
SERVICE_NAME="${CLOUD_RUN_SERVICE:-sre-agent-cloudrun}"
ARTIFACT_REPO="${ARTIFACT_REPO:-sre-agent-repo}"
IMAGE_NAME="$LOCATION-docker.pkg.dev/$PROJECT/$ARTIFACT_REPO/$SERVICE_NAME"

# AI Defense configuration
INTEGRATION_MODE="${AGENTSEC_LLM_INTEGRATION_MODE:-api}"
API_MODE="${AGENTSEC_API_MODE_LLM:-on_monitor}"
API_ENDPOINT="${AI_DEFENSE_API_MODE_LLM_ENDPOINT:-}"
API_KEY="${AI_DEFENSE_API_MODE_LLM_API_KEY:-}"
GOOGLE_AI_SDK="${GOOGLE_AI_SDK:-vertexai}"

echo "=============================================="
echo "Deploying to Cloud Run with AI Defense"
echo "=============================================="
echo "Project:         $PROJECT"
echo "Location:        $LOCATION"
echo "Service:         $SERVICE_NAME"
echo "Image:           $IMAGE_NAME"
echo "AI SDK:          $GOOGLE_AI_SDK"
echo "AI Defense Mode: $INTEGRATION_MODE ($API_MODE)"
echo ""

# Check for test mode (local testing)
if [ "${1:-}" = "test" ]; then
    echo "Running local test..."
    cd "$PROJECT_DIR"
    
    poetry install --quiet 2>/dev/null || poetry install
    
    export PYTHONPATH="$PROJECT_DIR"
    export GOOGLE_CLOUD_PROJECT="$PROJECT"
    export GOOGLE_CLOUD_LOCATION="$LOCATION"
    export GOOGLE_GENAI_USE_VERTEXAI="True"
    export GOOGLE_AI_SDK="$GOOGLE_AI_SDK"
    export PORT="8080"
    
    echo "Starting server on http://localhost:8080"
    poetry run python "$DEPLOY_DIR/app.py"
    exit 0
fi

# Ensure gcloud is configured
gcloud config set project "$PROJECT" --quiet

# Create Artifact Registry repository if it doesn't exist
echo "Creating Artifact Registry repository (if needed)..."
gcloud artifacts repositories create "$ARTIFACT_REPO" \
    --repository-format=docker \
    --location="$LOCATION" \
    --description="SRE Agent container images" \
    2>/dev/null || echo "Repository already exists"

# Configure Docker for Artifact Registry
echo "Configuring Docker authentication..."
gcloud auth configure-docker "$LOCATION-docker.pkg.dev" --quiet

# Prepare build context - copy agentsec package
echo "Preparing build context..."
BUILD_CONTEXT="$PROJECT_DIR"
AGENTSEC_DEST="$BUILD_CONTEXT/agentsec_package"

# Clean up any previous build artifacts and create fresh directory
rm -rf "$AGENTSEC_DEST"
mkdir -p "$AGENTSEC_DEST"

# Copy aidefense SDK source (includes agentsec at aidefense/runtime/agentsec)
cp -r "$REPO_ROOT/aidefense" "$AGENTSEC_DEST/"
cp "$REPO_ROOT/pyproject.toml" "$AGENTSEC_DEST/"
cp "$REPO_ROOT/README.md" "$AGENTSEC_DEST/" 2>/dev/null || echo "# cisco-aidefense-sdk" > "$AGENTSEC_DEST/README.md"

# Cleanup function
cleanup() {
    rm -rf "$AGENTSEC_DEST"
}
trap cleanup EXIT

# Build the container
echo "Building Docker image (linux/amd64)..."
cd "$BUILD_CONTEXT"

docker build \
    --platform linux/amd64 \
    -f cloud-run-deploy/Dockerfile \
    -t "$IMAGE_NAME:latest" \
    .

# Check for build-only mode
if [ "${1:-}" = "build" ]; then
    echo ""
    echo "Build complete: $IMAGE_NAME:latest"
    echo ""
    echo "To run locally:"
    echo "  docker run -p 8080:8080 \\"
    echo "    -e GOOGLE_CLOUD_PROJECT=$PROJECT \\"
    echo "    -e GOOGLE_CLOUD_LOCATION=$LOCATION \\"
    echo "    -e AGENTSEC_LLM_INTEGRATION_MODE=$INTEGRATION_MODE \\"
    echo "    $IMAGE_NAME:latest"
    exit 0
fi

# Push to Artifact Registry
echo "Pushing to Artifact Registry..."
docker push "$IMAGE_NAME:latest"

# Build env vars for Cloud Run
ENV_VARS="GOOGLE_CLOUD_PROJECT=$PROJECT"
ENV_VARS="$ENV_VARS,GOOGLE_CLOUD_LOCATION=$LOCATION"
ENV_VARS="$ENV_VARS,GOOGLE_GENAI_USE_VERTEXAI=True"
ENV_VARS="$ENV_VARS,GOOGLE_AI_SDK=$GOOGLE_AI_SDK"
ENV_VARS="$ENV_VARS,AGENTSEC_LLM_INTEGRATION_MODE=$INTEGRATION_MODE"
ENV_VARS="$ENV_VARS,AGENTSEC_API_MODE_LLM=$API_MODE"

if [ -n "$API_ENDPOINT" ]; then
    ENV_VARS="$ENV_VARS,AI_DEFENSE_API_MODE_LLM_ENDPOINT=$API_ENDPOINT"
fi
if [ -n "$API_KEY" ]; then
    ENV_VARS="$ENV_VARS,AI_DEFENSE_API_MODE_LLM_API_KEY=$API_KEY"
fi

# Deploy to Cloud Run
echo "Deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
    --image "$IMAGE_NAME:latest" \
    --platform managed \
    --region "$LOCATION" \
    --allow-unauthenticated \
    --set-env-vars="$ENV_VARS" \
    --memory=512Mi \
    --timeout=60 \
    --quiet

# Get the service URL
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --platform managed \
    --region "$LOCATION" \
    --format 'value(status.url)')

echo ""
echo "=============================================="
echo "Deployment complete!"
echo "=============================================="
echo "Service URL: $SERVICE_URL"
echo "AI Defense:  $INTEGRATION_MODE mode ($API_MODE)"
echo ""
echo "Test with:"
echo "  curl $SERVICE_URL/health"
echo "  curl -X POST $SERVICE_URL/invoke -H 'Content-Type: application/json' -d '{\"prompt\": \"Check service health\"}'"
echo ""
echo "View logs (to verify AI Defense):"
echo "  gcloud run services logs read $SERVICE_NAME --region $LOCATION --limit 50"
