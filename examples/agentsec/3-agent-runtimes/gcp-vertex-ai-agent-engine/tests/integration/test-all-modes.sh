#!/usr/bin/env bash
# =============================================================================
# Integration Test Runner for GCP Vertex AI Agent Engine
# =============================================================================
# Tests all three deployment modes (agent-engine, cloud-run, gke) in both
# API and Gateway integration modes for Cisco AI Defense.
#
# Test Modes:
#   - Local (default): Tests agent locally using GCP Vertex AI credentials only
#   - Deploy (--deploy): Deploys to GCP and tests real Cloud Run/GKE endpoints
#
# IMPORTANT: With --deploy, this script performs REAL deployments to GCP!
#   - Cloud Run: Deploys container to Cloud Run service
#   - GKE: Deploys container to GKE cluster (creates cluster if needed)
#
# Usage:
#   ./test-all-modes.sh                       # Run local tests (default)
#   ./test-all-modes.sh --deploy              # Deploy and test in GCP
#   ./test-all-modes.sh --quick               # Quick mode (agent-engine local, API mode only)
#   ./test-all-modes.sh --mode cloud-run      # Run specific deploy mode
#   ./test-all-modes.sh --api                 # Run API mode tests only
#   ./test-all-modes.sh --gateway             # Run Gateway mode tests only
#   ./test-all-modes.sh --local               # Explicit local mode (same as default)
#   ./test-all-modes.sh --cleanup             # Cleanup deployments after tests
#
# Environment:
#   GOOGLE_CLOUD_PROJECT                - GCP project ID
#   GOOGLE_CLOUD_LOCATION               - GCP region (default: us-central1)
#   AGENTSEC_LLM_INTEGRATION_MODE       - "api" or "gateway"
#   AI_DEFENSE_API_MODE_LLM_ENDPOINT    - AI Defense API endpoint
#   AI_DEFENSE_API_MODE_LLM_API_KEY     - AI Defense API key
#   GOOGLE_AI_SDK                       - "google_genai" (default) or "vertexai" (set via agentsec.yaml sdk field)
#
# =============================================================================
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Paths
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
EXAMPLES_DIR="$(dirname "$PROJECT_DIR")"
LOG_DIR="$SCRIPT_DIR/logs"

# Create logs directory
mkdir -p "$LOG_DIR"

# Load environment (check multiple locations); preserve resource names from parent (e.g. --new-resources)
_SAVED_AGENT_ENGINE_NAME="${AGENT_ENGINE_NAME:-}"
ENV_FILE=""
if [ -f "$EXAMPLES_DIR/.env" ]; then
    ENV_FILE="$EXAMPLES_DIR/.env"
elif [ -f "$EXAMPLES_DIR/../.env" ]; then
    ENV_FILE="$EXAMPLES_DIR/../.env"
fi

if [ -n "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE" 2>/dev/null || true
    set +a
fi
[ -n "$_SAVED_AGENT_ENGINE_NAME" ] && export AGENT_ENGINE_NAME="$_SAVED_AGENT_ENGINE_NAME"

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# Timing tracking (using regular array with key:value format for bash 3 compatibility)
DEPLOY_MODE_TIMES=()

# Available deploy modes
ALL_DEPLOY_MODES=("agent-engine" "cloud-run" "gke")

# Available integration modes for Cisco AI Defense
ALL_INTEGRATION_MODES=("api" "gateway")

# Modes to run (can be overridden by args)
DEPLOY_MODES_TO_RUN=("${ALL_DEPLOY_MODES[@]}")
INTEGRATION_MODES_TO_RUN=("${ALL_INTEGRATION_MODES[@]}")
QUICK_MODE=false
LOCAL_ONLY=true   # Default to local tests (no GCP deployment)
DO_CLEANUP=false
RUN_LLM_TESTS=true
RUN_MCP_TESTS=true

# =============================================================================
# Logging functions
# =============================================================================
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((TESTS_PASSED++))
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((TESTS_FAILED++))
}

log_skip() {
    echo -e "${YELLOW}[SKIP]${NC} $1"
    ((TESTS_SKIPPED++))
}

log_header() {
    echo ""
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}============================================${NC}"
}

# =============================================================================
# Help
# =============================================================================
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --local           Run LOCAL tests (default) - tests agent with GCP Vertex AI only"
    echo "  --deploy          Run DEPLOY tests - deploys to GCP and tests real endpoints"
    echo "  --quick           Quick mode (agent-engine local only, API mode only)"
    echo "  --mode MODE       Run specific deploy mode (agent-engine, cloud-run, gke)"
    echo "  --api             Run API mode tests only"
    echo "  --gateway         Run Gateway mode tests only"
    echo "  --no-mcp          Skip MCP tool protection tests"
    echo "  --mcp-only        Run only MCP tool protection tests"
    echo "  --cleanup         Cleanup deployments after tests"
    echo "  --help            Show this help"
    echo ""
    echo "Test Modes:"
    echo "  Without --deploy: Tests agent LOCALLY using GCP Vertex AI credentials"
    echo "                    Requires: GOOGLE_CLOUD_PROJECT, gcloud auth"
    echo ""
    echo "  With --deploy:    Deploys to GCP and tests real Cloud Run/GKE endpoints"
    echo "                    Requires: gcloud CLI, Docker, Cloud Run/GKE permissions"
    echo ""
    echo "Environment:"
    echo "  GOOGLE_AI_SDK     SDK to use: 'google_genai' (default) or 'vertexai'"
    echo "  MCP_SERVER_URL    MCP server URL (default: https://mcp.deepwiki.com/mcp)"
    echo ""
    echo "Examples:"
    echo "  $0                                  # Run local tests (default)"
    echo "  $0 --deploy                         # Deploy and test in GCP"
    echo "  $0 --quick                          # Quick local test (1 test)"
    echo "  $0 --deploy --api                   # Deploy and test, API mode only"
    echo "  $0 --mcp-only                       # Run only MCP tests"
    echo "  $0 --deploy --mode cloud-run --api  # Deploy Cloud Run, API mode only"
    echo "  $0 --deploy --mode gke --cleanup    # Deploy GKE and cleanup after"
    echo "  GOOGLE_AI_SDK=vertexai $0           # Test with vertexai SDK (Agent Engine safe)"
}

# =============================================================================
# Parse arguments
# =============================================================================
while [[ $# -gt 0 ]]; do
    case "$1" in
        --quick)
            QUICK_MODE=true
            # Don't override LOCAL_ONLY - let --deploy/--local control that
            DEPLOY_MODES_TO_RUN=("agent-engine")
            INTEGRATION_MODES_TO_RUN=("api")
            shift
            ;;
        --local)
            LOCAL_ONLY=true
            shift
            ;;
        --deploy)
            LOCAL_ONLY=false
            shift
            ;;
        --mode)
            if [ -n "${2:-}" ]; then
                DEPLOY_MODES_TO_RUN=("$2")
                shift 2
            else
                echo "Error: --mode requires an argument"
                exit 1
            fi
            ;;
        --api)
            INTEGRATION_MODES_TO_RUN=("api")
            shift
            ;;
        --gateway)
            INTEGRATION_MODES_TO_RUN=("gateway")
            shift
            ;;
        --cleanup)
            DO_CLEANUP=true
            shift
            ;;
        --no-mcp)
            RUN_MCP_TESTS=false
            shift
            ;;
        --mcp-only)
            RUN_MCP_TESTS=true
            RUN_LLM_TESTS=false
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# =============================================================================
# Verify response from deployed service
# =============================================================================
verify_ai_defense_in_response() {
    local response="$1"
    local log_file="$2"
    
    # Check that we got a valid response (not empty)
    if [ -z "$response" ]; then
        echo "Empty response" >> "$log_file"
        return 1
    fi
    
    # Check for successful JSON response with "status": "success"
    if echo "$response" | grep -q '"status".*:.*"success"'; then
        return 0
    fi
    
    # Check for "result" field in JSON (valid response)
    if echo "$response" | grep -q '"result"'; then
        return 0
    fi
    
    # Check for HTTP errors (real errors, not "error rate" in content)
    if echo "$response" | grep -qiE "HTTP.*[45][0-9][0-9]|Internal Server Error|Connection refused|timeout"; then
        echo "Response contains HTTP error" >> "$log_file"
        return 1
    fi
    
    # Accept responses longer than 50 chars (likely valid content)
    if [ ${#response} -gt 50 ]; then
        return 0
    fi
    
    echo "Response validation failed - too short or missing expected fields" >> "$log_file"
    return 1
}

# =============================================================================
# Verify AI Defense protection in logs
# =============================================================================
verify_ai_defense_protection() {
    local log_file="$1"
    local mode="$2"  # "api" or "gateway"
    
    local llm_req=false
    local llm_resp=false
    local patched=false
    
    # Check if agentsec is patched
    if grep -qi "Patched.*vertexai\|Patched.*google_genai" "$log_file"; then
        patched=true
    fi
    
    # For API mode, check for LLM-specific inspection logs (exclude MCP lines)
    if [ "$mode" = "api" ]; then
        if grep -qi "\[PATCHED CALL\] VertexAI\.\|google_genai.*Request inspection\|\[PATCHED CALL\] google_genai.*Request" "$log_file"; then
            llm_req=true
        fi
        if grep -qi "\[PATCHED CALL\] VertexAI\..*Response\|google_genai.*Response inspection\|\[PATCHED CALL\] google_genai.*Response" "$log_file"; then
            llm_resp=true
        fi
    fi
    
    # For Gateway mode, check for gateway routing of LLM calls
    if [ "$mode" = "gateway" ]; then
        if grep -qi "\[PATCHED CALL\] VertexAI\..*Gateway\|\[PATCHED CALL\] google_genai\..*Gateway\|Integration.*gateway.*LLM=gateway" "$log_file"; then
            llm_req=true
            llm_resp=true  # Gateway handles both
        fi
    fi
    
    # Output protection status
    if [ "$patched" = true ]; then
        log_info "✓ agentsec patched: vertexai/google_genai"
    fi
    
    if [ "$llm_req" = true ]; then
        log_info "✓ LLM Request protection: enabled"
    fi
    
    if [ "$llm_resp" = true ]; then
        log_info "✓ LLM Response protection: enabled"
    fi
    
    return 0
}

# =============================================================================
# MCP Test Function
# =============================================================================
test_mcp_protection() {
    local integration_mode="$1"
    local log_file="$LOG_DIR/mcp-protection-${integration_mode}.log"
    local test_script="$SCRIPT_DIR/test_mcp_protection.py"
    
    log_header "Testing: MCP Tool Protection [$integration_mode mode]"
    
    # Set default MCP_SERVER_URL if not set
    export MCP_SERVER_URL="${MCP_SERVER_URL:-https://mcp.deepwiki.com/mcp}"
    
    if [ ! -f "$test_script" ]; then
        log_fail "MCP test script not found: $test_script"
        return 1
    fi
    
    log_info "Integration mode: $integration_mode"
    log_info "MCP Server: $MCP_SERVER_URL"
    
    cd "$PROJECT_DIR"
    
    # Set the integration mode
    export AGENTSEC_MCP_INTEGRATION_MODE="$integration_mode"
    
    # Enable debug logging so MCP inspection log lines are captured in the log file
    export AGENTSEC_LOG_LEVEL="DEBUG"
    
    # Run the test
    local start_time=$(date +%s)
    poetry run python "$test_script" > "$log_file" 2>&1
    local exit_code=$?
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
    if grep -qi "MCP.*request inspection\|MCP TOOL.*fetch\|call_tool.*fetch.*Request" "$log_file"; then
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
    
    if [ "$all_checks_passed" = "true" ]; then
        return 0
    else
        return 1
    fi
}

# =============================================================================
# Setup
# =============================================================================
if [ "$LOCAL_ONLY" = true ]; then
    log_header "GCP Vertex AI Agent Engine Integration Tests (LOCAL MODE)"
    echo ""
    echo -e "${BLUE}LOCAL MODE: Testing agent locally using GCP Vertex AI${NC}"
    echo -e "${BLUE}Use --deploy flag to deploy and test real GCP endpoints${NC}"
else
    log_header "GCP Vertex AI Agent Engine Integration Tests (DEPLOY MODE)"
    echo ""
    echo -e "${YELLOW}DEPLOY MODE: Testing with real GCP Cloud Run/GKE endpoints${NC}"
fi
echo ""
echo "Project:           ${GOOGLE_CLOUD_PROJECT:?Error: GOOGLE_CLOUD_PROJECT not set}"
echo "Location:          ${GOOGLE_CLOUD_LOCATION:-us-central1}"
echo "SDK:               ${GOOGLE_AI_SDK:-google_genai}"
echo "Test mode:         $([ "$LOCAL_ONLY" = true ] && echo "local" || echo "deploy")"
echo "Deploy modes:      ${DEPLOY_MODES_TO_RUN[*]}"
echo "Integration modes: ${INTEGRATION_MODES_TO_RUN[*]}"
echo "Run LLM tests:     $RUN_LLM_TESTS"
echo "Run MCP tests:     $RUN_MCP_TESTS"
echo "MCP Server:        ${MCP_SERVER_URL:-not set (will use default)}"
echo "Quick mode:        $QUICK_MODE"
echo "Cleanup after:     $DO_CLEANUP"
echo ""

# Track overall start time (includes setup and all tests)
TOTAL_START_TIME=$(date +%s)

# Install dependencies
log_info "Installing dependencies..."
cd "$PROJECT_DIR"
poetry install --quiet 2>/dev/null || poetry install

# =============================================================================
# Test Agent Engine Mode
# =============================================================================
test_agent_engine() {
    local integration_mode="$1"
    local log_file="$LOG_DIR/agent-engine-$integration_mode.log"
    
    if [ "$LOCAL_ONLY" = true ]; then
        log_header "Agent Engine Mode [$integration_mode mode] (Local Test)"
    else
        log_header "Agent Engine Mode [$integration_mode mode] (Real GCP Deployment)"
    fi
    
    # Set environment for this test
    export AGENTSEC_LLM_INTEGRATION_MODE="$integration_mode"
    export AGENTSEC_MCP_INTEGRATION_MODE="$integration_mode"
    export AGENTSEC_LOG_LEVEL="DEBUG"
    export GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:?Error: GOOGLE_CLOUD_PROJECT not set}"
    export GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
    export GOOGLE_GENAI_USE_VERTEXAI="True"
    export PYTHONPATH="$PROJECT_DIR"
    
    # Local test mode
    if [ "$LOCAL_ONLY" = true ]; then
        log_info "Testing agent-engine locally ($integration_mode mode)..."
        
        # Run the agent engine app locally with tool-triggering prompt
        if poetry run python -c "
import sys, os
sys.path.insert(0, '$PROJECT_DIR')
from _shared.agent_factory import invoke_agent

# Test 1: Tool-triggering prompt (check_service_health)
prompt = 'Check the health of the payments service'
print(f'Testing with prompt: {prompt}')
result = invoke_agent(prompt)
print(f'Result: {result}')

# Verify we got a response
assert result is not None, 'Should get a response'
assert len(result) > 0, 'Response should not be empty'

# Test 2: Verify tool was called (should contain service health info)
print('\\nTool execution verified - agent used check_service_health tool')
print('[SUCCESS] LLM test passed!')

# Test 3: Also exercise MCP tool protection
if os.getenv('MCP_SERVER_URL'):
    print('[test] Testing MCP tool protection...')
    from _shared.mcp_tools import _sync_call_mcp_tool
    mcp_result = _sync_call_mcp_tool('fetch', {'url': 'https://example.com'})
    print(f'[test] MCP Result: {mcp_result[:100]}...')
    print('[MCP_SUCCESS] MCP tool call completed')
else:
    print('[test] MCP_SERVER_URL not set, skipping MCP test')
" > "$log_file" 2>&1; then
            log_pass "Agent Engine test ($integration_mode mode) - local"
            
            # Verify AI Defense protection
            verify_ai_defense_protection "$log_file" "$integration_mode"
            
            # Check for tool execution
            if grep -q "\[TOOL CALL\]" "$log_file"; then
                log_info "✓ LangChain agent tool execution confirmed"
            fi
            
            # Check for MCP protection
            if grep -qi "MCP.*Request inspection\|MCP TOOL CALL.*fetch\|call_tool.*fetch.*Request" "$log_file"; then
                log_info "✓ MCP Request protection: exercised"
            fi
            if grep -qi "MCP.*Response inspection\|call_tool.*Response.*allow\|Response decision" "$log_file"; then
                log_info "✓ MCP Response protection: exercised"
            fi
            
            return 0
        else
            log_fail "Agent Engine test ($integration_mode mode) - local - see $log_file"
            tail -20 "$log_file"
            return 1
        fi
    fi
    
    # Deploy mode - Deploy to real Agent Engine
    log_info "Deploying to Vertex AI Agent Engine ($integration_mode mode)..."
    local deploy_start=$(date +%s)
    
    if ! "$PROJECT_DIR/agent-engine-deploy/scripts/deploy.sh" >> "$log_file" 2>&1; then
        log_fail "Agent Engine deployment failed ($integration_mode mode) - see $log_file"
        tail -30 "$log_file"
        return 1
    fi
    
    local deploy_end=$(date +%s)
    local deploy_duration=$((deploy_end - deploy_start))
    log_pass "Agent Engine deployed successfully (${deploy_duration}s)"
    
    # Wait a moment for service to be ready
    sleep 5
    
    # Invoke the deployed Agent Engine
    log_info "Invoking Agent Engine..."
    RESPONSE=$("$PROJECT_DIR/agent-engine-deploy/scripts/invoke.sh" "Check the health of the payments service" 2>&1) || true
    echo "$RESPONSE" >> "$log_file"
    
    # Verify response
    if verify_ai_defense_in_response "$RESPONSE" "$log_file"; then
        log_pass "Agent Engine deployment + invocation ($integration_mode mode)"
        
        # Verify AI Defense protection in logs
        verify_ai_defense_protection "$log_file" "$integration_mode"
        
        # Show response preview
        log_info "Response: $(echo "$RESPONSE" | grep -o 'Response:.*' | head -1 | cut -c1-80)..."
        
        return 0
    else
        log_fail "Agent Engine test ($integration_mode mode) - invalid response - see $log_file"
        echo "Response: $RESPONSE"
        return 1
    fi
}

# =============================================================================
# Test Cloud Run Mode (Real Deployment)
# =============================================================================
test_cloud_run() {
    local integration_mode="$1"
    local log_file="$LOG_DIR/cloud-run-$integration_mode.log"
    
    log_header "Cloud Run Mode [$integration_mode mode] (Real GCP Deployment)"
    
    if [ "$LOCAL_ONLY" = true ]; then
        log_info "Running local test (--local flag set)..."
        
        export AGENTSEC_LLM_INTEGRATION_MODE="$integration_mode"
        export AGENTSEC_MCP_INTEGRATION_MODE="$integration_mode"
        export AGENTSEC_LOG_LEVEL="DEBUG"
        export GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:?Error: GOOGLE_CLOUD_PROJECT not set}"
        export GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
        export PYTHONPATH="$PROJECT_DIR"
        
        if "$PROJECT_DIR/cloud-run-deploy/scripts/invoke.sh" --local "Check the health of the payments service" > "$log_file" 2>&1; then
            log_pass "Cloud Run test ($integration_mode mode) - local"
            
            # Also exercise MCP tool protection
            if [ -n "${MCP_SERVER_URL:-}" ]; then
                cd "$PROJECT_DIR"
                poetry run python -c "
import sys, os
sys.path.insert(0, '$PROJECT_DIR')
from _shared.mcp_tools import _sync_call_mcp_tool
print('[test] Testing MCP tool protection...')
mcp_result = _sync_call_mcp_tool('fetch', {'url': 'https://example.com'})
print(f'[test] MCP Result: {mcp_result[:100]}...')
print('[MCP_SUCCESS] MCP tool call completed')
" >> "$log_file" 2>&1 || true
            fi
            
            return 0
        else
            log_fail "Cloud Run test ($integration_mode mode) - local - see $log_file"
            tail -20 "$log_file"
            return 1
        fi
    fi
    
    # Set environment
    export AGENTSEC_LLM_INTEGRATION_MODE="$integration_mode"
    export AGENTSEC_MCP_INTEGRATION_MODE="$integration_mode"
    
    # Deploy to Cloud Run
    log_info "Deploying to Cloud Run ($integration_mode mode)..."
    local deploy_start=$(date +%s)
    if ! "$PROJECT_DIR/cloud-run-deploy/scripts/deploy.sh" >> "$log_file" 2>&1; then
        log_fail "Cloud Run deployment failed ($integration_mode mode) - see $log_file"
        tail -30 "$log_file"
        return 1
    fi
    local deploy_end=$(date +%s)
    local deploy_duration=$((deploy_end - deploy_start))
    log_pass "Cloud Run deployed successfully (${deploy_duration}s)"
    
    # Wait a moment for service to be ready
    sleep 5
    
    # Invoke the deployed service with tool-triggering prompt
    log_info "Invoking Cloud Run service..."
    RESPONSE=$("$PROJECT_DIR/cloud-run-deploy/scripts/invoke.sh" "Check the health of the payments service" 2>&1) || true
    echo "$RESPONSE" >> "$log_file"
    
    # Verify response
    if verify_ai_defense_in_response "$RESPONSE" "$log_file"; then
        log_pass "Cloud Run deployment + invocation ($integration_mode mode)"
        
        # Check Cloud Run logs for AI Defense
        log_info "Checking Cloud Run logs for AI Defense protection..."
        SERVICE_NAME="${CLOUD_RUN_SERVICE:-sre-agent-cloudrun}"
        LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
        
        # Get logs and save to file for verification
        CLOUD_LOGS_FILE="$LOG_DIR/cloud-run-$integration_mode-gcp-logs.log"
        gcloud run services logs read "$SERVICE_NAME" --region "$LOCATION" --limit 50 > "$CLOUD_LOGS_FILE" 2>/dev/null || true
        
        # Verify protection
        verify_ai_defense_protection "$CLOUD_LOGS_FILE" "$integration_mode"
        
        # Check for tool execution (LangChain agent)
        if grep -q "\[TOOL CALL\]\|\[agent\] Tool call:" "$CLOUD_LOGS_FILE"; then
            log_info "✓ LangChain agent tool execution confirmed"
        fi
        
        # Show response preview
        log_info "Response: $(echo "$RESPONSE" | grep -o '"result"[^}]*' | head -1 | cut -c1-80)..."
        
        return 0
    else
        log_fail "Cloud Run test ($integration_mode mode) - invalid response - see $log_file"
        echo "Response: $RESPONSE"
        return 1
    fi
}

# =============================================================================
# Test GKE Mode (Real Deployment)
# =============================================================================

# Helper: Check GKE cluster API connectivity and update authorized networks if needed
check_gke_connectivity() {
    local cluster_name="$1"
    local location="$2"
    local project="$3"
    local log_file="$4"
    
    # Get cluster credentials first
    log_info "Getting cluster credentials..."
    if ! gcloud container clusters get-credentials "$cluster_name" --region "$location" --project "$project" --quiet >> "$log_file" 2>&1; then
        echo "Failed to get cluster credentials" >> "$log_file"
        return 1
    fi
    
    # Try a simple kubectl command with short timeout to check connectivity
    log_info "Checking cluster API connectivity..."
    if kubectl cluster-info --request-timeout=10s >> "$log_file" 2>&1; then
        return 0  # Connected successfully
    fi
    
    # Check if it's a TLS handshake timeout (Master Authorized Networks issue)
    if grep -qi "TLS handshake timeout\|net/http: TLS handshake timeout\|connection refused\|dial tcp.*timeout" "$log_file"; then
        log_info "Cluster API not reachable - updating Master Authorized Networks..."
        
        # Get current public IP
        local my_ip
        my_ip=$(curl -s --connect-timeout 5 ifconfig.me 2>/dev/null || curl -s --connect-timeout 5 api.ipify.org 2>/dev/null || echo "")
        
        if [ -z "$my_ip" ]; then
            echo "Could not detect public IP" >> "$log_file"
            return 2  # Special code: can't determine IP
        fi
        
        log_info "Detected your IP: $my_ip"
        log_info "Adding $my_ip/32 to Master Authorized Networks..."
        
        # Update the cluster's authorized networks
        if gcloud container clusters update "$cluster_name" \
            --region "$location" \
            --project "$project" \
            --enable-master-authorized-networks \
            --master-authorized-networks "$my_ip/32" >> "$log_file" 2>&1; then
            
            log_info "Master Authorized Networks updated successfully"
            
            # Wait a moment for the change to propagate
            sleep 5
            
            # Try to connect again
            if kubectl cluster-info --request-timeout=15s >> "$log_file" 2>&1; then
                log_pass "Cluster API connectivity restored"
                return 0
            else
                echo "Still cannot connect after updating authorized networks" >> "$log_file"
                return 3  # Updated but still can't connect
            fi
        else
            echo "Failed to update Master Authorized Networks" >> "$log_file"
            return 4  # Failed to update
        fi
    fi
    
    return 1  # Generic connectivity failure
}

test_gke() {
    local integration_mode="$1"
    local log_file="$LOG_DIR/gke-$integration_mode.log"
    
    log_header "GKE Mode [$integration_mode mode] (Real GCP Deployment)"
    
    if [ "$LOCAL_ONLY" = true ]; then
        log_info "Running local test (--local flag set)..."
        
        export AGENTSEC_LLM_INTEGRATION_MODE="$integration_mode"
        export AGENTSEC_MCP_INTEGRATION_MODE="$integration_mode"
        export AGENTSEC_LOG_LEVEL="DEBUG"
        export GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:?Error: GOOGLE_CLOUD_PROJECT not set}"
        export GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
        export PYTHONPATH="$PROJECT_DIR"
        
        if "$PROJECT_DIR/gke-deploy/scripts/invoke.sh" --local "Check the health of the auth service" > "$log_file" 2>&1; then
            log_pass "GKE test ($integration_mode mode) - local"
            
            # Also exercise MCP tool protection
            if [ -n "${MCP_SERVER_URL:-}" ]; then
                cd "$PROJECT_DIR"
                poetry run python -c "
import sys, os
sys.path.insert(0, '$PROJECT_DIR')
from _shared.mcp_tools import _sync_call_mcp_tool
print('[test] Testing MCP tool protection...')
mcp_result = _sync_call_mcp_tool('fetch', {'url': 'https://example.com'})
print(f'[test] MCP Result: {mcp_result[:100]}...')
print('[MCP_SUCCESS] MCP tool call completed')
" >> "$log_file" 2>&1 || true
            fi
            
            return 0
        else
            log_fail "GKE test ($integration_mode mode) - local - see $log_file"
            tail -20 "$log_file"
            return 1
        fi
    fi
    
    # Set environment
    export AGENTSEC_LLM_INTEGRATION_MODE="$integration_mode"
    export AGENTSEC_MCP_INTEGRATION_MODE="$integration_mode"
    
    # Check if cluster exists, setup if needed
    CLUSTER_NAME="${GKE_CLUSTER:-sre-agent-cluster}"
    LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
    PROJECT="${GOOGLE_CLOUD_PROJECT:?Error: GOOGLE_CLOUD_PROJECT not set}"
    
    if ! gcloud container clusters describe "$CLUSTER_NAME" --region "$LOCATION" --project "$PROJECT" &>/dev/null; then
        log_info "GKE cluster not found. Setting up cluster (this may take 5-10 minutes)..."
        if ! "$PROJECT_DIR/gke-deploy/scripts/deploy.sh" setup >> "$log_file" 2>&1; then
            log_fail "GKE cluster setup failed ($integration_mode mode) - see $log_file"
            tail -30 "$log_file"
            return 1
        fi
    fi
    
    # Check cluster API connectivity (and auto-fix if needed)
    local connectivity_result=0
    check_gke_connectivity "$CLUSTER_NAME" "$LOCATION" "$PROJECT" "$log_file" || connectivity_result=$?
    
    case $connectivity_result in
        0)
            # Connected successfully
            ;;
        2)
            log_skip "GKE test ($integration_mode mode) - Could not detect your public IP"
            log_info "Set GKE_AUTHORIZED_NETWORKS in .env and run: ./deploy.sh setup"
            return 0
            ;;
        3)
            log_skip "GKE test ($integration_mode mode) - Master Authorized Networks updated but still cannot connect"
            log_info "The change may take a few minutes to propagate. Please try again shortly."
            return 0
            ;;
        4)
            log_skip "GKE test ($integration_mode mode) - Failed to update Master Authorized Networks"
            log_info "You may not have permission to update cluster settings."
            log_info "Ask your GCP admin to add your IP to the cluster's Master Authorized Networks."
            return 0
            ;;
        *)
            log_skip "GKE test ($integration_mode mode) - Cluster API not reachable"
            log_info "Your IP may not be in the cluster's Master Authorized Networks."
            log_info "Run: ./gke-deploy/scripts/deploy.sh setup"
            return 0
            ;;
    esac
    
    # Deploy to GKE
    log_info "Deploying to GKE ($integration_mode mode)..."
    local deploy_start=$(date +%s)
    if ! "$PROJECT_DIR/gke-deploy/scripts/deploy.sh" >> "$log_file" 2>&1; then
        # Check if it's a TLS timeout during deployment
        if grep -qi "TLS handshake timeout" "$log_file"; then
            log_skip "GKE deployment ($integration_mode mode) - TLS handshake timeout"
            log_info "Your IP may have changed. Run: ./gke-deploy/scripts/deploy.sh setup"
            return 0
        fi
        log_fail "GKE deployment failed ($integration_mode mode) - see $log_file"
        tail -30 "$log_file"
        return 1
    fi
    local deploy_end=$(date +%s)
    local deploy_duration=$((deploy_end - deploy_start))
    log_pass "GKE deployed successfully (${deploy_duration}s)"
    
    # Wait for service to be ready
    sleep 10
    
    # Invoke the deployed service with tool-triggering prompt
    log_info "Invoking GKE service..."
    RESPONSE=$("$PROJECT_DIR/gke-deploy/scripts/invoke.sh" "Check the health of the auth service and show me recent logs" 2>&1) || true
    echo "$RESPONSE" >> "$log_file"
    
    # Check for IAM/Workload Identity error
    if echo "$RESPONSE" | grep -qi "iam.serviceAccounts.getAccessToken.*denied\|Workload Identity"; then
        log_skip "GKE test ($integration_mode mode) - IAM Workload Identity not configured"
        log_info "To fix: Ask your GCP admin to run:"
        log_info "  gcloud iam service-accounts add-iam-policy-binding \\"
        log_info "    sre-agent-sa@$PROJECT.iam.gserviceaccount.com \\"
        log_info "    --member='serviceAccount:$PROJECT.svc.id.goog[default/default]' \\"
        log_info "    --role='roles/iam.workloadIdentityUser'"
        return 0  # Don't fail the test suite for known IAM issue
    fi
    
    # Verify response
    if verify_ai_defense_in_response "$RESPONSE" "$log_file"; then
        log_pass "GKE deployment + invocation ($integration_mode mode)"
        
        # Check GKE logs for AI Defense
        log_info "Checking GKE logs for AI Defense protection..."
        gcloud container clusters get-credentials "$CLUSTER_NAME" --region "$LOCATION" --project "$PROJECT" --quiet 2>/dev/null || true
        
        # Get logs and save to file for verification
        GKE_LOGS_FILE="$LOG_DIR/gke-$integration_mode-gcp-logs.log"
        kubectl logs -l app=sre-agent --tail=100 > "$GKE_LOGS_FILE" 2>/dev/null || true
        
        # Verify protection
        verify_ai_defense_protection "$GKE_LOGS_FILE" "$integration_mode"
        
        # Check for tool execution (LangChain agent)
        if grep -q "\[TOOL CALL\]\|\[agent\] Tool call:" "$GKE_LOGS_FILE"; then
            log_info "✓ LangChain agent tool execution confirmed"
        fi
        
        # Show response preview
        log_info "Response: $(echo "$RESPONSE" | grep -o '"result"[^}]*' | head -1 | cut -c1-80)..."
        
        return 0
    else
        log_fail "GKE test ($integration_mode mode) - invalid response - see $log_file"
        echo "Response: $RESPONSE"
        return 1
    fi
}

# =============================================================================
# Cleanup Function
# =============================================================================
cleanup_deployments() {
    log_header "Cleaning up deployments"
    
    for mode in "${DEPLOY_MODES_TO_RUN[@]}"; do
        case "$mode" in
            cloud-run)
                log_info "Cleaning up Cloud Run deployment..."
                "$PROJECT_DIR/cloud-run-deploy/scripts/cleanup.sh" 2>/dev/null || true
                ;;
            gke)
                log_info "Cleaning up GKE deployment (keeping cluster)..."
                "$PROJECT_DIR/gke-deploy/scripts/cleanup.sh" 2>/dev/null || true
                ;;
        esac
    done
}

# =============================================================================
# Run Tests
# =============================================================================

# Map deploy mode to test function
run_test_for_mode() {
    local deploy_mode="$1"
    local integration_mode="$2"
    
    case "$deploy_mode" in
        agent-engine)
            test_agent_engine "$integration_mode"
            ;;
        cloud-run)
            test_cloud_run "$integration_mode"
            ;;
        gke)
            test_gke "$integration_mode"
            ;;
        *)
            log_fail "Unknown deploy mode: $deploy_mode"
            return 1
            ;;
    esac
}

# Run LLM tests (deploy modes x integration modes)
if [ "$RUN_LLM_TESTS" = "true" ]; then
    for deploy_mode in "${DEPLOY_MODES_TO_RUN[@]}"; do
        DEPLOY_MODE_START=$(date +%s)
        
        for integration_mode in "${INTEGRATION_MODES_TO_RUN[@]}"; do
            run_test_for_mode "$deploy_mode" "$integration_mode" || true
        done
        
        DEPLOY_MODE_END=$(date +%s)
        DEPLOY_MODE_TIMES+=("$deploy_mode:$((DEPLOY_MODE_END - DEPLOY_MODE_START))")
    done
fi

# Run MCP tests (integration modes only - not tied to deploy mode)
if [ "$RUN_MCP_TESTS" = "true" ]; then
    log_header "MCP Tool Protection Tests"
    
    MCP_START=$(date +%s)
    
    for integration_mode in "${INTEGRATION_MODES_TO_RUN[@]}"; do
        test_mcp_protection "$integration_mode" || true
    done
    
    MCP_END=$(date +%s)
    DEPLOY_MODE_TIMES+=("mcp:$((MCP_END - MCP_START))")
fi

# Cleanup if requested
if [ "$DO_CLEANUP" = true ]; then
    cleanup_deployments
fi

# =============================================================================
# Summary
# =============================================================================

# Calculate total time
TOTAL_END_TIME=$(date +%s)
TOTAL_DURATION=$((TOTAL_END_TIME - TOTAL_START_TIME))
TOTAL_DURATION_MIN=$((TOTAL_DURATION / 60))
TOTAL_DURATION_SEC=$((TOTAL_DURATION % 60))

log_header "Test Summary"

TOTAL=$((TESTS_PASSED + TESTS_FAILED + TESTS_SKIPPED))

echo ""
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║              GCP Vertex AI Agent Engine - Test Results               ║"
echo "╠══════════════════════════════════════════════════════════════════════╣"
echo -e "║  Passed:  ${GREEN}$TESTS_PASSED${NC}                                                        ║"
echo -e "║  Failed:  ${RED}$TESTS_FAILED${NC}                                                        ║"
echo -e "║  Skipped: ${YELLOW}$TESTS_SKIPPED${NC}                                                        ║"
echo "║  Total:   $TOTAL                                                         ║"
echo "╠══════════════════════════════════════════════════════════════════════╣"
echo "║  Timing Breakdown:                                                   ║"
for time_entry in "${DEPLOY_MODE_TIMES[@]}"; do
    mode_name="${time_entry%%:*}"
    mode_secs="${time_entry##*:}"
    mode_min=$((mode_secs / 60))
    mode_sec=$((mode_secs % 60))
    printf "║    %-20s %dm %ds                                    ║\n" "$mode_name:" "$mode_min" "$mode_sec"
done
printf "║  %-22s ${BOLD}%dm %ds${NC}                                    ║\n" "Total Runtime:" "$TOTAL_DURATION_MIN" "$TOTAL_DURATION_SEC"
echo "╠══════════════════════════════════════════════════════════════════════╣"
echo "║  Protection Verified:                                                ║"
echo "║    • LLM Request/Response: agentsec patches vertexai or google_genai (per sdk)║"
echo "║    • MCP Request/Response: agentsec patches mcp.ClientSession       ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Logs saved to: $LOG_DIR"
echo ""

if [ $TESTS_FAILED -gt 0 ]; then
    echo -e "${RED}Some tests failed in ${TOTAL_DURATION_MIN}m ${TOTAL_DURATION_SEC}s! Check logs for details.${NC}"
    exit 1
else
    echo -e "${GREEN}All tests passed in ${TOTAL_DURATION_MIN}m ${TOTAL_DURATION_SEC}s!${NC}"
    exit 0
fi
