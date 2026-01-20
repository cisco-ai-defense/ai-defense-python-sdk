# agentsec Examples

Comprehensive examples demonstrating how to secure AI agents with **Cisco AI Defense** using the `agentsec` SDK.

## Quick Start

```bash
# 1. Configure credentials
cp .env.example .env
# Edit .env with your AI Defense API key and provider credentials

# 2. Run a simple example
cd 1-simple && poetry install && poetry run python basic_protection.py

# 3. Or run an agent framework example
cd 2-agent-frameworks/strands-agent && poetry install && ./scripts/run.sh --openai
```

---

## Overview

| Category | Description | Examples |
|----------|-------------|----------|
| **1-simple/** | Standalone examples for core features | 7 examples |
| **2-agent-frameworks/** | Agent frameworks with MCP tools | 6 frameworks |
| **3-agent-runtimes/** | Cloud deployment with AI Defense | 2 runtimes, 6 modes |

---

## Core Concepts

### Integration Modes

agentsec supports two ways to integrate with Cisco AI Defense:

| Mode | How It Works | When to Use |
|------|--------------|-------------|
| **API Mode** (default) | SDK inspects requests via AI Defense API, then calls LLM directly | Most deployments |
| **Gateway Mode** | SDK routes all traffic through AI Defense Gateway proxy | Centralized policy, caching |

Set via environment variable:
```bash
AGENTSEC_LLM_INTEGRATION_MODE=api      # or "gateway"
```

### Protection Coverage

agentsec inspects both **requests** (user prompts) and **responses** (LLM outputs):

| Inspection | What It Checks | When It Happens |
|------------|----------------|-----------------|
| **Request** | Prompt injection, jailbreak, PII in prompts | Before LLM call |
| **Response** | Sensitive data leakage, harmful content | After LLM response |

### Inspection Modes

| Mode | Behavior | Use Case |
|------|----------|----------|
| `off` | No inspection | Disabled |
| `on_monitor` | Inspect & log, never block | Testing, observability |
| `on_enforce` | Inspect & block violations | Production |

Set via environment variable:
```bash
AGENTSEC_API_MODE_LLM=on_enforce   # or "on_monitor", "off"
```

---

## Directory Structure

```
examples/
├── .env.example                    # Template - copy to .env
├── README.md                       # This file
│
├── 1-simple/                       # Standalone examples
│   ├── basic_protection.py         # Minimal setup
│   ├── openai_example.py           # OpenAI client
│   ├── streaming_example.py        # Streaming responses
│   ├── mcp_example.py              # MCP tool inspection
│   ├── gateway_mode_example.py     # Gateway mode
│   ├── skip_inspection_example.py  # Per-call exclusion
│   ├── simple_strands_bedrock.py   # Strands + Bedrock
│   ├── run-all-integration-tests.sh
│   └── tests/
│
├── 2-agent-frameworks/             # Agent framework examples
│   ├── strands-agent/              # AWS Strands SDK
│   ├── langgraph-agent/            # LangGraph
│   ├── langchain-agent/            # LangChain
│   ├── crewai-agent/               # CrewAI
│   ├── autogen-agent/              # AutoGen
│   ├── openai-agent/               # OpenAI Agents SDK
│   ├── _shared/                    # Shared provider configs
│   └── run-all-integration-tests.sh
│
└── 3-agent-runtimes/               # Cloud runtime examples
    ├── amazon-bedrock-agentcore/   # AWS AgentCore
    │   ├── direct-deploy/          # Direct code (boto3 SDK)
    │   ├── container-deploy/       # Docker container
    │   └── lambda-deploy/          # AWS Lambda
    ├── gcp-vertex-ai-agent-engine/ # GCP Vertex AI
    │   ├── agent-engine-deploy/    # Managed Agent Engine
    │   ├── cloud-run-deploy/       # Cloud Run
    │   └── gke-deploy/             # GKE Kubernetes
    └── run-all-integration-tests.sh
```

---

## 1. Simple Examples

Standalone examples demonstrating core agentsec features without agent frameworks.

| Example | Description | Request | Response |
|---------|-------------|:-------:|:--------:|
| `basic_protection.py` | Minimal setup - modes, patched clients | ✅ | ✅ |
| `openai_example.py` | OpenAI client with automatic inspection | ✅ | ✅ |
| `streaming_example.py` | Streaming responses with chunk inspection | ✅ | ✅ |
| `mcp_example.py` | MCP tool call inspection (pre & post) | ✅ | ✅ |
| `gateway_mode_example.py` | Gateway mode configuration | ✅ | ✅ |
| `skip_inspection_example.py` | Per-call exclusion with context manager | ✅ | ✅ |
| `simple_strands_bedrock.py` | Strands agent with Bedrock Claude | ✅ | ✅ |

### Run Examples

```bash
cd 1-simple
poetry install  # First time only

# Run individual examples
poetry run python basic_protection.py
poetry run python openai_example.py
poetry run python streaming_example.py
poetry run python mcp_example.py
poetry run python gateway_mode_example.py
poetry run python skip_inspection_example.py
poetry run python simple_strands_bedrock.py

# Run integration tests
./run-all-integration-tests.sh
```

---

## 2. Agent Frameworks

Agent framework examples with MCP tool support and multi-provider configuration.

### Supported Frameworks

| Framework | Package | Description |
|-----------|---------|-------------|
| **Strands** | `strands-agents` | AWS Strands SDK with native tool support |
| **LangGraph** | `langgraph` | LangChain's state graph pattern |
| **LangChain** | `langchain` | LCEL chains with tool calling |
| **CrewAI** | `crewai` | Multi-agent crew orchestration |
| **AutoGen** | `ag2` | Microsoft's multi-agent framework |
| **OpenAI Agents** | `openai` | OpenAI's native agent SDK |

### Provider Support

All frameworks support multiple LLM providers:

| Provider | Flag | Auth Methods | Config File |
|----------|------|--------------|-------------|
| **OpenAI** | `--openai` | API key | `config-openai.yaml` |
| **AWS Bedrock** | `--bedrock` | default, profile, session_token, iam_role | `config-bedrock.yaml` |
| **Azure OpenAI** | `--azure` | api_key, managed_identity, cli | `config-azure.yaml` |
| **GCP Vertex AI** | `--vertex` | adc, service_account | `config-vertex.yaml` |

### Run Examples

```bash
cd 2-agent-frameworks

# Run with specific provider
./strands-agent/scripts/run.sh --openai
./strands-agent/scripts/run.sh --bedrock
./langgraph-agent/scripts/run.sh --azure
./crewai-agent/scripts/run.sh --vertex

# Run integration tests
./run-all-integration-tests.sh                    # All frameworks, all providers
./run-all-integration-tests.sh --quick            # OpenAI only (faster)
./run-all-integration-tests.sh --verbose          # Detailed output
./run-all-integration-tests.sh strands langgraph  # Specific frameworks
./run-all-integration-tests.sh --api              # API mode only
./run-all-integration-tests.sh --gateway          # Gateway mode only
```

### Protection Coverage

All agent frameworks support both request and response inspection:

- **LLM Calls**: Every `chat.completions.create()` / `converse()` / `generate_content()` is inspected
- **MCP Tool Calls**: Tool request and response payloads are inspected (when MCP is used)
- **Streaming**: Response chunks are buffered and inspected at completion

---

## 3. Agent Runtimes

Cloud deployment examples with full AI Defense protection.

### AWS Bedrock AgentCore

Three deployment modes for AWS AgentCore agents:

| Mode | Description | Protection | Request | Response |
|------|-------------|------------|:-------:|:--------:|
| **Direct Deploy** | Agent runs in AgentCore, client calls via boto3 SDK | Client-side | ✅ | ✅ |
| **Container Deploy** | Docker container on AgentCore | Server-side | ✅ | ✅ |
| **Lambda Deploy** | AWS Lambda function | Server-side | ✅ | ✅ |

> **Note**: Direct Deploy uses the **boto3 SDK directly** (not the AgentCore CLI) to ensure full response inspection. The CLI bypasses the patched client path for responses.

```bash
cd 3-agent-runtimes/amazon-bedrock-agentcore
poetry install

# Direct Deploy (boto3 SDK)
./direct-deploy/scripts/deploy.sh
poetry run python direct-deploy/test_with_protection.py "What is 5+5?"

# Container Deploy
./container-deploy/scripts/deploy.sh
./container-deploy/scripts/invoke.sh "What is 5+5?"

# Lambda Deploy
./lambda-deploy/scripts/deploy.sh
./lambda-deploy/scripts/invoke.sh "What is 5+5?"

# Run all integration tests (6 tests: 3 deploy modes x 2 integration modes)
./tests/integration/test-all-modes.sh --verbose
```

### GCP Vertex AI Agent Engine

Three deployment modes for GCP Vertex AI agents:

| Mode | Description | Protection | Request | Response |
|------|-------------|------------|:-------:|:--------:|
| **Agent Engine** | Google's managed agent service | Server-side | ✅ | ✅ |
| **Cloud Run** | Serverless containers | Server-side | ✅ | ✅ |
| **GKE** | Kubernetes deployment | Server-side | ✅ | ✅ |

**Supported Google AI SDKs:**

| SDK | Package | Status | Environment Variable |
|-----|---------|--------|----------------------|
| **vertexai** | `google-cloud-aiplatform` | Legacy (default) | `GOOGLE_AI_SDK=vertexai` |
| **google-genai** | `google-genai` | Modern (recommended) | `GOOGLE_AI_SDK=google_genai` |

```bash
cd 3-agent-runtimes/gcp-vertex-ai-agent-engine
poetry install

# Choose SDK (optional, defaults to vertexai)
export GOOGLE_AI_SDK=google_genai  # Use modern SDK

# Agent Engine (local test)
./agent-engine-deploy/scripts/deploy.sh test

# Cloud Run (deploy to GCP)
./cloud-run-deploy/scripts/deploy.sh
./cloud-run-deploy/scripts/invoke.sh "Check service health"
./cloud-run-deploy/scripts/cleanup.sh  # Clean up

# GKE (deploy to GCP)
./gke-deploy/scripts/deploy.sh setup   # First time: create cluster
./gke-deploy/scripts/deploy.sh
./gke-deploy/scripts/invoke.sh "Check service health"
./gke-deploy/scripts/cleanup.sh        # Clean up

# Run all integration tests (6 tests: 3 deploy modes x 2 integration modes)
./tests/integration/test-all-modes.sh --verbose
```

### Runtime Integration Tests

```bash
cd 3-agent-runtimes

# Run all runtime tests (12 total: 6 per runtime)
./run-all-integration-tests.sh                          # All runtimes, all modes
./run-all-integration-tests.sh --quick                  # Direct/Agent Engine only
./run-all-integration-tests.sh --verbose                # Detailed output
./run-all-integration-tests.sh amazon-bedrock-agentcore # Specific runtime
./run-all-integration-tests.sh gcp-vertex-ai-agent-engine
```

---

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

#### AI Defense API (Required)

| Variable | Required | Description |
|----------|:--------:|-------------|
| `AI_DEFENSE_API_MODE_LLM_ENDPOINT` | Yes | AI Defense API endpoint |
| `AI_DEFENSE_API_MODE_LLM_API_KEY` | Yes | AI Defense API key |
| `AGENTSEC_API_MODE_LLM` | No | Mode: `on_enforce`, `on_monitor`, `off` (default: `on_monitor`) |
| `AGENTSEC_LLM_INTEGRATION_MODE` | No | Integration: `api`, `gateway` (default: `api`) |

#### AI Defense Gateway (For Gateway Mode)

| Variable | When Required | Description |
|----------|:-------------:|-------------|
| `AGENTSEC_OPENAI_GATEWAY_URL` | Gateway + OpenAI | OpenAI gateway URL |
| `AGENTSEC_OPENAI_GATEWAY_API_KEY` | Gateway + OpenAI | OpenAI gateway API key |
| `AGENTSEC_BEDROCK_GATEWAY_URL` | Gateway + Bedrock | Bedrock gateway URL |
| `AGENTSEC_BEDROCK_GATEWAY_API_KEY` | Gateway + Bedrock | Bedrock gateway API key |
| `AGENTSEC_VERTEXAI_GATEWAY_URL` | Gateway + Vertex | Vertex AI gateway URL |
| `AGENTSEC_VERTEXAI_GATEWAY_API_KEY` | Gateway + Vertex | Vertex AI gateway API key |

### Provider Credentials

<details>
<summary><strong>OpenAI</strong></summary>

```bash
OPENAI_API_KEY=sk-your-openai-api-key
```

</details>

<details>
<summary><strong>Azure OpenAI</strong></summary>

```bash
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-azure-openai-key
```

</details>

<details>
<summary><strong>AWS Bedrock</strong></summary>

```bash
# Option 1: Access keys
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1

# Option 2: Profile (recommended)
AWS_PROFILE=your-profile
AWS_REGION=us-east-1

# Option 3: SSO (interactive)
aws sso login
```

</details>

<details>
<summary><strong>GCP Vertex AI / Google GenAI</strong></summary>

```bash
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1

# Authenticate via gcloud CLI (ADC)
gcloud auth application-default login

# Choose SDK (optional)
GOOGLE_AI_SDK=google_genai  # Modern SDK (recommended)
# or
GOOGLE_AI_SDK=vertexai      # Legacy SDK (default)
```

</details>

### YAML Config (Agent Frameworks)

Each agent framework has config files in `config/`:

```yaml
# config/config-bedrock.yaml
provider: bedrock
bedrock:
  model_id: anthropic.claude-3-haiku-20240307-v1:0
  region: us-east-1
  auth:
    method: default  # or: profile, session_token, iam_role
```

Select config via flag:
```bash
./scripts/run.sh --bedrock   # Uses config/config-bedrock.yaml
./scripts/run.sh --azure     # Uses config/config-azure.yaml
./scripts/run.sh --vertex    # Uses config/config-vertex.yaml
./scripts/run.sh --openai    # Uses config/config-openai.yaml
```

---

## Testing

### Test Summary

| Category | Test Type | Test Count | What It Validates |
|----------|-----------|:----------:|-------------------|
| **Core SDK** | Unit | 392 | Patching, inspection, decisions, config |
| **Simple Examples** | Unit | ~10 | Example file structure, syntax |
| **Simple Examples** | Integration | 7 | Real API calls with AI Defense |
| **Agent Frameworks** | Unit | ~30 | Agent setup, provider config |
| **Agent Frameworks** | Integration | 24 | 6 frameworks x 4 providers |
| **AgentCore** | Unit | 53 | Deploy scripts, protection setup |
| **AgentCore** | Integration | 6 | 3 deploy modes x 2 integration modes |
| **Vertex AI** | Unit | ~30 | Deploy scripts, SDK selection |
| **Vertex AI** | Integration | 6 | 3 deploy modes x 2 integration modes |

### Run Tests

```bash
# From project root
cd /path/to/agentsec

# Core SDK unit tests (392 tests)
poetry run pytest tests/unit/ -v

# Simple examples
cd examples/1-simple
./run-all-integration-tests.sh

# Agent frameworks
cd examples/2-agent-frameworks
./run-all-integration-tests.sh --quick    # Fast: OpenAI only
./run-all-integration-tests.sh --verbose  # All providers

# Agent runtimes
cd examples/3-agent-runtimes
./run-all-integration-tests.sh --verbose  # All modes

# Example-specific unit tests
poetry run pytest examples/3-agent-runtimes/amazon-bedrock-agentcore/tests/unit/ -v
poetry run pytest examples/3-agent-runtimes/gcp-vertex-ai-agent-engine/tests/unit/ -v
```

---

## Integration Pattern

The standard pattern for integrating agentsec:

```python
# 1. Load environment variables
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

# 2. Enable protection BEFORE importing LLM clients
from aidefense.runtime import agentsec
agentsec.protect()

# 3. Import and use LLM clients normally - they're now protected
from openai import OpenAI
client = OpenAI()

# 4. All calls are inspected by AI Defense
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

**Key Rule**: Always call `agentsec.protect()` **before** importing LLM client libraries.

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: agentsec` | Run `poetry install` in the example directory |
| AWS auth fails | Run `aws sts get-caller-identity` to verify credentials |
| Azure 401 Unauthorized | Check endpoint format: `https://your-resource.openai.azure.com` |
| GCP auth fails | Run `gcloud auth application-default login` |
| OpenAI 401 Unauthorized | Verify key at https://platform.openai.com/api-keys |
| `SecurityPolicyError` raised | Expected in enforce mode when content violates policies |
| No inspection happening | Ensure `agentsec.protect()` is called BEFORE importing LLM clients |

### Debug Logging

Enable detailed logs to see what agentsec is doing:

```bash
export AGENTSEC_LOG_LEVEL=DEBUG
```

You'll see output like:

```
╔══════════════════════════════════════════════════════════════
║ [PATCHED] LLM CALL: gpt-4o-mini
║ Operation: OpenAI.chat.completions.create | Mode: enforce | Integration: api
╚══════════════════════════════════════════════════════════════
[agentsec.patchers.bedrock] DEBUG: Request inspection (1 messages)
[agentsec.inspectors.llm] DEBUG: AI Defense response: {'action': 'Allow', ...}
[agentsec.patchers.bedrock] DEBUG: Response inspection (response: 42 chars)
```

### Getting Help

- Check the individual example READMEs for detailed setup instructions
- Review the main [README.md](../README.md) for SDK configuration
- Enable DEBUG logging to trace inspection flow
