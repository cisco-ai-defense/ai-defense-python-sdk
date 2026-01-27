#!/bin/bash
# =============================================================================
# OpenAI Agent Integration Tests
# =============================================================================
# Tests all 4 providers (Bedrock, Azure, GCP Vertex AI, OpenAI) in BOTH modes:
#   - API Mode: Inspection via Cisco AI Defense API
#   - Gateway Mode: Route through Cisco AI Defense Gateway
#
# For each test, verifies:
#   1. LLM calls are intercepted by AI Defense
#   2. MCP tool calls are made and intercepted
#   3. No errors occur during execution
#
# Usage:
#   ./tests/integration/test-all-providers.sh           # Run all tests (both modes)
#   ./tests/integration/test-all-providers.sh --verbose # Verbose: show Cisco requests/responses
#   ./tests/integration/test-all-providers.sh --api     # API mode only
#   ./tests/integration/test-all-providers.sh --gateway # Gateway mode only
#   ./tests/integration/test-all-providers.sh openai    # Test single provider
# =============================================================================

set -o pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Get script and project directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
# Poetry is used instead of venv
LOG_DIR="$SCRIPT_DIR/logs"

# Test configuration
TIMEOUT_SECONDS=120
# Test question - uses fetch_url tool (same MCP server for both API and Gateway modes)
TEST_QUESTION="Use the fetch_url tool to fetch https://example.com and tell me what this domain is for."

# Detect timeout command (gtimeout on macOS via homebrew, timeout on Linux)
if command -v gtimeout &> /dev/null; then
    TIMEOUT_CMD="gtimeout"
elif command -v timeout &> /dev/null; then
    TIMEOUT_CMD="timeout"
else
    TIMEOUT_CMD=""
fi

# Available providers and modes
ALL_PROVIDERS=("openai" "azure")
ALL_MODES=("api" "gateway")

# Counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# =============================================================================
# Helper Functions
# =============================================================================

log_header() {
    echo ""
    echo -e "${BOLD}${BLUE}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${BLUE}  $1${NC}"
    echo -e "${BOLD}${BLUE}════════════════════════════════════════════════════════════════${NC}"
}

log_subheader() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

log_pass() {
    echo -e "  ${GREEN}✓ PASS${NC}: $1"
}

log_fail() {
    echo -e "  ${RED}✗ FAIL${NC}: $1"
}

log_skip() {
    echo -e "  ${YELLOW}⊘ SKIP${NC}: $1"
}

log_info() {
    echo -e "  ${BLUE}ℹ${NC} $1"
}

log_detail() {
    if [ "$VERBOSE" = "true" ]; then
        echo -e "    ${NC}$1${NC}"
    fi
}

log_verbose_section() {
    if [ "$VERBOSE" = "true" ]; then
        echo -e "    ${MAGENTA}$1${NC}"
    fi
}

show_help() {
    echo "Usage: $0 [OPTIONS] [PROVIDER]"
    echo ""
    echo "Options:"
    echo "  --verbose, -v    Show detailed output including Cisco API requests/responses"
    echo "  --api            Test API mode only (default: both modes)"
    echo "  --gateway        Test Gateway mode only (default: both modes)"
    echo "  --help, -h       Show this help"
    echo ""
    echo "Providers:"
    echo "  openai           Test OpenAI provider"
    echo "  azure            Test Azure OpenAI provider"
    echo "  vertex           Test GCP Vertex AI (Vertex AI) provider"
    echo "  bedrock          Test AWS Bedrock provider"
    echo ""
    echo "Examples:"
    echo "  $0                      # Run all provider tests (both modes)"
    echo "  $0 --verbose            # Run all tests with Cisco API details"
    echo "  $0 --api openai         # Test only OpenAI in API mode"
    echo "  $0 --gateway strands    # Test only in Gateway mode"
}

setup_log_dir() {
    mkdir -p "$LOG_DIR"
    # Clean old logs
    rm -f "$LOG_DIR"/*.log 2>/dev/null || true
}

check_config_exists() {
    local provider=$1
    local config_file="$PROJECT_DIR/config/config-${provider}.yaml"
    
    if [ ! -f "$config_file" ]; then
        return 1
    fi
    return 0
}

# =============================================================================
# Verbose Output Functions - Show Cisco Requests/Responses
# =============================================================================

show_verbose_output() {
    local log_file=$1
    local mode=$2
    
    if [ "$VERBOSE" != "true" ]; then
        return
    fi
    
    echo ""
    echo -e "    ${MAGENTA}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "    ${MAGENTA}  Cisco AI Defense Communication ($mode mode)${NC}"
    echo -e "    ${MAGENTA}═══════════════════════════════════════════════════════════════${NC}"
    
    if [ "$mode" = "api" ]; then
        # Show API mode - Request payload
        if grep -q "AI Defense.*request payload" "$log_file"; then
            echo ""
            echo -e "    ${CYAN}┌─ REQUEST SENT TO CISCO AI DEFENSE API ─────────────────────────${NC}"
            # Show full first request line
            grep "AI Defense.*request payload" "$log_file" | head -1 | sed 's/^[^{]*/      /' | fold -w 100 | head -10
            echo -e "    ${CYAN}└────────────────────────────────────────────────────────────────${NC}"
        fi
        
        # Show API mode - Response
        if grep -q "AI Defense.*response:" "$log_file"; then
            echo ""
            echo -e "    ${CYAN}┌─ RESPONSE FROM CISCO AI DEFENSE API ──────────────────────────${NC}"
            # Extract key fields from response
            local response_line=$(grep "AI Defense.*response:" "$log_file" | head -1)
            local action=$(echo "$response_line" | grep -o "'action': '[^']*'" | head -1 | sed "s/'//g")
            local is_safe=$(echo "$response_line" | grep -o "'is_safe': [^,}]*" | head -1 | sed "s/'//g")
            local severity=$(echo "$response_line" | grep -o "'severity': '[^']*'" | head -1 | sed "s/'//g")
            echo "      $action"
            echo "      $is_safe"
            echo "      $severity"
            # Show processed rules
            echo "      Processed rules:"
            echo "$response_line" | grep -o "'rule_name': '[^']*'" | head -5 | while read rule; do
                echo "        - $(echo "$rule" | sed "s/'rule_name': '//;s/'$//")"
            done
            echo -e "    ${CYAN}└────────────────────────────────────────────────────────────────${NC}"
        fi
    else
        # Show Gateway mode - Request
        if grep -q "Gateway.*request" "$log_file"; then
            echo ""
            echo -e "    ${CYAN}┌─ REQUEST SENT TO CISCO GATEWAY ───────────────────────────────${NC}"
            # Show gateway URL
            grep "Gateway request to" "$log_file" | head -1 | sed 's/^.*Gateway request to /      URL: /'
            # Show full request payload
            grep "Gateway.*request payload" "$log_file" | head -1 | sed 's/^[^{]*/      /' | fold -w 100 | head -10
            echo -e "    ${CYAN}└────────────────────────────────────────────────────────────────${NC}"
        fi
        
        # Show Gateway mode - Response
        if grep -q "Gateway.*response:" "$log_file"; then
            echo ""
            echo -e "    ${CYAN}┌─ RESPONSE FROM CISCO GATEWAY ─────────────────────────────────${NC}"
            local response_line=$(grep "Gateway.*response:" "$log_file" | head -1)
            # Extract content and model
            local content=$(echo "$response_line" | grep -o "'content': '[^']*'" | head -1 | sed "s/'content': '//;s/'$//")
            local model=$(echo "$response_line" | grep -o "'model': '[^']*'" | head -1 | sed "s/'model': '//;s/'$//")
            local tokens=$(echo "$response_line" | grep -o "'total_tokens': [0-9]*" | head -1 | sed "s/'total_tokens': //")
            echo "      Model: $model"
            echo "      Response: ${content:0:200}..."
            echo "      Tokens: $tokens"
            echo -e "    ${CYAN}└────────────────────────────────────────────────────────────────${NC}"
        fi
    fi
    
    # Show MCP inspection (both modes)
    if grep -q "MCP.*request payload\|MCP.*response:" "$log_file"; then
        echo ""
        echo -e "    ${CYAN}┌─ MCP TOOL INSPECTION ─────────────────────────────────────────${NC}"
        # Show MCP request
        if grep -q "MCP.*request payload" "$log_file"; then
            grep "MCP.*request payload" "$log_file" | head -1 | sed 's/^[^{]*/      Request: /' | fold -w 100 | head -3
        fi
        # Show MCP response action
        local mcp_response=$(grep "MCP.*response:" "$log_file" | head -1)
        if [ -n "$mcp_response" ]; then
            local mcp_action=$(echo "$mcp_response" | grep -o "'action': '[^']*'" | head -1 | sed "s/'//g")
            echo "      Response: $mcp_action"
        fi
        echo -e "    ${CYAN}└────────────────────────────────────────────────────────────────${NC}"
    fi
    
    # Show AI Defense decisions summary
    if grep -q "Request decision:\|Response decision:" "$log_file"; then
        echo ""
        echo -e "    ${CYAN}┌─ AI DEFENSE DECISIONS ────────────────────────────────────────${NC}"
        grep -E "Request decision:|Response decision:" "$log_file" | head -6 | while read line; do
            echo "      $(echo "$line" | sed 's/.*\[PATCHED CALL\] //')"
        done
        echo -e "    ${CYAN}└────────────────────────────────────────────────────────────────${NC}"
    fi
    
    echo ""
}

# =============================================================================
# Test Functions
# =============================================================================

test_provider_with_mode() {
    local provider=$1
    local mode=$2
    local config_file="config/config-${provider}.yaml"
    local log_file="$LOG_DIR/${provider}-${mode}.log"
    
    log_subheader "Testing: $provider [$mode mode]"
    
    # Check config exists
    if ! check_config_exists "$provider"; then
        log_skip "Config file not found: $config_file"
        ((TESTS_SKIPPED++))
        return 2
    fi
    log_info "Using config: $config_file"
    log_info "Integration mode: $mode"
    
    # Run the test
    log_info "Running test with question: \"$TEST_QUESTION\""
    if [ -n "$TIMEOUT_CMD" ]; then
        log_info "Timeout: ${TIMEOUT_SECONDS}s (using $TIMEOUT_CMD)"
    else
        log_info "Timeout: disabled (install coreutils for timeout support)"
    fi
    
    cd "$PROJECT_DIR"
    export CONFIG_FILE="$config_file"
    
    # Set integration mode via environment variables
    export AGENTSEC_LLM_INTEGRATION_MODE="$mode"
    export AGENTSEC_MCP_INTEGRATION_MODE="$mode"
    
    # Enable debug logging for verbose output
    if [ "$VERBOSE" = "true" ]; then
        export AGENTSEC_LOG_LEVEL="DEBUG"
    fi
    
    # Capture both stdout and stderr
    local start_time=$(date +%s)
    
    # Use poetry run python
    local PYTHON_CMD="poetry run python"
    
    # In verbose mode, capture output then show Cisco communication clearly
    if [ "$VERBOSE" = "true" ]; then
        # Run and capture to log file
        if [ -n "$TIMEOUT_CMD" ]; then
            $TIMEOUT_CMD "$TIMEOUT_SECONDS" $PYTHON_CMD agent.py "$TEST_QUESTION" > "$log_file" 2>&1 || local exit_code=$?
        else
            $PYTHON_CMD agent.py "$TEST_QUESTION" > "$log_file" 2>&1 || local exit_code=$?
        fi
        exit_code=${exit_code:-0}
        
        # Now show Cisco communication in a clear format
        echo ""
        echo -e "    ${MAGENTA}═══════════════════════════════════════════════════════════════${NC}"
        echo -e "    ${MAGENTA}  CISCO AI DEFENSE COMMUNICATION${NC}"
        echo -e "    ${MAGENTA}═══════════════════════════════════════════════════════════════${NC}"
        echo ""
        
        # Show all LLM calls
        if grep -q "PATCHED.*LLM CALL" "$log_file"; then
            echo -e "    ${CYAN}► LLM CALLS INTERCEPTED:${NC}"
            grep "PATCHED.*LLM CALL" "$log_file" | sed 's/^/      /'
            echo ""
        fi
        
        # Show REQUEST sent to Cisco (API mode)
        if grep -q "AI Defense.*request payload" "$log_file"; then
            echo -e "    ${CYAN}► REQUEST SENT TO CISCO AI DEFENSE:${NC}"
            grep "AI Defense.*request payload" "$log_file" | while read line; do
                # Extract just the JSON payload
                echo "$line" | sed 's/.*request payload: /      /'
            done
            echo ""
        fi
        
        # Show RESPONSE from Cisco (API mode)
        if grep -q "AI Defense.*response:" "$log_file"; then
            echo -e "    ${CYAN}► RESPONSE FROM CISCO AI DEFENSE:${NC}"
            grep "AI Defense.*response:" "$log_file" | while read line; do
                # Extract just the JSON response
                echo "$line" | sed 's/.*response: /      /'
            done
            echo ""
        fi
        
        # Show Gateway mode communication
        if grep -q "Gateway request to" "$log_file"; then
            echo -e "    ${CYAN}► GATEWAY REQUESTS:${NC}"
            grep "Gateway request to" "$log_file" | sed 's/^/      /'
            echo ""
        fi
        
        if grep -q "Gateway.*request payload" "$log_file"; then
            echo -e "    ${CYAN}► GATEWAY REQUEST PAYLOAD:${NC}"
            grep "Gateway.*request payload" "$log_file" | sed 's/.*payload: /      /' | head -5
            echo ""
        fi
        
        if grep -q "Gateway.*response:" "$log_file"; then
            echo -e "    ${CYAN}► GATEWAY RESPONSE:${NC}"
            grep "Gateway.*response:" "$log_file" | sed 's/.*response: /      /' | head -5
            echo ""
        fi
        
        # Show MCP inspection
        if grep -q "MCP.*inspection" "$log_file"; then
            echo -e "    ${CYAN}► MCP TOOL INSPECTION:${NC}"
            grep "MCP.*inspection" "$log_file" | sed 's/^/      /'
            echo ""
        fi
        
        # Show decisions
        if grep -q "decision:" "$log_file"; then
            echo -e "    ${CYAN}► DECISIONS:${NC}"
            grep "decision:" "$log_file" | sed 's/^/      /'
            echo ""
        fi
        
        echo -e "    ${MAGENTA}═══════════════════════════════════════════════════════════════${NC}"
    else
        # Non-verbose: just capture to log file
        if [ -n "$TIMEOUT_CMD" ]; then
            if $TIMEOUT_CMD "$TIMEOUT_SECONDS" $PYTHON_CMD agent.py "$TEST_QUESTION" > "$log_file" 2>&1; then
                local exit_code=0
            else
                local exit_code=$?
            fi
        else
            if $PYTHON_CMD agent.py "$TEST_QUESTION" > "$log_file" 2>&1; then
                local exit_code=0
            else
                local exit_code=$?
            fi
        fi
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_info "Completed in ${duration}s (exit code: $exit_code)"
    
    # Show summary from log file (only in non-verbose mode, verbose shows real-time)
    if [ "$VERBOSE" != "true" ]; then
        show_verbose_output "$log_file" "$mode"
    fi
    
    # Check for timeout
    if [ $exit_code -eq 124 ]; then
        log_fail "Test timed out after ${TIMEOUT_SECONDS}s"
        ((TESTS_FAILED++))
        return 1
    fi
    
    # Check for Python errors
    if [ $exit_code -ne 0 ]; then
        log_fail "Python script exited with error (code: $exit_code)"
        if [ "$VERBOSE" = "true" ]; then
            echo ""
            echo "  Last 20 lines of output:"
            tail -20 "$log_file" | sed 's/^/    /'
        fi
        ((TESTS_FAILED++))
        return 1
    fi
    
    # Validate test results
    local all_checks_passed=true
    
    # Check 1: LLM call was intercepted
    if grep -q "\[PATCHED\] LLM CALL" "$log_file" || grep -q "\[PATCHED CALL\]" "$log_file"; then
        log_pass "LLM call intercepted by AI Defense"
        log_detail "$(grep -m1 'PATCHED.*LLM CALL' "$log_file" | head -1)"
    else
        log_fail "LLM call NOT intercepted (no PATCHED LLM CALL in log)"
        all_checks_passed=false
    fi
    
    # Check 2: MCP tool call was made
    if grep -q "MCP TOOL CALL" "$log_file" || grep -q "\[TOOL\]" "$log_file"; then
        log_pass "MCP tool call executed"
        log_detail "$(grep -m1 'MCP TOOL CALL\|Got response' "$log_file" | head -1)"
    else
        log_fail "MCP tool call NOT executed"
        all_checks_passed=false
    fi
    
    # Check 3: AI Defense decisions were made (mode-specific)
    if [ "$mode" = "api" ]; then
        if grep -q "Request decision: allow" "$log_file" || grep -q "Response decision: allow" "$log_file"; then
            log_pass "AI Defense API decisions received"
            local request_decisions=$(grep -c "Request decision:" "$log_file" || echo "0")
            log_detail "Found $request_decisions AI Defense decision(s)"
        else
            log_fail "No AI Defense API decisions found in log"
            all_checks_passed=false
        fi
    else
        # Gateway mode - check for gateway communication
        if grep -qE "Gateway.*response|Gateway handled|\[MCP GATEWAY\]|MCPGatewayInspector|gateway handles" "$log_file"; then
            log_pass "Gateway mode communication successful"
        else
            log_fail "No Gateway communication found in log"
            all_checks_passed=false
        fi
    fi
    
    # Check 4: No ERROR or BLOCKED in output
    # Exclude DEBUG-level log messages that contain "Error" as part of normal operation
    # Focus on actual errors: Python tracebacks, BLOCKED decisions, ERROR log level
    if grep -E "^Traceback|BLOCKED|^\s*ERROR\s*:|raise |SecurityPolicyError" "$log_file" | grep -v "DEBUG:" > /dev/null 2>&1; then
        local error_line=$(grep -E "^Traceback|BLOCKED|^\s*ERROR\s*:|raise |SecurityPolicyError" "$log_file" | grep -v "DEBUG:" | head -1)
        log_fail "Errors found in output: $error_line"
        all_checks_passed=false
    else
        log_pass "No errors or blocks in output"
    fi
    
    # Check 5: Got a final response
    if grep -q "Assistant:" "$log_file" || grep -q "final response\|Response:" "$log_file"; then
        log_pass "Agent produced final response"
    else
        # This is a soft check - don't fail if other checks passed
        log_info "Could not verify final response (may be OK)"
    fi
    
    # Summary for this provider/mode
    if [ "$all_checks_passed" = "true" ]; then
        echo ""
        echo -e "  ${GREEN}${BOLD}► $provider [$mode]: ALL CHECKS PASSED${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo ""
        echo -e "  ${RED}${BOLD}► $provider [$mode]: SOME CHECKS FAILED${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

# =============================================================================
# Main
# =============================================================================

VERBOSE="false"
PROVIDERS_TO_TEST=()
MODES_TO_TEST=()

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_help
            exit 0
            ;;
        --verbose|-v)
            VERBOSE="true"
            shift
            ;;
        --api)
            MODES_TO_TEST+=("api")
            shift
            ;;
        --gateway)
            MODES_TO_TEST+=("gateway")
            shift
            ;;
        openai|azure|vertex|bedrock)
            PROVIDERS_TO_TEST+=("$1")
            shift
            ;;
        *)
            echo -e "${RED}Unknown argument: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Default to all providers if none specified
if [ ${#PROVIDERS_TO_TEST[@]} -eq 0 ]; then
    PROVIDERS_TO_TEST=("${ALL_PROVIDERS[@]}")
fi

# Default to both modes if none specified
if [ ${#MODES_TO_TEST[@]} -eq 0 ]; then
    MODES_TO_TEST=("${ALL_MODES[@]}")
fi

# Setup
log_header "OpenAI Agent Integration Tests"
echo ""
echo "  Project:   $PROJECT_DIR"
echo "  Providers: ${PROVIDERS_TO_TEST[*]}"
echo "  Modes:     ${MODES_TO_TEST[*]}"
echo "  Verbose:   $VERBOSE"

# Check poetry is available
if ! command -v poetry &> /dev/null; then
    echo ""
    echo -e "${RED}ERROR: Poetry is not installed${NC}"
    echo "Install Poetry: https://python-poetry.org/docs/#installation"
    exit 1
fi

# Check poetry.lock exists (setup has been run)
if [ ! -f "$PROJECT_DIR/poetry.lock" ]; then
    echo ""
    echo -e "${YELLOW}Running 'poetry install' first...${NC}"
    cd "$PROJECT_DIR"
    poetry install
fi

# Load shared environment variables (includes AGENTSEC_LLM_RULES)
SHARED_ENV="$PROJECT_DIR/../../.env"
if [ -f "$SHARED_ENV" ]; then
    log_info "Loading environment from $SHARED_ENV"
    set -a  # automatically export all variables
    source "$SHARED_ENV"
    set +a
fi

# Setup log directory
setup_log_dir

# Run tests
log_header "Running Tests"

for provider in "${PROVIDERS_TO_TEST[@]}"; do
    for mode in "${MODES_TO_TEST[@]}"; do
        test_provider_with_mode "$provider" "$mode"
    done
done

# Summary
log_header "Test Summary"
echo ""
echo -e "  ${GREEN}Passed${NC}:  $TESTS_PASSED"
echo -e "  ${RED}Failed${NC}:  $TESTS_FAILED"
echo -e "  ${YELLOW}Skipped${NC}: $TESTS_SKIPPED"
echo ""

TOTAL=$((TESTS_PASSED + TESTS_FAILED))
if [ $TESTS_FAILED -eq 0 ] && [ $TOTAL -gt 0 ]; then
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}${BOLD}  ✓ ALL TESTS PASSED ($TESTS_PASSED/$TOTAL)${NC}"
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    exit 0
else
    echo -e "${RED}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}${BOLD}  ✗ TESTS FAILED ($TESTS_FAILED/$TOTAL failed)${NC}"
    echo -e "${RED}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "  Logs available at: $LOG_DIR/"
    exit 1
fi
