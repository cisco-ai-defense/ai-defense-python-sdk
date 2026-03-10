# GCP Vertex AI Agent Engine with Cisco AI Defense

This example demonstrates how to protect AI agents running on Google Cloud Platform's Vertex AI using **agentsec** (Cisco AI Defense SDK). The example uses a **LangChain-based agent** with tool calling capabilities, similar to how the Amazon Bedrock AgentCore example uses Strands Agent.

## Architecture

```
User Prompt → LangChain Agent → ChatGoogleGenerativeAI (LLM)  [or ChatVertexAI when sdk=vertexai]
                     ↓
               Tool Calling (Protected by agentsec)
                     ↓
         ┌──────────┴───────────┐
         │     Local Tools      │    MCP Tools
         │  - check_service_    │    - fetch_url()
         │    health()          │      ↓
         │  - get_recent_logs() │    MCP Server
         │  - calculate_        │    (agentsec protected)
         │    capacity()        │
         └──────────┬───────────┘
                    ↓
               Final Response
```

## Key Features

- **LangChain Agent**: Uses modern LangChain 1.0+ pattern with `llm.bind_tools()` and agentic loop
- **Tool Calling**: Agent reasons about when to use tools based on the prompt
- **Local Tools**: Demo SRE tools (check_service_health, get_recent_logs, calculate_capacity)
- **MCP Tools**: fetch_url tool connects to external MCP server (when `MCP_SERVER_URL` is set)
- **AI Defense Protection**: Both LLM calls and MCP calls are protected by agentsec

## Deployment Modes

| Mode | Directory | Description |
|------|-----------|-------------|
| **Agent Engine** | `agent-engine-deploy/` | Google's fully managed agent service |
| **Cloud Run** | `cloud-run-deploy/` | Serverless container deployment |
| **GKE** | `gke-deploy/` | Google Kubernetes Engine deployment |

## AI Defense Integration Modes

Each deployment mode supports two integration modes for Cisco AI Defense:

| Mode | Description | Use Case |
|------|-------------|----------|
| **API Mode** | Requests inspected via AI Defense API | Development, testing, full visibility |
| **Gateway Mode** | Requests routed through AI Defense Gateway | Production, lower latency |

## Prerequisites

1. **Google Cloud Setup**
   ```bash
   # Install gcloud CLI
   # https://cloud.google.com/sdk/docs/install

   # Authenticate
   gcloud auth application-default login
   
   # Set project
   gcloud config set project YOUR_PROJECT_ID
   export GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID
   export GOOGLE_CLOUD_LOCATION=us-central1
   ```

2. **Enable APIs**
   ```bash
   gcloud services enable aiplatform.googleapis.com
   gcloud services enable run.googleapis.com
   gcloud services enable container.googleapis.com
   ```

3. **AI Defense Configuration**

   All agentsec settings (gateway URLs, API mode, etc.) are in `examples/agentsec/agentsec.yaml`.
   Secrets referenced via `${VAR_NAME}` are resolved from `examples/agentsec/.env`:

   ```bash
   # Secrets in examples/agentsec/.env
   AI_DEFENSE_API_MODE_LLM_API_KEY=your-api-key
   AI_DEFENSE_API_MODE_MCP_API_KEY=your-mcp-api-key

   # MCP Server for fetch_url tool (optional)
   MCP_SERVER_URL=https://mcp.deepwiki.com/mcp
   ```

## Quick Start

### 1. Install Dependencies

```bash
cd examples/3-agent-runtimes/gcp-vertex-ai-agent-engine
poetry install
```

### 2. Test Locally (Agent Engine Mode)

```bash
# Set environment
export GOOGLE_CLOUD_PROJECT=your-project
export GOOGLE_CLOUD_LOCATION=us-central1
export GOOGLE_GENAI_USE_VERTEXAI=True

# Run local test
./agent-engine-deploy/scripts/deploy.sh test
```

### 3. Deploy to Cloud Run

```bash
# Build and deploy
./cloud-run-deploy/scripts/deploy.sh

# Invoke with tool-triggering prompt
./cloud-run-deploy/scripts/invoke.sh "Check the health of the payments service"

# Invoke with MCP tool (requires MCP_SERVER_URL)
./cloud-run-deploy/scripts/invoke.sh "Fetch https://example.com and summarize it"
```

### 4. Deploy to GKE

> **Security Note**: GKE clusters at Cisco require Master Authorized Networks for compliance.
> The deploy script auto-detects your IP, or you can set `GKE_AUTHORIZED_NETWORKS` in `.env`.

```bash
# Optional: Set your IP for cluster access (auto-detected if not set)
export GKE_AUTHORIZED_NETWORKS=$(curl -s ifconfig.me)/32

# Setup cluster (first time only)
./gke-deploy/scripts/deploy.sh setup

# Build and deploy
./gke-deploy/scripts/deploy.sh

# Invoke with tool-triggering prompt
./gke-deploy/scripts/invoke.sh "Check the health of the auth service and show me recent logs"
```

## Project Structure

```
gcp-vertex-ai-agent-engine/
├── _shared/
│   ├── __init__.py           # Exports agent and tools
│   ├── agent_factory.py      # LangChain agent with agentsec protection
│   ├── tools.py              # Local SRE tools (LangChain @tool)
│   └── mcp_tools.py          # MCP tools (LangChain @tool)
├── agent-engine-deploy/
│   ├── app.py                # Agent Engine entry point
│   ├── requirements.txt
│   └── scripts/
│       ├── deploy.sh         # Deploy/test script
│       └── invoke.sh         # Invoke script
├── cloud-run-deploy/
│   ├── app.py                # FastAPI app
│   ├── Dockerfile
│   ├── requirements.txt
│   └── scripts/
│       ├── deploy.sh         # Build & deploy to Cloud Run
│       ├── invoke.sh         # Invoke deployed service
│       └── cleanup.sh        # Delete Cloud Run deployment
├── gke-deploy/
│   ├── app.py                # FastAPI app
│   ├── Dockerfile
│   ├── k8s/
│   │   ├── deployment.yaml   # Kubernetes Deployment
│   │   └── service.yaml      # Kubernetes Service
│   ├── requirements.txt
│   └── scripts/
│       ├── deploy.sh         # Build & deploy to GKE
│       ├── invoke.sh         # Invoke deployed service
│       └── cleanup.sh        # Delete GKE deployment
├── tests/
│   ├── integration/
│   │   ├── test-all-modes.sh     # Real GCP deployment tests
│   │   └── test_mcp_protection.py # MCP tool protection test
│   └── unit/
│       └── test_vertex_agent_example.py
├── pyproject.toml
└── README.md
```

## How agentsec Protection Works

The `_shared/agent_factory.py` module calls `agentsec.protect()` **before** importing any AI library. All configuration is loaded from `agentsec.yaml`:

```python
# Configure AI Defense protection BEFORE importing AI libraries
from aidefense.runtime import agentsec

agentsec.protect(
    config=str(_yaml_config),  # path to agentsec.yaml
    auto_dotenv=False,         # .env already loaded manually
)

# NOW import LangChain (will use patched google-genai)
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
```

All gateway URLs, API mode settings, retry policies, and fail-open defaults are defined in `agentsec.yaml`. Secrets are referenced via `${VAR_NAME}` and resolved from `.env`.

> **Per-Gateway GCP Credentials**: When using `auth_mode: google_adc`, each Vertex AI gateway in `agentsec.yaml` can specify its own `gcp_project`, `gcp_location`, `gcp_service_account_key_file`, or `gcp_target_service_account` (for SA impersonation). All are optional -- when omitted, `google.auth.default()` ADC is used. See the main agentsec [README](../../README.md) for details.

The agent uses modern LangChain patterns:

```python
# Create LLM with tool binding
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-001", vertexai=True)
llm_with_tools = llm.bind_tools([check_service_health, get_recent_logs, fetch_url])

# Agent loop: invoke → check tool_calls → execute tools → repeat until done
response = llm_with_tools.invoke(messages)
if response.tool_calls:
    for tool_call in response.tool_calls:
        result = tools_dict[tool_call["name"]].invoke(tool_call["args"])
        messages.append(ToolMessage(content=result, tool_call_id=tool_call["id"]))
```

## Running Tests

### Integration Tests (Real GCP Deployments)

```bash
cd tests/integration

# Run all tests (LLM + MCP protection)
./test-all-modes.sh

# Quick test - local only, no GCP deployment
./test-all-modes.sh --quick

# Local tests only (no GCP deployment)
./test-all-modes.sh --local

# Test specific deployment mode
./test-all-modes.sh --mode cloud-run --api    # Cloud Run + API mode
./test-all-modes.sh --mode gke --gateway      # GKE + Gateway mode

# Test MCP protection only
./test-all-modes.sh --mcp-only

# Run tests and cleanup deployments after
./test-all-modes.sh --mode cloud-run --cleanup
```

### Unit Tests

```bash
cd examples/3-agent-runtimes/gcp-vertex-ai-agent-engine
poetry run pytest tests/unit/ -v
```

## Configuration Reference

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_CLOUD_PROJECT` | GCP project ID | Required |
| `GOOGLE_AI_SDK` | Google AI SDK: `google_genai` (ChatGoogleGenerativeAI) or `vertexai` (ChatVertexAI). Set via `agentsec.yaml` gateway `sdk` field (resolves `${GOOGLE_AI_SDK}`) | `google_genai` |
| `GOOGLE_CLOUD_LOCATION` | GCP region | `us-central1` |
| `VERTEX_AI_MODEL` | Model to use | `gemini-2.0-flash-001` |
| `MCP_SERVER_URL` | MCP server for fetch_url tool | Optional |
| `AI_DEFENSE_API_MODE_LLM_API_KEY` | AI Defense API key (referenced by agentsec.yaml) | Required (API mode) |
| `AI_DEFENSE_API_MODE_MCP_API_KEY` | AI Defense MCP API key (referenced by agentsec.yaml) | Required (API mode) |

All other agentsec settings (integration modes, gateway URLs, fail-open, retry, etc.) are configured in `agentsec.yaml`.

### Deployment-Specific Variables

| Variable | Description | Used By |
|----------|-------------|---------|
| `CLOUD_RUN_SERVICE` | Cloud Run service name | Cloud Run |
| `GKE_CLUSTER` | GKE cluster name | GKE |
| `GKE_SERVICE` | GKE service name | GKE |
| `GKE_AUTHORIZED_NETWORKS` | CIDR for Master Authorized Networks | GKE |

## Comparison with Amazon Bedrock AgentCore

| Feature | GCP Vertex AI (this example) | Amazon Bedrock AgentCore |
|---------|------------------------------|--------------------------|
| **Agent Framework** | LangChain | Strands Agent |
| **LLM** | ChatGoogleGenerativeAI (Gemini) | BedrockModel (Claude) |
| **Tool Definition** | `@tool` decorator (LangChain) | `@tool` decorator (Strands) |
| **MCP Integration** | `mcp.client.session.ClientSession` | Same |
| **agentsec Protection** | LLM + MCP calls | LLM + MCP calls |

## Troubleshooting

### Authentication Issues

```bash
# Re-authenticate
gcloud auth application-default login

# Check current project
gcloud config get-value project
```

### Agent Not Using Tools

1. Ensure prompts are clear about what action to take
2. Use tool-triggering prompts like "Check the health of X" instead of "What is X status?"
3. Check logs for `[TOOL CALL]` output

### MCP Tool Not Working

1. Verify `MCP_SERVER_URL` is set
2. Check network connectivity to MCP server
3. Look for `[MCP TOOL]` output in logs

### AI Defense Not Working

1. Verify environment variables are set
2. Check agentsec is imported before LangChain
3. Review logs for `[agentsec]` output showing patched clients

## Related Documentation

- [Cisco AI Defense SDK](https://github.com/cisco/agentsec)
- [LangChain Google Vertex AI](https://python.langchain.com/docs/integrations/chat/google_vertex_ai_palm)
- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [GKE Documentation](https://cloud.google.com/kubernetes-engine/docs)
