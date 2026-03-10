#!/bin/bash
#
# Run all integration tests across the project
#
# Usage:
#   ./scripts/run-integration-tests.sh              # Run all integration tests
#   ./scripts/run-integration-tests.sh --simple     # Run only simple examples tests
#   ./scripts/run-integration-tests.sh --agents     # Run only agent framework tests
#   ./scripts/run-integration-tests.sh --runtimes   # Run only agent runtime tests
#   ./scripts/run-integration-tests.sh --api        # Run only API mode tests
#   ./scripts/run-integration-tests.sh --gateway    # Run only Gateway mode tests
#   ./scripts/run-integration-tests.sh strands      # Run specific agent framework tests
#   ./scripts/run-integration-tests.sh amazon-bedrock-agentcore       # Run specific runtime tests
#   ./scripts/run-integration-tests.sh gcp-vertex-ai-agent-engine     # Run specific runtime tests
#   ./scripts/run-integration-tests.sh microsoft-foundry              # Run specific runtime tests
#   ./scripts/run-integration-tests.sh --agents --gateway   # Combine flags
#   ./scripts/run-integration-tests.sh --runtimes --deploy --new-resources  # Unique names (timestamp)
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
RUN_RUNTIMES=true
SPECIFIC_AGENT=""
SPECIFIC_RUNTIME=""
MODE_FLAG=""  # --api or --gateway to pass to test scripts
DEPLOY_FLAG=""  # --deploy to deploy to cloud and test real endpoints
NEW_RESOURCES=false  # --new-resources: append timestamp (YYYYMMDD-HHMMSS) to runtime resource names

while [[ $# -gt 0 ]]; do
    case $1 in
        --simple)
            RUN_AGENTS=false
            RUN_RUNTIMES=false
            shift
            ;;
        --agents)
            RUN_SIMPLE=false
            RUN_RUNTIMES=false
            shift
            ;;
        --runtimes)
            RUN_SIMPLE=false
            RUN_AGENTS=false
            shift
            ;;
        --deploy)
            DEPLOY_FLAG="--deploy"
            shift
            ;;
        --new-resources)
            NEW_RESOURCES=true
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
            RUN_RUNTIMES=false
            SPECIFIC_AGENT="$1-agent"
            shift
            ;;
        amazon-bedrock-agentcore)
            RUN_SIMPLE=false
            RUN_AGENTS=false
            SPECIFIC_RUNTIME="amazon-bedrock-agentcore"
            shift
            ;;
        gcp-vertex-ai-agent-engine)
            RUN_SIMPLE=false
            RUN_AGENTS=false
            SPECIFIC_RUNTIME="gcp-vertex-ai-agent-engine"
            shift
            ;;
        microsoft-foundry)
            RUN_SIMPLE=false
            RUN_AGENTS=false
            SPECIFIC_RUNTIME="microsoft-foundry"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--simple] [--agents] [--runtimes] [--deploy] [--new-resources] [--api] [--gateway] [strands|...|microsoft-foundry]"
            exit 1
            ;;
    esac
done

# When --new-resources: use timestamped names only for runtimes we're actually running;
# merge with existing .last_new_resources_run so single-CSP runs don't overwrite other CSPs' names.
if [ "$NEW_RESOURCES" = true ] && [ "$RUN_RUNTIMES" = true ]; then
    if [ -f "$PROJECT_DIR/examples/agentsec/.env" ]; then
        set -a
        source "$PROJECT_DIR/examples/agentsec/.env"
        set +a
    fi
    # Which runtimes are we running? (only set names for these)
    RUNNING_AWS=false
    RUNNING_GCP=false
    RUNNING_AZURE=false
    if [ -n "$SPECIFIC_RUNTIME" ]; then
        [ "$SPECIFIC_RUNTIME" = "amazon-bedrock-agentcore" ] && RUNNING_AWS=true
        [ "$SPECIFIC_RUNTIME" = "gcp-vertex-ai-agent-engine" ] && RUNNING_GCP=true
        [ "$SPECIFIC_RUNTIME" = "microsoft-foundry" ] && RUNNING_AZURE=true
    else
        RUNNING_AWS=true
        RUNNING_GCP=true
        RUNNING_AZURE=true
    fi
    # Load existing resource names so we preserve names for CSPs we're not running
    LAST_RESOURCES_FILE="$SCRIPT_DIR/.last_new_resources_run"
    if [ -f "$LAST_RESOURCES_FILE" ]; then
        set -a
        source "$LAST_RESOURCES_FILE"
        set +a
    fi
    # Set and export only for runtimes we're running (timestamps only for those CSPs)
    if [ "$RUNNING_AWS" = true ]; then
        RESOURCE_SUFFIX="$(date '+%Y%m%d-%H%M%S')"
        RESOURCE_SUFFIX_AWS="$(date '+%Y%m%d_%H%M%S')"
        export AGENTCORE_DIRECT_AGENT_NAME="${AGENTCORE_DIRECT_AGENT_NAME:-agentcore_sre_direct_${RESOURCE_SUFFIX_AWS}}"
        export AGENTCORE_CONTAINER_AGENT_NAME="${AGENTCORE_CONTAINER_AGENT_NAME:-agentcore_sre_container_${RESOURCE_SUFFIX_AWS}}"
        export FUNCTION_NAME="${FUNCTION_NAME:-agentcore-sre-lambda-${RESOURCE_SUFFIX}}"
    fi
    if [ "$RUNNING_GCP" = true ]; then
        RESOURCE_SUFFIX="${RESOURCE_SUFFIX:-$(date '+%Y%m%d-%H%M%S')}"
        export AGENT_ENGINE_NAME="${AGENT_ENGINE_NAME:-sre-agent-engine-${RESOURCE_SUFFIX}}"
    fi
    if [ "$RUNNING_AZURE" = true ]; then
        RESOURCE_SUFFIX_AZURE="$(date '+%y%m%d%H%M')"
        export AGENT_ENDPOINT_NAME="${AGENT_ENDPOINT_NAME:-foundry-sre-agent-${RESOURCE_SUFFIX_AZURE}}"
        export CONTAINER_ENDPOINT_NAME="${CONTAINER_ENDPOINT_NAME:-foundry-sre-container-${RESOURCE_SUFFIX_AZURE}}"
        export AZURE_FUNCTION_APP_NAME="aid-sre-agent-func-${RESOURCE_SUFFIX_AZURE}"
    fi
    # For file write: use current values (set above or preserved from existing file)
    RESOURCE_SUFFIX="${RESOURCE_SUFFIX:-}"
    RESOURCE_SUFFIX_AWS="${RESOURCE_SUFFIX_AWS:-}"
    RESOURCE_SUFFIX_AZURE="${RESOURCE_SUFFIX_AZURE:-}"
    AGENTCORE_DIRECT_AGENT_NAME="${AGENTCORE_DIRECT_AGENT_NAME:-}"
    AGENTCORE_CONTAINER_AGENT_NAME="${AGENTCORE_CONTAINER_AGENT_NAME:-}"
    FUNCTION_NAME="${FUNCTION_NAME:-}"
    AGENT_ENGINE_NAME="${AGENT_ENGINE_NAME:-}"
    AGENT_ENDPOINT_NAME="${AGENT_ENDPOINT_NAME:-}"
    CONTAINER_ENDPOINT_NAME="${CONTAINER_ENDPOINT_NAME:-}"
    AZURE_FUNCTION_APP_NAME="${AZURE_FUNCTION_APP_NAME:-}"
    # Echo only the CSPs we're running
    echo -e "${BLUE}New resources: ${YELLOW}${RESOURCE_SUFFIX}${NC} (AWS: ${RESOURCE_SUFFIX_AWS}, Azure: ${RESOURCE_SUFFIX_AZURE})"
    [ "$RUNNING_AWS" = true ] && echo -e "  AWS: direct=${AGENTCORE_DIRECT_AGENT_NAME}, container=${AGENTCORE_CONTAINER_AGENT_NAME}, lambda=${FUNCTION_NAME}"
    [ "$RUNNING_GCP" = true ] && echo -e "  GCP: ${AGENT_ENGINE_NAME}"
    [ "$RUNNING_AZURE" = true ] && echo -e "  Azure: agent=${AGENT_ENDPOINT_NAME}, container=${CONTAINER_ENDPOINT_NAME}, func=${AZURE_FUNCTION_APP_NAME}"
    # Persist: merge so only runtimes we ran get updated; others keep previous values from sourced file
    cat > "$LAST_RESOURCES_FILE" << EOF
RESOURCE_SUFFIX=$RESOURCE_SUFFIX
RESOURCE_SUFFIX_AWS=$RESOURCE_SUFFIX_AWS
RESOURCE_SUFFIX_AZURE=$RESOURCE_SUFFIX_AZURE
AGENTCORE_DIRECT_AGENT_NAME=$AGENTCORE_DIRECT_AGENT_NAME
AGENTCORE_CONTAINER_AGENT_NAME=$AGENTCORE_CONTAINER_AGENT_NAME
FUNCTION_NAME=$FUNCTION_NAME
AGENT_ENGINE_NAME=$AGENT_ENGINE_NAME
AGENT_ENDPOINT_NAME=$AGENT_ENDPOINT_NAME
CONTAINER_ENDPOINT_NAME=$CONTAINER_ENDPOINT_NAME
AZURE_FUNCTION_APP_NAME=$AZURE_FUNCTION_APP_NAME
EOF
    echo -e "${BLUE}  Resource names saved to $LAST_RESOURCES_FILE for verification.${NC}"
    echo ""
fi

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
    
    run_test "Simple Examples" "examples/agentsec/1-simple/tests/integration/test-simple-examples.sh" "$DEPLOY_FLAG $MODE_FLAG"
fi

# Run agent examples integration tests
if [ "$RUN_AGENTS" = true ]; then
    echo -e "${BLUE}══════════════════════════════════════════════"
    echo "  Agent Framework Integration Tests"
    echo -e "══════════════════════════════════════════════${NC}"
    echo ""
    
    AGENTS=("strands-agent" "langgraph-agent" "langchain-agent" "crewai-agent" "autogen-agent" "openai-agent")
    
    for agent in "${AGENTS[@]}"; do
        # Skip if specific agent requested and this isn't it
        if [ -n "$SPECIFIC_AGENT" ] && [ "$agent" != "$SPECIFIC_AGENT" ]; then
            continue
        fi
        
        test_script="examples/agentsec/2-agent-frameworks/$agent/tests/integration/test-all-providers.sh"
        if [ -f "$test_script" ]; then
            run_test "$agent" "$test_script" "$DEPLOY_FLAG $MODE_FLAG"
        else
            echo -e "${YELLOW}  ⚠ No integration test found for $agent${NC}"
            echo ""
        fi
    done
fi

# Run agent runtime integration tests
if [ "$RUN_RUNTIMES" = true ]; then
    echo -e "${BLUE}══════════════════════════════════════════════"
    echo "  Agent Runtime Integration Tests"
    echo -e "══════════════════════════════════════════════${NC}"
    echo ""
    
    RUNTIMES=("amazon-bedrock-agentcore" "gcp-vertex-ai-agent-engine" "microsoft-foundry")
    
    for runtime in "${RUNTIMES[@]}"; do
        # Skip if specific runtime requested and this isn't it
        if [ -n "$SPECIFIC_RUNTIME" ] && [ "$runtime" != "$SPECIFIC_RUNTIME" ]; then
            continue
        fi
        
        test_script="examples/agentsec/3-agent-runtimes/$runtime/tests/integration/test-all-modes.sh"
        if [ -f "$test_script" ]; then
            run_test "$runtime" "$test_script" "$DEPLOY_FLAG $MODE_FLAG"
        else
            echo -e "${YELLOW}  ⚠ No integration test found for $runtime${NC}"
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





