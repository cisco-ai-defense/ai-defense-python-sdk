#!/bin/bash
#
# Run all integration tests across the project
#
# Usage:
#   ./scripts/run-integration-tests.sh              # Run all integration tests
#   ./scripts/run-integration-tests.sh --simple     # Run only simple examples tests
#   ./scripts/run-integration-tests.sh --agents     # Run only agent examples tests
#   ./scripts/run-integration-tests.sh --api        # Run only API mode tests
#   ./scripts/run-integration-tests.sh --gateway    # Run only Gateway mode tests
#   ./scripts/run-integration-tests.sh strands      # Run specific agent tests
#  ./scripts/run-integration-tests.sh --agents --gateway   # Combine flags
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Track results
TOTAL_PASSED=0
TOTAL_FAILED=0
FAILED_TESTS=""

echo -e "${BLUE}=============================================="
echo "  Running All Integration Tests"
echo -e "==============================================${NC}"
echo ""
echo -e "${RED}⚠️  WARNING: Integration tests take 5-20 minutes to complete.${NC}"
echo -e "${YELLOW}   Tests make real API calls to LLM providers and AI Defense.${NC}"
echo ""

# Parse arguments
RUN_SIMPLE=true
RUN_AGENTS=true
SPECIFIC_AGENT=""
MODE_FLAG=""  # --api or --gateway to pass to test scripts

while [[ $# -gt 0 ]]; do
    case $1 in
        --simple)
            RUN_AGENTS=false
            shift
            ;;
        --agents)
            RUN_SIMPLE=false
            shift
            ;;
        --api)
            MODE_FLAG="--api"
            shift
            ;;
        --gateway)
            MODE_FLAG="--gateway"
            shift
            ;;
        strands|langgraph|langchain|crewai|autogen|openai)
            RUN_SIMPLE=false
            SPECIFIC_AGENT="$1-agent"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--simple] [--agents] [--api] [--gateway] [strands|langgraph|langchain|crewai|autogen|openai]"
            exit 1
            ;;
    esac
done

# Show mode if specified
if [ -n "$MODE_FLAG" ]; then
    echo -e "${BLUE}Mode: ${YELLOW}${MODE_FLAG#--} mode only${NC}"
    echo ""
fi

# Function to run a test script
run_test() {
    local name="$1"
    local script="$2"
    local extra_args="$3"
    
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}► $name${NC}"
    if [ -n "$extra_args" ]; then
        echo -e "${BLUE}  Mode: $extra_args${NC}"
    fi
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    if [ ! -f "$script" ]; then
        echo -e "${YELLOW}  ⚠ Script not found: $script${NC}"
        return 0
    fi
    
    if [ ! -x "$script" ]; then
        echo -e "${YELLOW}  ⚠ Script not executable: $script${NC}"
        chmod +x "$script"
    fi
    
    local exit_code=0
    "$script" $extra_args || exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}  ✓ PASSED: $name${NC}"
        TOTAL_PASSED=$((TOTAL_PASSED + 1))
    else
        echo -e "${RED}  ✗ FAILED: $name (exit code: $exit_code)${NC}"
        TOTAL_FAILED=$((TOTAL_FAILED + 1))
        FAILED_TESTS="$FAILED_TESTS\n  - $name"
    fi
    
    echo ""
}

# Run simple examples integration tests
if [ "$RUN_SIMPLE" = true ]; then
    echo -e "${BLUE}══════════════════════════════════════════════"
    echo "  Simple Examples Integration Tests"
    echo -e "══════════════════════════════════════════════${NC}"
    echo ""
    
    run_test "Simple Examples" "examples/agentsec/1_simple/tests/integration/test-simple-examples.sh" "$MODE_FLAG"
fi

# Run agent examples integration tests
if [ "$RUN_AGENTS" = true ]; then
    echo -e "${BLUE}══════════════════════════════════════════════"
    echo "  Agent Examples Integration Tests"
    echo -e "══════════════════════════════════════════════${NC}"
    echo ""
    
    AGENTS=("strands-agent" "langgraph-agent" "langchain-agent" "crewai-agent" "autogen-agent" "openai-agent")
    
    for agent in "${AGENTS[@]}"; do
        # Skip if specific agent requested and this isn't it
        if [ -n "$SPECIFIC_AGENT" ] && [ "$agent" != "$SPECIFIC_AGENT" ]; then
            continue
        fi
        
        test_script="examples/agentsec/2_agent-frameworks/$agent/tests/integration/test-all-providers.sh"
        if [ -f "$test_script" ]; then
            run_test "$agent" "$test_script" "$MODE_FLAG"
        else
            echo -e "${YELLOW}  ⚠ No integration test found for $agent${NC}"
            echo ""
        fi
    done
fi

# Summary
echo -e "${BLUE}=============================================="
echo "  Integration Test Results Summary"
echo -e "==============================================${NC}"
echo ""
echo -e "Passed: ${GREEN}$TOTAL_PASSED${NC}"
echo -e "Failed: ${RED}$TOTAL_FAILED${NC}"

if [ $TOTAL_FAILED -gt 0 ]; then
    echo -e "\nFailed tests:${FAILED_TESTS}"
    echo ""
    echo -e "${RED}Some integration tests failed!${NC}"
    exit 1
else
    echo ""
    echo -e "${GREEN}ALL INTEGRATION TESTS PASSED!${NC}"
    exit 0
fi





