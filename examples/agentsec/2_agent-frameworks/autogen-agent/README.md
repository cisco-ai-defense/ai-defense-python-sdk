# AutoGen Agent Example with agentsec Security

This example demonstrates how to build an AutoGen multi-agent conversation with **agentsec** security protection and MCP tool integration.

## Features

- **AutoGen Multi-Agent**: AssistantAgent + UserProxyAgent with native AG2 provider integrations (no LiteLLM)
- **agentsec Protection**: All LLM and MCP calls automatically inspected by Cisco AI Defense
- **MCP Tool Integration**: Connects to DeepWiki MCP server to query GitHub repositories
- **Multi-Provider Support**: OpenAI, Azure OpenAI, AWS Bedrock, GCP Vertex AI

## Quick Start

```bash
# From the autogen-agent directory
./scripts/run.sh

# Or with a specific question
./scripts/run.sh "What is the GIL in python/cpython?"
```

## Project Structure

```
autogen-agent/
├── agent.py                    # Main agent script
├── scripts/
│   └── run.sh                  # Runner script (with auto-setup)
├── config/                     # Provider config files
│   ├── config.yaml             # Default config
│   ├── config-bedrock.yaml     # AWS Bedrock config
│   ├── config-azure.yaml       # Azure OpenAI config
│   ├── config-vertex.yaml      # GCP Vertex AI config
│   └── config-openai.yaml      # OpenAI config
├── tests/
│   ├── unit/                   # Unit tests
│   │   └── test_autogen_example.py
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
# Use different LLM providers
./scripts/run.sh --provider openai    # OpenAI (default)
./scripts/run.sh --azure              # Azure OpenAI
./scripts/run.sh --bedrock            # AWS Bedrock
./scripts/run.sh --vertex             # GCP Vertex AI

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

# Provider-specific credentials (set based on provider)
# OpenAI
OPENAI_API_KEY=your-openai-key

# Azure OpenAI
AZURE_OPENAI_API_KEY=your-azure-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com

# AWS Bedrock - uses AWS CLI credentials by default
# Or set:
# AWS_ACCESS_KEY_ID=your-access-key
# AWS_SECRET_ACCESS_KEY=your-secret-key

# GCP Vertex AI
VERTEXAI_PROJECT=your-gcp-project
VERTEXAI_LOCATION=us-central1
```

## Multi-Provider Support

This example supports 4 LLM providers using **AG2's native integrations** (no LiteLLM):

| Provider | AG2 api_type | Installation | Config File |
|----------|--------------|--------------|-------------|
| OpenAI | (default) | `ag2[openai]` | `config/config-openai.yaml` |
| Azure OpenAI | `azure` | `ag2[openai]` | `config/config-azure.yaml` |
| AWS Bedrock | `bedrock` | `ag2[bedrock]` | `config/config-bedrock.yaml` |
| GCP Vertex AI | `vertex_ai` | `ag2[vertexai]` | `config/config-vertex.yaml` |

### LLM Inspection

All LLM calls are automatically intercepted by `agentsec.protect()`:
- **OpenAI**: Patched via OpenAI client
- **Azure OpenAI**: Patched via OpenAI client (Azure mode)
- **Bedrock**: Patched via boto3 client
- **Vertex AI**: Patched via Vertex AI SDK

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

# NOW import AutoGen
from autogen import ConversableAgent, AssistantAgent, UserProxyAgent, LLMConfig
```

**What `protect()` Does Automatically:**
- Sets up OpenTelemetry TracerProvider
- Reads config from environment variables
- Patches all LLM clients

### 2. Native AG2 Provider Configuration
AG2/AutoGen has native integrations for all providers via `LLMConfig`:

```python
from autogen import LLMConfig

# OpenAI
llm_config = LLMConfig(config_list=[{
    'model': 'gpt-4o-mini',
    'api_key': 'sk-...',
}])

# Azure OpenAI
llm_config = LLMConfig(config_list=[{
    'model': 'gpt-4.1',  # deployment name
    'api_type': 'azure',
    'api_key': '...',
    'base_url': 'https://<resource>.openai.azure.com',
    'api_version': '2024-02-01',
}])

# AWS Bedrock (requires ag2[bedrock])
llm_config = LLMConfig(config_list=[{
    'model': 'anthropic.claude-3-haiku-20240307-v1:0',
    'api_type': 'bedrock',
    'aws_region': 'us-east-1',
}])

# GCP Vertex AI (requires ag2[vertexai])
llm_config = LLMConfig(config_list=[{
    'model': 'gemini-2.5-flash-lite',
    'api_type': 'vertex_ai',
    'project': 'your-gcp-project',
    'location': 'us-central1',
}])
```

### 3. Multi-Agent Conversation
```python
assistant = AssistantAgent(
    name="assistant",
    llm_config=llm_config,
    system_message="...",
)

user_proxy = UserProxyAgent(
    name="user_proxy",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=3,
)

# Register tools
@user_proxy.register_for_execution()
@assistant.register_for_llm(description="Ask DeepWiki about a GitHub repo")
def deepwiki_tool(repo_name: str, question: str) -> str:
    return ask_deepwiki(repo_name, question)

# Start conversation
chat_result = user_proxy.initiate_chat(assistant, message="Your question")
```

### 4. MCP Tool Integration
The `ask_deepwiki` function connects to DeepWiki MCP server:
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
# From the autogen-agent directory
pytest aidefense/tests/agentsec/unit/ -v

# Or from the project root
pytest examples/agentsec/2_agent-frameworks/autogen-agent/tests/unit/ -v
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
5. ✅ Agent produces final response

## Troubleshooting

### "OPENAI_API_KEY not configured"
Edit `../../../.env` and add your OpenAI API key.

### "No module named 'autogen'"
Install AG2 with required extras:
```bash
pip install ag2[openai,bedrock,vertexai]
```

### Bedrock credentials not found
```bash
# Configure AWS CLI
aws configure

# Or use environment variables
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
```

### MCP Connection Failed
Verify `MCP_SERVER_URL` is correct and the server is accessible.

### Security Policy Blocked
If running in `on_enforce` mode, adjust `AGENTSEC_API_MODE_LLM=on_monitor` for development.

## Related Examples

- [strands-agent](../strands-agent/) - AWS Strands Agents example
- [langgraph-agent](../langgraph-agent/) - LangGraph example
- [openai-agent](../openai-agent/) - OpenAI example
- [crewai-agent](../crewai-agent/) - CrewAI example

## License

See the main project LICENSE file.
