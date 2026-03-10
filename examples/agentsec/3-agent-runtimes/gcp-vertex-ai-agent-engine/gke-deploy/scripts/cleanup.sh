#!/usr/bin/env bash
# =============================================================================
# Cleanup GKE deployment
# =============================================================================
#
# Usage:
#   ./cleanup.sh              # Delete deployment and service (keep cluster)
#   ./cleanup.sh --all        # Delete everything including cluster
#
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$(dirname "$DEPLOY_DIR")"
EXAMPLES_DIR="$(dirname "$PROJECT_DIR")"

# Load environment (check multiple locations)
ENV_FILE=""
if [ -f "$EXAMPLES_DIR/.env" ]; then
    ENV_FILE="$EXAMPLES_DIR/.env"
elif [ -f "$EXAMPLES_DIR/../.env" ]; then
    ENV_FILE="$EXAMPLES_DIR/../.env"
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

echo "=============================================="
echo "Cleaning up GKE deployment"
echo "=============================================="
echo "Project:  $PROJECT"
echo "Location: $LOCATION"
echo "Cluster:  $CLUSTER_NAME"
echo "Service:  $SERVICE_NAME"
echo ""

# Get cluster credentials
echo "Getting cluster credentials..."
if gcloud container clusters get-credentials "$CLUSTER_NAME" --region "$LOCATION" --project "$PROJECT" &>/dev/null; then
    # Delete Kubernetes resources
    echo "Deleting Kubernetes deployment..."
    kubectl delete deployment sre-agent --ignore-not-found
    
    echo "Deleting Kubernetes service..."
    kubectl delete service sre-agent-service --ignore-not-found
    
    echo "Kubernetes resources deleted."
else
    echo "Could not connect to cluster (may not exist)."
fi

# Delete container images if --all flag
if [ "${1:-}" = "--all" ]; then
    echo ""
    echo "Deleting container images from Artifact Registry..."
    IMAGE_PATH="$LOCATION-docker.pkg.dev/$PROJECT/$ARTIFACT_REPO/$SERVICE_NAME"
    
    gcloud artifacts docker images delete "$IMAGE_PATH" \
        --delete-tags \
        --quiet 2>/dev/null || echo "No images found to delete."
    
    echo ""
    echo "Deleting GKE cluster (this may take several minutes)..."
    if gcloud container clusters describe "$CLUSTER_NAME" --region "$LOCATION" --project "$PROJECT" &>/dev/null; then
        gcloud container clusters delete "$CLUSTER_NAME" \
            --region "$LOCATION" \
            --project "$PROJECT" \
            --quiet
        echo "Cluster deleted."
    else
        echo "Cluster not found (already deleted or never created)."
    fi
fi

echo ""
echo "=============================================="
echo "Cleanup complete!"
echo "=============================================="
if [ "${1:-}" != "--all" ]; then
    echo ""
    echo "Note: GKE cluster '$CLUSTER_NAME' was NOT deleted."
    echo "To delete everything including the cluster, run:"
    echo "  ./cleanup.sh --all"
fi
