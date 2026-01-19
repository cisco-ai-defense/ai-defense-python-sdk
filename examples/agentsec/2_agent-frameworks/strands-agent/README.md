# Strands Agent Example with agentsec

A complete example demonstrating **agentsec** security integration with:
- **Multi-provider LLM support** using Strands' native models (no LiteLLM):
  - `BedrockModel` - AWS Bedrock
  - `OpenAIModel` - OpenAI and Azure OpenAI
  - `VertexAIModel` - GCP Vertex AI (via ADC)
- **MCP** tool integration (DeepWiki for GitHub repos)
- **AI Defense** inspection for both LLM and MCP calls
- Interactive and single-message modes

## Quick Start

```bash
# 1. Configure credentials in shared .env
# Edit ../../../.env with your API keys

# 2. Run (auto-setup on first run)
./scripts/run.sh
```

## Project Structure

```
strands-agent/
├── agent.py                    # Main agent script
├── scripts/
│   └── run.sh                  # Runner script (with auto-setup)
├── config/                     # Provider config files
│   ├── config.yaml             # Default config (Bedrock)
│   ├── config-bedrock.yaml     # AWS Bedrock config
│   ├── config-azure.yaml       # Azure OpenAI config
│   ├── config-vertex.yaml      # GCP Vertex AI config
│   └── config-openai.yaml      # OpenAI config
├── tests/
│   ├── unit/                   # Unit tests
│   │   └── test_strands_example.py
│   └── integration/            # Integration tests
│       └── test-all-providers.sh
├── pyproject.toml              # Poetry dependencies
└── README.md                   # This file

# Shared infrastructure (in ../_shared/)
../_shared/
├── .env                        # Common environment variables (secrets)
├── config.py                   # Config loading
└── providers/                  # Multi-provider implementations
```

## Usage

### Demo Mode (LLM + MCP tool call)
```bash
./scripts/run.sh
```

### Single Question
```bash
./scripts/run.sh "What is the capital of France?"
```

### With MCP Tool (DeepWiki)
```bash
./scripts/run.sh "What is the GIL in python/cpython?"
```

### Interactive Mode
```bash
./scripts/run.sh --interactive
```

### Force Re-setup
```bash
./scripts/run.sh --setup
```

## Provider Selection

```bash
# Use different LLM providers
./scripts/run.sh --provider bedrock   # AWS Bedrock
./scripts/run.sh --azure              # Azure OpenAI
./scripts/run.sh --vertex             # GCP Vertex AI
./scripts/run.sh --openai             # OpenAI

# List available providers
./scripts/run.sh --list-providers

# Quick test all providers
./scripts/run.sh --test-all
```

## Multi-Provider Configuration

Each provider has its own config file in the `config/` directory:

### AWS Bedrock (`config/config-bedrock.yaml`)

Auth Methods: `default`, `session_token`, `profile`, `iam_role`, `access_key`

```yaml
provider: bedrock
bedrock:
  model_id: anthropic.claude-3-haiku-20240307-v1:0
  region: us-east-1
  auth:
    method: default  # Uses AWS CLI credentials
```

### Azure OpenAI (`config/config-azure.yaml`)

Auth Methods: `api_key` (default), `managed_identity`, `service_principal`, `cli`

```yaml
provider: azure
azure:
  deployment_name: gpt-4o
  endpoint: ${AZURE_OPENAI_ENDPOINT}
  api_version: "2024-02-01"
  auth:
    method: api_key
    api_key: ${AZURE_OPENAI_API_KEY}
```

### GCP Vertex AI (`config/config-vertex.yaml`)

Auth Methods: `adc` (default), `service_account`, `workload_identity`, `impersonation`

```yaml
provider: vertex
vertex:
  model_id: gemini-2.5-flash-lite
  project_id: ${VERTEXAI_PROJECT}
  location: ${VERTEXAI_LOCATION:-us-central1}
  auth:
    method: adc  # Uses gcloud auth application-default login
```

### OpenAI (`config/config-openai.yaml`)

Auth Methods: `api_key`

```yaml
provider: openai
openai:
  model: gpt-4o-mini
  auth:
    method: api_key
    api_key: ${OPENAI_API_KEY}
```

## Environment Variables (`../../../.env`)

All agent examples share a common `.env` file in `../_shared/`:

```bash
# Cisco AI Defense (required for inspection)
AI_DEFENSE_API_MODE_LLM_ENDPOINT=https://your-ai-defense-endpoint/api
AI_DEFENSE_API_MODE_LLM_API_KEY=your-key-here

# MCP Server
MCP_SERVER_URL=https://mcp.deepwiki.com/mcp

# agentsec modes: off | monitor | enforce
AGENTSEC_API_MODE_LLM=on_monitor
AGENTSEC_API_MODE_MCP=on_monitor

# Fail-open behavior (allow requests if AI Defense is unreachable)
AGENTSEC_API_MODE_FAIL_OPEN_LLM=true
AGENTSEC_API_MODE_FAIL_OPEN_MCP=true

# Provider credentials (set based on which provider you use)
# AWS Bedrock - uses AWS CLI credentials by default

# Azure OpenAI
AZURE_OPENAI_API_KEY=your-azure-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com

# GCP Vertex AI (uses ADC - run: gcloud auth application-default login)
VERTEXAI_PROJECT=your-gcp-project
VERTEXAI_LOCATION=us-central1

# OpenAI
OPENAI_API_KEY=your-openai-key
```

## How It Works

1. **Shared .env is loaded** from `../../../.env`
2. **agentsec.protect()** is called BEFORE importing strands
3. It automatically sets up OpenTelemetry and patches clients
4. Each LLM call is sent to Cisco AI Defense for inspection
5. MCP tool calls are also inspected by AI Defense
6. AI Defense returns `allow`, `block`, or `sanitize` decisions
7. In `enforce` mode, blocked calls raise `SecurityPolicyError`

```python
# agent.py - Integration pattern
from pathlib import Path
from dotenv import load_dotenv

# Load shared .env
shared_env = Path(__file__).parent.parent / "_shared" / ".env"
if shared_env.exists():
    load_dotenv(shared_env)

from aidefense.runtime import agentsec
agentsec.protect()  # Patches clients

from strands import Agent  # Now imports are safe
```

### Native Strands Models (No LiteLLM)

This example uses **Strands' first-class native models** for each provider:

```python
# OpenAI
from strands.models.openai import OpenAIModel
model = OpenAIModel(
    client_args={"api_key": "sk-..."},
    model_id="gpt-4o-mini",
    params={"max_tokens": 4096, "temperature": 0.7},
)

# Azure OpenAI (via OpenAI-compatible endpoint)
from strands.models.openai import OpenAIModel
model = OpenAIModel(
    client_args={
        "api_key": "your-azure-key",
        "base_url": "https://<resource>.openai.azure.com/openai/deployments/<deployment>",
        "default_headers": {"api-key": "your-azure-key"},
        "default_query": {"api-version": "2024-02-01"},
    },
    model_id="gpt-4.1",
)

# GCP Vertex AI (uses Application Default Credentials)
from strands.models.vertexai import VertexAIModel
model = VertexAIModel(
    model_id="gemini-2.5-flash-lite",
    project="your-gcp-project",
    location="us-central1",
    params={"temperature": 0.7},
)

# AWS Bedrock (uses model_id string - Strands creates BedrockModel internally)
model = "anthropic.claude-3-haiku-20240307-v1:0"

# Create agent
agent = Agent(model=model, tools=[...])
```

### Patched Clients

When `agentsec.protect()` runs, it patches these clients:
- `openai` - OpenAI and Azure OpenAI calls
- `bedrock` - AWS Bedrock Converse API
- `vertexai` - GCP Vertex AI SDK
- `mcp` - MCP tool calls

## Security Modes

| Mode | Behavior |
|------|----------|
| `off` | No inspection, no patching |
| `monitor` | Inspect & log, never block |
| `enforce` | Inspect & block policy violations |

## Integration Tests

Run comprehensive tests across all 4 providers:

```bash
# Run all provider tests
./tests/integration/test-all-providers.sh

# Run with verbose output
./tests/integration/test-all-providers.sh --verbose

# Test specific provider(s)
./tests/integration/test-all-providers.sh openai
./tests/integration/test-all-providers.sh azure bedrock
```

### What's Tested

For each provider, the integration tests verify:

| Check | Description |
|-------|-------------|
| LLM Interception | LLM calls are intercepted by agentsec |
| MCP Tool Call | MCP tools are invoked and intercepted |
| AI Defense Decisions | AI Defense API returns allow/block decisions |
| No Errors | No Python exceptions, timeouts, or blocks |

### Expected Output

```
════════════════════════════════════════════════════════════════
  Strands Agent Integration Tests
════════════════════════════════════════════════════════════════

► openai:  ALL CHECKS PASSED (25s)
► azure:   ALL CHECKS PASSED (19s)
► vertex:  ALL CHECKS PASSED (19s)
► bedrock: ALL CHECKS PASSED (20s)

═══════════════════════════════════════════════════════════════
  ✓ ALL TESTS PASSED (4/4)
═══════════════════════════════════════════════════════════════
```

## Unit Tests

```bash
# Run from strands-agent directory with venv activated
source .venv/bin/activate
pytest aidefense/tests/agentsec/unit/ -v
```

## Example Output

```
[agentsec] LLM: monitor | MCP: monitor | Patched: ['openai', 'bedrock', 'vertexai', 'mcp']
[mcp] Connected! Tools: ['read_wiki_structure', 'read_wiki_contents', 'ask_question']
  Provider: openai | Model: gpt-4o-mini

============================================================
  Strands Agent + agentsec + MCP
============================================================

You: What is the GIL in python/cpython?

[agentsec.patchers.openai] ║ [PATCHED] LLM CALL (async): gpt-4o-mini
[agentsec.patchers.mcp] ║ [PATCHED] MCP TOOL CALL: ask_question

Agent: The GIL (Global Interpreter Lock) is a mutex that protects...
```

## Troubleshooting

**Provider credentials not found:**
```bash
# AWS - configure with CLI
aws configure

# Or use STS session token
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...
```

**AI Defense 401 error:**
- Check your `AI_DEFENSE_API_MODE_LLM_API_KEY` in `../../../.env`
- Ensure a policy is attached in AI Defense console

**AI Defense 400 error:**
- Check your `AI_DEFENSE_API_MODE_LLM_ENDPOINT` is correct
- Verify the endpoint URL doesn't have trailing slashes

**MCP connection failed:**
- Check `MCP_SERVER_URL` in `../../../.env`
- Verify MCP server is running and accessible

**GCP Vertex AI not being intercepted:**
- Ensure `google-cloud-aiplatform` package is installed
- Run `gcloud auth application-default login` to set up ADC
- The `vertexai` patcher handles Strands' VertexAIModel

**Virtual environment issues:**
```bash
# Force re-setup
./scripts/run.sh --setup
```
