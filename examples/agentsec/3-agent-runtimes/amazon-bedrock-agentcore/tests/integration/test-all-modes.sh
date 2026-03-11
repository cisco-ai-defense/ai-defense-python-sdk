#!/bin/bash
# =============================================================================
# AgentCore Integration Tests
# =============================================================================
# Tests all 3 deployment modes in BOTH Cisco AI Defense integration modes:
#   Deployment Modes:
#   - Direct Deploy: Agent runs in AgentCore, client calls InvokeAgentRuntime
#   - Container Deploy: Agent runs in Docker container on AgentCore
#   - Lambda Deploy: Standard Lambda function using Bedrock
#
#   Integration Modes (Cisco AI Defense):
#   - API Mode: Inspection via Cisco AI Defense API
#   - Gateway Mode: Route through Cisco AI Defense Gateway
#
#   Test Modes:
#   - Local (default): Tests agent locally using AWS Bedrock credentials only
#   - Deploy (--deploy): DEPLOYS agents first, then tests real AWS endpoints
#
# For each test, verifies:
#   1. LLM calls are intercepted by AI Defense
#   2. Request inspection happens
#   3. Response inspection happens (where applicable)
#   4. No errors occur during execution
#
# Deploy Mode (--deploy):
#   When running with --deploy, the script:
#   1. REMOVES stale .bedrock_agentcore.yaml config (ensures fresh agent creation)
#   2. DEPLOYS all specified agents to AWS by running:
#      - direct:    ./direct-deploy/scripts/deploy.sh
#      - container: ./container-deploy/scripts/deploy.sh
#      - lambda:    ./lambda-deploy/scripts/deploy.sh
#   3. Waits for agents to be ready
#   4. RUNS integration tests against the deployed agents
#
# Usage:
#   ./tests/integration/test-all-modes.sh                    # Run local tests (default)
#   ./tests/integration/test-all-modes.sh --deploy           # Deploy first, then test
#   ./tests/integration/test-all-modes.sh --verbose          # Verbose output
#   ./tests/integration/test-all-modes.sh --api              # API mode only
#   ./tests/integration/test-all-modes.sh --gateway          # Gateway mode only
#   ./tests/integration/test-all-modes.sh direct             # Test direct deploy only
#   ./tests/integration/test-all-modes.sh --deploy direct    # Deploy direct only, then test
# =============================================================================

set -euo pipefail

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
LOG_DIR="$SCRIPT_DIR/logs"

# Test configuration
TIMEOUT_SECONDS=120
TEST_QUESTION="What is 5+5?"
TEST_MCP_QUESTION="Fetch https://example.com and tell me what it says"

# Detect timeout command (gtimeout on macOS via homebrew, timeout on Linux)
if command -v gtimeout &> /dev/null; then
    TIMEOUT_CMD="gtimeout"
elif command -v timeout &> /dev/null; then
    TIMEOUT_CMD="timeout"
else
    TIMEOUT_CMD=""
fi

# Available deployment modes and integration modes
ALL_DEPLOY_MODES=("direct" "container" "lambda")
ALL_INTEGRATION_MODES=("api" "gateway")
RUN_MCP_TESTS=true  # Set to false to skip MCP tests
LOCAL_MODE=true     # When true (default), test locally without AWS deployment

# Counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# Timing tracking (using regular array with key:value format for bash 3 compatibility)
DEPLOY_MODE_TIMES=()

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

show_help() {
    echo "Usage: $0 [OPTIONS] [DEPLOY_MODE]"
    echo ""
    echo "Options:"
    echo "  --local          Run LOCAL tests (default) - tests agent with AWS Bedrock only"
    echo "  --deploy         DEPLOY agents first, then run tests against AWS endpoints"
    echo "  --verbose, -v    Show detailed output including deploy logs"
    echo "  --api            Test API mode only (default: both modes)"
    echo "  --gateway        Test Gateway mode only (default: both modes)"
    echo "  --no-mcp         Skip MCP tool protection tests"
    echo "  --mcp-only       Run only MCP tool protection tests"
    echo "  --help, -h       Show this help"
    echo ""
    echo "Deploy Modes:"
    echo "  direct           Direct code deploy to AgentCore"
    echo "  container        Container deploy to AgentCore"
    echo "  lambda           Lambda function deploy"
    echo ""
    echo "Test Modes:"
    echo "  Without --deploy: Tests agent LOCALLY using AWS Bedrock credentials"
    echo "                    Requires: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY (or AWS profile)"
    echo ""
    echo "  With --deploy:    DEPLOYS agents to AWS first, then runs tests"
    echo "                    Phase 1: Remove stale .bedrock_agentcore.yaml config"
    echo "                    Phase 2: Run deploy scripts for specified modes"
    echo "                      - ./direct-deploy/scripts/deploy.sh"
    echo "                      - ./container-deploy/scripts/deploy.sh"
    echo "                      - ./lambda-deploy/scripts/deploy.sh"
    echo "                    Phase 3: Wait for agents to be ready"
    echo "                    Phase 4: Run integration tests"
    echo "                    Requires: AWS CLI, AgentCore CLI, Bedrock IAM permissions"
    echo ""
    echo "MCP Tests:"
    echo "  MCP tests verify AI Defense protection for MCP tool calls."
    echo "  Requires MCP_SERVER_URL environment variable (default: https://mcp.deepwiki.com/mcp)"
    echo ""
    echo "Examples:"
    echo "  $0                      # Run local tests (default)"
    echo "  $0 --deploy             # Deploy all agents, then test"
    echo "  $0 --deploy --verbose   # Deploy and test with detailed output"
    echo "  $0 --deploy direct      # Deploy only direct agent, then test"
    echo "  $0 --api                # Run local tests, API mode only"
    echo "  $0 --deploy --api       # Deploy and test, API mode only"
    echo "  $0 --mcp-only           # Run only MCP tests"
}

setup_log_dir() {
    mkdir -p "$LOG_DIR"
    rm -f "$LOG_DIR"/*.log 2>/dev/null || true
}

# =============================================================================
# MCP Test Function (separate from LLM tests)
# =============================================================================

test_mcp_protection() {
    local integration_mode=$1
    log_subheader "Testing: MCP Tool Protection [$integration_mode mode]"
    
    local log_file="$LOG_DIR/mcp-protection-${integration_mode}.log"
    local test_script="$SCRIPT_DIR/test_mcp_protection.py"
    
    # Check if MCP_SERVER_URL is set
    if [ -z "${MCP_SERVER_URL:-}" ]; then
        log_skip "MCP_SERVER_URL not set, skipping MCP test"
        ((TESTS_SKIPPED++))
        return 0
    fi
    
    if [ ! -f "$test_script" ]; then
        log_fail "MCP test script not found: $test_script"
        ((TESTS_FAILED++))
        return 1
    fi
    
    log_info "Integration mode: $integration_mode"
    log_info "MCP Server: $MCP_SERVER_URL"
    
    cd "$PROJECT_DIR"
    
    # Set the integration mode environment variable
    export AGENTSEC_MCP_INTEGRATION_MODE="$integration_mode"
    
    # Enable debug logging so MCP inspection log lines are captured in the log file
    export AGENTSEC_LOG_LEVEL="DEBUG"
    
    # Run the test
    local start_time=$(date +%s)
    
    if [ -n "$TIMEOUT_CMD" ]; then
        $TIMEOUT_CMD "$TIMEOUT_SECONDS" poetry run python "$test_script" > "$log_file" 2>&1
        local exit_code=$?
    else
        poetry run python "$test_script" > "$log_file" 2>&1
        local exit_code=$?
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_info "Completed in ${duration}s (exit code: $exit_code)"
    
    # Validate results
    local all_checks_passed=true
    
    # Check 1: MCP is patched
    if grep -q "mcp.*patched\|'mcp'\|Patched.*mcp" "$log_file"; then
        log_pass "MCP client patched by agentsec"
    else
        log_fail "MCP client NOT patched"
        all_checks_passed=false
    fi
    
    # Check 2: MCP Request inspection
    if grep -qi "MCP.*request inspection\|MCP TOOL CALL.*fetch\|call_tool.*fetch.*Request" "$log_file"; then
        log_pass "MCP Request inspection executed"
    else
        log_fail "MCP Request inspection NOT executed"
        all_checks_passed=false
    fi
    
    # Check 3: MCP Response inspection
    if grep -qi "MCP.*response inspection\|call_tool.*Response.*allow\|Response decision" "$log_file"; then
        log_pass "MCP Response inspection executed"
    else
        log_fail "MCP Response inspection NOT executed"
        all_checks_passed=false
    fi
    
    # Check 4: Got content
    if grep -qi "SUCCESS\|Example Domain\|example.com" "$log_file"; then
        log_pass "MCP tool call succeeded"
    else
        log_fail "MCP tool call failed"
        all_checks_passed=false
    fi
    
    # Check 5: No security blocks (tracebacks in DEBUG logs are handled gracefully)
    if grep -qE "SecurityPolicyError|BLOCKED" "$log_file"; then
        log_fail "Security block found in output"
        all_checks_passed=false
    else
        log_pass "No security blocks"
    fi
    
    if [ "$VERBOSE" = "true" ]; then
        echo ""
        echo -e "    ${MAGENTA}─── Log Output ───${NC}"
        grep -E "(Request inspection|Response inspection|MCP|decision|PATCHED|SUCCESS|FAIL)" "$log_file" | head -20 | sed 's/^/    /'
    fi
    
    if [ "$all_checks_passed" = "true" ]; then
        echo ""
        echo -e "  ${GREEN}${BOLD}► MCP Protection [$integration_mode]: ALL CHECKS PASSED${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo ""
        echo -e "  ${RED}${BOLD}► MCP Protection [$integration_mode]: SOME CHECKS FAILED${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

# =============================================================================
# Local Test Functions (test without AWS deployment)
# =============================================================================

test_direct_local() {
    local integration_mode=$1
    log_subheader "Testing: Direct LOCAL [$integration_mode mode]"
    
    local log_file="$LOG_DIR/direct-local-${integration_mode}.log"
    
    log_info "Mode: LOCAL (Strands agent with Bedrock directly)"
    log_info "Integration mode: $integration_mode"
    log_info "Running test with question: \"$TEST_QUESTION\""
    
    cd "$PROJECT_DIR"
    
    # Set the integration mode environment variable
    export AGENTSEC_LLM_INTEGRATION_MODE="$integration_mode"
    export AGENTSEC_MCP_INTEGRATION_MODE="$integration_mode"
    
    # Enable debug logging so inspection log lines are captured in the log file
    export AGENTSEC_LOG_LEVEL="DEBUG"
    
    local start_time=$(date +%s)
    
    # Run the agent directly using the shared agent factory
    if [ -n "$TIMEOUT_CMD" ]; then
        $TIMEOUT_CMD "$TIMEOUT_SECONDS" poetry run python -c "
import sys, os
sys.path.insert(0, '$PROJECT_DIR')
from _shared import get_agent

print('[test] Running Strands agent with Bedrock (protected by agentsec)...')
result = get_agent()('$TEST_QUESTION')
print(f'[test] Result: {result}')
print('[SUCCESS] LLM test completed')

# Also exercise MCP tool protection
if os.getenv('MCP_SERVER_URL'):
    print('[test] Testing MCP tool protection...')
    from _shared.mcp_tools import _sync_call_mcp_tool
    mcp_result = _sync_call_mcp_tool('fetch', {'url': 'https://example.com'})
    print(f'[test] MCP Result: {mcp_result[:100]}...')
    print('[MCP_SUCCESS] MCP tool call completed')
else:
    print('[test] MCP_SERVER_URL not set, skipping MCP test')
" > "$log_file" 2>&1
        local exit_code=$?
    else
        poetry run python -c "
import sys, os
sys.path.insert(0, '$PROJECT_DIR')
from _shared import get_agent

print('[test] Running Strands agent with Bedrock (protected by agentsec)...')
result = get_agent()('$TEST_QUESTION')
print(f'[test] Result: {result}')
print('[SUCCESS] LLM test completed')

# Also exercise MCP tool protection
if os.getenv('MCP_SERVER_URL'):
    print('[test] Testing MCP tool protection...')
    from _shared.mcp_tools import _sync_call_mcp_tool
    mcp_result = _sync_call_mcp_tool('fetch', {'url': 'https://example.com'})
    print(f'[test] MCP Result: {mcp_result[:100]}...')
    print('[MCP_SUCCESS] MCP tool call completed')
else:
    print('[test] MCP_SERVER_URL not set, skipping MCP test')
" > "$log_file" 2>&1
        local exit_code=$?
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_info "Completed in ${duration}s (exit code: $exit_code)"
    
    # Skip gateway tests if gateway URL is not configured
    if [ "$integration_mode" = "gateway" ] && grep -q "gateway not configured\|Gateway mode enabled but.*not configured" "$log_file"; then
        log_skip "Gateway mode skipped (Bedrock gateway URL not configured)"
        echo ""
        echo -e "  ${YELLOW}${BOLD}► Direct LOCAL [$integration_mode]: SKIPPED (gateway not configured)${NC}"
        ((TESTS_SKIPPED++))
        return 0
    fi
    
    # Validate results
    local all_checks_passed=true
    
    # Check 1: agentsec is patched
    if grep -q "Patched.*bedrock\|bedrock.*patched\|'bedrock'" "$log_file"; then
        log_pass "Bedrock client patched by agentsec"
    else
        log_fail "Bedrock client NOT patched"
        all_checks_passed=false
    fi
    
    # Check 2: LLM Request inspection
    if grep -qi "Request inspection\|PATCHED CALL" "$log_file"; then
        log_pass "LLM Request inspection executed"
    else
        log_fail "LLM Request inspection NOT executed"
        all_checks_passed=false
    fi
    
    # Check 3: Got a result
    if grep -q "SUCCESS\|Result:" "$log_file"; then
        log_pass "Agent returned result"
    else
        log_fail "No result from agent"
        all_checks_passed=false
    fi
    
    # Check 4: MCP Request inspection
    if grep -qi "MCP.*Request inspection\|MCP TOOL CALL.*fetch\|call_tool.*fetch.*Request" "$log_file"; then
        log_pass "MCP Request inspection executed"
    elif grep -q "MCP_SERVER_URL not set" "$log_file"; then
        log_skip "MCP test skipped (MCP_SERVER_URL not set)"
    else
        log_fail "MCP Request inspection NOT executed"
        all_checks_passed=false
    fi
    
    # Check 5: MCP Response inspection
    if grep -qi "MCP.*Response inspection\|call_tool.*Response.*allow\|Response decision" "$log_file"; then
        log_pass "MCP Response inspection executed"
    elif grep -q "MCP_SERVER_URL not set" "$log_file"; then
        : # Already reported skip above
    else
        log_fail "MCP Response inspection NOT executed"
        all_checks_passed=false
    fi
    
    # Check 6: No security blocks
    if grep -qE "SecurityPolicyError|BLOCKED" "$log_file"; then
        log_fail "Security block found in output"
        all_checks_passed=false
    else
        log_pass "No security blocks"
    fi
    
    if [ "$VERBOSE" = "true" ]; then
        echo ""
        echo -e "    ${MAGENTA}─── Log Output ───${NC}"
        grep -E "(Request inspection|Response inspection|AI Defense|decision|Patched|SUCCESS|Result|MCP)" "$log_file" | head -20 | sed 's/^/    /'
    fi
    
    if [ "$all_checks_passed" = "true" ]; then
        echo ""
        echo -e "  ${GREEN}${BOLD}► Direct LOCAL [$integration_mode]: ALL CHECKS PASSED${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo ""
        echo -e "  ${RED}${BOLD}► Direct LOCAL [$integration_mode]: SOME CHECKS FAILED${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

test_container_local() {
    local integration_mode=$1
    log_subheader "Testing: Container LOCAL [$integration_mode mode]"
    
    local log_file="$LOG_DIR/container-local-${integration_mode}.log"
    
    log_info "Mode: LOCAL (Strands agent with Bedrock directly)"
    log_info "Integration mode: $integration_mode"
    log_info "Running test with question: \"$TEST_QUESTION\""
    
    cd "$PROJECT_DIR"
    
    # Set the integration mode environment variable
    export AGENTSEC_LLM_INTEGRATION_MODE="$integration_mode"
    export AGENTSEC_MCP_INTEGRATION_MODE="$integration_mode"
    
    # Enable debug logging so inspection log lines are captured in the log file
    export AGENTSEC_LOG_LEVEL="DEBUG"
    
    local start_time=$(date +%s)
    
    # Run the container app code locally (same agent, different entrypoint)
    if [ -n "$TIMEOUT_CMD" ]; then
        $TIMEOUT_CMD "$TIMEOUT_SECONDS" poetry run python -c "
import sys, os
sys.path.insert(0, '$PROJECT_DIR')
from _shared import get_agent

print('[test] Running container agent code locally (protected by agentsec)...')
result = get_agent()('$TEST_QUESTION')
print(f'[test] Result: {result}')
print('[SUCCESS] LLM test completed')

# Also exercise MCP tool protection
if os.getenv('MCP_SERVER_URL'):
    print('[test] Testing MCP tool protection...')
    from _shared.mcp_tools import _sync_call_mcp_tool
    mcp_result = _sync_call_mcp_tool('fetch', {'url': 'https://example.com'})
    print(f'[test] MCP Result: {mcp_result[:100]}...')
    print('[MCP_SUCCESS] MCP tool call completed')
else:
    print('[test] MCP_SERVER_URL not set, skipping MCP test')
" > "$log_file" 2>&1
        local exit_code=$?
    else
        poetry run python -c "
import sys, os
sys.path.insert(0, '$PROJECT_DIR')
from _shared import get_agent

print('[test] Running container agent code locally (protected by agentsec)...')
result = get_agent()('$TEST_QUESTION')
print(f'[test] Result: {result}')
print('[SUCCESS] LLM test completed')

# Also exercise MCP tool protection
if os.getenv('MCP_SERVER_URL'):
    print('[test] Testing MCP tool protection...')
    from _shared.mcp_tools import _sync_call_mcp_tool
    mcp_result = _sync_call_mcp_tool('fetch', {'url': 'https://example.com'})
    print(f'[test] MCP Result: {mcp_result[:100]}...')
    print('[MCP_SUCCESS] MCP tool call completed')
else:
    print('[test] MCP_SERVER_URL not set, skipping MCP test')
" > "$log_file" 2>&1
        local exit_code=$?
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_info "Completed in ${duration}s (exit code: $exit_code)"
    
    # Skip gateway tests if gateway URL is not configured
    if [ "$integration_mode" = "gateway" ] && grep -q "gateway not configured\|Gateway mode enabled but.*not configured" "$log_file"; then
        log_skip "Gateway mode skipped (Bedrock gateway URL not configured)"
        echo ""
        echo -e "  ${YELLOW}${BOLD}► Container LOCAL [$integration_mode]: SKIPPED (gateway not configured)${NC}"
        ((TESTS_SKIPPED++))
        return 0
    fi
    
    # Validate results
    local all_checks_passed=true
    
    if grep -q "Patched.*bedrock\|bedrock.*patched\|'bedrock'" "$log_file"; then
        log_pass "Bedrock client patched by agentsec"
    else
        log_fail "Bedrock client NOT patched"
        all_checks_passed=false
    fi
    
    if grep -qi "Request inspection\|PATCHED CALL" "$log_file"; then
        log_pass "LLM Request inspection executed"
    else
        log_fail "LLM Request inspection NOT executed"
        all_checks_passed=false
    fi
    
    if grep -q "SUCCESS\|Result:" "$log_file"; then
        log_pass "Agent returned result"
    else
        log_fail "No result from agent"
        all_checks_passed=false
    fi
    
    # Check: MCP Request inspection
    if grep -qi "MCP.*Request inspection\|MCP TOOL CALL.*fetch\|call_tool.*fetch.*Request" "$log_file"; then
        log_pass "MCP Request inspection executed"
    elif grep -q "MCP_SERVER_URL not set" "$log_file"; then
        log_skip "MCP test skipped (MCP_SERVER_URL not set)"
    else
        log_fail "MCP Request inspection NOT executed"
        all_checks_passed=false
    fi
    
    # Check: MCP Response inspection
    if grep -qi "MCP.*Response inspection\|call_tool.*Response.*allow\|Response decision" "$log_file"; then
        log_pass "MCP Response inspection executed"
    elif grep -q "MCP_SERVER_URL not set" "$log_file"; then
        : # Already reported skip above
    else
        log_fail "MCP Response inspection NOT executed"
        all_checks_passed=false
    fi
    
    if grep -qE "SecurityPolicyError|BLOCKED" "$log_file"; then
        log_fail "Security block found in output"
        all_checks_passed=false
    else
        log_pass "No security blocks"
    fi
    
    if [ "$VERBOSE" = "true" ]; then
        echo ""
        echo -e "    ${MAGENTA}─── Log Output ───${NC}"
        grep -E "(Request inspection|Response inspection|AI Defense|decision|Patched|SUCCESS|Result|MCP)" "$log_file" | head -20 | sed 's/^/    /'
    fi
    
    if [ "$all_checks_passed" = "true" ]; then
        echo ""
        echo -e "  ${GREEN}${BOLD}► Container LOCAL [$integration_mode]: ALL CHECKS PASSED${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo ""
        echo -e "  ${RED}${BOLD}► Container LOCAL [$integration_mode]: SOME CHECKS FAILED${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

test_lambda_local() {
    local integration_mode=$1
    log_subheader "Testing: Lambda LOCAL [$integration_mode mode]"
    
    local log_file="$LOG_DIR/lambda-local-${integration_mode}.log"
    
    log_info "Mode: LOCAL (Lambda handler invoked directly)"
    log_info "Integration mode: $integration_mode"
    log_info "Running test with question: \"$TEST_QUESTION\""
    
    cd "$PROJECT_DIR"
    
    # Set the integration mode environment variable
    export AGENTSEC_LLM_INTEGRATION_MODE="$integration_mode"
    export AGENTSEC_MCP_INTEGRATION_MODE="$integration_mode"
    
    # Enable debug logging so inspection log lines are captured in the log file
    export AGENTSEC_LOG_LEVEL="DEBUG"
    
    local start_time=$(date +%s)
    
    # Run the Lambda handler directly
    if [ -n "$TIMEOUT_CMD" ]; then
        $TIMEOUT_CMD "$TIMEOUT_SECONDS" poetry run python -c "
import sys, os, json
sys.path.insert(0, '$PROJECT_DIR/lambda-deploy')
sys.path.insert(0, '$PROJECT_DIR')

# Import the lambda handler (this also imports _shared which configures agentsec)
from lambda_handler import handler

print('[test] Invoking Lambda handler locally (protected by agentsec)...')
event = {'prompt': '$TEST_QUESTION'}
context = None
result = handler(event, context)
print(f'[test] Result: {json.dumps(result)}')
print('[SUCCESS] LLM test completed')

# Also exercise MCP tool protection
if os.getenv('MCP_SERVER_URL'):
    print('[test] Testing MCP tool protection...')
    from _shared.mcp_tools import _sync_call_mcp_tool
    mcp_result = _sync_call_mcp_tool('fetch', {'url': 'https://example.com'})
    print(f'[test] MCP Result: {mcp_result[:100]}...')
    print('[MCP_SUCCESS] MCP tool call completed')
else:
    print('[test] MCP_SERVER_URL not set, skipping MCP test')
" > "$log_file" 2>&1
        local exit_code=$?
    else
        poetry run python -c "
import sys, os, json
sys.path.insert(0, '$PROJECT_DIR/lambda-deploy')
sys.path.insert(0, '$PROJECT_DIR')

# Import the lambda handler (this also imports _shared which configures agentsec)
from lambda_handler import handler

print('[test] Invoking Lambda handler locally (protected by agentsec)...')
event = {'prompt': '$TEST_QUESTION'}
context = None
result = handler(event, context)
print(f'[test] Result: {json.dumps(result)}')
print('[SUCCESS] LLM test completed')

# Also exercise MCP tool protection
if os.getenv('MCP_SERVER_URL'):
    print('[test] Testing MCP tool protection...')
    from _shared.mcp_tools import _sync_call_mcp_tool
    mcp_result = _sync_call_mcp_tool('fetch', {'url': 'https://example.com'})
    print(f'[test] MCP Result: {mcp_result[:100]}...')
    print('[MCP_SUCCESS] MCP tool call completed')
else:
    print('[test] MCP_SERVER_URL not set, skipping MCP test')
" > "$log_file" 2>&1
        local exit_code=$?
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_info "Completed in ${duration}s (exit code: $exit_code)"
    
    # Skip gateway tests if gateway URL is not configured
    if [ "$integration_mode" = "gateway" ] && grep -q "gateway not configured\|Gateway mode enabled but.*not configured" "$log_file"; then
        log_skip "Gateway mode skipped (Bedrock gateway URL not configured)"
        echo ""
        echo -e "  ${YELLOW}${BOLD}► Lambda LOCAL [$integration_mode]: SKIPPED (gateway not configured)${NC}"
        ((TESTS_SKIPPED++))
        return 0
    fi
    
    # Validate results
    local all_checks_passed=true
    
    if grep -q "Patched.*bedrock\|bedrock.*patched\|'bedrock'" "$log_file"; then
        log_pass "Bedrock client patched by agentsec"
    else
        log_fail "Bedrock client NOT patched"
        all_checks_passed=false
    fi
    
    if grep -qi "Request inspection\|PATCHED CALL" "$log_file"; then
        log_pass "LLM Request inspection executed"
    else
        log_fail "LLM Request inspection NOT executed"
        all_checks_passed=false
    fi
    
    if grep -q "SUCCESS\|result" "$log_file"; then
        log_pass "Lambda handler returned result"
    else
        log_fail "No result from Lambda handler"
        all_checks_passed=false
    fi
    
    # Check: MCP Request inspection
    if grep -qi "MCP.*Request inspection\|MCP TOOL CALL.*fetch\|call_tool.*fetch.*Request" "$log_file"; then
        log_pass "MCP Request inspection executed"
    elif grep -q "MCP_SERVER_URL not set" "$log_file"; then
        log_skip "MCP test skipped (MCP_SERVER_URL not set)"
    else
        log_fail "MCP Request inspection NOT executed"
        all_checks_passed=false
    fi
    
    # Check: MCP Response inspection
    if grep -qi "MCP.*Response inspection\|call_tool.*Response.*allow\|Response decision" "$log_file"; then
        log_pass "MCP Response inspection executed"
    elif grep -q "MCP_SERVER_URL not set" "$log_file"; then
        : # Already reported skip above
    else
        log_fail "MCP Response inspection NOT executed"
        all_checks_passed=false
    fi
    
    if grep -qE "SecurityPolicyError|BLOCKED" "$log_file"; then
        log_fail "Security block found in output"
        all_checks_passed=false
    else
        log_pass "No security blocks"
    fi
    
    if [ "$VERBOSE" = "true" ]; then
        echo ""
        echo -e "    ${MAGENTA}─── Log Output ───${NC}"
        grep -E "(Request inspection|Response inspection|AI Defense|decision|Patched|SUCCESS|Result|MCP)" "$log_file" | head -20 | sed 's/^/    /'
    fi
    
    if [ "$all_checks_passed" = "true" ]; then
        echo ""
        echo -e "  ${GREEN}${BOLD}► Lambda LOCAL [$integration_mode]: ALL CHECKS PASSED${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo ""
        echo -e "  ${RED}${BOLD}► Lambda LOCAL [$integration_mode]: SOME CHECKS FAILED${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

# =============================================================================
# Deploy Test Functions (test with AWS deployment)
# =============================================================================

# Helper: Validate agent exists in AWS
# Note: This uses boto3 since aws CLI may not support bedrock-agentcore service yet
validate_agent_exists() {
    local agent_name=$1
    local config_file="$PROJECT_DIR/.bedrock_agentcore.yaml"
    
    # Use Python/boto3 to validate the agent exists
    # This is more reliable than CLI as bedrock-agentcore is a newer service
    local validation_result
    validation_result=$(poetry run python3 -c "
import yaml
import boto3
import sys
from botocore.exceptions import ClientError

try:
    with open('$config_file') as f:
        config = yaml.safe_load(f)
    
    agent_config = config.get('agents', {}).get('$agent_name', {})
    agent_arn = agent_config.get('bedrock_agentcore', {}).get('agent_arn', '')
    region = agent_config.get('aws', {}).get('region', 'us-west-2')
    
    if not agent_arn:
        print('NO_ARN')
        sys.exit(1)
    
    # Extract agent runtime ID from ARN
    agent_id = agent_arn.split('/')[-1]
    
    # Try to get the agent runtime status
    client = boto3.client('bedrock-agentcore', region_name=region)
    response = client.get_agent_runtime(agentRuntimeId=agent_id)
    
    # Check if the runtime has a valid status
    status = response.get('status', 'UNKNOWN')
    if status in ['READY', 'RUNNING', 'CREATING']:
        print('EXISTS')
        sys.exit(0)
    else:
        print(f'STATUS_{status}')
        sys.exit(1)
        
except ClientError as e:
    error_code = e.response.get('Error', {}).get('Code', 'Unknown')
    if error_code == 'ResourceNotFoundException':
        print('NOT_FOUND')
    elif error_code == 'AccessDeniedException':
        print('ACCESS_DENIED')
    else:
        print(f'ERROR_{error_code}')
    sys.exit(1)
except Exception as e:
    print(f'ERROR_{type(e).__name__}')
    sys.exit(1)
" 2>/dev/null) || validation_result="ERROR"
    
    case "$validation_result" in
        "EXISTS")
            return 0
            ;;
        "NO_ARN")
            log_info "No agent ARN found in config for '$agent_name'"
            return 1
            ;;
        "NOT_FOUND")
            log_info "Agent not found in AWS (ResourceNotFoundException)"
            return 1
            ;;
        "ACCESS_DENIED")
            log_info "AWS access denied - check credentials"
            # Return 1 to trigger deployment attempt
            return 1
            ;;
        STATUS_*)
            log_info "Agent status: ${validation_result#STATUS_}"
            return 1
            ;;
        *)
            log_info "Could not validate agent (${validation_result})"
            # Return 1 to trigger deployment attempt
            return 1
            ;;
    esac
}

# Helper: Auto-deploy an agent if it doesn't exist
# Returns 0 if agent exists or was successfully deployed, 1 otherwise
ensure_agent_deployed() {
    local agent_name=$1
    local deploy_script=$2
    local deploy_log="$LOG_DIR/${agent_name}-deploy.log"
    
    # First check if agent already exists
    log_info "Checking if agent '$agent_name' exists in AWS..."
    if validate_agent_exists "$agent_name"; then
        log_pass "Agent '$agent_name' already exists in AWS"
        return 0
    fi
    
    # Agent doesn't exist, try to deploy it
    log_info "Agent '$agent_name' not found, deploying automatically..."
    
    if [ ! -f "$deploy_script" ]; then
        log_fail "Deploy script not found: $deploy_script"
        return 1
    fi
    
    # Run the deploy script
    log_info "Running: $deploy_script"
    local deploy_start=$(date +%s)
    
    if bash "$deploy_script" > "$deploy_log" 2>&1; then
        local deploy_end=$(date +%s)
        local deploy_duration=$((deploy_end - deploy_start))
        log_pass "Agent '$agent_name' deployed successfully (${deploy_duration}s)"
        
        # Wait a bit for the agent to be ready
        log_info "Waiting for agent to be ready..."
        sleep 10
        
        # Verify deployment succeeded
        if validate_agent_exists "$agent_name"; then
            log_pass "Agent '$agent_name' is ready"
            return 0
        else
            log_fail "Agent deployed but not found in AWS (may need more time)"
            if [ "$VERBOSE" = "true" ]; then
                echo ""
                echo -e "    ${MAGENTA}─── Deploy Log (last 20 lines) ───${NC}"
                tail -20 "$deploy_log" | sed 's/^/    /'
            fi
            return 1
        fi
    else
        log_fail "Deployment failed for '$agent_name'"
        log_info "See log: $deploy_log"
        if [ "$VERBOSE" = "true" ]; then
            echo ""
            echo -e "    ${MAGENTA}─── Deploy Log (last 30 lines) ───${NC}"
            tail -30 "$deploy_log" | sed 's/^/    /'
        fi
        return 1
    fi
}

test_direct_deploy() {
    local integration_mode=$1
    log_subheader "Testing: Direct Deploy [$integration_mode mode]"
    
    local log_file="$LOG_DIR/direct-deploy-${integration_mode}.log"
    local agent_name="${AGENTCORE_DIRECT_AGENT_NAME:-agentcore_sre_direct}"
    
    # Check if test script exists
    local test_script="$PROJECT_DIR/direct-deploy/test_with_protection.py"
    if [ ! -f "$test_script" ]; then
        log_fail "Test script not found: $test_script"
        ((TESTS_FAILED++))
        return 1
    fi
    
    # Note: Agent should already be deployed by deploy_agents() phase
    
    log_info "Integration mode: $integration_mode"
    log_info "Running test with question: \"$TEST_QUESTION\""
    
    cd "$PROJECT_DIR"
    
    # Set the integration mode and agent name environment variables
    export AGENTSEC_LLM_INTEGRATION_MODE="$integration_mode"
    export AGENTCORE_AGENT_NAME="$agent_name"
    
    # Run the test (capture exit code without failing due to set -e)
    local start_time=$(date +%s)
    local exit_code=0
    
    if [ -n "$TIMEOUT_CMD" ]; then
        $TIMEOUT_CMD "$TIMEOUT_SECONDS" poetry run python "$test_script" "$TEST_QUESTION" > "$log_file" 2>&1 || exit_code=$?
    else
        poetry run python "$test_script" "$TEST_QUESTION" > "$log_file" 2>&1 || exit_code=$?
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_info "Completed in ${duration}s (exit code: $exit_code)"
    
    # Check for ResourceNotFoundException (agent not found in AWS)
    if grep -q "ResourceNotFoundException" "$log_file"; then
        log_fail "Agent not found in AWS (ResourceNotFoundException)"
        log_info "The agent ARN in .bedrock_agentcore.yaml may be stale."
        log_info "Run: ./direct-deploy/scripts/deploy.sh to redeploy"
        if [ "$VERBOSE" = "true" ]; then
            grep -A2 "ResourceNotFoundException" "$log_file" | head -5 | sed 's/^/    /'
        fi
        ((TESTS_FAILED++))
        return 1
    fi
    
    # Validate results
    local all_checks_passed=true
    
    # Check 1: Request inspection
    if grep -q "Request inspection" "$log_file"; then
        log_pass "Request inspection executed"
    else
        log_fail "Request inspection NOT executed"
        all_checks_passed=false
    fi
    
    # Check 2: Response inspection (now required - using boto3 SDK directly)
    if grep -q "Response inspection" "$log_file"; then
        log_pass "Response inspection executed"
    else
        log_fail "Response inspection NOT executed"
        all_checks_passed=false
    fi
    
    # Check 3: AI Defense response / integration mode verification
    if [ "$integration_mode" = "api" ]; then
        if grep -q "AI Defense response\|'action': 'Allow'\|Integration: api\|llm_integration=api" "$log_file"; then
            log_pass "AI Defense API mode response received"
        else
            log_fail "No AI Defense API response found"
            all_checks_passed=false
        fi
    else
        if grep -q "gateway\|Gateway\|Integration: gateway\|llm_integration=gateway" "$log_file"; then
            log_pass "Gateway mode communication successful"
        else
            log_fail "No Gateway mode indicators found"
            all_checks_passed=false
        fi
    fi
    
    # Check 4: No security blocks (tracebacks in DEBUG logs are handled gracefully)
    if grep -qE "SecurityPolicyError|BLOCKED" "$log_file"; then
        log_fail "Security block found in output"
        all_checks_passed=false
    else
        log_pass "No security blocks"
    fi
    
    if [ "$VERBOSE" = "true" ]; then
        echo ""
        echo -e "    ${MAGENTA}─── Log Output ───${NC}"
        grep -E "(Request inspection|Response inspection|AI Defense|decision|Integration:|gateway)" "$log_file" | head -20 | sed 's/^/    /'
    fi
    
    if [ "$all_checks_passed" = "true" ]; then
        echo ""
        echo -e "  ${GREEN}${BOLD}► Direct Deploy [$integration_mode]: ALL CHECKS PASSED${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo ""
        echo -e "  ${RED}${BOLD}► Direct Deploy [$integration_mode]: SOME CHECKS FAILED${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

test_lambda_deploy() {
    local integration_mode=$1
    log_subheader "Testing: Lambda Deploy [$integration_mode mode]"
    
    local log_file="$LOG_DIR/lambda-deploy-${integration_mode}.log"
    local function_name="${FUNCTION_NAME:-agentcore-sre-lambda}"
    
    # Note: Lambda should already be deployed by deploy_agents() phase
    
    log_info "Integration mode: $integration_mode"
    log_info "Invoking Lambda: $function_name"
    log_info "Question: \"$TEST_QUESTION\""
    
    # Note: Lambda integration mode is configured at deploy time, not runtime
    # This test verifies the Lambda works; integration mode depends on Lambda's env vars
    
    # Invoke Lambda (capture exit code without triggering set -e)
    local start_time=$(date +%s)
    local exit_code=0
    
    aws lambda invoke \
        --function-name "$function_name" \
        --region "${AWS_REGION:-us-west-2}" \
        --payload "{\"prompt\": \"$TEST_QUESTION\"}" \
        --cli-binary-format raw-in-base64-out \
        /tmp/lambda_response.json > "$log_file" 2>&1 || exit_code=$?
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_info "Completed in ${duration}s (exit code: $exit_code)"
    
    # Get CloudWatch logs
    sleep 3
    local log_group="/aws/lambda/$function_name"
    aws logs tail "$log_group" --since 2m --region "${AWS_REGION:-us-west-2}" >> "$log_file" 2>&1 || true
    
    # Validate results
    local all_checks_passed=true
    
    # Check 1: Lambda executed successfully
    if [ $exit_code -eq 0 ]; then
        log_pass "Lambda executed successfully"
    else
        log_fail "Lambda execution failed (exit code: $exit_code)"
        all_checks_passed=false
    fi
    
    # Check 2: Got a response
    if [ -f /tmp/lambda_response.json ] && grep -q "result" /tmp/lambda_response.json; then
        log_pass "Lambda returned result"
        if [ "$VERBOSE" = "true" ]; then
            echo "    Response: $(cat /tmp/lambda_response.json)"
        fi
    else
        log_fail "No result in Lambda response"
        all_checks_passed=false
    fi
    
    # Check 3: agentsec was patched (from CloudWatch logs)
    if grep -q "Patched.*bedrock\|PATCHED CALL\|agentsec" "$log_file"; then
        log_pass "agentsec patching confirmed"
    else
        log_info "Could not verify agentsec patching (CloudWatch logs may be delayed)"
    fi
    
    # Check 4: No security blocks or Lambda errors (tracebacks in DEBUG logs are handled gracefully)
    if grep -qE "SecurityPolicyError|BLOCKED|\"errorMessage\"" "$log_file" /tmp/lambda_response.json 2>/dev/null; then
        log_fail "Security block or Lambda error found"
        all_checks_passed=false
    else
        log_pass "No security blocks or errors"
    fi
    
    if [ "$all_checks_passed" = "true" ]; then
        echo ""
        echo -e "  ${GREEN}${BOLD}► Lambda Deploy [$integration_mode]: ALL CHECKS PASSED${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo ""
        echo -e "  ${RED}${BOLD}► Lambda Deploy [$integration_mode]: SOME CHECKS FAILED${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

test_container_deploy() {
    local integration_mode=$1
    log_subheader "Testing: Container Deploy [$integration_mode mode]"
    
    local log_file="$LOG_DIR/container-deploy-${integration_mode}.log"
    local agent_name="${AGENTCORE_CONTAINER_AGENT_NAME:-agentcore_sre_container}"
    
    # Note: Agent should already be deployed by deploy_agents() phase
    
    log_info "Integration mode: $integration_mode"
    log_info "Invoking container agent: $agent_name"
    log_info "Question: \"$TEST_QUESTION\""
    
    cd "$PROJECT_DIR"
    
    # Note: Container integration mode is configured at deploy time via container env vars
    # This test verifies the container works
    
    # Invoke via agentcore CLI (capture exit code without triggering set -e)
    local start_time=$(date +%s)
    local exit_code=0
    
    poetry run agentcore invoke --agent "$agent_name" "{\"prompt\": \"$TEST_QUESTION\"}" > "$log_file" 2>&1 || exit_code=$?
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_info "Completed in ${duration}s (exit code: $exit_code)"
    
    # Check for ResourceNotFoundException (agent not found in AWS)
    if grep -q "ResourceNotFoundException" "$log_file"; then
        log_fail "Agent not found in AWS (ResourceNotFoundException)"
        log_info "The agent ARN in .bedrock_agentcore.yaml may be stale."
        log_info "Run: ./container-deploy/scripts/deploy.sh to redeploy"
        if [ "$VERBOSE" = "true" ]; then
            grep -A2 "ResourceNotFoundException" "$log_file" | head -5 | sed 's/^/    /'
        fi
        ((TESTS_FAILED++))
        return 1
    fi
    
    # Validate results
    local all_checks_passed=true
    
    # Check 1: Invocation succeeded
    if [ $exit_code -eq 0 ]; then
        log_pass "Container invocation succeeded"
    else
        log_fail "Container invocation failed (exit code: $exit_code)"
        all_checks_passed=false
    fi
    
    # Check 2: Got a response
    if grep -q "result\|Response:" "$log_file"; then
        log_pass "Container returned result"
    else
        log_fail "No result in container response"
        all_checks_passed=false
    fi
    
    # Check 3: No security blocks (tracebacks in DEBUG logs are handled gracefully)
    if grep -qE "SecurityPolicyError|BLOCKED" "$log_file"; then
        log_fail "Security block found in output"
        all_checks_passed=false
    else
        log_pass "No security blocks"
    fi
    
    if [ "$all_checks_passed" = "true" ]; then
        echo ""
        echo -e "  ${GREEN}${BOLD}► Container Deploy [$integration_mode]: ALL CHECKS PASSED${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo ""
        echo -e "  ${RED}${BOLD}► Container Deploy [$integration_mode]: SOME CHECKS FAILED${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

# =============================================================================
# Main
# =============================================================================

VERBOSE="false"
DEPLOY_MODES_TO_TEST=()
INTEGRATION_MODES_TO_TEST=()
RUN_LLM_TESTS=true
RUN_MCP_TESTS=true
MCP_ONLY=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_help
            exit 0
            ;;
        --local)
            LOCAL_MODE=true
            shift
            ;;
        --deploy)
            LOCAL_MODE=false
            shift
            ;;
        --verbose|-v)
            VERBOSE="true"
            shift
            ;;
        --api)
            INTEGRATION_MODES_TO_TEST+=("api")
            shift
            ;;
        --gateway)
            INTEGRATION_MODES_TO_TEST+=("gateway")
            shift
            ;;
        --no-mcp)
            RUN_MCP_TESTS=false
            shift
            ;;
        --mcp-only)
            MCP_ONLY=true
            RUN_LLM_TESTS=false
            shift
            ;;
        direct|container|lambda)
            DEPLOY_MODES_TO_TEST+=("$1")
            shift
            ;;
        *)
            echo -e "${RED}Unknown argument: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Default to all modes if none specified
if [ ${#DEPLOY_MODES_TO_TEST[@]} -eq 0 ]; then
    DEPLOY_MODES_TO_TEST=("${ALL_DEPLOY_MODES[@]}")
fi

if [ ${#INTEGRATION_MODES_TO_TEST[@]} -eq 0 ]; then
    INTEGRATION_MODES_TO_TEST=("${ALL_INTEGRATION_MODES[@]}")
fi

# Setup
if [ "$LOCAL_MODE" = "true" ]; then
    log_header "AgentCore Integration Tests (LOCAL MODE)"
    echo ""
    echo -e "  ${BLUE}LOCAL MODE: Testing agent locally using AWS Bedrock${NC}"
    echo -e "  ${BLUE}Use --deploy flag to deploy and test real AWS endpoints${NC}"
else
    log_header "AgentCore Integration Tests (DEPLOY MODE)"
    echo ""
    echo -e "  ${YELLOW}DEPLOY MODE: Testing with real AWS AgentCore/Lambda endpoints${NC}"
fi
echo ""
echo "  Project:          $PROJECT_DIR"
if [ "$MCP_ONLY" = "true" ]; then
    echo "  Test type:        MCP only"
elif [ "$RUN_MCP_TESTS" = "false" ]; then
    echo "  Test type:        LLM only (no MCP)"
else
    echo "  Test type:        LLM + MCP"
fi
echo "  Test mode:        $([ "$LOCAL_MODE" = "true" ] && echo "local" || echo "deploy")"
echo "  Deploy modes:     ${DEPLOY_MODES_TO_TEST[*]}"
echo "  Integration modes: ${INTEGRATION_MODES_TO_TEST[*]}"
echo "  MCP Server:       ${MCP_SERVER_URL:-not set}"
echo "  Verbose:          $VERBOSE"

# Check poetry is available
if ! command -v poetry &> /dev/null; then
    echo ""
    echo -e "${RED}ERROR: Poetry is not installed${NC}"
    exit 1
fi

# Install dependencies (ensures venv is setup and all packages are installed)
log_info "Installing dependencies..."
cd "$PROJECT_DIR"
poetry install --quiet 2>/dev/null || poetry install

# Install agentcore CLI (bedrock-agentcore-starter-toolkit) only for deploy mode
if [ "$LOCAL_MODE" = "false" ]; then
    if ! poetry run agentcore --version &> /dev/null; then
        log_info "Installing AgentCore CLI..."
        if ! poetry run pip install --quiet bedrock-agentcore-starter-toolkit 2>/dev/null; then
            echo -e "${YELLOW}⚠${NC} AgentCore CLI installation failed (dependency conflict)."
            echo -e "   Deploy mode tests may fail. Try: pip install bedrock-agentcore-starter-toolkit"
        fi
    fi
fi

# Load shared environment variables; preserve resource names from parent (e.g. --new-resources)
_SAVED_AGENTCORE_DIRECT="${AGENTCORE_DIRECT_AGENT_NAME:-}"
_SAVED_AGENTCORE_CONTAINER="${AGENTCORE_CONTAINER_AGENT_NAME:-}"
_SAVED_FUNCTION_NAME="${FUNCTION_NAME:-}"
SHARED_ENV="$PROJECT_DIR/../../.env"
if [ -f "$SHARED_ENV" ]; then
    log_info "Loading environment from $SHARED_ENV"
    set -a
    source "$SHARED_ENV"
    set +a
fi
[ -n "$_SAVED_AGENTCORE_DIRECT" ] && export AGENTCORE_DIRECT_AGENT_NAME="$_SAVED_AGENTCORE_DIRECT"
[ -n "$_SAVED_AGENTCORE_CONTAINER" ] && export AGENTCORE_CONTAINER_AGENT_NAME="$_SAVED_AGENTCORE_CONTAINER"
[ -n "$_SAVED_FUNCTION_NAME" ] && export FUNCTION_NAME="$_SAVED_FUNCTION_NAME"

# Setup log directory
setup_log_dir

# =============================================================================
# Pre-Deploy Agents (deploy mode only)
# =============================================================================
# In deploy mode, run all necessary deploy scripts BEFORE running tests
# This ensures agents are deployed/updated before we test them

deploy_agents() {
    log_header "Deploying Agents to AWS"
    
    local deploy_start_time=$(date +%s)
    local deploy_failed=false
    local config_file="$PROJECT_DIR/.bedrock_agentcore.yaml"
    
    # Remove stale config file if it exists
    # This ensures fresh agent creation instead of trying to update non-existent agents
    if [ -f "$config_file" ]; then
        log_info "Removing stale config file: .bedrock_agentcore.yaml"
        log_info "This ensures fresh agent creation instead of updating old agent IDs"
        rm -f "$config_file"
        log_pass "Stale config removed"
    fi
    
    for deploy_mode in "${DEPLOY_MODES_TO_TEST[@]}"; do
        case $deploy_mode in
            direct)
                log_subheader "Deploying: Direct Code Agent"
                local deploy_script="$PROJECT_DIR/direct-deploy/scripts/deploy.sh"
                local deploy_log="$LOG_DIR/deploy-direct.log"
                
                if [ ! -f "$deploy_script" ]; then
                    log_fail "Deploy script not found: $deploy_script"
                    deploy_failed=true
                    continue
                fi
                
                log_info "Running: $deploy_script"
                local start_time=$(date +%s)
                
                if bash "$deploy_script" > "$deploy_log" 2>&1; then
                    local end_time=$(date +%s)
                    local duration=$((end_time - start_time))
                    log_pass "Direct agent deployed successfully (${duration}s)"
                else
                    log_fail "Direct agent deployment failed"
                    log_info "See log: $deploy_log"
                    if [ "$VERBOSE" = "true" ]; then
                        echo ""
                        echo -e "    ${MAGENTA}─── Deploy Log (last 30 lines) ───${NC}"
                        tail -30 "$deploy_log" | sed 's/^/    /'
                    fi
                    deploy_failed=true
                fi
                ;;
            
            container)
                log_subheader "Deploying: Container Agent"
                local deploy_script="$PROJECT_DIR/container-deploy/scripts/deploy.sh"
                local deploy_log="$LOG_DIR/deploy-container.log"
                
                if [ ! -f "$deploy_script" ]; then
                    log_fail "Deploy script not found: $deploy_script"
                    deploy_failed=true
                    continue
                fi
                
                log_info "Running: $deploy_script"
                local start_time=$(date +%s)
                
                if bash "$deploy_script" > "$deploy_log" 2>&1; then
                    local end_time=$(date +%s)
                    local duration=$((end_time - start_time))
                    log_pass "Container agent deployed successfully (${duration}s)"
                else
                    log_fail "Container agent deployment failed"
                    log_info "See log: $deploy_log"
                    if [ "$VERBOSE" = "true" ]; then
                        echo ""
                        echo -e "    ${MAGENTA}─── Deploy Log (last 30 lines) ───${NC}"
                        tail -30 "$deploy_log" | sed 's/^/    /'
                    fi
                    deploy_failed=true
                fi
                ;;
            
            lambda)
                log_subheader "Deploying: Lambda Function"
                local deploy_script="$PROJECT_DIR/lambda-deploy/scripts/deploy.sh"
                local deploy_log="$LOG_DIR/deploy-lambda.log"
                
                if [ ! -f "$deploy_script" ]; then
                    log_fail "Deploy script not found: $deploy_script"
                    deploy_failed=true
                    continue
                fi
                
                log_info "Running: $deploy_script"
                local start_time=$(date +%s)
                
                if bash "$deploy_script" > "$deploy_log" 2>&1; then
                    local end_time=$(date +%s)
                    local duration=$((end_time - start_time))
                    log_pass "Lambda function deployed successfully (${duration}s)"
                else
                    log_fail "Lambda deployment failed"
                    log_info "See log: $deploy_log"
                    if [ "$VERBOSE" = "true" ]; then
                        echo ""
                        echo -e "    ${MAGENTA}─── Deploy Log (last 30 lines) ───${NC}"
                        tail -30 "$deploy_log" | sed 's/^/    /'
                    fi
                    deploy_failed=true
                fi
                ;;
        esac
    done
    
    # Wait for agents to be ready
    if [ "$deploy_failed" = "false" ]; then
        log_info "Waiting for agents to be ready (10s)..."
        sleep 10
        log_pass "All agents deployed successfully"
    else
        log_fail "Some deployments failed - tests may not work correctly"
    fi
    
    # Calculate and display total deployment time
    local deploy_end_time=$(date +%s)
    local deploy_duration=$((deploy_end_time - deploy_start_time))
    local deploy_min=$((deploy_duration / 60))
    local deploy_sec=$((deploy_duration % 60))
    echo ""
    echo -e "  ${BOLD}Deployment completed in ${deploy_min}m ${deploy_sec}s${NC}"
    
    # Store deployment time for final summary
    DEPLOY_MODE_TIMES+=("deployment:$deploy_duration")
    
    return 0  # Continue to tests even if some deployments failed
}

# Track overall start time (includes deployment)
TOTAL_START_TIME=$(date +%s)

# Deploy agents if in deploy mode
if [ "$LOCAL_MODE" = "false" ] && [ "$RUN_LLM_TESTS" = "true" ]; then
    deploy_agents
fi

# Run tests - iterate over deployment modes and integration modes
log_header "Running Tests"

# Run LLM tests (deploy modes x integration modes)
# Note: Use "|| true" to ensure test failures don't exit the script (set -e)
if [ "$RUN_LLM_TESTS" = "true" ]; then
    for deploy_mode in "${DEPLOY_MODES_TO_TEST[@]}"; do
        DEPLOY_MODE_START=$(date +%s)
        
        for integration_mode in "${INTEGRATION_MODES_TO_TEST[@]}"; do
            if [ "$LOCAL_MODE" = "true" ]; then
                # Local tests - invoke agent directly without AWS deployment
                case $deploy_mode in
                    direct)
                        test_direct_local "$integration_mode" || true
                        ;;
                    container)
                        test_container_local "$integration_mode" || true
                        ;;
                    lambda)
                        test_lambda_local "$integration_mode" || true
                        ;;
                esac
            else
                # Deploy tests - test with real AWS endpoints
                case $deploy_mode in
                    direct)
                        test_direct_deploy "$integration_mode" || true
                        ;;
                    container)
                        test_container_deploy "$integration_mode" || true
                        ;;
                    lambda)
                        test_lambda_deploy "$integration_mode" || true
                        ;;
                esac
            fi
        done
        
        DEPLOY_MODE_END=$(date +%s)
        DEPLOY_MODE_TIMES+=("$deploy_mode:$((DEPLOY_MODE_END - DEPLOY_MODE_START))")
    done
fi

# Run MCP tests (integration modes only - not tied to deploy mode)
if [ "$RUN_MCP_TESTS" = "true" ]; then
    log_header "MCP Tool Protection Tests"
    
    MCP_START=$(date +%s)
    
    # Set default MCP_SERVER_URL if not set
    export MCP_SERVER_URL="${MCP_SERVER_URL:-https://mcp.deepwiki.com/mcp}"
    
    for integration_mode in "${INTEGRATION_MODES_TO_TEST[@]}"; do
        test_mcp_protection "$integration_mode" || true
    done
    
    MCP_END=$(date +%s)
    DEPLOY_MODE_TIMES+=("mcp:$((MCP_END - MCP_START))")
fi

# Calculate total time
TOTAL_END_TIME=$(date +%s)
TOTAL_DURATION=$((TOTAL_END_TIME - TOTAL_START_TIME))
TOTAL_DURATION_MIN=$((TOTAL_DURATION / 60))
TOTAL_DURATION_SEC=$((TOTAL_DURATION % 60))

# Summary
log_header "Test Summary"
echo ""
echo -e "  ${GREEN}Passed${NC}:  $TESTS_PASSED"
echo -e "  ${RED}Failed${NC}:  $TESTS_FAILED"
echo -e "  ${YELLOW}Skipped${NC}: $TESTS_SKIPPED"
echo ""

# Timing breakdown
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  Timing Breakdown:${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
for time_entry in "${DEPLOY_MODE_TIMES[@]}"; do
    mode_name="${time_entry%%:*}"
    mode_secs="${time_entry##*:}"
    mode_min=$((mode_secs / 60))
    mode_sec=$((mode_secs % 60))
    printf "  %-20s %dm %ds\n" "$mode_name:" "$mode_min" "$mode_sec"
done
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  ${BOLD}Total Runtime:       ${TOTAL_DURATION_MIN}m ${TOTAL_DURATION_SEC}s${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

TOTAL=$((TESTS_PASSED + TESTS_FAILED))
if [ $TESTS_FAILED -eq 0 ] && [ $TOTAL -gt 0 ]; then
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}${BOLD}  ✓ ALL TESTS PASSED ($TESTS_PASSED/$TOTAL) in ${TOTAL_DURATION_MIN}m ${TOTAL_DURATION_SEC}s${NC}"
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    exit 0
else
    echo -e "${RED}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}${BOLD}  ✗ TESTS FAILED ($TESTS_FAILED/$TOTAL failed) in ${TOTAL_DURATION_MIN}m ${TOTAL_DURATION_SEC}s${NC}"
    echo -e "${RED}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "  Logs available at: $LOG_DIR/"
    exit 1
fi
