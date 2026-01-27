# LangChain Agent Example with agentsec

A complete example demonstrating **agentsec** security integration with:
- **Modern LangChain 1.0+ pattern** (LCEL + native tool calling)
- **Multi-provider LLM support** (AWS Bedrock, Azure OpenAI, GCP Vertex AI, OpenAI)
- **LLM and MCP patching** for automatic security inspection
- **MCP** tool integration (fetch_url for web content)
- Interactive and single-message modes

> **Note:** This example uses the **modern LangChain 1.0+ approach** with LCEL (LangChain Expression Language) and native tool calling via `llm.bind_tools()`. This is different from the **LangGraph-based agents** (see `langgraph-agent/` for state graph patterns).

## Quick Start

```bash
# Run with auto-setup (first run will set up environment automatically)
./scripts/run.sh

# Or run with a specific question
./scripts/run.sh "What is the GIL in python/cpython?"

# Interactive mode
./scripts/run.sh --interactive

# Force re-setup
./scripts/run.sh --setup
```

## Project Structure

```
langchain-agent/
├── agent.py                    # Main agent script (LCEL + tool calling)
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
│   │   └── test_langchain_example.py
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

## LangChain vs LangGraph

This example uses the **modern LangChain 1.0+ pattern**:

| Pattern | This Example | LangGraph Example |
|---------|-------------|-------------------|
| Approach | LCEL + `llm.bind_tools()` | `create_react_agent()` from `langgraph.prebuilt` |
| Execution | Simple agentic loop | `agent.ainvoke()` with state graph |
| Messages | `HumanMessage`, `AIMessage`, `ToolMessage` | Full state graph with message history |
| State | In-memory conversation | Full state graph with persistence |
| Use Case | Simple agents, prototyping | Production agents with persistence |

## Usage

### Demo Mode (Default)
```bash
# Runs with default question that triggers LLM + MCP tool call
./scripts/run.sh
```

### Interactive Mode
```bash
./scripts/run.sh --interactive
# or
./scripts/run.sh -i
```

### Single Question
```bash
./scripts/run.sh "What is the capital of France?"
```

### With MCP Tool
```bash
./scripts/run.sh "Fetch https://example.com and tell me what it's for"
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

### Environment Variables (`../_shared/.env`)

All agent examples share a common `.env` file in `../_shared/`:

```bash
# Cisco AI Defense (required for inspection)
AI_DEFENSE_API_MODE_LLM_ENDPOINT=https://preview.api.inspect.aidefense.aiteam.cisco.com/api
AI_DEFENSE_API_MODE_LLM_API_KEY=your-key-here

# MCP Server (optional)
MCP_SERVER_URL=https://mcp.deepwiki.com/mcp

# agentsec mode: off | on_monitor | on_enforce
AGENTSEC_API_MODE_LLM=on_monitor
AGENTSEC_API_MODE_MCP=on_monitor

# Provider-specific credentials (set based on provider)
# AWS Bedrock
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_SESSION_TOKEN=your-session-token

# Azure OpenAI
AZURE_OPENAI_API_KEY=your-azure-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com

# GCP Vertex AI (uses ADC - run: gcloud auth application-default login)
GOOGLE_CLOUD_PROJECT=your-gcp-project
GOOGLE_CLOUD_LOCATION=us-central1

# OpenAI
OPENAI_API_KEY=your-openai-key
```

## Multi-Provider Support

This example supports 4 LLM providers. LangChain adapters are used automatically:

| Provider | LangChain Class | Config File |
|----------|-----------------|-------------|
| AWS Bedrock | `ChatBedrock` | `config/config-bedrock.yaml` |
| Azure OpenAI | `AzureChatOpenAI` | `config/config-azure.yaml` |
| GCP Vertex AI | `ChatVertexAI` | `config/config-vertex.yaml` |
| OpenAI | `ChatOpenAI` | `config/config-openai.yaml` |

See the [examples README](../../README.md) for full authentication method documentation.

## How It Works

1. **Shared .env is loaded** from `../_shared/.env`
2. **agentsec.protect()** is called BEFORE importing LangChain
3. It automatically patches all LLM clients for security inspection
4. Each LLM call is sent to Cisco AI Defense for inspection
5. AI Defense returns `allow`, `block`, or `sanitize` decisions
6. In `enforce` mode, blocked calls raise `SecurityPolicyError`

```python
# agent.py - Integration pattern
from pathlib import Path
from dotenv import load_dotenv

# Load shared .env
shared_env = Path(__file__).parent.parent / "_shared" / ".env"
if shared_env.exists():
    load_dotenv(shared_env)

from aidefense.runtime import agentsec
agentsec.protect()  # Patches LLM clients for AI Defense inspection

# Modern LangChain imports (after protect())
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage

# Define tools
@tool
def fetch_url(url: str) -> str:
    """Fetch URL contents."""
    ...

# Bind tools to LLM (modern LangChain 1.0+ pattern)
llm_with_tools = llm.bind_tools([fetch_url])

# Invoke with messages - inspection is automatic
response = llm_with_tools.invoke([HumanMessage(content="Hello")])
```

### What `protect()` Does Automatically
- Loads `.env` file (if python-dotenv installed)
- Reads config from environment variables
- Patches all LLM clients (Bedrock, OpenAI, etc.)

## Security Modes

| Mode | Behavior |
|------|----------|
| `off` | No inspection, no patching |
| `on_monitor` | Inspect & log, never block |
| `on_enforce` | Inspect & block policy violations |

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
═══════════════════════════════════════════════════════════════
  ✓ ALL TESTS PASSED (4/4)
═══════════════════════════════════════════════════════════════

  openai:  ALL CHECKS PASSED
  azure:   ALL CHECKS PASSED
  vertex:  ALL CHECKS PASSED
  bedrock: ALL CHECKS PASSED
```

## Unit Tests

```bash
# From the langchain-agent directory
source .venv/bin/activate
pytest tests/unit/ -v
```

## Example Output

```
[DEBUG] Loading environment...
[DEBUG] Calling agentsec.protect()...
[agentsec] LLM: monitor | MCP: monitor | Patched: ['bedrock', 'mcp']
[mcp] Connected! Tools: ['fetch']
[agent] Creating LLM with model: anthropic.claude-3-haiku-20240307-v1:0

============================================================
  LangChain Agent + agentsec + MCP
  (Modern LCEL + Tool Calling Pattern)
============================================================

You: Fetch https://example.com and tell me what it's for
[TOOL CALL] fetch_url(url='https://example.com')
[TOOL] Got response (1234 chars) in 2.3s
Agent: Based on the content I fetched, example.com is...
```

## Troubleshooting

**AWS credentials not found:**
```bash
aws sso login
# or
aws configure
```

**AI Defense 401 error:**
- Check your API key in `../_shared/.env`
- Ensure a policy is attached in AI Defense console

**MCP connection failed:**
- Check `MCP_SERVER_URL` in `../_shared/.env`
- Verify MCP server is running

**LangChain import errors:**
- Ensure langchain is installed: `pip install langchain langchain-core langchain-openai`
- Check Python version is 3.10+
- LangChain 1.0+ is required for the modern tool calling pattern

**LangChain vs LangGraph confusion:**
- This example uses pure LangChain with `llm.bind_tools()` (modern pattern)
- See `langgraph-agent/` for the LangGraph state graph approach
