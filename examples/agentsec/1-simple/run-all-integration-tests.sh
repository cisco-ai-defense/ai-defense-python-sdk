#!/bin/bash
# =============================================================================
# Run All Simple Examples Integration Tests
# =============================================================================
# Runs tests/integration/test-simple-examples.sh
# Tests all simple examples in BOTH API mode and Gateway mode.
# 
# Usage:
#   ./run-all-integration-tests.sh           # Run all tests, both modes
#   ./run-all-integration-tests.sh --verbose # Verbose: show Cisco API requests/responses
#   ./run-all-integration-tests.sh -v        # Same as --verbose
# =============================================================================

set -o pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Simple examples to test
EXAMPLES=(
    "basic_protection.py"
    "openai_example.py"
    "streaming_example.py"
    "mcp_example.py"
    "gateway_mode_example.py"
    "skip_inspection_example.py"
    "simple_strands_bedrock.py"
)

# Parse arguments
VERBOSE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --verbose, -v    Show detailed output including Cisco API requests/responses"
            echo "  --help, -h       Show this help"
            echo ""
            echo "Examples:"
            echo "  $0                # Run all tests in both API and Gateway modes"
            echo "  $0 --verbose      # Run with detailed Cisco API communication"
            exit 0
            ;;
        --verbose|-v)
            VERBOSE="--verbose"
            shift
            ;;
        *)
            echo -e "${RED}Unknown argument: $1${NC}"
            exit 1
            ;;
    esac
done

# =============================================================================
# Warning Banner
# =============================================================================
echo ""
echo -e "${BOLD}${BLUE}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${BLUE}║         SIMPLE EXAMPLES INTEGRATION TEST SUITE                   ║${NC}"
echo -e "${BOLD}${BLUE}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}${BOLD}⚠️  WARNING: This will run live integration tests!${NC}"
echo ""
echo -e "   These tests make ${BOLD}real API calls${NC} to:"
echo -e "   • Cisco AI Defense API (API mode)"
echo -e "   • Cisco AI Defense Gateway (Gateway mode)"
echo -e "   • OpenAI API"
echo -e "   • AWS Bedrock"
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Test Plan:${NC}"
echo ""
echo -e "   ${GREEN}✓${NC} ${BOLD}Simple Examples${NC}"
echo -e "     Examples: ${#EXAMPLES[@]} (each tested in API + Gateway mode)"
echo -e "     Total tests: $((${#EXAMPLES[@]} * 2))"
echo ""

for example in "${EXAMPLES[@]}"; do
    echo -e "       • $example"
done

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Summary:${NC}"
echo -e "   Total examples: ${#EXAMPLES[@]}"
echo -e "   Total tests:    $((${#EXAMPLES[@]} * 2)) (API + Gateway mode each)"
echo -e "   Estimated time: ${BOLD}~3-5 minutes${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Confirmation
read -p "$(echo -e ${YELLOW}Press ENTER to continue or Ctrl+C to cancel...${NC})" -r
echo ""

# =============================================================================
# Load Environment
# =============================================================================
SHARED_ENV="$SCRIPT_DIR/../.env"
if [ -f "$SHARED_ENV" ]; then
    echo -e "${BLUE}ℹ${NC} Loading environment from $SHARED_ENV"
    set -a
    source "$SHARED_ENV"
    set +a
else
    echo -e "${RED}ERROR: ../.env not found${NC}"
    echo "Please create $SHARED_ENV with required credentials"
    exit 1
fi

# =============================================================================
# Run Tests
# =============================================================================
START_TIME=$(date +%s)

echo ""
echo -e "${BOLD}${BLUE}════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${BLUE}  Running Integration Tests${NC}"
echo -e "${BOLD}${BLUE}════════════════════════════════════════════════════════════════════${NC}"

TEST_SCRIPT="$SCRIPT_DIR/tests/integration/test-simple-examples.sh"

if [ ! -f "$TEST_SCRIPT" ]; then
    echo -e "  ${RED}✗ ERROR${NC}: Test script not found: $TEST_SCRIPT"
    exit 1
fi

# Run the test script
cd "$SCRIPT_DIR"
if bash "$TEST_SCRIPT" $VERBOSE; then
    TEST_RESULT="PASSED"
    EXIT_CODE=0
else
    TEST_RESULT="FAILED"
    EXIT_CODE=1
fi

# =============================================================================
# Final Summary
# =============================================================================
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
DURATION_MIN=$((DURATION / 60))
DURATION_SEC=$((DURATION % 60))

echo ""
echo ""
echo -e "${BOLD}${BLUE}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${BLUE}║                    FINAL TEST SUMMARY                            ║${NC}"
echo -e "${BOLD}${BLUE}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""

if [ "$TEST_RESULT" = "PASSED" ]; then
    echo -e "   simple-examples: ${GREEN}✅ PASSED${NC}"
else
    echo -e "   simple-examples: ${RED}❌ FAILED${NC}"
fi

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "   Duration: ${DURATION_MIN}m ${DURATION_SEC}s"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ "$TEST_RESULT" = "PASSED" ]; then
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}${BOLD}  ✅ ALL INTEGRATION TESTS PASSED!${NC}"
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════════════════${NC}"
else
    echo -e "${RED}${BOLD}═══════════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}${BOLD}  ❌ SOME TESTS FAILED${NC}"
    echo -e "${RED}${BOLD}═══════════════════════════════════════════════════════════════════${NC}"
fi

exit $EXIT_CODE
