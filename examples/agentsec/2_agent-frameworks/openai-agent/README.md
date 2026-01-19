# OpenAI Agent Example with agentsec Security

This example demonstrates how to build an OpenAI agent with **agentsec** security protection and MCP tool integration using the native OpenAI SDK.

## Features

- **OpenAI SDK**: Direct use of the OpenAI Python SDK (no LiteLLM)
- **agentsec Protection**: All LLM and MCP calls automatically inspected by Cisco AI Defense
- **MCP Tool Integration**: Connects to DeepWiki MCP server to query GitHub repositories
- **Provider Support**: OpenAI and Azure OpenAI only (OpenAI SDK limitation)

> **Note**: This example uses the OpenAI SDK directly, which only supports OpenAI and Azure OpenAI. For other providers (Bedrock, Vertex AI), see `strands-agent`, `crewai-agent`, or `autogen-agent`.

## Quick Start

```bash
# From the openai-agent directory
./scripts/run.sh

# Or with a specific question
./scripts/run.sh "What is the GIL in python/cpython?"
```

## Project Structure

```
openai-agent/
├── agent.py                    # Main agent script
├── scripts/
│   └── run.sh                  # Runner script (with auto-setup)
├── config/                     # Provider config files
│   ├── config.yaml             # Default config (OpenAI)
│   ├── config-openai.yaml      # OpenAI config
│   └── config-azure.yaml       # Azure OpenAI config
├── tests/
│   ├── unit/                   # Unit tests
│   │   └── test_openai_example.py
│   └── integration/            # Integration tests
│       ├── test-all-providers.sh
│       └── logs/
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
# OpenAI (default)
./scripts/run.sh --provider openai

# Azure OpenAI
./scripts/run.sh --azure

# List all available providers
./scripts/run.sh --list-providers

# Test all providers
./scripts/run.sh --test-all
```

### Environment Variables (`../../../.env`)

All agent examples share a common `.env` file in `../_shared/`:

```bash
# Cisco AI Defense
AI_DEFENSE_API_MODE_LLM_ENDPOINT=https://your-ai-defense-endpoint/api
AI_DEFENSE_API_MODE_LLM_API_KEY=your-api-key

# MCP Server (auto-configured if not set)
MCP_SERVER_URL=https://mcp.deepwiki.com/mcp

# agentsec Configuration
AGENTSEC_API_MODE_LLM=on_monitor
AGENTSEC_API_MODE_MCP=on_monitor
AGENTSEC_API_MODE_FAIL_OPEN_LLM=true
AGENTSEC_LOG_LEVEL=DEBUG

# Provider-specific credentials
# OpenAI
OPENAI_API_KEY=your-openai-key

# Azure OpenAI
AZURE_OPENAI_API_KEY=your-azure-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
```

## Provider Support

This example only supports **OpenAI SDK-compatible providers**:

| Provider | Config File | Notes |
|----------|-------------|-------|
| OpenAI | `config/config-openai.yaml` | Default |
| Azure OpenAI | `config/config-azure.yaml` | Uses OpenAI SDK with Azure endpoint |

### Why Limited Providers?

The OpenAI SDK is designed specifically for OpenAI and Azure OpenAI. For other providers:

| Provider | Recommended Example |
|----------|---------------------|
| AWS Bedrock | `strands-agent`, `crewai-agent`, `autogen-agent` |
| GCP Vertex AI | `strands-agent`, `crewai-agent`, `autogen-agent` |

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

# NOW import OpenAI
from openai import OpenAI
```

**What `protect()` Does Automatically:**
- Sets up OpenTelemetry TracerProvider
- Reads config from environment variables
- Patches OpenAI client for LLM inspection

### 2. OpenAI Client Configuration
```python
from openai import OpenAI, AzureOpenAI

# OpenAI
client = OpenAI(api_key="sk-...")

# Azure OpenAI
client = AzureOpenAI(
    api_key="...",
    api_version="2024-02-01",
    azure_endpoint="https://<resource>.openai.azure.com",
)
```

### 3. Function Calling with Tools
```python
TOOLS = [{
    "type": "function",
    "function": {
        "name": "ask_deepwiki",
        "description": "Ask about a GitHub repository",
        "parameters": {
            "type": "object",
            "properties": {
                "repo_name": {"type": "string"},
                "question": {"type": "string"}
            },
            "required": ["repo_name", "question"]
        }
    }
}]

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages,
    tools=TOOLS,
)
```

## Example Output

When running the demo, you'll see agentsec intercepting both MCP and LLM calls:

```
╔══════════════════════════════════════════════════════════════
║ [PATCHED] MCP TOOL CALL: ask_question
║ Arguments: {'repoName': 'python/cpython', 'question': 'What is the GIL?'}
║ Mode: monitor
╚══════════════════════════════════════════════════════════════
[TOOL] Got response (3693 chars) in 12.2s

╔══════════════════════════════════════════════════════════════
║ [PATCHED] LLM CALL: gpt-4o-mini
║ Operation: OpenAI.chat.completions.create | Mode: monitor
╚══════════════════════════════════════════════════════════════
```

## Testing

### Unit Tests
```bash
# From the openai-agent directory
pytest aidefense/tests/agentsec/unit/ -v

# Or from the project root
pytest examples/agentsec/2_agent-frameworks/openai-agent/tests/unit/ -v
```

### Integration Tests

The integration tests verify OpenAI and Azure work correctly with AI Defense:

```bash
# Run all provider tests
./tests/integration/test-all-providers.sh

# Test specific provider
./tests/integration/test-all-providers.sh openai
./tests/integration/test-all-providers.sh azure

# Verbose mode
./tests/integration/test-all-providers.sh --verbose
```

The integration tests check:
1. ✅ LLM calls intercepted by AI Defense
2. ✅ MCP tool calls executed and intercepted
3. ✅ AI Defense decisions received
4. ✅ No critical errors in output
5. ✅ Agent produces final response

## Troubleshooting

### "OPENAI_API_KEY not configured"
Edit `../../../.env` and add your OpenAI API key.

### Azure authentication error
Ensure `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_API_KEY` are set in `../../../.env`.

### MCP Connection Failed
Verify `MCP_SERVER_URL` is correct and the server is accessible.

### Security Policy Blocked
If running in `on_enforce` mode, adjust `AGENTSEC_API_MODE_LLM=on_monitor` for development.

### "Provider not supported"
This example only supports OpenAI and Azure OpenAI. For Bedrock or Vertex AI, use:
- `strands-agent`
- `crewai-agent`
- `autogen-agent`

## Related Examples

- [strands-agent](../strands-agent/) - AWS Strands (Bedrock, OpenAI, Azure, Vertex AI)
- [langgraph-agent](../langgraph-agent/) - LangGraph (all providers)
- [crewai-agent](../crewai-agent/) - CrewAI (all providers)
- [autogen-agent](../autogen-agent/) - AutoGen (all providers)

## License

See the main project LICENSE file.
