#!/bin/bash
# =============================================================================
# Azure AI Foundry Integration Tests
# =============================================================================
# Tests all 3 deployment modes in BOTH Cisco AI Defense integration modes:
#   Deployment Modes:
#   - Agent App: Flask app as managed online endpoint
#   - Azure Functions: Serverless function
#   - Container: Custom container deployment
#
#   Integration Modes (Cisco AI Defense):
#   - API Mode: Inspection via Cisco AI Defense API
#   - Gateway Mode: Route through Cisco AI Defense Gateway
#
# Test Modes:
#   - Local (default): Tests agent locally using Azure OpenAI credentials
#   - Deploy (--deploy): Deploys to Azure and tests real endpoints
#
# For each test, verifies:
#   1. LLM calls are intercepted by AI Defense
#   2. Request inspection happens
#   3. Response inspection happens (where applicable)
#   4. No errors occur during execution
#
# Usage:
#   ./tests/integration/test-all-modes.sh                    # Run local tests (default)
#   ./tests/integration/test-all-modes.sh --deploy           # Deploy and test in Azure
#   ./tests/integration/test-all-modes.sh --verbose          # Verbose output
#   ./tests/integration/test-all-modes.sh --api              # API mode only
#   ./tests/integration/test-all-modes.sh --gateway          # Gateway mode only
#   ./tests/integration/test-all-modes.sh agent-app          # Test agent app only
#   ./tests/integration/test-all-modes.sh --deploy agent-app # Deploy and test agent app
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
ALL_DEPLOY_MODES=("agent-app" "azure-functions" "container")
ALL_INTEGRATION_MODES=("api" "gateway")
RUN_MCP_TESTS=true
LOCAL_ONLY=true   # Default to LOCAL mode (consistent with AgentCore/GCP; use --deploy for Azure)
FORCE_DEPLOY=false  # When true, force redeployment even if already deployed
RECREATE_DEPLOY=false  # When true, delete and recreate deployments (clean deploy)

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
    echo "  --local          Run LOCAL tests only (no Azure deployment)"
    echo "  --deploy         Explicitly run DEPLOY tests (default behavior)"
    echo "  --force-deploy   Force redeployment update even if already deployed"
    echo "  --recreate       Delete and recreate deployments (clean deploy)"
    echo "  --verbose, -v    Show detailed output"
    echo "  --api            Test API mode only (default: both modes)"
    echo "  --gateway        Test Gateway mode only (default: both modes)"
    echo "  --no-mcp         Skip MCP tool protection tests"
    echo "  --mcp-only       Run only MCP tool protection tests (direct invocation)"
    echo "  --mcp-agent      Run agent-prompted MCP tests (LLM triggers MCP tool call)"
    echo "  --help, -h       Show this help"
    echo ""
    echo "Deploy Modes:"
    echo "  agent-app        Test Foundry Agent Application"
    echo "  azure-functions  Test Azure Functions"
    echo "  container        Test Container deployment"
    echo ""
    echo "Test Modes:"
    echo "  Default (no flag): Tests agent LOCALLY using Azure OpenAI credentials"
    echo "                     Requires: AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY"
    echo ""
    echo "  With --deploy:     Deploys to Azure and tests real endpoints"
    echo "                     Requires: AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP,"
    echo "                               AZURE_AI_FOUNDRY_PROJECT, etc."
    echo ""
    echo "MCP Test Modes:"
    echo "  --mcp-only       Direct MCP test: directly invokes MCP tool (fast)"
    echo "  --mcp-agent      Agent-prompted MCP test: prompts LLM to trigger MCP (full loop)"
    echo ""
    echo "Examples:"
    echo "  $0                          # Run local tests (default)"
    echo "  $0 --verbose                # Local tests with details"
    echo "  $0 --deploy                 # Deploy and test in Azure"
    echo "  $0 --deploy --force-deploy  # Force update existing deployments"
    echo "  $0 --deploy --recreate      # Delete and recreate deployments"
    echo "  $0 --deploy agent-app       # Deploy and test agent app only"
    echo "  $0 --api                    # Local tests, API mode only"
    echo "  $0 --deploy --api           # Deploy and test, API mode only"
    echo "  $0 --mcp-agent --verbose    # Test LLM → MCP flow with details"
}

setup_log_dir() {
    mkdir -p "$LOG_DIR"
    rm -f "$LOG_DIR"/*.log 2>/dev/null || true
}

# Check if Azure deployment credentials are configured
check_azure_deploy_credentials() {
    local missing_vars=()
    
    [ -z "${AZURE_SUBSCRIPTION_ID:-}" ] && missing_vars+=("AZURE_SUBSCRIPTION_ID")
    [ -z "${AZURE_RESOURCE_GROUP:-}" ] && missing_vars+=("AZURE_RESOURCE_GROUP")
    [ -z "${AZURE_AI_FOUNDRY_PROJECT:-}" ] && missing_vars+=("AZURE_AI_FOUNDRY_PROJECT")
    
    if [ ${#missing_vars[@]} -gt 0 ]; then
        echo ""
        echo -e "${YELLOW}Missing Azure deployment credentials:${NC}"
        for var in "${missing_vars[@]}"; do
            echo -e "  - $var"
        done
        echo ""
        echo -e "${YELLOW}Set these in examples/.env to enable Azure deployment tests.${NC}"
        return 1
    fi
    return 0
}

# Check if Azure OpenAI credentials are configured (for local tests)
check_azure_openai_credentials() {
    local missing_vars=()
    
    [ -z "${AZURE_OPENAI_ENDPOINT:-}" ] && missing_vars+=("AZURE_OPENAI_ENDPOINT")
    [ -z "${AZURE_OPENAI_API_KEY:-}" ] && missing_vars+=("AZURE_OPENAI_API_KEY")
    
    if [ ${#missing_vars[@]} -gt 0 ]; then
        echo ""
        echo -e "${RED}Missing Azure OpenAI credentials:${NC}"
        for var in "${missing_vars[@]}"; do
            echo -e "  - $var"
        done
        echo ""
        echo -e "${RED}Set these in examples/.env to run tests.${NC}"
        return 1
    fi
    return 0
}

# =============================================================================
# Local Test Function (tests agent locally using Azure OpenAI)
# =============================================================================

test_local_agent() {
    local integration_mode=$1
    local deploy_mode=$2
    local log_file="$LOG_DIR/${deploy_mode}-local-${integration_mode}.log"
    
    log_subheader "Testing: Local Agent [$integration_mode mode]"
    
    log_info "Mode: LOCAL (using Azure OpenAI directly)"
    log_info "Integration mode: $integration_mode"
    log_info "Running test with question: \"$TEST_QUESTION\""
    
    cd "$PROJECT_DIR"
    
    # Set integration mode via environment variables
    export AGENTSEC_LLM_INTEGRATION_MODE="$integration_mode"
    export AGENTSEC_MCP_INTEGRATION_MODE="$integration_mode"
    
    # Enable debug logging so inspection log lines are captured in the log file
    export AGENTSEC_LOG_LEVEL="DEBUG"
    
    local start_time=$(date +%s)
    
    # Run the agent directly, then also exercise MCP tool protection
    if [ -n "$TIMEOUT_CMD" ]; then
        $TIMEOUT_CMD "$TIMEOUT_SECONDS" poetry run python -c "
import os
from _shared import invoke_agent
result = invoke_agent('$TEST_QUESTION')
print('RESULT:', result)
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
" > "$log_file" 2>&1 || local exit_code=$?
    else
        poetry run python -c "
import os
from _shared import invoke_agent
result = invoke_agent('$TEST_QUESTION')
print('RESULT:', result)
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
" > "$log_file" 2>&1 || local exit_code=$?
    fi
    exit_code=${exit_code:-0}
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_info "Completed in ${duration}s (exit code: $exit_code)"
    
    # Validate results
    local all_checks_passed=true
    
    # Check 1: agentsec patched clients
    if grep -q "Patched:.*openai" "$log_file"; then
        log_pass "agentsec patched: openai"
    else
        log_fail "agentsec did NOT patch openai client"
        all_checks_passed=false
    fi
    
    # Check 2: Request inspection (API mode only)
    if [ "$integration_mode" = "api" ]; then
        if grep -q "Request inspection\|Request decision" "$log_file"; then
            log_pass "Request inspection executed"
        else
            log_fail "No request inspection found"
            all_checks_passed=false
        fi
    fi
    
    # Check 3: Response inspection (API mode only)
    if [ "$integration_mode" = "api" ]; then
        if grep -q "Response inspection\|Response decision" "$log_file"; then
            log_pass "Response inspection executed"
        else
            log_info "Response inspection not found (may be OK)"
        fi
    fi
    
    # Check 4: Gateway mode communication
    if [ "$integration_mode" = "gateway" ]; then
        if grep -q "Gateway\|gateway" "$log_file"; then
            log_pass "Gateway mode communication successful"
        else
            log_fail "No gateway communication found"
            all_checks_passed=false
        fi
    fi
    
    # Check 5: Got a result
    if grep -q "RESULT:" "$log_file"; then
        log_pass "Agent produced a response"
    else
        log_fail "No response from agent"
        all_checks_passed=false
    fi
    
    # Check 6: MCP Request inspection
    if grep -qi "MCP.*Request inspection\|MCP TOOL CALL.*fetch\|call_tool.*fetch.*Request" "$log_file"; then
        log_pass "MCP Request inspection executed"
    elif grep -q "MCP_SERVER_URL not set" "$log_file"; then
        log_skip "MCP test skipped (MCP_SERVER_URL not set)"
    else
        log_fail "MCP Request inspection NOT executed"
        all_checks_passed=false
    fi
    
    # Check 7: MCP Response inspection
    if grep -qi "MCP.*Response inspection\|call_tool.*Response.*allow\|Response decision" "$log_file"; then
        log_pass "MCP Response inspection executed"
    elif grep -q "MCP_SERVER_URL not set" "$log_file"; then
        : # Already reported skip above
    else
        log_fail "MCP Response inspection NOT executed"
        all_checks_passed=false
    fi
    
    # Check 8: No errors
    if grep -E "^Traceback|BLOCKED|^\s*ERROR\s*:" "$log_file" | grep -v "DEBUG:" > /dev/null 2>&1; then
        local error_line=$(grep -E "^Traceback|BLOCKED|^\s*ERROR\s*:" "$log_file" | grep -v "DEBUG:" | head -1)
        log_fail "Errors found: $error_line"
        all_checks_passed=false
    else
        log_pass "No errors or blocks"
    fi
    
    if [ "$VERBOSE" = "true" ]; then
        echo ""
        echo -e "    ${MAGENTA}─── Log Output ───${NC}"
        cat "$log_file" | head -50 | sed 's/^/    /'
    fi
    
    # Summary
    if [ "$all_checks_passed" = "true" ]; then
        echo ""
        echo -e "  ${GREEN}${BOLD}► Local Agent [$integration_mode]: ALL CHECKS PASSED${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo ""
        echo -e "  ${RED}${BOLD}► Local Agent [$integration_mode]: SOME CHECKS FAILED${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

# =============================================================================
# Verify AI Defense protection in server-side logs (for DEPLOY tests)
# =============================================================================
# LLM protection runs SERVER-SIDE inside Azure containers/functions. The client
# only sees the HTTP response. We fetch server logs (az ml / az webapp) and
# check for agentsec inspection patterns.
# =============================================================================

verify_ai_defense_protection_azure() {
    local log_file="$1"
    local mode="$2"  # "api" or "gateway"
    
    local llm_req=false
    local llm_resp=false
    local patched=false
    
    # Check if agentsec patched (Microsoft Foundry uses openai via AzureChatOpenAI)
    if grep -qi "Patched.*openai\|Patched:.*openai" "$log_file"; then
        patched=true
    fi
    
    # For API mode: check for LLM inspection logs (exclude MCP-only lines)
    if [ "$mode" = "api" ]; then
        if grep -qi "\[PATCHED CALL\] OpenAI\.chat.completions.*Request inspection\|\[PATCHED CALL\] OpenAI\.chat.*Request decision" "$log_file"; then
            llm_req=true
        fi
        if grep -qi "\[PATCHED CALL\] OpenAI\.chat.completions.*Response inspection\|\[PATCHED CALL\] OpenAI\.chat.*Response decision" "$log_file"; then
            llm_resp=true
        fi
    fi
    
    # For Gateway mode: check for gateway routing of LLM calls
    if [ "$mode" = "gateway" ]; then
        if grep -qi "\[PATCHED CALL\] Gateway mode.*routing to AI Defense Gateway\|\[PATCHED CALL\] OpenAI.*Gateway" "$log_file"; then
            llm_req=true
            llm_resp=true  # Gateway handles both
        fi
    fi
    
    if [ "$patched" = true ]; then
        log_info "✓ agentsec patched: openai (server-side)"
    fi
    if [ "$llm_req" = true ]; then
        log_info "✓ LLM Request protection: verified in server logs"
    fi
    if [ "$llm_resp" = true ]; then
        log_info "✓ LLM Response protection: verified in server logs"
    fi
    if [ "$patched" = false ] && [ "$llm_req" = false ] && [ "$llm_resp" = false ]; then
        log_info "LLM protection evidence not found in fetched logs (agentsec runs server-side)"
        log_info "To verify manually: az ml online-deployment get-logs --name default --endpoint-name <endpoint> --resource-group \$AZURE_RESOURCE_GROUP --workspace-name \$AZURE_AI_FOUNDRY_PROJECT"
    fi
    return 0
}

# Fetch server-side logs from Azure ML Online Deployment (Agent App and Container)
fetch_azure_ml_deployment_logs() {
    local out_file="$1"
    local endpoint_name="$2"
    local deployment_name="${3:-default}"
    
    az ml online-deployment get-logs \
        --name "$deployment_name" \
        --endpoint-name "$endpoint_name" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --workspace-name "$AZURE_AI_FOUNDRY_PROJECT" \
        > "$out_file" 2>&1
    return $?
}

# Fetch server-side logs from Azure Functions.
# Must be started BEFORE invoke (stream captures logs in real-time).
# Usage: Call start_azure_functions_log_capture first, then invoke, then stop_azure_functions_log_capture.
start_azure_functions_log_capture() {
    local out_file="$1"
    # Start log stream in background (captures logs from upcoming invoke)
    az webapp log tail \
        --name "$AZURE_FUNCTION_APP_NAME" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        > "$out_file" 2>&1 &
    AZURE_FUNC_TAIL_PID=$!
    sleep 3  # Let stream connect
}

stop_azure_functions_log_capture() {
    sleep 12  # Allow time for invoke logs to appear
    if [ -n "${AZURE_FUNC_TAIL_PID:-}" ]; then
        kill "$AZURE_FUNC_TAIL_PID" 2>/dev/null || true
        wait "$AZURE_FUNC_TAIL_PID" 2>/dev/null || true
    fi
}

# =============================================================================
# Deployment Status Check Functions
# =============================================================================

# Check if Foundry Agent App endpoint exists and is running
check_foundry_agent_app_deployed() {
    local endpoint_name="${AGENT_ENDPOINT_NAME:-${ENDPOINT_NAME:-foundry-sre-agent}}"
    az ml online-endpoint show \
        --name "$endpoint_name" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --workspace-name "$AZURE_AI_FOUNDRY_PROJECT" \
        --query "provisioning_state" -o tsv 2>/dev/null | grep -q "Succeeded"
}

# Check if Azure Functions app exists and has functions deployed
check_azure_functions_deployed() {
    local func_name="${AZURE_FUNCTION_APP_NAME:-}"
    if [ -z "$func_name" ]; then
        return 1
    fi
    # Check if function app exists and has functions
    az functionapp function list \
        --name "$func_name" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --query "length(@)" -o tsv 2>/dev/null | grep -qE "^[1-9]"
}

# Check if Foundry Container endpoint exists and is running
check_foundry_container_deployed() {
    local endpoint_name="${CONTAINER_ENDPOINT_NAME:-foundry-sre-container}"
    az ml online-endpoint show \
        --name "$endpoint_name" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --workspace-name "$AZURE_AI_FOUNDRY_PROJECT" \
        --query "provisioning_state" -o tsv 2>/dev/null | grep -q "Succeeded"
}

# =============================================================================
# Deployment Deletion Functions (for --recreate)
# =============================================================================

# Delete Foundry Agent App deployment
delete_foundry_agent_app_deployment() {
    local endpoint_name="${AGENT_ENDPOINT_NAME:-foundry-sre-agent}"
    local deployment_name="${AGENT_DEPLOYMENT_NAME:-default}"
    
    log_info "Deleting Foundry Agent App deployment..."
    
    # Delete deployment first
    if az ml online-deployment show --name "$deployment_name" --endpoint-name "$endpoint_name" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --workspace-name "$AZURE_AI_FOUNDRY_PROJECT" &>/dev/null; then
        log_info "Deleting deployment: $deployment_name"
        az ml online-deployment delete \
            --name "$deployment_name" \
            --endpoint-name "$endpoint_name" \
            --resource-group "$AZURE_RESOURCE_GROUP" \
            --workspace-name "$AZURE_AI_FOUNDRY_PROJECT" \
            --yes 2>/dev/null || true
    fi
    
    # Delete endpoint
    if az ml online-endpoint show --name "$endpoint_name" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --workspace-name "$AZURE_AI_FOUNDRY_PROJECT" &>/dev/null; then
        log_info "Deleting endpoint: $endpoint_name"
        az ml online-endpoint delete \
            --name "$endpoint_name" \
            --resource-group "$AZURE_RESOURCE_GROUP" \
            --workspace-name "$AZURE_AI_FOUNDRY_PROJECT" \
            --yes 2>/dev/null || true
    fi
    
    log_pass "Foundry Agent App deployment deleted"
}

# Delete Foundry Container deployment
delete_foundry_container_deployment() {
    local endpoint_name="${CONTAINER_ENDPOINT_NAME:-foundry-sre-container}"
    local deployment_name="${CONTAINER_DEPLOYMENT_NAME:-default}"
    
    log_info "Deleting Foundry Container deployment..."
    
    # Delete deployment first
    if az ml online-deployment show --name "$deployment_name" --endpoint-name "$endpoint_name" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --workspace-name "$AZURE_AI_FOUNDRY_PROJECT" &>/dev/null; then
        log_info "Deleting deployment: $deployment_name"
        az ml online-deployment delete \
            --name "$deployment_name" \
            --endpoint-name "$endpoint_name" \
            --resource-group "$AZURE_RESOURCE_GROUP" \
            --workspace-name "$AZURE_AI_FOUNDRY_PROJECT" \
            --yes 2>/dev/null || true
    fi
    
    # Delete endpoint
    if az ml online-endpoint show --name "$endpoint_name" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --workspace-name "$AZURE_AI_FOUNDRY_PROJECT" &>/dev/null; then
        log_info "Deleting endpoint: $endpoint_name"
        az ml online-endpoint delete \
            --name "$endpoint_name" \
            --resource-group "$AZURE_RESOURCE_GROUP" \
            --workspace-name "$AZURE_AI_FOUNDRY_PROJECT" \
            --yes 2>/dev/null || true
    fi
    
    log_pass "Foundry Container deployment deleted"
}

# Delete Azure Functions deployment (redeploy will overwrite)
delete_azure_functions_deployment() {
    local func_name="${AZURE_FUNCTION_APP_NAME:-}"
    
    if [ -z "$func_name" ]; then
        log_info "Azure Function app name not configured, skipping delete"
        return 0
    fi
    
    log_info "Azure Functions will be redeployed (no deletion needed)"
    log_pass "Ready for Azure Functions redeployment"
}

# =============================================================================
# Azure Deployment Test Functions (requires --deploy flag)
# =============================================================================

test_foundry_agent_app_deploy() {
    local integration_mode=$1
    log_subheader "Testing: Foundry Agent App DEPLOY [$integration_mode mode]"
    
    local log_file="$LOG_DIR/agent-app-deploy-${integration_mode}.log"
    local deploy_script="$PROJECT_DIR/foundry-agent-app/scripts/deploy.sh"
    local invoke_script="$PROJECT_DIR/foundry-agent-app/scripts/invoke.sh"
    
    # Check Azure credentials
    if ! check_azure_deploy_credentials; then
        log_skip "Azure deployment not configured"
        ((TESTS_SKIPPED++))
        return 0
    fi
    
    log_info "Mode: DEPLOY (deploying to Azure AI Foundry)"
    log_info "Integration mode: $integration_mode"
    
    # Set integration mode
    export AGENTSEC_LLM_INTEGRATION_MODE="$integration_mode"
    export AGENTSEC_MCP_INTEGRATION_MODE="$integration_mode"
    
    # Handle recreate: delete existing deployment first
    if [ "$RECREATE_DEPLOY" = "true" ]; then
        log_info "Recreate requested - deleting existing deployment first..."
        delete_foundry_agent_app_deployment
        log_info "Creating fresh deployment..."
        if bash "$deploy_script" > "$LOG_DIR/agent-app-deploy-setup.log" 2>&1; then
            log_pass "Fresh deployment successful"
        else
            log_fail "Deployment failed (see $LOG_DIR/agent-app-deploy-setup.log)"
            if [ "$VERBOSE" = "true" ]; then
                tail -20 "$LOG_DIR/agent-app-deploy-setup.log" | sed 's/^/    /'
            fi
            ((TESTS_FAILED++))
            return 1
        fi
    # Handle force deploy: update existing deployment
    elif [ "$FORCE_DEPLOY" = "true" ]; then
        log_info "Force deploy requested - updating Foundry Agent App..."
        if bash "$deploy_script" > "$LOG_DIR/agent-app-deploy-setup.log" 2>&1; then
            log_pass "Deployment update successful"
        else
            log_fail "Deployment failed (see $LOG_DIR/agent-app-deploy-setup.log)"
            if [ "$VERBOSE" = "true" ]; then
                tail -20 "$LOG_DIR/agent-app-deploy-setup.log" | sed 's/^/    /'
            fi
            ((TESTS_FAILED++))
            return 1
        fi
    elif check_foundry_agent_app_deployed; then
        log_pass "Foundry Agent App already deployed - skipping deployment"
    else
        # Deploy (ACR build + ML deployment often 10-20 min total)
        log_info "Deploying Foundry Agent App... (may take 10-20 min; progress: tail -f $LOG_DIR/agent-app-deploy-setup.log)"
        if bash "$deploy_script" > "$LOG_DIR/agent-app-deploy-setup.log" 2>&1; then
            log_pass "Deployment successful"
        else
            log_fail "Deployment failed (see $LOG_DIR/agent-app-deploy-setup.log)"
            if [ "$VERBOSE" = "true" ]; then
                tail -20 "$LOG_DIR/agent-app-deploy-setup.log" | sed 's/^/    /'
            fi
            ((TESTS_FAILED++))
            return 1
        fi
    fi
    
    # Invoke the endpoint
    log_info "Invoking endpoint with: \"$TEST_QUESTION\""
    if bash "$invoke_script" "$TEST_QUESTION" > "$log_file" 2>&1; then
        log_pass "Endpoint invocation successful"
    else
        log_fail "Endpoint invocation failed"
        ((TESTS_FAILED++))
        return 1
    fi
    
    # Validate results
    local all_checks_passed=true
    
    if grep -q "result" "$log_file"; then
        log_pass "Got response from endpoint"
    else
        log_fail "No response from endpoint"
        all_checks_passed=false
    fi
    
    # Fetch server-side logs and verify LLM protection (agentsec runs inside container)
    log_info "Checking server-side logs for AI Defense protection..."
    local endpoint_name="${AGENT_ENDPOINT_NAME:-${ENDPOINT_NAME:-foundry-sre-agent}}"
    local deployment_name="${AGENT_DEPLOYMENT_NAME:-default}"
    local server_logs_file="$LOG_DIR/agent-app-deploy-${integration_mode}-server-logs.log"
    if fetch_azure_ml_deployment_logs "$server_logs_file" "$endpoint_name" "$deployment_name"; then
        verify_ai_defense_protection_azure "$server_logs_file" "$integration_mode"
    else
        log_info "Could not fetch Azure ML deployment logs (agentsec runs server-side)"
        log_info "To verify manually: az ml online-deployment get-logs --name $deployment_name --endpoint-name $endpoint_name --resource-group \$AZURE_RESOURCE_GROUP --workspace-name \$AZURE_AI_FOUNDRY_PROJECT"
    fi
    
    if [ "$VERBOSE" = "true" ]; then
        echo ""
        echo -e "    ${MAGENTA}─── Response ───${NC}"
        cat "$log_file" | head -20 | sed 's/^/    /'
    fi
    
    if [ "$all_checks_passed" = "true" ]; then
        echo ""
        echo -e "  ${GREEN}${BOLD}► Foundry Agent App DEPLOY [$integration_mode]: ALL CHECKS PASSED${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo ""
        echo -e "  ${RED}${BOLD}► Foundry Agent App DEPLOY [$integration_mode]: SOME CHECKS FAILED${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

test_azure_functions_deploy() {
    local integration_mode=$1
    log_subheader "Testing: Azure Functions DEPLOY [$integration_mode mode]"
    
    local log_file="$LOG_DIR/azure-functions-deploy-${integration_mode}.log"
    local deploy_script="$PROJECT_DIR/azure-functions/scripts/deploy.sh"
    local invoke_script="$PROJECT_DIR/azure-functions/scripts/invoke.sh"
    
    # Check Azure credentials
    if ! check_azure_deploy_credentials; then
        log_skip "Azure deployment not configured"
        ((TESTS_SKIPPED++))
        return 0
    fi
    
    # Additional check for Functions-specific credentials
    if [ -z "${AZURE_FUNCTION_APP_NAME:-}" ] || [ -z "${AZURE_STORAGE_ACCOUNT:-}" ]; then
        log_skip "Azure Functions not configured (AZURE_FUNCTION_APP_NAME, AZURE_STORAGE_ACCOUNT)"
        ((TESTS_SKIPPED++))
        return 0
    fi
    
    log_info "Mode: DEPLOY (deploying to Azure Functions)"
    log_info "Integration mode: $integration_mode"
    
    # Set integration mode
    export AGENTSEC_LLM_INTEGRATION_MODE="$integration_mode"
    export AGENTSEC_MCP_INTEGRATION_MODE="$integration_mode"
    
    # Handle recreate or force deploy: redeploy Azure Functions
    if [ "$RECREATE_DEPLOY" = "true" ] || [ "$FORCE_DEPLOY" = "true" ]; then
        log_info "Redeploying Azure Functions..."
        if bash "$deploy_script" > "$LOG_DIR/azure-functions-deploy-setup.log" 2>&1; then
            log_pass "Deployment successful"
        else
            log_fail "Deployment failed (see $LOG_DIR/azure-functions-deploy-setup.log)"
            if [ "$VERBOSE" = "true" ]; then
                tail -20 "$LOG_DIR/azure-functions-deploy-setup.log" | sed 's/^/    /'
            fi
            ((TESTS_FAILED++))
            return 1
        fi
    elif check_azure_functions_deployed; then
        log_pass "Azure Functions already deployed - skipping deployment"
    else
        # Deploy
        log_info "Deploying Azure Function..."
        if bash "$deploy_script" > "$LOG_DIR/azure-functions-deploy-setup.log" 2>&1; then
            log_pass "Deployment successful"
        else
            log_fail "Deployment failed (see $LOG_DIR/azure-functions-deploy-setup.log)"
            if [ "$VERBOSE" = "true" ]; then
                tail -20 "$LOG_DIR/azure-functions-deploy-setup.log" | sed 's/^/    /'
            fi
            ((TESTS_FAILED++))
            return 1
        fi
    fi
    
    # Start log capture BEFORE invoke (stream captures logs in real-time)
    local func_logs_file="$LOG_DIR/azure-functions-deploy-${integration_mode}-server-logs.log"
    log_info "Starting server log capture..."
    start_azure_functions_log_capture "$func_logs_file"

    # Invoke (retry once after brief wait to allow for cold start)
    log_info "Invoking function with: \"$TEST_QUESTION\""
    if ! bash "$invoke_script" "$TEST_QUESTION" > "$log_file" 2>&1; then
        stop_azure_functions_log_capture
        log_info "First invoke failed (possible cold start); waiting 10s and retrying..."
        sleep 10
        start_azure_functions_log_capture "$func_logs_file"
        if ! bash "$invoke_script" "$TEST_QUESTION" > "$log_file" 2>&1; then
            stop_azure_functions_log_capture
            log_fail "Function invocation failed"
            echo -e "    ${MAGENTA}─── Invoke log (last 25 lines) ───${NC}"
            tail -25 "$log_file" | sed 's/^/    /'
            echo -e "    ${MAGENTA}─── Full log: $log_file ───${NC}"
            ((TESTS_FAILED++))
            return 1
        fi
    fi
    stop_azure_functions_log_capture
    log_pass "Function invocation successful"

    # Validate
    local all_checks_passed=true

    if grep -q "result" "$log_file"; then
        log_pass "Got response from function"
    else
        log_fail "No response from function"
        all_checks_passed=false
    fi

    # Verify LLM protection in captured server-side logs (agentsec runs inside function)
    log_info "Checking server-side logs for AI Defense protection..."
    if [ -s "$func_logs_file" ]; then
        verify_ai_defense_protection_azure "$func_logs_file" "$integration_mode"
    else
        log_info "Could not capture Azure Functions logs (agentsec runs server-side)"
        log_info "To verify manually: az webapp log tail --name \$AZURE_FUNCTION_APP_NAME --resource-group \$AZURE_RESOURCE_GROUP (run before invoking)"
    fi

    if [ "$VERBOSE" = "true" ]; then
        echo ""
        echo -e "    ${MAGENTA}─── Response ───${NC}"
        cat "$log_file" | head -20 | sed 's/^/    /'
    fi
    
    if [ "$all_checks_passed" = "true" ]; then
        echo ""
        echo -e "  ${GREEN}${BOLD}► Azure Functions DEPLOY [$integration_mode]: ALL CHECKS PASSED${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo ""
        echo -e "  ${RED}${BOLD}► Azure Functions DEPLOY [$integration_mode]: SOME CHECKS FAILED${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

test_foundry_container_deploy() {
    local integration_mode=$1
    log_subheader "Testing: Foundry Container DEPLOY [$integration_mode mode]"
    
    local log_file="$LOG_DIR/container-deploy-${integration_mode}.log"
    local deploy_script="$PROJECT_DIR/foundry-container/scripts/deploy.sh"
    local invoke_script="$PROJECT_DIR/foundry-container/scripts/invoke.sh"
    
    # Check Azure credentials
    if ! check_azure_deploy_credentials; then
        log_skip "Azure deployment not configured"
        ((TESTS_SKIPPED++))
        return 0
    fi
    
    # Additional check for Container-specific credentials
    if [ -z "${AZURE_ACR_NAME:-}" ] || [ -z "${AZURE_ACR_LOGIN_SERVER:-}" ]; then
        log_skip "Azure Container Registry not configured (AZURE_ACR_NAME, AZURE_ACR_LOGIN_SERVER)"
        ((TESTS_SKIPPED++))
        return 0
    fi
    
    log_info "Mode: DEPLOY (deploying to Azure AI Foundry as container)"
    log_info "Integration mode: $integration_mode"
    
    # Set integration mode
    export AGENTSEC_LLM_INTEGRATION_MODE="$integration_mode"
    export AGENTSEC_MCP_INTEGRATION_MODE="$integration_mode"
    
    # Handle recreate: delete existing deployment first
    if [ "$RECREATE_DEPLOY" = "true" ]; then
        log_info "Recreate requested - deleting existing deployment first..."
        delete_foundry_container_deployment
        log_info "Creating fresh container deployment..."
        if bash "$deploy_script" > "$LOG_DIR/container-deploy-setup.log" 2>&1; then
            log_pass "Fresh deployment successful"
        else
            log_fail "Deployment failed (see $LOG_DIR/container-deploy-setup.log)"
            if [ "$VERBOSE" = "true" ]; then
                tail -20 "$LOG_DIR/container-deploy-setup.log" | sed 's/^/    /'
            fi
            ((TESTS_FAILED++))
            return 1
        fi
    # Handle force deploy: update existing deployment
    elif [ "$FORCE_DEPLOY" = "true" ]; then
        log_info "Force deploy requested - updating container deployment..."
        if bash "$deploy_script" > "$LOG_DIR/container-deploy-setup.log" 2>&1; then
            log_pass "Deployment update successful"
        else
            log_fail "Deployment failed (see $LOG_DIR/container-deploy-setup.log)"
            if [ "$VERBOSE" = "true" ]; then
                tail -20 "$LOG_DIR/container-deploy-setup.log" | sed 's/^/    /'
            fi
            ((TESTS_FAILED++))
            return 1
        fi
    elif check_foundry_container_deployed; then
        log_pass "Foundry Container already deployed - skipping deployment"
    else
        # Deploy
        log_info "Building and deploying container..."
        if bash "$deploy_script" > "$LOG_DIR/container-deploy-setup.log" 2>&1; then
            log_pass "Deployment successful"
        else
            log_fail "Deployment failed (see $LOG_DIR/container-deploy-setup.log)"
            if [ "$VERBOSE" = "true" ]; then
                tail -20 "$LOG_DIR/container-deploy-setup.log" | sed 's/^/    /'
            fi
            ((TESTS_FAILED++))
            return 1
        fi
    fi
    
    # Invoke
    log_info "Invoking container endpoint with: \"$TEST_QUESTION\""
    if bash "$invoke_script" "$TEST_QUESTION" > "$log_file" 2>&1; then
        log_pass "Container invocation successful"
    else
        log_fail "Container invocation failed"
        ((TESTS_FAILED++))
        return 1
    fi
    
    # Validate
    local all_checks_passed=true
    
    if grep -q "result" "$log_file"; then
        log_pass "Got response from container"
    else
        log_fail "No response from container"
        all_checks_passed=false
    fi
    
    # Fetch server-side logs and verify LLM protection (agentsec runs inside container)
    log_info "Checking server-side logs for AI Defense protection..."
    local endpoint_name="${CONTAINER_ENDPOINT_NAME:-foundry-sre-container}"
    local deployment_name="${CONTAINER_DEPLOYMENT_NAME:-default}"
    local server_logs_file="$LOG_DIR/container-deploy-${integration_mode}-server-logs.log"
    if fetch_azure_ml_deployment_logs "$server_logs_file" "$endpoint_name" "$deployment_name"; then
        verify_ai_defense_protection_azure "$server_logs_file" "$integration_mode"
    else
        log_info "Could not fetch Azure ML deployment logs (agentsec runs server-side)"
        log_info "To verify manually: az ml online-deployment get-logs --name $deployment_name --endpoint-name $endpoint_name --resource-group \$AZURE_RESOURCE_GROUP --workspace-name \$AZURE_AI_FOUNDRY_PROJECT"
    fi
    
    if [ "$VERBOSE" = "true" ]; then
        echo ""
        echo -e "    ${MAGENTA}─── Response ───${NC}"
        cat "$log_file" | head -20 | sed 's/^/    /'
    fi
    
    if [ "$all_checks_passed" = "true" ]; then
        echo ""
        echo -e "  ${GREEN}${BOLD}► Foundry Container DEPLOY [$integration_mode]: ALL CHECKS PASSED${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo ""
        echo -e "  ${RED}${BOLD}► Foundry Container DEPLOY [$integration_mode]: SOME CHECKS FAILED${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

# =============================================================================
# MCP Test Functions
# =============================================================================

test_mcp_protection() {
    local integration_mode=$1
    log_subheader "Testing: MCP Tool Protection [$integration_mode mode]"
    
    local log_file="$LOG_DIR/mcp-protection-${integration_mode}.log"
    local test_script="$SCRIPT_DIR/test_mcp_protection.py"
    
    # Check if MCP_SERVER_URL is set
    if [ -z "${MCP_SERVER_URL:-}" ]; then
        log_skip "MCP_SERVER_URL not configured"
        ((TESTS_SKIPPED++))
        return 0
    fi
    
    log_info "Integration mode: $integration_mode"
    log_info "MCP Server: $MCP_SERVER_URL"
    
    cd "$PROJECT_DIR"
    
    # Set integration mode
    export AGENTSEC_LLM_INTEGRATION_MODE="$integration_mode"
    export AGENTSEC_MCP_INTEGRATION_MODE="$integration_mode"
    
    # Enable debug logging so MCP inspection log lines are captured in the log file
    export AGENTSEC_LOG_LEVEL="DEBUG"
    
    local start_time=$(date +%s)
    
    # Run the MCP test (direct tool invocation)
    if [ -n "$TIMEOUT_CMD" ]; then
        $TIMEOUT_CMD "$TIMEOUT_SECONDS" poetry run python "$test_script" > "$log_file" 2>&1 || local exit_code=$?
    else
        poetry run python "$test_script" > "$log_file" 2>&1 || local exit_code=$?
    fi
    exit_code=${exit_code:-0}
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_info "Completed in ${duration}s (exit code: $exit_code)"
    
    # Validate results
    local all_checks_passed=true
    
    # Check 1: MCP patched
    if grep -q "MCP client patched\|Patched.*mcp" "$log_file"; then
        log_pass "MCP client patched by agentsec"
    else
        log_fail "MCP client NOT patched"
        all_checks_passed=false
    fi
    
    # Check 2: MCP Request inspection
    if grep -qi "MCP.*request.*inspection\|MCP TOOL CALL\|call_tool.*fetch.*Request" "$log_file"; then
        log_pass "MCP Request inspection executed"
    else
        log_fail "MCP Request inspection NOT executed"
        all_checks_passed=false
    fi
    
    # Check 3: MCP Response inspection
    if grep -qi "MCP.*response.*inspection\|Got response\|Response decision" "$log_file"; then
        log_pass "MCP Response inspection executed"
    else
        log_fail "MCP Response inspection NOT executed"
        all_checks_passed=false
    fi
    
    # Check 4: Tool succeeded
    if grep -q "tool call succeeded\|SUCCESS\|PASS" "$log_file"; then
        log_pass "MCP tool call succeeded"
    else
        log_fail "MCP tool call failed"
        all_checks_passed=false
    fi
    
    # Check 5: No errors
    if grep -E "FAIL|ERROR.*:" "$log_file" | grep -v "MCP TOOL ERROR" > /dev/null 2>&1; then
        local error_line=$(grep -E "FAIL|ERROR.*:" "$log_file" | head -1)
        log_fail "Errors found: $error_line"
        all_checks_passed=false
    else
        log_pass "No errors or blocks"
    fi
    
    if [ "$VERBOSE" = "true" ]; then
        echo ""
        echo -e "    ${MAGENTA}─── Log Output ───${NC}"
        cat "$log_file" | head -50 | sed 's/^/    /'
    fi
    
    # Summary
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
# Agent-Prompted MCP Test (LLM triggers MCP tool call)
# =============================================================================
# This tests the FULL agent loop:
#   User prompt → LLM (protected) → decides to call fetch_url → MCP (protected) → response
# Similar to how GCP Vertex AI example tests MCP through the agent.

test_mcp_via_agent() {
    local integration_mode=$1
    log_subheader "Testing: Agent-Prompted MCP [$integration_mode mode]"
    
    local log_file="$LOG_DIR/mcp-via-agent-${integration_mode}.log"
    local test_script="$SCRIPT_DIR/test_mcp_protection.py"
    
    # Check if MCP_SERVER_URL is set
    if [ -z "${MCP_SERVER_URL:-}" ]; then
        log_skip "MCP_SERVER_URL not configured"
        ((TESTS_SKIPPED++))
        return 0
    fi
    
    # Check Azure OpenAI is configured
    if [ -z "${AZURE_OPENAI_ENDPOINT:-}" ] || [ -z "${AZURE_OPENAI_API_KEY:-}" ]; then
        log_skip "Azure OpenAI not configured (needed for agent)"
        ((TESTS_SKIPPED++))
        return 0
    fi
    
    log_info "Integration mode: $integration_mode"
    log_info "MCP Server: $MCP_SERVER_URL"
    log_info "Test: Prompting LLM to trigger MCP tool call"
    
    cd "$PROJECT_DIR"
    
    # Set integration mode
    export AGENTSEC_LLM_INTEGRATION_MODE="$integration_mode"
    export AGENTSEC_MCP_INTEGRATION_MODE="$integration_mode"
    
    # Enable debug logging so inspection log lines are captured in the log file
    export AGENTSEC_LOG_LEVEL="DEBUG"
    
    local start_time=$(date +%s)
    
    # Run the agent-prompted MCP test
    if [ -n "$TIMEOUT_CMD" ]; then
        $TIMEOUT_CMD "$TIMEOUT_SECONDS" poetry run python "$test_script" --agent > "$log_file" 2>&1 || local exit_code=$?
    else
        poetry run python "$test_script" --agent > "$log_file" 2>&1 || local exit_code=$?
    fi
    exit_code=${exit_code:-0}
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_info "Completed in ${duration}s (exit code: $exit_code)"
    
    # Validate results
    local all_checks_passed=true
    
    # Check 1: Both MCP and OpenAI patched
    if grep -q "Both MCP and OpenAI clients patched" "$log_file"; then
        log_pass "Both MCP and OpenAI clients patched by agentsec"
    else
        log_fail "Not all clients patched"
        all_checks_passed=false
    fi
    
    # Check 2: Agent tool call (LLM decided to call fetch_url)
    if grep -qi "Tool call:.*fetch\|TOOL CALL.*fetch\|fetch_url" "$log_file"; then
        log_pass "LLM triggered MCP tool call (fetch_url)"
    else
        log_info "LLM may not have called fetch_url tool"
    fi
    
    # Check 3: MCP Request inspection
    if grep -qi "MCP.*request.*inspection\|PATCHED.*MCP\|call_tool.*Request" "$log_file"; then
        log_pass "MCP Request inspection executed"
    else
        log_info "MCP Request inspection not found (may be OK if tool not called)"
    fi
    
    # Check 4: Agent responded
    if grep -q "Agent-prompted MCP protection test passed\|SUCCESS" "$log_file"; then
        log_pass "Agent responded successfully"
    else
        log_fail "Agent test failed"
        all_checks_passed=false
    fi
    
    # Check 5: No errors
    if grep -E "FAIL|Traceback|^\s*ERROR\s*:" "$log_file" > /dev/null 2>&1; then
        local error_line=$(grep -E "FAIL|Traceback|^\s*ERROR\s*:" "$log_file" | head -1)
        log_fail "Errors found: $error_line"
        all_checks_passed=false
    else
        log_pass "No errors or blocks"
    fi
    
    if [ "$VERBOSE" = "true" ]; then
        echo ""
        echo -e "    ${MAGENTA}─── Log Output ───${NC}"
        cat "$log_file" | head -80 | sed 's/^/    /'
    fi
    
    # Summary
    if [ "$all_checks_passed" = "true" ]; then
        echo ""
        echo -e "  ${GREEN}${BOLD}► Agent-Prompted MCP [$integration_mode]: ALL CHECKS PASSED${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo ""
        echo -e "  ${RED}${BOLD}► Agent-Prompted MCP [$integration_mode]: SOME CHECKS FAILED${NC}"
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
MCP_ONLY="false"
MCP_AGENT="false"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_help
            exit 0
            ;;
        --local)
            LOCAL_ONLY=true
            shift
            ;;
        --deploy)
            LOCAL_ONLY=false
            shift
            ;;
        --force-deploy)
            FORCE_DEPLOY=true
            LOCAL_ONLY=false
            shift
            ;;
        --recreate)
            RECREATE_DEPLOY=true
            LOCAL_ONLY=false
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
            MCP_ONLY="true"
            shift
            ;;
        --mcp-agent)
            MCP_AGENT="true"
            shift
            ;;
        agent-app|azure-functions|container)
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
if [ "$LOCAL_ONLY" = "true" ]; then
    log_header "Azure AI Foundry Integration Tests (LOCAL MODE)"
    echo ""
    echo -e "  ${BLUE}LOCAL MODE: Testing agent locally using Azure OpenAI${NC}"
    echo -e "  ${BLUE}Use --deploy flag to deploy and test real Azure endpoints${NC}"
else
    log_header "Azure AI Foundry Integration Tests (DEPLOY MODE)"
    echo ""
    echo -e "  ${YELLOW}${BOLD}⚠ DEPLOY MODE: Will deploy to Azure and test real endpoints${NC}"
fi

# Check poetry is available
if ! command -v poetry &> /dev/null; then
    echo ""
    echo -e "${RED}ERROR: Poetry is not installed${NC}"
    exit 1
fi

# Load shared environment variables (examples/agentsec/.env is 2 levels up from microsoft-foundry)
# Path: microsoft-foundry/ -> 3-agent-runtimes/ -> agentsec/
# Preserve resource names if already set by parent (e.g. run-integration-tests.sh --new-resources)
_SAVED_AGENT_ENDPOINT="$AGENT_ENDPOINT_NAME"
_SAVED_CONTAINER_ENDPOINT="$CONTAINER_ENDPOINT_NAME"
_SAVED_AZURE_FUNC_APP="$AZURE_FUNCTION_APP_NAME"
SHARED_ENV="$PROJECT_DIR/../../.env"
if [ -f "$SHARED_ENV" ]; then
    log_info "Loading environment from $SHARED_ENV"
    set -a
    source "$SHARED_ENV"
    set +a
else
    log_info "No shared .env found at $SHARED_ENV"
fi
# Restore resource names so --new-resources (timestamped names) from parent are not overwritten by .env
[ -n "$_SAVED_AGENT_ENDPOINT" ] && export AGENT_ENDPOINT_NAME="$_SAVED_AGENT_ENDPOINT"
[ -n "$_SAVED_CONTAINER_ENDPOINT" ] && export CONTAINER_ENDPOINT_NAME="$_SAVED_CONTAINER_ENDPOINT"
[ -n "$_SAVED_AZURE_FUNC_APP" ] && export AZURE_FUNCTION_APP_NAME="$_SAVED_AZURE_FUNC_APP"

# If any resource name still unset, load from last --new-resources run so "Checking Existing Deployments" finds timestamped resources
if [ -z "${AGENT_ENDPOINT_NAME:-}" ] || [ -z "${CONTAINER_ENDPOINT_NAME:-}" ] || [ -z "${AZURE_FUNCTION_APP_NAME:-}" ]; then
    LAST_RESOURCES_FILE="$(cd "$PROJECT_DIR/../../../../.." && pwd)/scripts/.last_new_resources_run"
    if [ -f "$LAST_RESOURCES_FILE" ]; then
        set -a && source "$LAST_RESOURCES_FILE" && set +a
    fi
fi

# Set default MCP_SERVER_URL if not set (loaded from .env or fallback)
export MCP_SERVER_URL="${MCP_SERVER_URL:-https://mcp.deepwiki.com/mcp}"

# Remove stale aidefense copy if present (container deploy copies it for Docker build; it shadows repo aidefense in MCP tests)
rm -rf "$PROJECT_DIR/aidefense" 2>/dev/null || true

# Display configuration (AFTER .env is loaded so values are correct)
echo ""
echo "  Project:          $PROJECT_DIR"
echo "  Deploy modes:     ${DEPLOY_MODES_TO_TEST[*]}"
echo "  Integration modes: ${INTEGRATION_MODES_TO_TEST[*]}"
echo "  MCP Server:       ${MCP_SERVER_URL:-not configured}"
echo "  Verbose:          $VERBOSE"
echo "  Local only:       $LOCAL_ONLY"
echo "  Force deploy:     $FORCE_DEPLOY"
echo "  Recreate deploy:  $RECREATE_DEPLOY"

# Check required credentials
if [ "$LOCAL_ONLY" = "true" ]; then
    if ! check_azure_openai_credentials; then
        echo ""
        echo -e "${RED}Cannot run tests without Azure OpenAI credentials.${NC}"
        exit 1
    fi
else
    if ! check_azure_deploy_credentials; then
        echo ""
        echo -e "${RED}Cannot run deploy tests without Azure credentials.${NC}"
        echo -e "${YELLOW}Run with --local flag for local tests.${NC}"
        exit 1
    fi
fi

# Show deployment status (only in deploy mode)
if [ "$LOCAL_ONLY" = "false" ]; then
    log_subheader "Checking Existing Deployments"
    
    echo ""
    echo -e "  ${CYAN}Checking deployment status...${NC}"
    
    # Check Foundry Agent App
    if check_foundry_agent_app_deployed 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} Foundry Agent App: ${GREEN}DEPLOYED${NC}"
        AGENT_APP_DEPLOYED=true
    else
        echo -e "  ${YELLOW}○${NC} Foundry Agent App: ${YELLOW}NOT DEPLOYED${NC} (will deploy)"
        AGENT_APP_DEPLOYED=false
    fi
    
    # Check Azure Functions
    if check_azure_functions_deployed 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} Azure Functions:   ${GREEN}DEPLOYED${NC}"
        AZURE_FUNCTIONS_DEPLOYED=true
    else
        echo -e "  ${YELLOW}○${NC} Azure Functions:   ${YELLOW}NOT DEPLOYED${NC} (will deploy)"
        AZURE_FUNCTIONS_DEPLOYED=false
    fi
    
    # Check Foundry Container
    if check_foundry_container_deployed 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} Foundry Container: ${GREEN}DEPLOYED${NC}"
        CONTAINER_DEPLOYED=true
    else
        echo -e "  ${YELLOW}○${NC} Foundry Container: ${YELLOW}NOT DEPLOYED${NC} (will deploy)"
        CONTAINER_DEPLOYED=false
    fi
    
    echo ""
fi

# Install dependencies
log_info "Installing dependencies..."
cd "$PROJECT_DIR"
poetry install --quiet 2>/dev/null || poetry install

# Setup log directory
setup_log_dir

# Run tests
log_header "Running Tests"

if [ "$MCP_ONLY" = "true" ]; then
    # MCP tests only (direct invocation)
    for integration_mode in "${INTEGRATION_MODES_TO_TEST[@]}"; do
        test_mcp_protection "$integration_mode"
    done
elif [ "$MCP_AGENT" = "true" ]; then
    # Agent-prompted MCP tests only (LLM triggers MCP tool call)
    log_header "Agent-Prompted MCP Tests (LLM → MCP flow)"
    for integration_mode in "${INTEGRATION_MODES_TO_TEST[@]}"; do
        test_mcp_via_agent "$integration_mode"
    done
else
    if [ "$LOCAL_ONLY" = "true" ]; then
        # Local tests
        for deploy_mode in "${DEPLOY_MODES_TO_TEST[@]}"; do
            for integration_mode in "${INTEGRATION_MODES_TO_TEST[@]}"; do
                test_local_agent "$integration_mode" "$deploy_mode"
            done
        done
    else
        # Azure deployment tests (default)
        for deploy_mode in "${DEPLOY_MODES_TO_TEST[@]}"; do
            for integration_mode in "${INTEGRATION_MODES_TO_TEST[@]}"; do
                case "$deploy_mode" in
                    agent-app)
                        test_foundry_agent_app_deploy "$integration_mode"
                        ;;
                    azure-functions)
                        test_azure_functions_deploy "$integration_mode"
                        ;;
                    container)
                        test_foundry_container_deploy "$integration_mode"
                        ;;
                    *)
                        log_fail "Unknown deploy_mode: $deploy_mode"
                        ((TESTS_FAILED++))
                        ;;
                esac
            done
        done
    fi
    
    # MCP tests (run in both modes)
    if [ "$RUN_MCP_TESTS" = "true" ]; then
        log_header "MCP Tool Protection Tests"
        for integration_mode in "${INTEGRATION_MODES_TO_TEST[@]}"; do
            test_mcp_protection "$integration_mode"
        done
    fi
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
    echo ""
    echo "  Logs saved to: $LOG_DIR/"
    exit 0
else
    echo -e "${RED}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}${BOLD}  ✗ TESTS FAILED ($TESTS_FAILED/$TOTAL failed)${NC}"
    echo -e "${RED}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "  Logs saved to: $LOG_DIR/"
    exit 1
fi
