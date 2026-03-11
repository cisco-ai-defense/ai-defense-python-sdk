#!/usr/bin/env bash
# List GCP resources deployed by this example (Vertex Agent Engine, Cloud Run, GKE).
# Use this to see what you have deployed and compare after changes.
#
# Prerequisites: gcloud CLI, authenticated (gcloud auth login and gcloud auth application-default login).
#
# Usage:
#   ./list-deployed-agents.sh           # List all
#
set -euo pipefail

echo "Starting list-deployed-agents.sh..."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$(dirname "$DEPLOY_DIR")"

# Load environment (same pattern as deploy.sh)
echo "Loading .env..."
if [ -f "$PROJECT_DIR/../../../.env" ]; then
    set -a
    source "$PROJECT_DIR/../../../.env" 2>/dev/null || true
    set +a
fi

# Allow project/location from env or first argument (project only)
PROJECT="${GOOGLE_CLOUD_PROJECT:-$1}"
LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"

if [ -z "$PROJECT" ]; then
    echo "Error: GOOGLE_CLOUD_PROJECT not set. Set it in examples/agentsec/.env or export it, or run: $0 YOUR_GCP_PROJECT_ID"
    exit 1
fi

echo "Using project=$PROJECT region=$LOCATION"

# Check ADC so list commands work (never capture token; show gcloud stderr only on failure)
echo "Checking Application Default Credentials..."
ADC_ERR=$(mktemp)
if ! gcloud auth application-default print-access-token >/dev/null 2>"$ADC_ERR"; then
    echo "Error: Application Default Credentials not set or expired."
    echo "Run: gcloud auth application-default login"
    [ -s "$ADC_ERR" ] && cat "$ADC_ERR"
    rm -f "$ADC_ERR"
    exit 1
fi
rm -f "$ADC_ERR"
echo "Credentials OK."

echo "Setting gcloud project..."
gcloud config set project "$PROJECT" --quiet 2>/dev/null || true

echo ""
echo "=============================================="
echo "GCP resources (project=$PROJECT, region=$LOCATION)"
echo "=============================================="

# 1) Vertex AI Agent Engine (reasoning engines)
echo ""
echo "--- Vertex AI Agent Engine (reasoning-engines) ---"
if gcloud alpha ai reasoning-engines list --region="$LOCATION" --project="$PROJECT" 2>/dev/null; then
    :
else
    echo "(none or list not supported: run 'gcloud alpha ai reasoning-engines list --region=$LOCATION')"
fi

# 2) Cloud Run services
echo ""
echo "--- Cloud Run services ---"
gcloud run services list --region="$LOCATION" --project="$PROJECT" --format="table(metadata.name,status.url,status.conditions[0].status)" 2>/dev/null || echo "(none or error)"

# 3) GKE clusters
echo ""
echo "--- GKE clusters ---"
gcloud container clusters list --project="$PROJECT" --filter="location:$LOCATION" --format="table(name,location,status)" 2>/dev/null || echo "(none or error)"

# 4) Artifact Registry repos
echo ""
echo "--- Artifact Registry (Docker repos) ---"
gcloud artifacts repositories list --location="$LOCATION" --project="$PROJECT" --format="table(name,format)" 2>/dev/null || echo "(none or error)"

echo ""
echo "Done. Use this output to compare with a previous run to see what changed."
