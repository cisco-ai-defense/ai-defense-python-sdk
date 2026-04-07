#!/usr/bin/env bash
# Run the Google ADK agentsec example.
#
# Usage:
#   ./scripts/run.sh                     # defaults to monitor mode
#   AGENTSEC_API_MODE_LLM=enforce ./scripts/run.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$AGENT_DIR"
python agent.py "$@"
