#!/usr/bin/env bash
# =============================================================================
# Cleanup Cloud Run deployment
# =============================================================================
#
# Usage:
#   ./cleanup.sh              # Delete Cloud Run service
#   ./cleanup.sh --all        # Delete service and container images
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
SERVICE_NAME="${CLOUD_RUN_SERVICE:-sre-agent-cloudrun}"
ARTIFACT_REPO="${ARTIFACT_REPO:-sre-agent-repo}"

echo "=============================================="
echo "Cleaning up Cloud Run deployment"
echo "=============================================="
echo "Project:  $PROJECT"
echo "Location: $LOCATION"
echo "Service:  $SERVICE_NAME"
echo ""

# Delete Cloud Run service
echo "Deleting Cloud Run service..."
if gcloud run services describe "$SERVICE_NAME" --platform managed --region "$LOCATION" &>/dev/null; then
    gcloud run services delete "$SERVICE_NAME" \
        --platform managed \
        --region "$LOCATION" \
        --quiet
    echo "Service deleted."
else
    echo "Service not found (already deleted or never created)."
fi

# Delete container images if --all flag
if [ "${1:-}" = "--all" ]; then
    echo ""
    echo "Deleting container images from Artifact Registry..."
    IMAGE_PATH="$LOCATION-docker.pkg.dev/$PROJECT/$ARTIFACT_REPO/$SERVICE_NAME"
    
    # List and delete all versions
    gcloud artifacts docker images delete "$IMAGE_PATH" \
        --delete-tags \
        --quiet 2>/dev/null || echo "No images found to delete."
fi

echo ""
echo "=============================================="
echo "Cleanup complete!"
echo "=============================================="
