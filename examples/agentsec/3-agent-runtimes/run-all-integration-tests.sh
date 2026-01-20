#!/bin/bash
# =============================================================================
# Run All Agent Runtime Integration Tests
# =============================================================================
# Runs tests/integration/test-all-modes.sh for each agent runtime
# Tests all deployment modes (direct, container, lambda) in BOTH
# Cisco AI Defense integration modes (API + Gateway).
# 
# Full test = 3 deploy modes x 2 integration modes = 6 tests per runtime
# 
# Usage:
#   ./run-all-integration-tests.sh           # Run all runtimes, all modes (6 tests)
#   ./run-all-integration-tests.sh --quick   # Quick: direct deploy, API mode only (1 test)
#   ./run-all-integration-tests.sh --verbose # Verbose output
#   ./run-all-integration-tests.sh amazon-bedrock-agentcore  # Run specific runtime
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

# All agent runtimes
ALL_RUNTIMES=("amazon-bedrock-agentcore" "gcp-vertex-ai-agent-engine")

# Test counts per runtime (function to get count - works in bash and zsh)
# Full test = 3 deploy modes x 2 integration modes = 6 tests
get_mode_count() {
    case "$1" in
        amazon-bedrock-agentcore) echo 6 ;;  # 3 deploy (direct, container, lambda) x 2 integration (api, gateway)
        gcp-vertex-ai-agent-engine) echo 6 ;;  # 3 deploy (agent-engine, cloud-run, gke) x 2 integration (api, gateway)
        *) echo 1 ;;
    esac
}

# Estimated time per mode (seconds)
EST_TIME_PER_MODE=60

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
            echo "  --verbose, -v    Show detailed output"
            echo "  --quick, -q      Quick mode: direct deploy + API mode only (1 test)"
            echo "  --help, -h       Show this help"
            echo ""
            echo "Runtimes (default: all):"
            echo "  amazon-bedrock-agentcore     AWS Bedrock AgentCore"
            echo "  gcp-vertex-ai-agent-engine   GCP Vertex AI Agent Engine"
            echo ""
            echo "Examples:"
            echo "  $0                              # Run all runtimes, all modes"
            echo "  $0 --quick                      # Run all runtimes, direct mode only"
            echo "  $0 --verbose                    # Verbose output"
            echo "  $0 amazon-bedrock-agentcore     # Run only amazon-bedrock-agentcore"
            echo "  $0 gcp-vertex-ai-agent-engine   # Run only gcp-vertex-ai-agent-engine"
            exit 0
            ;;
        --verbose|-v)
            VERBOSE="--verbose"
            shift
            ;;
        --quick|-q)
            QUICK="direct --api"
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
echo -e "${YELLOW}${BOLD}⚠️  WARNING: This will run live integration tests!${NC}"
echo ""
echo -e "   These tests make ${BOLD}real API calls${NC} to:"
echo -e "   • Cisco AI Defense API (API mode)"
echo -e "   • Cisco AI Defense Gateway (Gateway mode)"
echo -e "   • AWS Bedrock (via AgentCore)"
echo -e "   • AWS Lambda (for lambda deploy mode)"
echo -e "   • GCP Vertex AI (via google-genai)"
echo -e "   • GCP Cloud Run / GKE (for container modes)"
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Test Plan:${NC}"
echo ""

for runtime in "${RUNTIMES_TO_RUN[@]}"; do
    if [ -n "$QUICK" ]; then
        mode_count=1
        case "$runtime" in
            amazon-bedrock-agentcore)
                echo -e "   ${GREEN}✓${NC} ${BOLD}$runtime${NC}"
                echo -e "     Deploy modes: direct (api only)"
                ;;
            gcp-vertex-ai-agent-engine)
                echo -e "   ${GREEN}✓${NC} ${BOLD}$runtime${NC}"
                echo -e "     Deploy modes: agent-engine (api only)"
                ;;
        esac
    else
        mode_count=6
        case "$runtime" in
            amazon-bedrock-agentcore)
                echo -e "   ${GREEN}✓${NC} ${BOLD}$runtime${NC}"
                echo -e "     Deploy modes: direct, container, lambda"
                echo -e "     Integration modes: api, gateway"
                ;;
            gcp-vertex-ai-agent-engine)
                echo -e "   ${GREEN}✓${NC} ${BOLD}$runtime${NC}"
                echo -e "     Deploy modes: agent-engine, cloud-run, gke"
                echo -e "     Integration modes: api, gateway"
                ;;
        esac
    fi
    echo -e "     Total: $mode_count tests"
done

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Summary:${NC}"
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

echo ""
echo -e "${BOLD}${BLUE}════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${BLUE}  Running Integration Tests${NC}"
echo -e "${BOLD}${BLUE}════════════════════════════════════════════════════════════════════${NC}"

for runtime in "${RUNTIMES_TO_RUN[@]}"; do
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  Runtime: ${BOLD}$runtime${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    RUNTIME_DIR="$SCRIPT_DIR/$runtime"
    TEST_SCRIPT="$RUNTIME_DIR/tests/integration/test-all-modes.sh"
    
    if [ ! -f "$TEST_SCRIPT" ]; then
        echo -e "  ${YELLOW}⊘ SKIP${NC}: Test script not found: $TEST_SCRIPT"
        RUNTIME_RESULTS+=("$runtime: SKIPPED")
        ((SKIPPED++))
        continue
    fi
    
    # Build test arguments based on runtime
    TEST_ARGS=""
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
        esac
    fi
    
    # Run tests
    cd "$RUNTIME_DIR"
    if bash "$TEST_SCRIPT" $TEST_ARGS; then
        RUNTIME_RESULTS+=("$runtime: ✅ PASSED")
        ((PASSED++))
    else
        RUNTIME_RESULTS+=("$runtime: ❌ FAILED")
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

for result in "${RUNTIME_RESULTS[@]}"; do
    echo -e "   $result"
done

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "   ${GREEN}Passed${NC}:  $PASSED"
echo -e "   ${RED}Failed${NC}:  $FAILED"
echo -e "   ${YELLOW}Skipped${NC}: $SKIPPED"
echo -e "   Duration: ${DURATION_MIN}m ${DURATION_SEC}s"
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
