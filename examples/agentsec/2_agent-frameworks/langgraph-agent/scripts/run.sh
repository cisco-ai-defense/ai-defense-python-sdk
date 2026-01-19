#!/bin/bash
# =============================================================================
# LangGraph Agent Runner (with auto-setup and multi-provider support)
# =============================================================================
# Usage:
#   ./scripts/run.sh                     # Demo mode (default provider)
#   ./scripts/run.sh "What is the GIL?"  # Single question
#   ./scripts/run.sh --interactive       # Interactive mode
#   ./scripts/run.sh --setup             # Force re-run setup
#
# Provider Selection:
#   ./scripts/run.sh --provider bedrock  # Use Bedrock
#   ./scripts/run.sh --provider azure    # Use Azure OpenAI
#   ./scripts/run.sh --provider vertex   # Use GCP Vertex AI
#   ./scripts/run.sh --provider openai   # Use OpenAI
#
# Shortcuts:
#   ./scripts/run.sh --bedrock           # Same as --provider bedrock
#   ./scripts/run.sh --azure             # Same as --provider azure
#   ./scripts/run.sh --vertex            # Same as --provider vertex
#   ./scripts/run.sh --openai            # Same as --provider openai
#
# Other:
#   ./scripts/run.sh --list-providers    # Show available providers
#   ./scripts/run.sh --test-all          # Test all providers
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script and project directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
AGENTS_DIR="$(cd "$PROJECT_DIR/.." && pwd)"
ENV_FILE="$AGENTS_DIR/../.env"
ENV_EXAMPLE="$AGENTS_DIR/_shared/templates/env-example.txt"
CONFIG_DIR="$PROJECT_DIR/config"

# Default demo question that triggers MCP tool call
DEFAULT_QUESTION="What is the GIL in python/cpython?"

# Available providers
PROVIDERS=("bedrock" "azure" "vertex" "openai")

# =============================================================================
# Helper Functions
# =============================================================================

show_help() {
    echo "Usage: $0 [OPTIONS] [QUESTION]"
    echo ""
    echo "Options:"
    echo "  --provider <name>   Select provider (bedrock, azure, vertex, openai)"
    echo "  --bedrock           Shortcut for --provider bedrock"
    echo "  --azure             Shortcut for --provider azure"
    echo "  --vertex            Shortcut for --provider vertex"
    echo "  --openai            Shortcut for --provider openai"
    echo "  --list-providers    Show available providers"
    echo "  --test-all          Test all providers"
    echo "  --interactive, -i   Interactive mode"
    echo "  --setup             Force re-run setup"
    echo "  --help, -h          Show this help"
    echo ""
    echo "Examples:"
    echo "  $0                              # Demo with default provider"
    echo "  $0 --azure 'Hello'              # Use Azure, ask 'Hello'"
    echo "  $0 --provider vertex -i         # Use Vertex AI, interactive mode"
    echo "  $0 --test-all                   # Test all providers"
}

list_providers() {
    echo "Available providers:"
    echo ""
    for provider in "${PROVIDERS[@]}"; do
        config_file="$CONFIG_DIR/config-${provider}.yaml"
        if [ -f "$config_file" ]; then
            echo -e "  ${GREEN}✓${NC} $provider (config/config-${provider}.yaml)"
        else
            echo -e "  ${RED}✗${NC} $provider (config/config-${provider}.yaml not found)"
        fi
    done
    echo ""
    echo "Usage: $0 --provider <name>"
    echo "   or: $0 --<provider-name>"
}

check_poetry() {
    if ! command -v poetry &> /dev/null; then
        echo -e "${RED}ERROR: Poetry is not installed${NC}"
        echo "Please install Poetry: https://python-poetry.org/docs/#installation"
        echo "  curl -sSL https://install.python-poetry.org | python3 -"
        exit 1
    fi
}

setup_poetry() {
    echo "Installing dependencies with Poetry..."
    
    cd "$PROJECT_DIR"
    poetry install
    
    echo -e "${GREEN}✓ Setup complete${NC}"
}

check_env() {
    if [ ! -f "$ENV_FILE" ]; then
        if [ -f "$ENV_EXAMPLE" ]; then
            echo "Creating .env from template..."
            cp "$ENV_EXAMPLE" "$ENV_FILE"
            echo -e "${YELLOW}⚠ Please edit .env and configure your API keys${NC}"
        else
            echo -e "${YELLOW}⚠ No .env file found. Create one with your API keys.${NC}"
        fi
    fi
}

needs_setup() {
    # Setup needed if poetry.lock doesn't exist
    [ ! -f "$PROJECT_DIR/poetry.lock" ] && return 0
    
    # Setup needed if pyproject.toml is newer than poetry.lock
    if [ "$PROJECT_DIR/pyproject.toml" -nt "$PROJECT_DIR/poetry.lock" ]; then
        return 0
    fi
    
    return 1
}

run_setup() {
    echo "=============================================="
    echo "  LangGraph Agent - Setup"
    echo "=============================================="
    echo ""
    
    check_poetry
    setup_poetry
    check_env
    
    echo ""
    echo -e "${GREEN}Setup complete!${NC}"
    echo ""
}

test_provider() {
    local provider=$1
    local config_file="$CONFIG_DIR/config-${provider}.yaml"
    
    if [ ! -f "$config_file" ]; then
        echo -e "  ${RED}✗${NC} $provider - config file not found"
        return 1
    fi
    
    echo -n "  Testing $provider... "
    
    # Run a quick test
    export CONFIG_FILE="config/config-${provider}.yaml"
    if timeout 30 poetry run python "$PROJECT_DIR/agent.py" "Say hello in one word" 2>/dev/null | grep -q -i "hello\|hi\|hey\|greetings"; then
        echo -e "${GREEN}✓${NC}"
        return 0
    else
        echo -e "${YELLOW}?${NC} (response unclear or timeout)"
        return 0
    fi
}

test_all_providers() {
    echo "=============================================="
    echo "  Testing All Providers"
    echo "=============================================="
    echo ""
    
    cd "$PROJECT_DIR"
    
    local passed=0
    local failed=0
    
    for provider in "${PROVIDERS[@]}"; do
        if test_provider "$provider"; then
            ((passed++))
        else
            ((failed++))
        fi
    done
    
    echo ""
    if [ $failed -eq 0 ]; then
        echo -e "${GREEN}All providers tested successfully!${NC}"
    else
        echo -e "${YELLOW}$passed passed, $failed failed${NC}"
    fi
}

run_agent() {
    cd "$PROJECT_DIR"
    
    # Set CONFIG_FILE if provider specified
    if [ -n "$PROVIDER" ]; then
        export CONFIG_FILE="config/config-${PROVIDER}.yaml"
        echo -e "${BLUE}Using provider: $PROVIDER${NC}"
    fi
    
    if [ "$INTERACTIVE" = "true" ]; then
        # Interactive mode
        poetry run python agent.py
    elif [ -n "$QUESTION" ]; then
        # User-provided question
        poetry run python agent.py "$QUESTION"
    else
        # Demo mode with default question (invokes LLM + MCP tool)
        echo "Running demo with: \"$DEFAULT_QUESTION\""
        echo "(Use --interactive for interactive mode)"
        echo ""
        poetry run python agent.py "$DEFAULT_QUESTION"
    fi
}

# =============================================================================
# Main
# =============================================================================

cd "$PROJECT_DIR"

PROVIDER=""
QUESTION=""
INTERACTIVE="false"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_help
            exit 0
            ;;
        --list-providers)
            list_providers
            exit 0
            ;;
        --test-all)
            if needs_setup; then
                run_setup
            fi
            test_all_providers
            exit 0
            ;;
        --setup)
            run_setup
            exit 0
            ;;
        --provider)
            PROVIDER="$2"
            shift 2
            ;;
        --bedrock)
            PROVIDER="bedrock"
            shift
            ;;
        --azure)
            PROVIDER="azure"
            shift
            ;;
        --vertex)
            PROVIDER="vertex"
            shift
            ;;
        --openai)
            PROVIDER="openai"
            shift
            ;;
        --interactive|-i)
            INTERACTIVE="true"
            shift
            ;;
        *)
            # Assume it's a question
            if [ -z "$QUESTION" ]; then
                QUESTION="$1"
            else
                QUESTION="$QUESTION $1"
            fi
            shift
            ;;
    esac
done

# Validate provider if specified
if [ -n "$PROVIDER" ]; then
    valid=false
    for p in "${PROVIDERS[@]}"; do
        if [ "$p" = "$PROVIDER" ]; then
            valid=true
            break
        fi
    done
    if [ "$valid" = "false" ]; then
        echo -e "${RED}ERROR: Unknown provider: $PROVIDER${NC}"
        echo "Available providers: ${PROVIDERS[*]}"
        exit 1
    fi
fi

# Auto-setup if needed
if needs_setup; then
    run_setup
fi

# Check .env exists
check_env

# Run the agent
run_agent
