#!/usr/bin/env bash
# List GCP resources deployed by this example (Vertex Agent Engine, Cloud Run, GKE).
# Use this to see what you have deployed and compare after changes.
#
# Prerequisites: gcloud CLI, authenticated (gcloud auth login and gcloud auth application-default login).
#
# Usage:
#   ./list-deployed-agents.sh           # List all
#   ./list-deployed-agents.sh --json    # Output JSON for diffing
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Load environment (same pattern as deploy scripts)
if [ -f "$PROJECT_DIR/../../.env" ]; then
    set -a
    source "$PROJECT_DIR/../../.env" 2>/dev/null || true
    set +a
fi

PROJECT="${GOOGLE_CLOUD_PROJECT:-}"
LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
OUTPUT_JSON=false
[ "${1:-}" = "--json" ] && OUTPUT_JSON=true

if [ -z "$PROJECT" ]; then
    echo "Error: GOOGLE_CLOUD_PROJECT not set. Set it in .env or export it."
    exit 1
fi

# Check ADC so list commands work
if ! gcloud auth application-default print-access-token &>/dev/null; then
    echo "Error: Application Default Credentials not set. Run: gcloud auth application-default login"
    exit 1
fi

gcloud config set project "$PROJECT" --quiet 2>/dev/null || true

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

# 2) Cloud Run services (default names from this example)
echo ""
echo "--- Cloud Run services ---"
gcloud run services list --region="$LOCATION" --project="$PROJECT" --format="table(metadata.name,status.url,status.conditions[0].status)" 2>/dev/null || echo "(none or error)"

# 3) GKE clusters (default name from this example)
echo ""
echo "--- GKE clusters ---"
gcloud container clusters list --project="$PROJECT" --filter="location:$LOCATION" --format="table(name,location,status)" 2>/dev/null || echo "(none or error)"

# 4) Artifact Registry repos (where our images are pushed)
echo ""
echo "--- Artifact Registry (Docker repos) ---"
gcloud artifacts repositories list --location="$LOCATION" --project="$PROJECT" --format="table(name,format)" 2>/dev/null || echo "(none or error)"

echo ""
echo "Done. Use these to compare with a previous run (e.g. diff) to see what changed."
