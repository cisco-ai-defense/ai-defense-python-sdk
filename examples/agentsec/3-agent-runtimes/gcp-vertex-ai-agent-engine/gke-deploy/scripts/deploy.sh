#!/usr/bin/env bash
# =============================================================================
# Deploy SRE agent to Google Kubernetes Engine (GKE) with Cisco AI Defense
# =============================================================================
#
# GKE provides:
# - Full Kubernetes orchestration
# - Fine-grained control over resources
# - Integration with Google Cloud services
# - Workload Identity for secure service accounts
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - Docker installed
#   - kubectl installed
#
# Usage:
#   ./deploy.sh              # Build and deploy to GKE
#   ./deploy.sh build        # Build Docker image only
#   ./deploy.sh test         # Run local test
#   ./deploy.sh setup        # Create GKE cluster (first time)
#
# Environment Variables:
#   GOOGLE_CLOUD_PROJECT         - GCP project ID
#   GOOGLE_CLOUD_LOCATION        - GCP region (default: us-central1)
#   GKE_CLUSTER                  - Cluster name (default: sre-agent-cluster)
#   GKE_SERVICE                  - Service name (default: sre-agent-gke)
#   GKE_AUTHORIZED_NETWORKS      - CIDR for Master Authorized Networks (e.g., YOUR_IP/32)
#   AGENTSEC_LLM_INTEGRATION_MODE - api or gateway (default: api)
#   AGENTSEC_API_MODE_LLM        - off/on_monitor/on_enforce (default: on_monitor)
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
CLUSTER_NAME="${GKE_CLUSTER:-sre-agent-cluster}"
SERVICE_NAME="${GKE_SERVICE:-sre-agent-gke}"
ARTIFACT_REPO="${ARTIFACT_REPO:-sre-agent-repo}"
IMAGE_NAME="$LOCATION-docker.pkg.dev/$PROJECT/$ARTIFACT_REPO/$SERVICE_NAME"

# AI Defense configuration
INTEGRATION_MODE="${AGENTSEC_LLM_INTEGRATION_MODE:-api}"
API_MODE="${AGENTSEC_API_MODE_LLM:-on_monitor}"
API_ENDPOINT="${AI_DEFENSE_API_MODE_LLM_ENDPOINT:-}"
API_KEY="${AI_DEFENSE_API_MODE_LLM_API_KEY:-}"
GOOGLE_AI_SDK="${GOOGLE_AI_SDK:-vertexai}"

echo "=============================================="
echo "Deploying to GKE with AI Defense"
echo "=============================================="
echo "Project:         $PROJECT"
echo "Location:        $LOCATION"
echo "Cluster:         $CLUSTER_NAME"
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

# Check for setup mode (create GKE cluster)
if [ "${1:-}" = "setup" ]; then
    echo "Setting up GKE cluster..."
    
    # Determine authorized networks for cluster access
    # Required by Cisco security guardrails - public endpoints must have Master Authorized Networks
    AUTHORIZED_NETWORKS="${GKE_AUTHORIZED_NETWORKS:-}"
    
    if [ -z "$AUTHORIZED_NETWORKS" ]; then
        echo "GKE_AUTHORIZED_NETWORKS not set, auto-detecting your public IP..."
        MY_IP=$(curl -s --connect-timeout 5 ifconfig.me 2>/dev/null || curl -s --connect-timeout 5 api.ipify.org 2>/dev/null || echo "")
        if [ -n "$MY_IP" ]; then
            AUTHORIZED_NETWORKS="$MY_IP/32"
            echo "Detected IP: $MY_IP"
        else
            echo "ERROR: Could not detect public IP and GKE_AUTHORIZED_NETWORKS is not set."
            echo ""
            echo "Please set GKE_AUTHORIZED_NETWORKS in your .env file:"
            echo "  GKE_AUTHORIZED_NETWORKS=YOUR_PUBLIC_IP/32"
            echo ""
            echo "Get your IP with: curl ifconfig.me"
            exit 1
        fi
    fi
    
    echo "Master Authorized Networks: $AUTHORIZED_NETWORKS"
    echo ""
    
    # Enable required APIs
    echo "Enabling required APIs..."
    gcloud services enable container.googleapis.com --project "$PROJECT"
    gcloud services enable artifactregistry.googleapis.com --project "$PROJECT"
    
    # Create cluster if it doesn't exist
    if ! gcloud container clusters describe "$CLUSTER_NAME" --region "$LOCATION" --project "$PROJECT" &> /dev/null; then
        echo "Creating GKE Autopilot cluster: $CLUSTER_NAME (this may take 5-10 minutes)..."
        echo "Using Master Authorized Networks for security compliance..."
        gcloud container clusters create-auto "$CLUSTER_NAME" \
            --region "$LOCATION" \
            --project "$PROJECT" \
            --enable-master-authorized-networks \
            --master-authorized-networks "$AUTHORIZED_NETWORKS"
    else
        echo "Cluster $CLUSTER_NAME already exists"
        # Update authorized networks on existing cluster
        echo "Updating Master Authorized Networks..."
        gcloud container clusters update "$CLUSTER_NAME" \
            --region "$LOCATION" \
            --project "$PROJECT" \
            --enable-master-authorized-networks \
            --master-authorized-networks "$AUTHORIZED_NETWORKS" || true
    fi
    
    # Get cluster credentials
    gcloud container clusters get-credentials "$CLUSTER_NAME" \
        --region "$LOCATION" \
        --project "$PROJECT"
    
    echo ""
    echo "Cluster setup complete!"
    echo "Authorized networks: $AUTHORIZED_NETWORKS"
    echo "Now run: ./deploy.sh"
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
    -f gke-deploy/Dockerfile \
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

# Get cluster credentials
echo "Getting cluster credentials..."
gcloud container clusters get-credentials "$CLUSTER_NAME" \
    --region "$LOCATION" \
    --project "$PROJECT"

# Create/update Kubernetes deployment with env vars
echo "Applying Kubernetes manifests..."

# Generate deployment manifest with AI Defense env vars
cat > /tmp/sre-agent-deployment.yaml <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sre-agent
  labels:
    app: sre-agent
spec:
  replicas: 1
  selector:
    matchLabels:
      app: sre-agent
  template:
    metadata:
      labels:
        app: sre-agent
    spec:
      containers:
      - name: sre-agent
        image: $IMAGE_NAME:latest
        ports:
        - containerPort: 8080
        env:
        - name: GOOGLE_CLOUD_PROJECT
          value: "$PROJECT"
        - name: GOOGLE_CLOUD_LOCATION
          value: "$LOCATION"
        - name: GOOGLE_GENAI_USE_VERTEXAI
          value: "True"
        - name: GOOGLE_AI_SDK
          value: "$GOOGLE_AI_SDK"
        - name: AGENTSEC_LLM_INTEGRATION_MODE
          value: "$INTEGRATION_MODE"
        - name: AGENTSEC_API_MODE_LLM
          value: "$API_MODE"
EOF

# Add optional env vars
if [ -n "$API_ENDPOINT" ]; then
    cat >> /tmp/sre-agent-deployment.yaml <<EOF
        - name: AI_DEFENSE_API_MODE_LLM_ENDPOINT
          value: "$API_ENDPOINT"
EOF
fi

if [ -n "$API_KEY" ]; then
    cat >> /tmp/sre-agent-deployment.yaml <<EOF
        - name: AI_DEFENSE_API_MODE_LLM_API_KEY
          value: "$API_KEY"
EOF
fi

# Add resource limits
cat >> /tmp/sre-agent-deployment.yaml <<EOF
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 30
EOF

kubectl apply --validate=false -f /tmp/sre-agent-deployment.yaml
kubectl apply --validate=false -f "$DEPLOY_DIR/k8s/service.yaml"

# Wait for deployment
echo "Waiting for deployment to be ready..."
kubectl rollout status deployment/sre-agent --timeout=180s

# Get the external IP
echo "Getting service external IP (this may take 1-2 minutes)..."
EXTERNAL_IP=""
for i in {1..30}; do
    EXTERNAL_IP=$(kubectl get service sre-agent-service -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
    if [ -n "$EXTERNAL_IP" ]; then
        break
    fi
    echo "Waiting for external IP... ($i/30)"
    sleep 5
done

echo ""
echo "=============================================="
echo "Deployment complete!"
echo "=============================================="
if [ -n "$EXTERNAL_IP" ]; then
    echo "Service URL: http://$EXTERNAL_IP"
    echo "AI Defense:  $INTEGRATION_MODE mode ($API_MODE)"
    echo ""
    echo "Test with:"
    echo "  curl http://$EXTERNAL_IP/health"
    echo "  curl -X POST http://$EXTERNAL_IP/invoke -H 'Content-Type: application/json' -d '{\"prompt\": \"Check service health\"}'"
else
    echo "External IP not yet assigned. Check with:"
    echo "  kubectl get service sre-agent-service"
fi
echo ""
echo "View logs (to verify AI Defense):"
echo "  kubectl logs -l app=sre-agent --tail=100"
