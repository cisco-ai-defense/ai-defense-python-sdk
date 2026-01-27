#!/bin/bash
# =============================================================================
# Run All Agent Integration Tests
# =============================================================================
# Runs tests/integration/test-all-providers.sh for each agent framework
# Tests run in BOTH API mode and Gateway mode by default.
# 
# Usage:
#   ./run-all-integration-tests.sh           # Run all frameworks, all providers, both modes
#   ./run-all-integration-tests.sh --quick   # Run all frameworks, openai only, both modes
#   ./run-all-integration-tests.sh --verbose # Verbose: show Cisco API requests/responses
#   ./run-all-integration-tests.sh --api     # API mode only
#   ./run-all-integration-tests.sh --gateway # Gateway mode only
#   ./run-all-integration-tests.sh langgraph # Run only langgraph framework
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

# All agent frameworks
ALL_FRAMEWORKS=("langgraph-agent" "langchain-agent" "openai-agent" "autogen-agent" "crewai-agent" "strands-agent")

# Provider counts per framework (function for bash/zsh compatibility)
get_provider_count() {
    case "$1" in
        langgraph-agent) echo 4 ;;
        langchain-agent) echo 4 ;;
        openai-agent) echo 2 ;;
        autogen-agent) echo 4 ;;
        crewai-agent) echo 4 ;;
        strands-agent) echo 4 ;;
        *) echo 1 ;;
    esac
}

# Estimated time per provider (seconds)
EST_TIME_PER_PROVIDER=25

# Parse arguments
VERBOSE=""
QUICK=""
MODE_ARG=""
FRAMEWORKS_TO_RUN=()

while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            echo "Usage: $0 [OPTIONS] [FRAMEWORKS...]"
            echo ""
            echo "Options:"
            echo "  --verbose, -v    Show detailed output including Cisco API requests/responses"
            echo "  --quick, -q      Quick mode: only test openai provider"
            echo "  --api            Test API mode only (default: both modes)"
            echo "  --gateway        Test Gateway mode only (default: both modes)"
            echo "  --help, -h       Show this help"
            echo ""
            echo "Frameworks (default: all):"
            echo "  langgraph        LangGraph agent"
            echo "  langchain        LangChain agent (LCEL + tool calling)"
            echo "  openai           OpenAI Agents SDK"
            echo "  autogen          AutoGen agent"
            echo "  crewai           CrewAI agent"
            echo "  strands          Strands agent"
            echo ""
            echo "Examples:"
            echo "  $0                      # Run all frameworks, all providers, both modes"
            echo "  $0 --quick              # Run all frameworks, openai only, both modes"
            echo "  $0 --api                # Run all frameworks in API mode only"
            echo "  $0 --gateway --verbose  # Gateway mode with Cisco API details"
            echo "  $0 langgraph strands    # Run only langgraph and strands"
            exit 0
            ;;
        --verbose|-v)
            VERBOSE="--verbose"
            shift
            ;;
        --quick|-q)
            QUICK="openai"
            shift
            ;;
        --api)
            MODE_ARG="--api"
            shift
            ;;
        --gateway)
            MODE_ARG="--gateway"
            shift
            ;;
        langgraph)
            FRAMEWORKS_TO_RUN+=("langgraph-agent")
            shift
            ;;
        langchain)
            FRAMEWORKS_TO_RUN+=("langchain-agent")
            shift
            ;;
        openai)
            FRAMEWORKS_TO_RUN+=("openai-agent")
            shift
            ;;
        autogen)
            FRAMEWORKS_TO_RUN+=("autogen-agent")
            shift
            ;;
        crewai)
            FRAMEWORKS_TO_RUN+=("crewai-agent")
            shift
            ;;
        strands)
            FRAMEWORKS_TO_RUN+=("strands-agent")
            shift
            ;;
        *)
            echo -e "${RED}Unknown argument: $1${NC}"
            exit 1
            ;;
    esac
done

# Default to all frameworks
if [ ${#FRAMEWORKS_TO_RUN[@]} -eq 0 ]; then
    FRAMEWORKS_TO_RUN=("${ALL_FRAMEWORKS[@]}")
fi

# Calculate totals (account for both modes if not specified)
TOTAL_TESTS=0
TOTAL_TIME=0

# Mode multiplier: 2 if both modes, 1 if single mode
if [ -n "$MODE_ARG" ]; then
    MODE_MULTIPLIER=1
else
    MODE_MULTIPLIER=2
fi

for framework in "${FRAMEWORKS_TO_RUN[@]}"; do
    if [ -n "$QUICK" ]; then
        TOTAL_TESTS=$((TOTAL_TESTS + 1 * MODE_MULTIPLIER))
    else
        TOTAL_TESTS=$((TOTAL_TESTS + $(get_provider_count "$framework") * MODE_MULTIPLIER))
    fi
done

TOTAL_TIME=$((TOTAL_TESTS * EST_TIME_PER_PROVIDER))
TOTAL_MINUTES=$((TOTAL_TIME / 60))
TOTAL_SECONDS=$((TOTAL_TIME % 60))

# =============================================================================
# Warning Banner
# =============================================================================
echo ""
echo -e "${BOLD}${BLUE}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${BLUE}║         AGENT INTEGRATION TEST SUITE                             ║${NC}"
echo -e "${BOLD}${BLUE}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}${BOLD}⚠️  WARNING: This will run live integration tests!${NC}"
echo ""
echo -e "   These tests make ${BOLD}real API calls${NC} to:"
echo -e "   • Cisco AI Defense API"
echo -e "   • LLM providers (OpenAI, Azure, Vertex, Bedrock)"
echo -e "   • MCP servers (remote fetch server)"
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Test Plan:${NC}"
echo ""

# Determine modes to show
if [ -n "$MODE_ARG" ]; then
    modes_display=$(echo "$MODE_ARG" | sed 's/--//')
    mode_multiplier=1
else
    modes_display="api, gateway"
    mode_multiplier=2
fi

for framework in "${FRAMEWORKS_TO_RUN[@]}"; do
    if [ -n "$QUICK" ]; then
        providers="openai"
        provider_count=1
    else
        case $framework in
            openai-agent)
                providers="openai, azure"
                provider_count=2
                ;;
            *)
                providers="openai, azure, vertex, bedrock"
                provider_count=4
                ;;
        esac
    fi
    test_count=$((provider_count * mode_multiplier))
    echo -e "   ${GREEN}✓${NC} ${BOLD}$framework${NC}"
    echo -e "     Providers: $providers"
    echo -e "     Modes: $modes_display ($test_count tests)"
done

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Summary:${NC}"
echo -e "   Total frameworks: ${#FRAMEWORKS_TO_RUN[@]}"
echo -e "   Total tests:      $TOTAL_TESTS"
echo -e "   Estimated time:   ${BOLD}~${TOTAL_MINUTES}m ${TOTAL_SECONDS}s${NC}"
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
FRAMEWORK_RESULTS=()

echo ""
echo -e "${BOLD}${BLUE}════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${BLUE}  Running Integration Tests${NC}"
echo -e "${BOLD}${BLUE}════════════════════════════════════════════════════════════════════${NC}"

for framework in "${FRAMEWORKS_TO_RUN[@]}"; do
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  Framework: ${BOLD}$framework${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    FRAMEWORK_DIR="$SCRIPT_DIR/$framework"
    TEST_SCRIPT="$FRAMEWORK_DIR/tests/integration/test-all-providers.sh"
    
    if [ ! -f "$TEST_SCRIPT" ]; then
        echo -e "  ${YELLOW}⊘ SKIP${NC}: Test script not found"
        FRAMEWORK_RESULTS+=("$framework: SKIPPED")
        continue
    fi
    
    # Activate framework venv if exists
    VENV_DIR="$FRAMEWORK_DIR/.venv"
    if [ -d "$VENV_DIR" ]; then
        source "$VENV_DIR/bin/activate"
    fi
    
    # Run tests
    cd "$FRAMEWORK_DIR"
    if bash "$TEST_SCRIPT" $VERBOSE $MODE_ARG $QUICK; then
        FRAMEWORK_RESULTS+=("$framework: ✅ PASSED")
        ((PASSED++))
    else
        FRAMEWORK_RESULTS+=("$framework: ❌ FAILED")
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

for result in "${FRAMEWORK_RESULTS[@]}"; do
    echo -e "   $result"
done

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "   ${GREEN}Passed${NC}:  $PASSED"
echo -e "   ${RED}Failed${NC}:  $FAILED"
echo -e "   Duration: ${DURATION_MIN}m ${DURATION_SEC}s"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}${BOLD}  ✅ ALL INTEGRATION TESTS PASSED!${NC}"
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════════════════${NC}"
    exit 0
else
    echo -e "${RED}${BOLD}═══════════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}${BOLD}  ❌ SOME TESTS FAILED ($FAILED/${#FRAMEWORKS_TO_RUN[@]} frameworks)${NC}"
    echo -e "${RED}${BOLD}═══════════════════════════════════════════════════════════════════${NC}"
    exit 1
fi

