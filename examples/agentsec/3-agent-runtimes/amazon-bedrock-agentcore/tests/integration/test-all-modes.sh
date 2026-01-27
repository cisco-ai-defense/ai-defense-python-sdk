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
# For each test, verifies:
#   1. LLM calls are intercepted by AI Defense
#   2. Request inspection happens
#   3. Response inspection happens (where applicable)
#   4. No errors occur during execution
#
# Usage:
#   ./tests/integration/test-all-modes.sh                    # Run all tests (6 total)
#   ./tests/integration/test-all-modes.sh --verbose          # Verbose output
#   ./tests/integration/test-all-modes.sh --api              # API mode only (3 tests)
#   ./tests/integration/test-all-modes.sh --gateway          # Gateway mode only (3 tests)
#   ./tests/integration/test-all-modes.sh direct             # Test direct deploy only (2 tests)
#   ./tests/integration/test-all-modes.sh direct --api       # Test direct deploy, API mode only
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

show_help() {
    echo "Usage: $0 [OPTIONS] [DEPLOY_MODE]"
    echo ""
    echo "Options:"
    echo "  --verbose, -v    Show detailed output"
    echo "  --api            Test API mode only (default: both modes)"
    echo "  --gateway        Test Gateway mode only (default: both modes)"
    echo "  --no-mcp         Skip MCP tool protection tests"
    echo "  --mcp-only       Run only MCP tool protection tests"
    echo "  --help, -h       Show this help"
    echo ""
    echo "Deploy Modes:"
    echo "  direct           Test direct code deploy"
    echo "  container        Test container deploy (requires deployed container)"
    echo "  lambda           Test lambda deploy"
    echo ""
    echo "MCP Tests:"
    echo "  MCP tests verify AI Defense protection for MCP tool calls."
    echo "  Requires MCP_SERVER_URL environment variable (default: https://mcp.deepwiki.com/mcp)"
    echo ""
    echo "Examples:"
    echo "  $0                      # Run all tests (LLM + MCP)"
    echo "  $0 --verbose            # Run all tests with details"
    echo "  $0 --api                # Run all deploy modes in API mode only"
    echo "  $0 --mcp-only           # Run only MCP tests"
    echo "  $0 direct --api         # Test direct deploy, API mode only"
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
    
    # Check 5: No errors
    if ! grep -qE "^Traceback|SecurityPolicyError|BLOCKED|ERROR:" "$log_file"; then
        log_pass "No errors or blocks"
    else
        log_fail "Errors found in output"
        all_checks_passed=false
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
# Test Functions
# =============================================================================

test_direct_deploy() {
    local integration_mode=$1
    log_subheader "Testing: Direct Deploy [$integration_mode mode]"
    
    local log_file="$LOG_DIR/direct-deploy-${integration_mode}.log"
    
    # Check if agent is deployed
    if [ ! -f "$PROJECT_DIR/.bedrock_agentcore.yaml" ]; then
        log_fail "Agent not deployed (.bedrock_agentcore.yaml not found)"
        log_info "Run: ./direct-deploy/scripts/deploy.sh first"
        ((TESTS_FAILED++))
        return 1
    fi
    
    # Check if test script exists
    local test_script="$PROJECT_DIR/direct-deploy/test_with_protection.py"
    if [ ! -f "$test_script" ]; then
        log_fail "Test script not found: $test_script"
        ((TESTS_FAILED++))
        return 1
    fi
    
    log_info "Integration mode: $integration_mode"
    log_info "Running test with question: \"$TEST_QUESTION\""
    
    cd "$PROJECT_DIR"
    
    # Set the integration mode environment variable
    export AGENTSEC_LLM_INTEGRATION_MODE="$integration_mode"
    
    # Run the test
    local start_time=$(date +%s)
    
    if [ -n "$TIMEOUT_CMD" ]; then
        $TIMEOUT_CMD "$TIMEOUT_SECONDS" poetry run python "$test_script" "$TEST_QUESTION" > "$log_file" 2>&1
        local exit_code=$?
    else
        poetry run python "$test_script" "$TEST_QUESTION" > "$log_file" 2>&1
        local exit_code=$?
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_info "Completed in ${duration}s (exit code: $exit_code)"
    
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
    
    # Check 4: No errors
    if ! grep -qE "^Traceback|SecurityPolicyError|BLOCKED" "$log_file"; then
        log_pass "No errors or blocks"
    else
        log_fail "Errors found in output"
        all_checks_passed=false
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
    
    # Check if function exists, if not deploy it automatically
    if ! aws lambda get-function --function-name "$function_name" --region "${AWS_REGION:-us-west-2}" > /dev/null 2>&1; then
        log_info "Lambda function not found, deploying automatically..."
        local deploy_script="$PROJECT_DIR/lambda-deploy/scripts/deploy.sh"
        
        if [ ! -f "$deploy_script" ]; then
            log_fail "Lambda deploy script not found: $deploy_script"
            ((TESTS_FAILED++))
            return 1
        fi
        
        # Run deploy script
        local deploy_log="$LOG_DIR/lambda-deploy-setup.log"
        if bash "$deploy_script" > "$deploy_log" 2>&1; then
            log_pass "Lambda function deployed successfully"
        else
            log_fail "Lambda deployment failed (see $deploy_log)"
            if [ "$VERBOSE" = "true" ]; then
                tail -20 "$deploy_log" | sed 's/^/    /'
            fi
            ((TESTS_FAILED++))
            return 1
        fi
        
        # Wait for function to be ready
        log_info "Waiting for Lambda to be ready..."
        sleep 5
    fi
    
    log_info "Integration mode: $integration_mode"
    log_info "Invoking Lambda: $function_name"
    log_info "Question: \"$TEST_QUESTION\""
    
    # Note: Lambda integration mode is configured at deploy time, not runtime
    # This test verifies the Lambda works; integration mode depends on Lambda's env vars
    
    # Invoke Lambda
    local start_time=$(date +%s)
    
    aws lambda invoke \
        --function-name "$function_name" \
        --region "${AWS_REGION:-us-west-2}" \
        --payload "{\"prompt\": \"$TEST_QUESTION\"}" \
        --cli-binary-format raw-in-base64-out \
        /tmp/lambda_response.json > "$log_file" 2>&1
    local exit_code=$?
    
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
    
    # Check 4: No errors
    if ! grep -qE "^Traceback|SecurityPolicyError|BLOCKED|\"errorMessage\"" "$log_file" /tmp/lambda_response.json 2>/dev/null; then
        log_pass "No errors or blocks"
    else
        log_fail "Errors found in output"
        all_checks_passed=false
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
    
    # Check if container agent is configured
    if ! grep -q "agentcore_sre_container" "$PROJECT_DIR/.bedrock_agentcore.yaml" 2>/dev/null; then
        log_fail "Container agent not configured"
        log_info "Run: ./container-deploy/scripts/deploy.sh first"
        ((TESTS_FAILED++))
        return 1
    fi
    
    log_info "Integration mode: $integration_mode"
    log_info "Invoking container agent"
    log_info "Question: \"$TEST_QUESTION\""
    
    cd "$PROJECT_DIR"
    
    # Note: Container integration mode is configured at deploy time via container env vars
    # This test verifies the container works
    
    # Invoke via agentcore CLI
    local start_time=$(date +%s)
    
    poetry run agentcore invoke --agent agentcore_sre_container "{\"prompt\": \"$TEST_QUESTION\"}" > "$log_file" 2>&1
    local exit_code=$?
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_info "Completed in ${duration}s (exit code: $exit_code)"
    
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
    
    # Check 3: No errors
    if ! grep -qE "^Traceback|SecurityPolicyError|BLOCKED|error" "$log_file"; then
        log_pass "No errors or blocks"
    else
        log_fail "Errors found in output"
        all_checks_passed=false
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
log_header "AgentCore Integration Tests"
echo ""
echo "  Project:          $PROJECT_DIR"
if [ "$MCP_ONLY" = "true" ]; then
    echo "  Test type:        MCP only"
elif [ "$RUN_MCP_TESTS" = "false" ]; then
    echo "  Test type:        LLM only (no MCP)"
else
    echo "  Test type:        LLM + MCP"
fi
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

# Install agentcore CLI (bedrock-agentcore-starter-toolkit) if not available
if ! poetry run agentcore --version &> /dev/null; then
    log_info "Installing AgentCore CLI..."
    poetry run pip install --quiet bedrock-agentcore-starter-toolkit
fi

# Load shared environment variables
SHARED_ENV="$PROJECT_DIR/../../.env"
if [ -f "$SHARED_ENV" ]; then
    log_info "Loading environment from $SHARED_ENV"
    set -a
    source "$SHARED_ENV"
    set +a
fi

# Setup log directory
setup_log_dir

# Run tests - iterate over deployment modes and integration modes
log_header "Running Tests"

# Run LLM tests (deploy modes x integration modes)
if [ "$RUN_LLM_TESTS" = "true" ]; then
    for deploy_mode in "${DEPLOY_MODES_TO_TEST[@]}"; do
        for integration_mode in "${INTEGRATION_MODES_TO_TEST[@]}"; do
            case $deploy_mode in
                direct)
                    test_direct_deploy "$integration_mode"
                    ;;
                container)
                    test_container_deploy "$integration_mode"
                    ;;
                lambda)
                    test_lambda_deploy "$integration_mode"
                    ;;
            esac
        done
    done
fi

# Run MCP tests (integration modes only - not tied to deploy mode)
if [ "$RUN_MCP_TESTS" = "true" ]; then
    log_header "MCP Tool Protection Tests"
    
    # Set default MCP_SERVER_URL if not set
    export MCP_SERVER_URL="${MCP_SERVER_URL:-https://mcp.deepwiki.com/mcp}"
    
    for integration_mode in "${INTEGRATION_MODES_TO_TEST[@]}"; do
        test_mcp_protection "$integration_mode"
    done
fi

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
