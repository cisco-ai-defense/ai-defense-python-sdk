# Runtime Protection Examples (agentsec)

Examples demonstrating the runtime protection SDK for securing AI agents with Cisco AI Defense.

## Quick Start

```bash
# 1. Copy and configure environment
cp .env.example .env
# Edit .env with your Cisco AI Defense credentials and provider API keys

# 2. Run a simple example
cd 1_simple
poetry install
poetry run python basic_protection.py

# 3. Or run an agent example
cd 2_agent-frameworks/strands-agent
poetry install
poetry run python agent.py
# Or use the run script:
./scripts/run.sh
```

## Directory Structure

```
examples/
├── .env                         # Your credentials (gitignored)
├── .env.example                 # Template - copy to .env
├── 1_simple/                    # Standalone examples (no agent framework)
│   ├── basic_protection.py      # Minimal setup - modes, patched clients
│   ├── openai_example.py        # OpenAI client with inspection
│   ├── streaming_example.py     # Streaming responses
│   ├── mcp_example.py           # MCP tool call inspection
│   ├── gateway_mode_example.py  # Gateway mode configuration
│   ├── skip_inspection_example.py  # Per-call exclusion
│   └── simple_strands_bedrock.py   # Strands + Bedrock
└── 2_agent-frameworks/          # Agent framework examples
    ├── strands-agent/           # AWS Strands SDK
    ├── langgraph-agent/         # LangGraph (state graph pattern)
    ├── langchain-agent/         # LangChain (LCEL + tool calling)
    ├── crewai-agent/            # CrewAI
    ├── openai-agent/            # OpenAI Agents SDK
    └── autogen-agent/           # AutoGen
```

## Simple Examples

Standalone examples demonstrating core runtime protection features without agent frameworks.

| Example | Description |
|---------|-------------|
| `basic_protection.py` | Minimal setup - modes (enforce/monitor/off), checking patched clients |
| `openai_example.py` | OpenAI client with automatic inspection of chat completions |
| `mcp_example.py` | MCP tool call inspection (request & response) with DeepWiki |
| `streaming_example.py` | Streaming responses with real-time chunk inspection |
| `gateway_mode_example.py` | Using Gateway mode instead of API mode |
| `skip_inspection_example.py` | Skip inspection for specific calls using context manager/decorator |
| `simple_strands_bedrock.py` | Strands agent with Bedrock Claude model and AI Defense protection |

```bash
cd 1_simple
poetry install  # First time only
poetry run python basic_protection.py
poetry run python openai_example.py
poetry run python mcp_example.py
poetry run python streaming_example.py
poetry run python gateway_mode_example.py
poetry run python skip_inspection_example.py
poetry run python simple_strands_bedrock.py
```

### Modes

| Mode | Behavior |
|------|----------|
| `off` | No inspection, no patching |
| `on_monitor` | Inspect & log, never block |
| `on_enforce` | Inspect & block policy violations |

## Agent Examples

All agent examples support multiple LLM providers:

| Provider | Flag | Auth Methods |
|----------|------|--------------|
| AWS Bedrock | `--bedrock` | default, session_token, profile, iam_role |
| Azure OpenAI | `--azure` | api_key, managed_identity, cli |
| GCP Vertex | `--vertex` | api_key, adc, service_account |
| OpenAI | `--openai` | api_key |

```bash
# Run with default provider
./2_agent-frameworks/strands-agent/scripts/run.sh

# Run with specific provider
./2_agent-frameworks/strands-agent/scripts/run.sh --bedrock
./2_agent-frameworks/langgraph-agent/scripts/run.sh --azure
./2_agent-frameworks/crewai-agent/scripts/run.sh --vertex
./2_agent-frameworks/openai-agent/scripts/run.sh --openai
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Required | Description |
|----------|----------|-------------|
| `AI_DEFENSE_API_MODE_LLM_API_KEY` | Yes | Cisco AI Defense API key |
| `AGENTSEC_API_MODE_LLM` | No | Mode: `enforce`, `monitor`, `off` |
| `AGENTSEC_API_MODE_MCP` | No | MCP mode: `enforce`, `monitor`, `off` |

Provider credentials (set based on which providers you use):

| Provider | Variables |
|----------|-----------|
| OpenAI | `OPENAI_API_KEY` |
| Azure | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT` |
| AWS Bedrock | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` (or use `aws sso login`) |
| GCP Vertex AI | `GOOGLE_APPLICATION_CREDENTIALS` or use `gcloud auth application-default login` (ADC) |

### YAML Config (Agents)

Each agent has config files in `config/`:

```yaml
# config/config-bedrock.yaml
provider: bedrock
bedrock:
  model_id: anthropic.claude-3-haiku-20240307-v1:0
  region: us-east-1
  auth:
    method: default
```

Select config via flag or environment:
```bash
./scripts/run.sh --bedrock
# or
CONFIG_FILE=config/config-azure.yaml python agent.py
```

## Testing

```bash
# Run all agent integration tests
cd 2_agent-frameworks
./run-all-integration-tests.sh              # All frameworks, all providers
./run-all-integration-tests.sh --quick      # OpenAI only (faster)
./run-all-integration-tests.sh --verbose    # With detailed output

# Run specific framework
./run-all-integration-tests.sh strands langgraph langchain

# Run simple examples tests
cd 1_simple/tests/integration
./test-simple-examples.sh

# Run unit tests (from project root)
cd ../..
poetry run pytest
```

## Integration Pattern

```python
# 1. Load environment
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

# 2. Enable protection BEFORE other imports
from aidefense.runtime import agentsec
agentsec.protect()

# 3. Use your LLM client normally - it's now protected
from openai import OpenAI
client = OpenAI()
response = client.chat.completions.create(...)
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| AWS auth fails | Run `aws sts get-caller-identity` to verify credentials |
| Azure 401 | Check endpoint format: `https://your-resource.openai.azure.com` |
| GCP auth fails | Run `gcloud auth application-default login` |
| OpenAI 401 | Verify key at https://platform.openai.com/api-keys |
