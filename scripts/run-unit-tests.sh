#!/bin/bash
#
# Run all unit tests across the project
#
# Usage:
#   ./scripts/run-unit-tests.sh           # Run all unit tests
#   ./scripts/run-unit-tests.sh -v        # Verbose output
#   ./scripts/run-unit-tests.sh --cov     # With coverage
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=============================================="
echo "  Running All Unit Tests"
echo -e "==============================================${NC}"
echo ""

# Collect all unit test directories
UNIT_TEST_DIRS=(
    "aidefense/tests"
    "aidefense/tests/agentsec/unit"
    "examples/agentsec/1_simple/tests/unit"
    "examples/agentsec/2_agent-frameworks/strands-agent/tests/unit"
    "examples/agentsec/2_agent-frameworks/langgraph-agent/tests/unit"
    "examples/agentsec/2_agent-frameworks/langchain-agent/tests/unit"
    "examples/agentsec/2_agent-frameworks/crewai-agent/tests/unit"
    "examples/agentsec/2_agent-frameworks/autogen-agent/tests/unit"
    "examples/agentsec/2_agent-frameworks/openai-agent/tests/unit"
    "examples/agentsec/2_agent-frameworks/_shared/tests"
)

# Build pytest paths (only include directories that exist)
PYTEST_PATHS=""
for dir in "${UNIT_TEST_DIRS[@]}"; do
    if [ -d "$PROJECT_DIR/$dir" ]; then
        PYTEST_PATHS="$PYTEST_PATHS $dir"
    fi
done

echo "Unit test directories:"
for dir in "${UNIT_TEST_DIRS[@]}"; do
    if [ -d "$PROJECT_DIR/$dir" ]; then
        echo "  ✓ $dir"
    else
        echo "  - $dir (not found)"
    fi
done
echo ""

# Run pytest with all arguments passed through
# Use importlib import mode to avoid namespace conflicts
echo "Running pytest..."
echo ""

poetry run python -m pytest --import-mode=importlib $PYTEST_PATHS "$@"

echo ""
echo -e "${GREEN}All unit tests completed!${NC}"

