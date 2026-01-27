# CrewAI Agent Example with agentsec Security

This example demonstrates how to build a CrewAI multi-agent crew with **agentsec** security protection and MCP tool integration.

## Features

- **CrewAI Multi-Agent**: 2-agent crew (Researcher + Writer) collaboration
- **agentsec Protection**: All LLM and MCP calls automatically inspected by Cisco AI Defense
- **MCP Tool Integration**: Connects to DeepWiki MCP server to query GitHub repositories
- **Multi-Provider Support**: AWS Bedrock, Azure OpenAI, GCP Vertex AI, OpenAI (all using CrewAI's native integrations - no LiteLLM)

## Quick Start

```bash
# From the crewai-agent directory
./scripts/run.sh

# Or with a specific question
./scripts/run.sh "What is the GIL in python/cpython?"
```

## Project Structure

```
crewai-agent/
├── agent.py                    # Main crew script
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
│   │   └── test_crewai_example.py
│   └── integration/            # Integration tests
│       ├── test-all-providers.sh  # Tests all 4 providers
│       └── logs/               # Test logs
├── pyproject.toml              # Poetry dependencies
└── README.md                   # This file

# Shared infrastructure (in ../_shared/)
../_shared/
├── .env                        # Common environment variables (secrets)
├── config.py                   # Config loading
└── providers/                  # Multi-provider implementations
```

## Usage

### Demo Mode (Default)
Runs a default question that triggers both LLM and MCP tool calls:
```bash
./scripts/run.sh
```

### Single Question
```bash
./scripts/run.sh "Your question here"
```

### Interactive Mode
```bash
./scripts/run.sh --interactive
```

### Force Re-setup
```bash
./scripts/run.sh --setup
```

## Configuration

### Quick Provider Switch

```bash
# Use different LLM providers
./scripts/run.sh --provider bedrock   # AWS Bedrock (default)
./scripts/run.sh --azure              # Azure OpenAI
./scripts/run.sh --vertex             # GCP Vertex AI
./scripts/run.sh --openai             # OpenAI

# List all available providers
./scripts/run.sh --list-providers

# Test all providers
./scripts/run.sh --test-all
```

### Environment Variables (`../../../.env`)

All agent examples share a common `.env` file in `../_shared/`:

```bash
# Cisco AI Defense
AI_DEFENSE_API_MODE_LLM_ENDPOINT=https://preview.api.inspect.aidefense.aiteam.cisco.com/api
AI_DEFENSE_API_MODE_LLM_API_KEY=your-api-key

# MCP Server (auto-configured if not set)
MCP_SERVER_URL=https://mcp.deepwiki.com/mcp

# agentsec Configuration
AGENTSEC_API_MODE_LLM=on_monitor
AGENTSEC_API_MODE_MCP=on_monitor
AGENTSEC_API_MODE_FAIL_OPEN_LLM=true
AGENTSEC_LOG_LEVEL=DEBUG

# Provider-specific credentials (set based on provider)
# AWS Bedrock
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_SESSION_TOKEN=your-session-token

# Azure OpenAI
AZURE_OPENAI_API_KEY=your-azure-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com

# GCP Vertex AI
GOOGLE_CLOUD_PROJECT=your-gcp-project
GOOGLE_CLOUD_LOCATION=us-central1

# OpenAI
OPENAI_API_KEY=your-openai-key
```

## Multi-Provider Support

This example supports 4 LLM providers using **CrewAI's native integrations** (no LiteLLM):

| Provider | CrewAI Integration | Default Auth | Config File |
|----------|-------------------|--------------|-------------|
| AWS Bedrock | Native (boto3 Converse API) | AWS CLI (`default`) | `config/config-bedrock.yaml` |
| Azure OpenAI | Native (`crewai[azure-ai-inference]`) | API Key | `config/config-azure.yaml` |
| GCP Vertex AI | Native | API Key | `config/config-vertex.yaml` |
| OpenAI | Native | API Key | `config/config-openai.yaml` |

### LLM Inspection

All LLM calls are automatically intercepted by `agentsec.protect()`:
- **Bedrock**: Patched via boto3 client (Converse API)
- **Azure OpenAI**: Patched via OpenAI client (Azure mode)
- **GCP Vertex AI**: Patched via Vertex AI SDK
- **OpenAI**: Patched via OpenAI client

See the [examples README](../../README.md) for full authentication method documentation.

### agentsec Modes

| Mode | Behavior |
|------|----------|
| `off` | No inspection, no patching |
| `monitor` | Inspect & log, never block (recommended for testing) |
| `on_enforce` | Inspect & block policy violations |

## How It Works

### 1. agentsec Protection (Just 2 Lines!)
```python
# Load shared .env
from pathlib import Path
from dotenv import load_dotenv
shared_env = Path(__file__).parent.parent / "_shared" / ".env"
if shared_env.exists():
    load_dotenv(shared_env)

# Minimal integration - agentsec handles everything!
from aidefense.runtime import agentsec
agentsec.protect()  # Sets up OTEL, patches clients

# NOW import CrewAI
from crewai import Agent, Task, Crew, LLM
```

**What `protect()` Does Automatically:**
- Sets up OpenTelemetry TracerProvider
- Reads config from environment variables
- Patches all LLM clients (including Bedrock via boto3)

### 2. Native LLM Configuration
CrewAI has native integrations for all major providers. Examples:

```python
from crewai import LLM

# AWS Bedrock (native boto3 Converse API)
llm = LLM(model="bedrock/anthropic.claude-3-haiku-20240307-v1:0", temperature=0.7)

# OpenAI (native)
llm = LLM(model="gpt-4o-mini", api_key="your-key", temperature=0.7)

# Azure OpenAI (native, requires crewai[azure-ai-inference])
llm = LLM(
    model="azure/gpt-4.1",
    api_key="your-azure-key",
    base_url="https://<resource>.openai.azure.com/openai/deployments/<deployment>",
    api_version="2024-02-15-preview",
    temperature=0.7,
)

# GCP Vertex AI (native, uses ADC)
llm = LLM(
    model="vertex_ai/gemini-2.5-flash-lite",
    vertex_project="your-gcp-project",
    vertex_location="us-central1",
    temperature=0.7,
)

researcher = Agent(
    role="Technical Researcher",
    llm=llm,  # Pass the configured LLM
    ...
)
```

### 3. Multi-Agent Crew
The crew consists of two agents:
- **Researcher**: Queries DeepWiki for technical information
- **Writer**: Summarizes research into clear explanations

### 4. MCP Tool Integration
The `ask_deepwiki` function connects to DeepWiki MCP server to query GitHub repositories:
```python
def ask_deepwiki(repo_name: str, question: str) -> str:
    # Calls MCP server - intercepted by agentsec
    result = await session.call_tool('ask_question', {...})
    return result
```

## Example Output

When running the demo, you'll see agentsec intercepting both MCP and LLM calls:

```
╔══════════════════════════════════════════════════════════════
║ [PATCHED] MCP TOOL CALL: ask_question
║ Arguments: {'repoName': 'python/cpython', 'question': 'What is the GIL...'}
║ Mode: monitor
╚══════════════════════════════════════════════════════════════
[agentsec.inspectors.mcp] DEBUG: MCP request intercepted: tool=ask_question, allowing by default

╔══════════════════════════════════════════════════════════════
║ [PATCHED] LLM CALL: anthropic.claude-3-haiku-20240307-v1:0
║ Operation: Bedrock.Converse | Mode: monitor
╚══════════════════════════════════════════════════════════════
[agentsec.inspectors.llm] DEBUG: AI Defense request payload: messages=2, metadata_keys=['model_id']
```

## Testing

### Unit Tests
```bash
# From the crewai-agent directory
pytest tests/unit/ -v

# Or from the project root
pytest examples/2-agent-frameworks/crewai-agent/tests/unit/ -v
```

### Integration Tests

The integration tests verify all 4 providers work correctly with AI Defense:

```bash
# Run all provider tests
./tests/integration/test-all-providers.sh

# Test specific provider
./tests/integration/test-all-providers.sh openai
./tests/integration/test-all-providers.sh azure
./tests/integration/test-all-providers.sh vertex
./tests/integration/test-all-providers.sh bedrock

# Verbose mode
./tests/integration/test-all-providers.sh --verbose
```

The integration tests check:
1. ✅ LLM calls intercepted by AI Defense
2. ✅ MCP tool calls executed and intercepted
3. ✅ AI Defense decisions received
4. ✅ No critical errors in output
5. ✅ Crew produces final response

## Troubleshooting

### "AWS credentials not configured or expired"
Run `aws configure` or `aws sso login` to set up/refresh credentials.

### "ExpiredTokenException"
Your AWS session token has expired. Refresh with:
```bash
aws sso login
```

### "Azure AI Inference native provider not available"
Install the Azure extra:
```bash
pip install "crewai[azure-ai-inference]"
```

### "OPENAI_API_KEY is required"
This error occurs if the LLM is not explicitly configured. Make sure to pass the API key:
```python
llm = LLM(model="gpt-4o-mini", api_key="your-key")
```

### MCP Connection Failed
Verify `MCP_SERVER_URL` is correct and the server is accessible. The script auto-configures DeepWiki if not set.

### Security Policy Blocked
If running in `on_enforce` mode, adjust `AGENTSEC_API_MODE_LLM=on_monitor` for development.

## Related Examples

- [strands-agent](../strands-agent/) - AWS Strands Agents example
- [langgraph-agent](../langgraph-agent/) - LangGraph example
- [openai-agent](../openai-agent/) - OpenAI example
- [autogen-agent](../autogen-agent/) - AutoGen example

## License

See the main project LICENSE file.
