#!/bin/bash
# =============================================================================
# Local Docker Test Script for Microsoft Foundry Examples
# =============================================================================
# Tests the Docker image locally before deploying to Azure.
# This helps debug container startup issues that are hard to diagnose in Azure.
#
# Usage:
#   ./scripts/test-docker-local.sh [agent-app|container]
#   ./scripts/test-docker-local.sh agent-app --build    # Force rebuild
#   ./scripts/test-docker-local.sh agent-app --shell    # Open shell in container
#
# Requirements:
#   - Docker installed and running
#   - .env file with Azure OpenAI credentials
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SHARED_ENV="$PROJECT_DIR/../../.env"

# Default settings
MODE="${1:-agent-app}"  # agent-app or container
FORCE_BUILD=false
SHELL_MODE=false
CONTAINER_PORT=5001
HOST_PORT=8080

# Parse additional arguments
shift || true
while [[ $# -gt 0 ]]; do
    case $1 in
        --build)
            FORCE_BUILD=true
            shift
            ;;
        --shell)
            SHELL_MODE=true
            shift
            ;;
        --port)
            HOST_PORT="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Local Docker Test - $MODE${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo ""

# Validate mode
if [[ "$MODE" != "agent-app" && "$MODE" != "container" ]]; then
    echo -e "${RED}Error: Mode must be 'agent-app' or 'container'${NC}"
    echo "Usage: $0 [agent-app|container] [--build] [--shell]"
    exit 1
fi

# Set paths based on mode
if [[ "$MODE" == "agent-app" ]]; then
    DOCKERFILE="$PROJECT_DIR/foundry-agent-app/Dockerfile"
    IMAGE_NAME="foundry-agent-app-local"
else
    DOCKERFILE="$PROJECT_DIR/foundry-container/Dockerfile"
    IMAGE_NAME="foundry-container-local"
fi

# Load environment variables
if [[ -f "$SHARED_ENV" ]]; then
    echo -e "${GREEN}✓${NC} Loading environment from $SHARED_ENV"
    set -a
    source "$SHARED_ENV"
    set +a
else
    echo -e "${RED}✗${NC} Environment file not found: $SHARED_ENV"
    exit 1
fi

# Check required environment variables
REQUIRED_VARS=("AZURE_OPENAI_ENDPOINT" "AZURE_OPENAI_API_KEY")
for var in "${REQUIRED_VARS[@]}"; do
    if [[ -z "${!var}" ]]; then
        echo -e "${RED}✗${NC} Required environment variable not set: $var"
        exit 1
    fi
done

echo -e "${GREEN}✓${NC} Environment variables loaded"
echo ""

# =============================================================================
# Copy aidefense SDK to build context
# =============================================================================
echo -e "${BLUE}Copying aidefense SDK to build context...${NC}"
# Path: microsoft-foundry/ -> 3-agent-runtimes/ -> agentsec/ -> examples/ -> repo-root/aidefense
AIDEFENSE_SRC="$PROJECT_DIR/../../../../aidefense"
if [[ -d "$AIDEFENSE_SRC" ]]; then
    rm -rf "$PROJECT_DIR/aidefense" 2>/dev/null || true
    cp -R "$AIDEFENSE_SRC" "$PROJECT_DIR/aidefense"
    echo -e "${GREEN}✓${NC} Copied aidefense from $AIDEFENSE_SRC"
else
    echo -e "${RED}✗${NC} aidefense source not found at $AIDEFENSE_SRC"
    exit 1
fi

# =============================================================================
# Build Docker Image
# =============================================================================
echo ""
echo -e "${BLUE}Building Docker image: $IMAGE_NAME${NC}"

# Check if image exists and if we should rebuild
if docker image inspect "$IMAGE_NAME" &>/dev/null && [[ "$FORCE_BUILD" != "true" ]]; then
    echo -e "${YELLOW}⚠${NC} Image already exists. Use --build to force rebuild."
    read -p "Rebuild? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        FORCE_BUILD=true
    fi
fi

if [[ "$FORCE_BUILD" == "true" ]] || ! docker image inspect "$IMAGE_NAME" &>/dev/null; then
    echo "Building from $DOCKERFILE..."
    docker build \
        -f "$DOCKERFILE" \
        -t "$IMAGE_NAME" \
        "$PROJECT_DIR"
    echo -e "${GREEN}✓${NC} Docker image built successfully"
else
    echo -e "${GREEN}✓${NC} Using existing image"
fi

# =============================================================================
# Cleanup function
# =============================================================================
cleanup() {
    echo ""
    echo -e "${BLUE}Cleaning up...${NC}"
    docker stop "$IMAGE_NAME-test" 2>/dev/null || true
    docker rm "$IMAGE_NAME-test" 2>/dev/null || true
    rm -rf "$PROJECT_DIR/aidefense" 2>/dev/null || true
    echo -e "${GREEN}✓${NC} Cleanup complete"
}
trap cleanup EXIT

# =============================================================================
# Run Container
# =============================================================================
echo ""

# Stop existing container if running
docker stop "$IMAGE_NAME-test" 2>/dev/null || true
docker rm "$IMAGE_NAME-test" 2>/dev/null || true

if [[ "$SHELL_MODE" == "true" ]]; then
    echo -e "${BLUE}Opening shell in container...${NC}"
    echo "Type 'exit' to quit"
    echo ""
    docker run -it --rm \
        --name "$IMAGE_NAME-test" \
        -e AZURE_OPENAI_ENDPOINT="$AZURE_OPENAI_ENDPOINT" \
        -e AZURE_OPENAI_API_KEY="$AZURE_OPENAI_API_KEY" \
        -e AZURE_OPENAI_DEPLOYMENT_NAME="${AZURE_OPENAI_DEPLOYMENT_NAME:-gpt-4o}" \
        -e AZURE_OPENAI_API_VERSION="${AZURE_OPENAI_API_VERSION:-2024-08-01-preview}" \
        -e AGENTSEC_LLM_INTEGRATION_MODE="${AGENTSEC_LLM_INTEGRATION_MODE:-api}" \
        -e AGENTSEC_MCP_INTEGRATION_MODE="${AGENTSEC_MCP_INTEGRATION_MODE:-api}" \
        -e AGENTSEC_API_MODE_LLM="${AGENTSEC_API_MODE_LLM:-monitor}" \
        -e AGENTSEC_API_MODE_MCP="${AGENTSEC_API_MODE_MCP:-monitor}" \
        -e AI_DEFENSE_API_MODE_LLM_ENDPOINT="${AI_DEFENSE_API_MODE_LLM_ENDPOINT:-}" \
        -e AI_DEFENSE_API_MODE_LLM_API_KEY="${AI_DEFENSE_API_MODE_LLM_API_KEY:-}" \
        -e MCP_SERVER_URL="${MCP_SERVER_URL:-}" \
        -e AGENTSEC_LOG_LEVEL="DEBUG" \
        "$IMAGE_NAME" \
        /bin/bash
else
    echo -e "${BLUE}Starting container...${NC}"
    
    # For Azure ML inference, we need to simulate the inference server
    # The container expects to be started by Azure ML's inference server
    # For local testing, we'll run Python directly to test imports
    
    echo ""
    echo -e "${BLUE}Testing Python imports in container...${NC}"
    docker run --rm \
        --name "$IMAGE_NAME-import-test" \
        -e AZURE_OPENAI_ENDPOINT="$AZURE_OPENAI_ENDPOINT" \
        -e AZURE_OPENAI_API_KEY="$AZURE_OPENAI_API_KEY" \
        -e AZURE_OPENAI_DEPLOYMENT_NAME="${AZURE_OPENAI_DEPLOYMENT_NAME:-gpt-4o}" \
        -e AZURE_OPENAI_API_VERSION="${AZURE_OPENAI_API_VERSION:-2024-08-01-preview}" \
        -e AGENTSEC_LLM_INTEGRATION_MODE="${AGENTSEC_LLM_INTEGRATION_MODE:-api}" \
        -e AGENTSEC_MCP_INTEGRATION_MODE="${AGENTSEC_MCP_INTEGRATION_MODE:-api}" \
        -e AGENTSEC_API_MODE_LLM="${AGENTSEC_API_MODE_LLM:-monitor}" \
        -e AGENTSEC_API_MODE_MCP="${AGENTSEC_API_MODE_MCP:-monitor}" \
        -e AI_DEFENSE_API_MODE_LLM_ENDPOINT="${AI_DEFENSE_API_MODE_LLM_ENDPOINT:-}" \
        -e AI_DEFENSE_API_MODE_LLM_API_KEY="${AI_DEFENSE_API_MODE_LLM_API_KEY:-}" \
        -e MCP_SERVER_URL="${MCP_SERVER_URL:-}" \
        -e AGENTSEC_LOG_LEVEL="DEBUG" \
        "$IMAGE_NAME" \
        python -c "
import sys
print('Python path:', sys.path)
print()

print('Testing imports...')
try:
    print('  Importing aidefense.runtime.agentsec...')
    from aidefense.runtime.agentsec import protect, get_patched_clients
    print('  ✓ aidefense.runtime.agentsec imported')
except Exception as e:
    print(f'  ✗ Failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print('  Importing _shared (this also initializes agentsec protection)...')
    from _shared import invoke_agent, get_client
    print('  ✓ _shared imported')
except Exception as e:
    print(f'  ✗ Failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print('  Importing main...')
    import main
    print('  ✓ main imported')
except Exception as e:
    print(f'  ✗ Failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print('Calling main.init()...')
try:
    main.init()
    print('✓ main.init() succeeded')
except Exception as e:
    print(f'✗ main.init() failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print('Testing invoke with simple prompt...')
try:
    import json
    result = main.run(json.dumps({'prompt': 'What is 2+2?'}))
    print(f'✓ Result: {result}')
except Exception as e:
    print(f'✗ Invoke failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print('All tests passed!')
"
    
    if [[ $? -ne 0 ]]; then
        echo ""
        echo -e "${RED}════════════════════════════════════════════════════════════════${NC}"
        echo -e "${RED}  ✗ Import test FAILED${NC}"
        echo -e "${RED}════════════════════════════════════════════════════════════════${NC}"
        exit 1
    fi
    
    # =============================================================================
    # Test Azure ML Inference Server (azmlinfsrv)
    # =============================================================================
    echo ""
    echo -e "${BLUE}Testing Azure ML inference server...${NC}"
    echo "Starting container with azmlinfsrv on port $CONTAINER_PORT (mapped to $HOST_PORT)..."
    
    # Start the container in background
    docker run -d \
        --name "$IMAGE_NAME-test" \
        -p "$HOST_PORT:$CONTAINER_PORT" \
        -e AZURE_OPENAI_ENDPOINT="$AZURE_OPENAI_ENDPOINT" \
        -e AZURE_OPENAI_API_KEY="$AZURE_OPENAI_API_KEY" \
        -e AZURE_OPENAI_DEPLOYMENT_NAME="${AZURE_OPENAI_DEPLOYMENT_NAME:-gpt-4o}" \
        -e AZURE_OPENAI_API_VERSION="${AZURE_OPENAI_API_VERSION:-2024-08-01-preview}" \
        -e AGENTSEC_LLM_INTEGRATION_MODE="${AGENTSEC_LLM_INTEGRATION_MODE:-api}" \
        -e AGENTSEC_MCP_INTEGRATION_MODE="${AGENTSEC_MCP_INTEGRATION_MODE:-api}" \
        -e AGENTSEC_API_MODE_LLM="${AGENTSEC_API_MODE_LLM:-monitor}" \
        -e AGENTSEC_API_MODE_MCP="${AGENTSEC_API_MODE_MCP:-monitor}" \
        -e AI_DEFENSE_API_MODE_LLM_ENDPOINT="${AI_DEFENSE_API_MODE_LLM_ENDPOINT:-}" \
        -e AI_DEFENSE_API_MODE_LLM_API_KEY="${AI_DEFENSE_API_MODE_LLM_API_KEY:-}" \
        -e MCP_SERVER_URL="${MCP_SERVER_URL:-}" \
        -e AGENTSEC_LOG_LEVEL="DEBUG" \
        "$IMAGE_NAME"
    
    # Wait for server to start
    echo "Waiting for inference server to start..."
    MAX_WAIT=30
    WAITED=0
    SERVER_READY=false
    
    while [[ $WAITED -lt $MAX_WAIT ]]; do
        sleep 2
        WAITED=$((WAITED + 2))
        
        # Check if container is still running
        if ! docker ps | grep -q "$IMAGE_NAME-test"; then
            echo -e "${RED}✗${NC} Container stopped unexpectedly!"
            echo ""
            echo "Container logs:"
            docker logs "$IMAGE_NAME-test" 2>&1 | tail -50
            exit 1
        fi
        
        # Test liveness endpoint (Azure ML inference server uses / for liveness)
        if curl -s -f "http://localhost:$HOST_PORT/" > /dev/null 2>&1; then
            SERVER_READY=true
            break
        fi
        
        echo "  Waiting... ($WAITED/$MAX_WAIT seconds)"
    done
    
    if [[ "$SERVER_READY" != "true" ]]; then
        echo -e "${RED}✗${NC} Server failed to start within $MAX_WAIT seconds"
        echo ""
        echo "Container logs:"
        docker logs "$IMAGE_NAME-test" 2>&1 | tail -100
        exit 1
    fi
    
    echo -e "${GREEN}✓${NC} Inference server started successfully"
    echo ""
    
    # Test liveness route
    echo -e "${BLUE}Testing liveness route (GET /)...${NC}"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$HOST_PORT/")
    if [[ "$HTTP_CODE" == "200" ]]; then
        echo -e "${GREEN}✓${NC} Liveness check passed (HTTP $HTTP_CODE)"
    else
        echo -e "${RED}✗${NC} Liveness check failed (HTTP $HTTP_CODE)"
        docker logs "$IMAGE_NAME-test" 2>&1 | tail -50
        exit 1
    fi
    
    # Test scoring route
    echo ""
    echo -e "${BLUE}Testing scoring route (POST /score)...${NC}"
    RESPONSE=$(curl -s -X POST "http://localhost:$HOST_PORT/score" \
        -H "Content-Type: application/json" \
        -d '{"prompt": "What is 2+2?"}')
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "http://localhost:$HOST_PORT/score" \
        -H "Content-Type: application/json" \
        -d '{"prompt": "What is 2+2?"}')
    
    if [[ "$HTTP_CODE" == "200" ]]; then
        echo -e "${GREEN}✓${NC} Scoring endpoint passed (HTTP $HTTP_CODE)"
        echo "Response: $RESPONSE"
    else
        echo -e "${RED}✗${NC} Scoring endpoint failed (HTTP $HTTP_CODE)"
        echo "Response: $RESPONSE"
        docker logs "$IMAGE_NAME-test" 2>&1 | tail -50
        exit 1
    fi
    
    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✓ Local Docker test PASSED${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
fi
