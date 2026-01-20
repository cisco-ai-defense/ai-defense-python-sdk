#!/bin/bash
#
# Integration tests for simple examples
#
# Tests that each simple example runs successfully in BOTH API mode and Gateway mode.
# This ensures examples work correctly regardless of which integration mode is configured.
#
# Usage:
#   ./test-simple-examples.sh           # Normal mode (summary output)
#   ./test-simple-examples.sh -v        # Verbose mode (shows API requests/responses)
#   ./test-simple-examples.sh --verbose # Verbose mode
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIMPLE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
PROJECT_DIR="$(cd "$SIMPLE_DIR/../../.." && pwd)"

# Check poetry is available
if ! command -v poetry &> /dev/null; then
    echo -e "${RED}ERROR: Poetry is not installed${NC}"
    echo "Install Poetry: https://python-poetry.org/docs/#installation"
    exit 1
fi

# Ensure poetry dependencies are installed
if [ ! -f "$SIMPLE_DIR/poetry.lock" ]; then
    echo "Running 'poetry install' first..."
    cd "$SIMPLE_DIR"
    poetry install
fi

# Load shared environment variables from project .env
if [ -f "$PROJECT_DIR/examples/agentsec/.env" ]; then
    set -a
    source "$PROJECT_DIR/examples/agentsec/.env"
    set +a
fi

# Parse arguments
VERBOSE=false
for arg in "$@"; do
    case $arg in
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
    esac
done

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Track results
PASSED=0
FAILED=0
FAILED_TESTS=""

echo "=============================================="
echo "  Simple Examples Integration Tests"
echo "  (Testing both API mode and Gateway mode)"
echo "=============================================="
echo ""
echo "Project directory: $PROJECT_DIR"
echo "Simple examples directory: $SIMPLE_DIR"
if [ "$VERBOSE" = true ]; then
    echo -e "Verbose mode: ${GREEN}ENABLED${NC} (showing API requests/responses)"
else
    echo "Verbose mode: OFF (use -v or --verbose to enable)"
fi
echo ""

# Function to run a test with specific mode
run_test_with_mode() {
    local name="$1"
    local script="$2"
    local llm_mode="$3"  # "api" or "gateway"
    local mcp_mode="$4"  # "api" or "gateway"
    
    local test_name="$name [$llm_mode/$mcp_mode]"
    echo -e "${BLUE}► Testing: $test_name${NC}"
    
    # Capture output and exit code
    local output
    local exit_code
    local log_file=$(mktemp)
    
    # Run and capture output
    output=$(cd "$PROJECT_DIR" && \
        AGENTSEC_LLM_INTEGRATION_MODE="$llm_mode" \
        AGENTSEC_MCP_INTEGRATION_MODE="$mcp_mode" \
        AGENTSEC_LOG_LEVEL="DEBUG" \
        poetry run python "$script" 2>&1) || exit_code=$?
    exit_code=${exit_code:-0}
    
    # In verbose mode, show Cisco communication
    if [ "$VERBOSE" = true ]; then
        echo ""
        echo -e "    ${MAGENTA}═══════════════════════════════════════════════════════════════${NC}"
        echo -e "    ${MAGENTA}  CISCO AI DEFENSE COMMUNICATION [$llm_mode mode]${NC}"
        echo -e "    ${MAGENTA}═══════════════════════════════════════════════════════════════${NC}"
        
        # Show REQUEST sent to Cisco (API mode)
        if echo "$output" | grep -q "AI Defense.*request payload"; then
            echo ""
            echo -e "    ${CYAN}► REQUEST SENT TO CISCO AI DEFENSE:${NC}"
            echo "$output" | grep "AI Defense.*request payload" | while read line; do
                echo "$line" | sed 's/.*request payload: /      /'
            done
        fi
        
        # Show RESPONSE from Cisco (API mode)
        if echo "$output" | grep -q "AI Defense.*response:"; then
            echo ""
            echo -e "    ${CYAN}► RESPONSE FROM CISCO AI DEFENSE:${NC}"
            echo "$output" | grep "AI Defense.*response:" | while read line; do
                echo "$line" | sed 's/.*response: /      /'
            done
        fi
        
        # Show Gateway mode communication
        if echo "$output" | grep -q "Gateway.*request payload"; then
            echo ""
            echo -e "    ${CYAN}► GATEWAY REQUEST:${NC}"
            echo "$output" | grep "Gateway.*request payload" | sed 's/.*payload: /      /' | head -3
        fi
        
        if echo "$output" | grep -q "Gateway.*response:"; then
            echo ""
            echo -e "    ${CYAN}► GATEWAY RESPONSE:${NC}"
            echo "$output" | grep "Gateway.*response:" | sed 's/.*response: /      /' | head -3
        fi
        
        # Show decisions
        if echo "$output" | grep -q "decision:"; then
            echo ""
            echo -e "    ${CYAN}► DECISIONS:${NC}"
            echo "$output" | grep "decision:" | sed 's/^/      /'
        fi
        
        echo ""
        echo -e "    ${MAGENTA}═══════════════════════════════════════════════════════════════${NC}"
    fi
    
    # Check for errors in output
    local has_error=false
    
    # Check for Python exceptions (but not handled ones)
    if echo "$output" | grep -q "Traceback (most recent call last)"; then
        # Check if it's a handled exception (followed by "This is expected")
        if ! echo "$output" | grep -q "This is expected"; then
            has_error=true
        fi
    fi
    
    # Check for critical error messages
    if echo "$output" | grep -qE "^ERROR:|CRITICAL:|FATAL:"; then
        has_error=true
    fi
    
    # Check exit code
    if [ $exit_code -ne 0 ]; then
        has_error=true
    fi
    
    if [ "$has_error" = true ]; then
        echo -e "${RED}  ✗ FAILED${NC}"
        echo "  Exit code: $exit_code"
        echo "  Output:"
        echo "$output" | sed 's/^/    /'
        FAILED=$((FAILED + 1))
        FAILED_TESTS="$FAILED_TESTS\n  - $test_name"
    else
        echo -e "${GREEN}  ✓ PASSED${NC}"
        
        # Show key verification points
        if echo "$output" | grep -q "Patched clients:"; then
            local clients=$(echo "$output" | grep "Patched clients:" | head -1)
            echo "    $clients"
        fi
        
        # Show integration mode
        local integration_info=$(echo "$output" | grep -o "llm_integration=[^,]*" | head -1)
        if [ -n "$integration_info" ]; then
            echo "    Integration: $integration_info"
        fi
        
        # In verbose mode, we already showed real-time output above
        # Show a brief summary for non-verbose mode
        if [ "$VERBOSE" != true ]; then
            local decision_count=$(echo "$output" | grep -c "decision:" || true)
            if [ "$decision_count" -gt 0 ]; then
                echo "    Found $decision_count AI Defense decision(s)"
            fi
        fi
        
        PASSED=$((PASSED + 1))
    fi
    
    echo ""
}

# Verify agentsec protection activates with specific mode
verify_protection_with_mode() {
    local name="$1"
    local script="$2"
    local llm_mode="$3"
    local mcp_mode="$4"
    
    echo -e "${CYAN}  Verifying protection mode...${NC}"
    
    local output
    output=$(cd "$PROJECT_DIR" && \
        AGENTSEC_LLM_INTEGRATION_MODE="$llm_mode" \
        AGENTSEC_MCP_INTEGRATION_MODE="$mcp_mode" \
        AGENTSEC_LOG_LEVEL="DEBUG" \
        poetry run python "$script" 2>&1) || true
    
    # Check that agentsec loaded with correct mode
    if echo "$output" | grep -q "\[agentsec\]"; then
        # Extract and verify mode
        local mode_line=$(echo "$output" | grep "llm_integration=" | head -1)
        if echo "$mode_line" | grep -q "llm_integration=$llm_mode"; then
            echo -e "${GREEN}  ✓ Correct mode: LLM=$llm_mode, MCP=$mcp_mode${NC}"
            return 0
        else
            echo -e "${YELLOW}  ⚠ Mode mismatch - expected LLM=$llm_mode${NC}"
            echo "    Got: $mode_line"
            return 1
        fi
    else
        echo -e "${YELLOW}  ⚠ agentsec status message not found${NC}"
        return 1
    fi
}

# Run all tests for a single example in both modes
run_example_tests() {
    local name="$1"
    local script="$2"
    
    echo "=============================================="
    echo -e "  ${CYAN}$name${NC}"
    echo "=============================================="
    echo ""
    
    # Test in API mode
    run_test_with_mode "$name" "$script" "api" "api"
    verify_protection_with_mode "$name" "$script" "api" "api"
    echo ""
    
    # Test in Gateway mode
    run_test_with_mode "$name" "$script" "gateway" "gateway"
    verify_protection_with_mode "$name" "$script" "gateway" "gateway"
    echo ""
}

echo ""
echo "=============================================="
echo "  Running Tests in Both API and Gateway Modes"
echo "=============================================="
echo ""

# Test each example in both modes
run_example_tests "basic_protection.py" "examples/agentsec/1-simple/basic_protection.py"
run_example_tests "openai_example.py" "examples/agentsec/1-simple/openai_example.py"
run_example_tests "streaming_example.py" "examples/agentsec/1-simple/streaming_example.py"
run_example_tests "mcp_example.py" "examples/agentsec/1-simple/mcp_example.py"
run_example_tests "gateway_mode_example.py" "examples/agentsec/1-simple/gateway_mode_example.py"
run_example_tests "skip_inspection_example.py" "examples/agentsec/1-simple/skip_inspection_example.py"
run_example_tests "simple_strands_bedrock.py" "examples/agentsec/1-simple/simple_strands_bedrock.py"

echo "=============================================="
echo "  Test Results Summary"
echo "=============================================="
echo ""
echo -e "Total Tests: $((PASSED + FAILED))"
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"

if [ $FAILED -gt 0 ]; then
    echo -e "\nFailed tests:${FAILED_TESTS}"
    echo ""
    echo -e "${RED}Some tests failed!${NC}"
    exit 1
else
    echo ""
    echo -e "${GREEN}ALL TESTS PASSED!${NC}"
    echo ""
    echo "✓ All examples work in API mode"
    echo "✓ All examples work in Gateway mode"
    exit 0
fi
