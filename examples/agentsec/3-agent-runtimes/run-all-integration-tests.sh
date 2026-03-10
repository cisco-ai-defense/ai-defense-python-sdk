#!/bin/bash
# =============================================================================
# Run All Agent Runtime Integration Tests
# =============================================================================
# Runs tests/integration/test-all-modes.sh for each agent runtime
# Tests all deployment modes (direct, container, lambda) in BOTH
# Cisco AI Defense integration modes (API + Gateway).
# 
# Test Modes:
#   --local:  Run local tests only (no cloud deployment)
#   --deploy: Deploy to cloud and test real endpoints
#   Default:  --deploy for AgentCore/VertexAI, --local for Microsoft Foundry
# 
# Full test = 3 deploy modes x 2 integration modes = 6 tests per runtime
# 
# Usage:
#   ./run-all-integration-tests.sh             # Default (deploy AWS/GCP, local Azure)
#   ./run-all-integration-tests.sh --local     # Run local tests for all runtimes
#   ./run-all-integration-tests.sh --deploy    # Deploy and test all runtimes
#   ./run-all-integration-tests.sh --quick     # Quick: API mode only (1 test)
#   ./run-all-integration-tests.sh --verbose   # Verbose output
#   ./run-all-integration-tests.sh amazon-bedrock-agentcore  # Run specific runtime
# =============================================================================

set -euo pipefail

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

# All agent runtimes
ALL_RUNTIMES=("amazon-bedrock-agentcore" "gcp-vertex-ai-agent-engine" "microsoft-foundry")

# Test counts per runtime (function to get count - works in bash and zsh)
# Full test = 3 deploy modes x 2 integration modes = 6 tests
get_mode_count() {
    case "$1" in
        amazon-bedrock-agentcore) echo 6 ;;  # 3 deploy (direct, container, lambda) x 2 integration (api, gateway)
        gcp-vertex-ai-agent-engine) echo 6 ;;  # 3 deploy (agent-engine, cloud-run, gke) x 2 integration (api, gateway)
        microsoft-foundry) echo 6 ;;  # 3 deploy (agent-app, azure-functions, container) x 2 integration (api, gateway)
        *) echo 1 ;;
    esac
}

# Estimated time per mode (seconds)
EST_TIME_PER_MODE=60

# Test mode: "default", "local", or "deploy"
# default = --deploy for AgentCore/VertexAI, --local for Foundry
TEST_MODE="default"

# Parse arguments
VERBOSE=""
QUICK=""
RUNTIMES_TO_RUN=()

while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            echo "Usage: $0 [OPTIONS] [RUNTIMES...]"
            echo ""
            echo "Options:"
            echo "  --local          Run LOCAL tests for all runtimes (no cloud deployment)"
            echo "  --deploy         Run DEPLOY tests for all runtimes (deploy to cloud)"
            echo "  --verbose, -v    Show detailed output"
            echo "  --quick, -q      Quick mode: API mode only (1 test per runtime)"
            echo "  --help, -h       Show this help"
            echo ""
            echo "Test Modes:"
            echo "  Default:   --deploy for AgentCore/VertexAI, --local for Foundry"
            echo "  --local:   Run local tests only (requires LLM provider credentials)"
            echo "  --deploy:  Deploy to cloud and test real endpoints"
            echo ""
            echo "Runtimes (default: all):"
            echo "  amazon-bedrock-agentcore     AWS Bedrock AgentCore"
            echo "  gcp-vertex-ai-agent-engine   GCP Vertex AI Agent Engine"
            echo "  microsoft-foundry            Microsoft Azure AI Foundry"
            echo ""
            echo "Examples:"
            echo "  $0                              # Default (deploy AWS/GCP, local Azure)"
            echo "  $0 --local                      # Run local tests for all runtimes"
            echo "  $0 --deploy                     # Deploy and test all runtimes"
            echo "  $0 --quick                      # Quick mode, API only"
            echo "  $0 --verbose                    # Verbose output"
            echo "  $0 amazon-bedrock-agentcore     # Run only amazon-bedrock-agentcore"
            echo "  $0 --local microsoft-foundry    # Run only foundry, local mode"
            exit 0
            ;;
        --local)
            TEST_MODE="local"
            shift
            ;;
        --deploy)
            TEST_MODE="deploy"
            shift
            ;;
        --verbose|-v)
            VERBOSE="--verbose"
            shift
            ;;
        --quick|-q)
            QUICK="--quick"
            shift
            ;;
        amazon-bedrock-agentcore)
            RUNTIMES_TO_RUN+=("amazon-bedrock-agentcore")
            shift
            ;;
        gcp-vertex-ai-agent-engine)
            RUNTIMES_TO_RUN+=("gcp-vertex-ai-agent-engine")
            shift
            ;;
        microsoft-foundry)
            RUNTIMES_TO_RUN+=("microsoft-foundry")
            shift
            ;;
        *)
            echo -e "${RED}Unknown argument: $1${NC}"
            exit 1
            ;;
    esac
done

# Default to all runtimes
if [ ${#RUNTIMES_TO_RUN[@]} -eq 0 ]; then
    RUNTIMES_TO_RUN=("${ALL_RUNTIMES[@]}")
fi

# Calculate totals
TOTAL_TESTS=0
TOTAL_TIME=0

for runtime in "${RUNTIMES_TO_RUN[@]}"; do
    if [ -n "$QUICK" ]; then
        TOTAL_TESTS=$((TOTAL_TESTS + 1))
    else
        TOTAL_TESTS=$((TOTAL_TESTS + $(get_mode_count "$runtime")))
    fi
done

TOTAL_TIME=$((TOTAL_TESTS * EST_TIME_PER_MODE))
TOTAL_MINUTES=$((TOTAL_TIME / 60))
TOTAL_SECONDS=$((TOTAL_TIME % 60))

# =============================================================================
# Warning Banner
# =============================================================================
echo ""
echo -e "${BOLD}${BLUE}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${BLUE}║         AGENT RUNTIME INTEGRATION TEST SUITE                     ║${NC}"
echo -e "${BOLD}${BLUE}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Display test mode
case "$TEST_MODE" in
    local)
        echo -e "${BLUE}Test Mode: LOCAL${NC} - Testing locally without cloud deployment"
        echo ""
        echo -e "   These tests make ${BOLD}real API calls${NC} to:"
        echo -e "   • Cisco AI Defense API (API mode)"
        echo -e "   • Cisco AI Defense Gateway (Gateway mode)"
        echo -e "   • AWS Bedrock (direct calls)"
        echo -e "   • GCP Vertex AI (direct calls)"
        echo -e "   • Azure OpenAI (direct calls)"
        ;;
    deploy)
        echo -e "${YELLOW}${BOLD}⚠️  Test Mode: DEPLOY${NC} - Deploying to cloud and testing real endpoints"
        echo ""
        echo -e "   These tests make ${BOLD}real deployments and API calls${NC} to:"
        echo -e "   • Cisco AI Defense API (API mode)"
        echo -e "   • Cisco AI Defense Gateway (Gateway mode)"
        echo -e "   • AWS Bedrock AgentCore, Lambda, Container"
        echo -e "   • GCP Cloud Run / GKE"
        echo -e "   • Azure Functions / Container Apps"
        ;;
    default)
        echo -e "${CYAN}Test Mode: DEFAULT${NC} - Deploy for AWS/GCP, Local for Azure"
        echo ""
        echo -e "   These tests make ${BOLD}real API calls${NC} to:"
        echo -e "   • Cisco AI Defense API (API mode)"
        echo -e "   • Cisco AI Defense Gateway (Gateway mode)"
        echo -e "   • AWS Bedrock AgentCore (deploy)"
        echo -e "   • GCP Cloud Run / GKE (deploy)"
        echo -e "   • Azure OpenAI (local only)"
        ;;
esac
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Test Plan:${NC}"
echo ""

# Function to get the test mode for a runtime
get_runtime_test_mode() {
    local runtime="$1"
    case "$TEST_MODE" in
        local) echo "local" ;;
        deploy) echo "deploy" ;;
        default)
            case "$runtime" in
                amazon-bedrock-agentcore) echo "deploy" ;;
                gcp-vertex-ai-agent-engine) echo "deploy" ;;
                microsoft-foundry) echo "local" ;;
            esac
            ;;
    esac
}

for runtime in "${RUNTIMES_TO_RUN[@]}"; do
    runtime_mode=$(get_runtime_test_mode "$runtime")
    if [ -n "$QUICK" ]; then
        mode_count=1
        case "$runtime" in
            amazon-bedrock-agentcore)
                echo -e "   ${GREEN}✓${NC} ${BOLD}$runtime${NC} [${runtime_mode}]"
                echo -e "     Deploy modes: direct (api only)"
                ;;
            gcp-vertex-ai-agent-engine)
                echo -e "   ${GREEN}✓${NC} ${BOLD}$runtime${NC} [${runtime_mode}]"
                echo -e "     Deploy modes: agent-engine (api only)"
                ;;
            microsoft-foundry)
                echo -e "   ${GREEN}✓${NC} ${BOLD}$runtime${NC} [${runtime_mode}]"
                echo -e "     Deploy modes: foundry-agent-app (api only)"
                ;;
        esac
    else
        mode_count=6
        case "$runtime" in
            amazon-bedrock-agentcore)
                echo -e "   ${GREEN}✓${NC} ${BOLD}$runtime${NC} [${runtime_mode}]"
                echo -e "     Deploy modes: direct, container, lambda"
                echo -e "     Integration modes: api, gateway"
                ;;
            gcp-vertex-ai-agent-engine)
                echo -e "   ${GREEN}✓${NC} ${BOLD}$runtime${NC} [${runtime_mode}]"
                echo -e "     Deploy modes: agent-engine, cloud-run, gke"
                echo -e "     Integration modes: api, gateway"
                ;;
            microsoft-foundry)
                echo -e "   ${GREEN}✓${NC} ${BOLD}$runtime${NC} [${runtime_mode}]"
                echo -e "     Deploy modes: foundry-agent-app, azure-functions, foundry-container"
                echo -e "     Integration modes: api, gateway"
                ;;
        esac
    fi
    echo -e "     Total: $mode_count tests"
done

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Summary:${NC}"
echo -e "   Test mode:      $TEST_MODE"
echo -e "   Total runtimes: ${#RUNTIMES_TO_RUN[@]}"
echo -e "   Total tests:    $TOTAL_TESTS"
echo -e "   Estimated time: ${BOLD}~${TOTAL_MINUTES}m ${TOTAL_SECONDS}s${NC}"
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

PASSED=0
FAILED=0
SKIPPED=0
RUNTIME_RESULTS=()
RUNTIME_TIMES=()  # Track time per runtime

echo ""
echo -e "${BOLD}${BLUE}════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${BLUE}  Running Integration Tests${NC}"
echo -e "${BOLD}${BLUE}════════════════════════════════════════════════════════════════════${NC}"

for runtime in "${RUNTIMES_TO_RUN[@]}"; do
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  Runtime: ${BOLD}$runtime${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    RUNTIME_START=$(date +%s)
    
    RUNTIME_DIR="$SCRIPT_DIR/$runtime"
    TEST_SCRIPT="$RUNTIME_DIR/tests/integration/test-all-modes.sh"
    
    if [ ! -f "$TEST_SCRIPT" ]; then
        echo -e "  ${YELLOW}⊘ SKIP${NC}: Test script not found: $TEST_SCRIPT"
        RUNTIME_RESULTS+=("$runtime: SKIPPED (0s)")
        RUNTIME_TIMES+=("$runtime:0")
        ((SKIPPED++))
        continue
    fi
    
    # Build test arguments based on runtime and test mode
    TEST_ARGS=""
    
    # Add local/deploy flag based on test mode
    runtime_mode=$(get_runtime_test_mode "$runtime")
    if [ "$runtime_mode" = "local" ]; then
        TEST_ARGS="$TEST_ARGS --local"
    else
        TEST_ARGS="$TEST_ARGS --deploy"
    fi
    
    if [ -n "$VERBOSE" ]; then
        TEST_ARGS="$TEST_ARGS --verbose"
    fi
    if [ -n "$QUICK" ]; then
        # Map quick mode to the appropriate args for each runtime
        case "$runtime" in
            amazon-bedrock-agentcore)
                TEST_ARGS="$TEST_ARGS direct --api"
                ;;
            gcp-vertex-ai-agent-engine)
                TEST_ARGS="$TEST_ARGS --quick"  # Uses agent-engine + api mode
                ;;
            microsoft-foundry)
                TEST_ARGS="$TEST_ARGS agent-app --api"  # Uses foundry-agent-app + api mode
                ;;
        esac
    fi
    
    # Run tests
    cd "$RUNTIME_DIR"
    if bash "$TEST_SCRIPT" $TEST_ARGS; then
        RUNTIME_END=$(date +%s)
        RUNTIME_DURATION=$((RUNTIME_END - RUNTIME_START))
        RUNTIME_DURATION_MIN=$((RUNTIME_DURATION / 60))
        RUNTIME_DURATION_SEC=$((RUNTIME_DURATION % 60))
        RUNTIME_RESULTS+=("$runtime: ✅ PASSED (${RUNTIME_DURATION_MIN}m ${RUNTIME_DURATION_SEC}s)")
        RUNTIME_TIMES+=("$runtime:$RUNTIME_DURATION")
        ((PASSED++))
    else
        RUNTIME_END=$(date +%s)
        RUNTIME_DURATION=$((RUNTIME_END - RUNTIME_START))
        RUNTIME_DURATION_MIN=$((RUNTIME_DURATION / 60))
        RUNTIME_DURATION_SEC=$((RUNTIME_DURATION % 60))
        RUNTIME_RESULTS+=("$runtime: ❌ FAILED (${RUNTIME_DURATION_MIN}m ${RUNTIME_DURATION_SEC}s)")
        RUNTIME_TIMES+=("$runtime:$RUNTIME_DURATION")
        ((FAILED++))
    fi
done

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

echo -e "${CYAN}Runtime Results:${NC}"
for result in "${RUNTIME_RESULTS[@]}"; do
    echo -e "   $result"
done

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}Timing Breakdown:${NC}"
for time_entry in "${RUNTIME_TIMES[@]}"; do
    runtime_name="${time_entry%%:*}"
    runtime_secs="${time_entry##*:}"
    runtime_m=$((runtime_secs / 60))
    runtime_s=$((runtime_secs % 60))
    printf "   %-30s %dm %ds\n" "$runtime_name:" "$runtime_m" "$runtime_s"
done
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${CYAN}Test Totals:${NC}"
echo -e "   ${GREEN}Passed${NC}:  $PASSED"
echo -e "   ${RED}Failed${NC}:  $FAILED"
echo -e "   ${YELLOW}Skipped${NC}: $SKIPPED"
echo -e "   ${BOLD}Total Duration: ${DURATION_MIN}m ${DURATION_SEC}s${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ $FAILED -eq 0 ] && [ $((PASSED + SKIPPED)) -gt 0 ]; then
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}${BOLD}  ✅ ALL INTEGRATION TESTS PASSED!${NC}"
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════════════════${NC}"
    exit 0
else
    echo -e "${RED}${BOLD}═══════════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}${BOLD}  ❌ SOME TESTS FAILED ($FAILED/${#RUNTIMES_TO_RUN[@]} runtimes)${NC}"
    echo -e "${RED}${BOLD}═══════════════════════════════════════════════════════════════════${NC}"
    exit 1
fi
