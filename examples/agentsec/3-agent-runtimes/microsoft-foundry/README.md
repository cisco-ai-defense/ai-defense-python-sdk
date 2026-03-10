# Microsoft Azure AI Foundry Examples with agentsec Protection

This directory contains examples demonstrating how to deploy AI agents to **Microsoft Azure AI Foundry** with **Cisco AI Defense** protection via the `agentsec` SDK.

## Overview

These examples show three deployment modes for Azure AI Foundry, all protected by agentsec for both LLM and MCP calls:

| Deployment Mode | Description | Use Case |
|-----------------|-------------|----------|
| **Foundry Agent App** | Azure ML managed online endpoint | Production web services |
| **Azure Functions** | Serverless function deployment | Event-driven, cost-efficient |
| **Foundry Container** | Custom container deployment | Full control, complex dependencies |

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                   Azure AI Foundry                           │
├──────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │ Foundry Agent   │  │ Azure Functions │  │ Container    │ │
│  │ Application     │  │                 │  │ Deployment   │ │
│  └────────┬────────┘  └────────┬────────┘  └──────┬───────┘ │
│           │                    │                   │         │
│           └────────────────────┼───────────────────┘         │
│                                │                             │
│                    ┌───────────▼───────────┐                 │
│                    │   _shared/            │                 │
│                    │   agent_factory.py    │                 │
│                    │   (LangChain Agent)   │                 │
│                    └───────────┬───────────┘                 │
│                                │                             │
│                    ┌───────────▼───────────┐                 │
│                    │     agentsec          │                 │
│                    │   (AI Defense SDK)    │                 │
│                    └───────────┬───────────┘                 │
└────────────────────────────────┼─────────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Azure OpenAI   │    │ Cisco AI Defense│    │   MCP Server    │
│  (LLM Provider) │    │ (Inspection)    │    │   (Tools)       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Protection Modes

agentsec supports two integration modes with Cisco AI Defense:

### API Mode (Default)
- Requests are inspected via Cisco AI Defense API
- Pre-call and post-call inspection
- Works with any LLM provider

### Gateway Mode
- Requests are routed through Cisco AI Defense Gateway
- Gateway handles inspection transparently
- Better performance for high-throughput scenarios

## Prerequisites

1. **Azure CLI** installed and configured
   ```bash
   az login
   ```

2. **Azure AI Foundry** workspace created

3. **Azure OpenAI** resource with a deployed model

4. **Poetry** for dependency management
   ```bash
   pip install poetry
   ```

5. **Environment variables** configured in `examples/agentsec/.env`:
   ```bash
   # Azure OpenAI (for API mode - direct calls)
   AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
   AZURE_OPENAI_API_KEY=your-api-key
   # IMPORTANT: Deployment name must match your Azure OpenAI resource deployment
   AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
   AZURE_OPENAI_API_VERSION=2024-08-01-preview
   
   # Azure AI Foundry Deployment
   AZURE_SUBSCRIPTION_ID=your-subscription-id
   AZURE_RESOURCE_GROUP=your-resource-group
   AZURE_AI_FOUNDRY_PROJECT=your-workspace-name
   
   # For container deployments
   AZURE_ACR_NAME=your-acr-name
   AZURE_ACR_LOGIN_SERVER=your-acr.azurecr.io
   
   # For Azure Functions
   AZURE_FUNCTION_APP_NAME=your-function-app
   AZURE_STORAGE_ACCOUNT=your-storage-account
   ```

## Quick Start

### 1. Install Dependencies

```bash
cd examples/agentsec/3-agent-runtimes/microsoft-foundry
poetry install
```

### 2. Local Testing

Test the agent locally before deploying:

```bash
# Set up environment
source ../../.env

# Test the agent directly
poetry run python -c "
from _shared import invoke_agent
result = invoke_agent('Check the health of the payments service')
print(result)
"
```

### 3. Deploy to Azure

Choose your deployment mode:

#### Foundry Agent Application
```bash
cd foundry-agent-app
./scripts/deploy.sh
./scripts/invoke.sh "Check payments health"
```

#### Azure Functions
```bash
cd azure-functions
./scripts/deploy.sh
./scripts/invoke.sh "Check payments health"
```

#### Foundry Container
```bash
cd foundry-container
./scripts/deploy.sh
./scripts/invoke.sh "Check payments health"
```

## Directory Structure

```
microsoft-foundry/
├── _shared/                      # Shared agent code
│   ├── __init__.py
│   ├── agent_factory.py          # LangChain agent + agentsec
│   ├── tools.py                  # Demo tools
│   └── mcp_tools.py              # MCP tool integration
├── agentsec/                     # Vendored SDK (generated at deploy time, git-ignored)
├── aidefense/                    # Vendored SDK (generated at deploy time, git-ignored)
├── foundry-agent-app/            # Azure ML managed online endpoint
│   ├── main.py                   # Azure ML inference script (init/run)
│   ├── Dockerfile
│   ├── deployment.yaml           # (generated at deploy time, git-ignored)
│   ├── endpoint.yaml             # (generated at deploy time, git-ignored)
│   ├── model/                    # (generated at deploy time, git-ignored)
│   ├── requirements.txt
│   └── scripts/
│       ├── deploy.sh
│       └── invoke.sh
├── azure-functions/              # Serverless functions
│   ├── _shared/                  # (generated at deploy time, git-ignored)
│   ├── agentsec/                 # (generated at deploy time, git-ignored)
│   ├── function_app.py
│   ├── host.json
│   ├── requirements.txt
│   └── scripts/
│       ├── deploy.sh
│       └── invoke.sh
├── foundry-container/            # Custom container deployment
│   ├── main.py                   # Azure ML inference script (init/run)
│   ├── Dockerfile
│   ├── deployment.yaml           # (generated at deploy time, git-ignored)
│   ├── endpoint.yaml             # (generated at deploy time, git-ignored)
│   ├── model/                    # (generated at deploy time, git-ignored)
│   ├── requirements.txt
│   └── scripts/
│       ├── deploy.sh
│       └── invoke.sh
├── tests/
│   ├── integration/              # Integration tests
│   │   ├── test-all-modes.sh
│   │   └── test_mcp_protection.py
│   └── unit/                     # Unit tests
│       └── test_foundry_example.py
├── pyproject.toml
└── README.md
```

## Agent Capabilities

The demo SRE (Site Reliability Engineering) agent includes:

### Local Tools
- `check_service_health(service_name)` - Check service health status
- `get_recent_logs(service_name, limit)` - Retrieve recent logs
- `calculate_capacity(current_usage, growth_rate)` - Capacity planning

### MCP Tools (Optional)
- `fetch_url(url)` - Fetch webpage content via MCP server

Enable MCP tools by setting `MCP_SERVER_URL` in your environment.

## Integration Tests

### Local Tests (Default)
Run integration tests locally using your Azure OpenAI credentials:

```bash
./tests/integration/test-all-modes.sh              # Run all local tests
./tests/integration/test-all-modes.sh --verbose    # With detailed output
./tests/integration/test-all-modes.sh --api        # API mode only
./tests/integration/test-all-modes.sh --gateway    # Gateway mode only
```

Local tests require only:
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`

### Azure Deployment Tests (--deploy flag)
When you have full Azure access, use `--deploy` to deploy and test real endpoints:

```bash
./tests/integration/test-all-modes.sh --deploy              # Deploy and test all
./tests/integration/test-all-modes.sh --deploy --verbose    # With detailed output
./tests/integration/test-all-modes.sh --deploy agent-app    # Deploy and test agent app only
./tests/integration/test-all-modes.sh --deploy --api        # Deploy, test API mode only
```

Deployment tests require additional Azure credentials:
- `AZURE_SUBSCRIPTION_ID`
- `AZURE_RESOURCE_GROUP`
- `AZURE_AI_FOUNDRY_PROJECT`
- `AZURE_ACR_NAME` / `AZURE_ACR_LOGIN_SERVER` (for container)
- `AZURE_FUNCTION_APP_NAME` / `AZURE_STORAGE_ACCOUNT` (for functions)

## Finding resources in Azure Portal

All deployment resources use the **resource group** and **subscription** from `examples/agentsec/.env` (`AZURE_RESOURCE_GROUP`, `AZURE_SUBSCRIPTION_ID`). With `--new-resources`, agent, container, and function app share the same timestamp suffix in their names.

### 1. Open the resource group

1. Go to [Azure Portal](https://portal.azure.com).
2. In the top search bar, type **Resource groups** and open it.
3. Select your subscription (e.g. the one matching `AZURE_SUBSCRIPTION_ID`).
4. Open the resource group named **`AZURE_RESOURCE_GROUP`** (e.g. `AI_Runtime_AID`).

You’ll see the Function App, Storage Account, and Container Registry in this group. The ML endpoints live inside the AI Foundry workspace (next step).

### 2. Agent App and Container endpoints (Azure AI Foundry / ML)

1. In the portal search bar, type **Azure AI** or **Machine Learning**.
2. Open **Azure AI** (or **Machine Learning**).
3. In the left menu, open **AI services** → **Azure AI Foundry** (or find the workspace under **Machine Learning**).
4. Open the workspace named **`AZURE_AI_FOUNDRY_PROJECT`** (e.g. `aid-ml-workspace`).
5. In the workspace, go to **Inference** (or **Endpoints**) → **Online endpoints**.
6. Your deployments appear as:
   - **Agent App:** endpoint name = `AGENT_ENDPOINT_NAME` (e.g. `foundry-sre-agent` or `foundry-sre-agent-26020619`).
   - **Container:** endpoint name = `CONTAINER_ENDPOINT_NAME` (e.g. `foundry-sre-container` or `foundry-sre-container-26020619`).

Click an endpoint to see deployments, scoring URL, and logs.

### 3. Azure Function App

1. Stay in the same **resource group** (step 1), or search for **Function App** in the top bar.
2. Open **Function App** in the left menu.
3. Find the app named **`AZURE_FUNCTION_APP_NAME`** (e.g. `aid-sre-agent-func` or `aid-sre-agent-func-26020619`).

From the function app you can open **Functions** (e.g. `invoke`), **Overview**, and **Deployment Center**.

### 4. Other resources in the same resource group

- **Storage account:** `AZURE_STORAGE_ACCOUNT` (e.g. `aidsreagentstorage`) — used by the Function App.
- **Container registry:** `AZURE_ACR_NAME` (e.g. `aidAIRuntime`) — used for container images.

### Quick lookup (same names as in scripts)

| Resource            | Env variable              | Example name (with `--new-resources`)   |
|---------------------|---------------------------|-----------------------------------------|
| Resource group      | `AZURE_RESOURCE_GROUP`    | `AI_Runtime_AID`                        |
| ML workspace        | `AZURE_AI_FOUNDRY_PROJECT`| `aid-ml-workspace`                      |
| Agent endpoint      | `AGENT_ENDPOINT_NAME`     | `foundry-sre-agent-26020619`            |
| Container endpoint  | `CONTAINER_ENDPOINT_NAME` | `foundry-sre-container-26020619`        |
| Function App        | `AZURE_FUNCTION_APP_NAME` | `aid-sre-agent-func-26020619`           |
| Storage account     | `AZURE_STORAGE_ACCOUNT`   | `aidsreagentstorage`                    |
| Container registry  | `AZURE_ACR_NAME`         | `aidAIRuntime`                          |

## Troubleshooting

### Azure OpenAI Connection Issues
- Verify `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_API_KEY` are set correctly
- **IMPORTANT**: `AZURE_OPENAI_DEPLOYMENT_NAME` must match your actual Azure OpenAI deployment name (not the model name like "gpt-4o")
  - To find your deployment name: Azure Portal → Azure OpenAI → Your Resource → Model Deployments
- Check that your Azure OpenAI deployment is active
- Ensure your IP is allowed in the Azure OpenAI firewall settings

### Deployment Failures
- Verify Azure CLI is logged in: `az account show`
- Check resource group exists: `az group show --name $AZURE_RESOURCE_GROUP`
- Ensure you have Contributor role on the resource group
- Check VM quota for the instance type: `az vm list-usage --location <region>`
- For container deployments, ensure ACR is accessible and image is pushed

### Container Startup Issues
- Test locally first: `./scripts/test-docker-local.sh agent-app`
- Check container logs: `az ml online-deployment get-logs --name default --endpoint-name <endpoint>`
- Azure ML inference server uses `/` for liveness checks and `/score` for scoring

### agentsec Not Patching
- Ensure `agentsec.protect()` is called BEFORE importing `langchain_openai`
- Check logs for `[agentsec] Patched: ['openai', ...]`
- Verify AI Defense API credentials in `.env`

## Related Examples

- [Amazon Bedrock AgentCore](../amazon-bedrock-agentcore/) - AWS deployment examples
- [GCP Vertex AI Agent Engine](../gcp-vertex-ai-agent-engine/) - GCP deployment examples
