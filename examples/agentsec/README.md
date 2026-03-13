# agentsec Examples

**agentsec** accelerates your integration with **Cisco AI Defense** when building AI applications using:

- **Chat Completions** - Direct LLM calls (OpenAI, Azure, Bedrock, Vertex AI, Cohere, Mistral, LiteLLM)
- **Agentic Frameworks** - LangChain, LangGraph, CrewAI, AutoGen, Strands, OpenAI Agents SDK
- **Agentic Runtimes (PaaS)** - AWS Bedrock AgentCore, GCP Vertex AI Agent Engine, Microsoft Azure AI Foundry

### How It Works

agentsec uses **dynamic code modification** to automatically intercept LLM and MCP tool calls, routing traffic through:

| Integration Mode | Description |
|------------------|-------------|
| **Cisco AI Defense Gateway** | Routes all LLM traffic through a secure proxy for centralized policy enforcement |
| **Cisco AI Defense API** | Inspects requests/responses via API calls while connecting directly to LLM providers |

With just **a few lines of code**, your existing AI application gains enterprise-grade security:

```python
from aidefense.runtime import agentsec
agentsec.protect(config="agentsec.yaml")  
```

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Use in Your Own Project](#use-in-your-own-project)
- [Environment Variables Quick Reference](#environment-variables-quick-reference)
- [Overview](#overview)
- [Core Concepts](#core-concepts)
- [Integration Pattern](#integration-pattern)
- [Directory Structure](#directory-structure)
- [1. Simple Examples](#1-simple-examples)
- [2. Agent Frameworks](#2-agent-frameworks)
- [3. Agent Runtimes](#3-agent-runtimes)
- [Configuration](#configuration) (see also [CONFIGURATION.md](CONFIGURATION.md) for the full parameter reference)
- [Advanced Usage](#advanced-usage)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

| Requirement | Version | Installation |
|-------------|---------|--------------|
| Python | 3.10+ | [python.org](https://www.python.org/downloads/) |
| Poetry | 1.5+ | `curl -sSL https://install.python-poetry.org \| python3 -` |
| Git | Any | `brew install git` or [git-scm.com](https://git-scm.com/) |

### Getting Your Credentials

Before running any example you need credentials for **Cisco AI Defense** and at least one **LLM provider**.

| Credential | Where to Get It | `.env` Variable |
|------------|----------------|-----------------|
| **AI Defense API key** | Cisco AI Defense portal — create an inspection profile and copy the API key | `AI_DEFENSE_API_MODE_LLM_API_KEY` |
| **AI Defense API endpoint** | Cisco AI Defense portal — shown on the inspection profile page | `AI_DEFENSE_API_MODE_LLM_ENDPOINT` |
| **OpenAI API key** | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | `OPENAI_API_KEY` |
| **Azure OpenAI** | Azure Portal — your OpenAI resource page | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT` |
| **AWS Bedrock** | AWS Console — configure via `aws sso login` or `AWS_PROFILE` | See `.env.example` AWS section |
| **GCP Vertex AI** | `gcloud auth application-default login` | See `.env.example` GCP section |
| **Cohere** | [dashboard.cohere.com/api-keys](https://dashboard.cohere.com/api-keys) | `COHERE_API_KEY` |
| **Mistral AI** | [console.mistral.ai](https://console.mistral.ai) — API Keys page | `MISTRAL_API_KEY` |

> **Minimum for a first run (API mode + OpenAI):** You only need three values in `.env`:
> `AI_DEFENSE_API_MODE_LLM_API_KEY`, `AI_DEFENSE_API_MODE_LLM_ENDPOINT`, and `OPENAI_API_KEY`.

---

## Quick Start

```bash
# 0. Navigate to the examples directory
cd examples/agentsec

# 1. Configure credentials and settings
cp .env.example .env
# Edit .env — at minimum set: AI_DEFENSE_API_MODE_LLM_API_KEY and your provider key (e.g. OPENAI_API_KEY)
# Edit agentsec.yaml — configure integration modes, gateway URLs, and inspection settings

# 2. Run a simple example
cd 1-simple && poetry install && poetry run python basic_protection.py

# 3. Or run an agent framework example
cd ../2-agent-frameworks/strands-agent && poetry install && ./scripts/run.sh --openai

# 4. Run all tests (from the repo root)
cd /path/to/ai-defense-python-sdk
./scripts/run-unit-tests.sh           # ~1210 unit tests
./scripts/run-integration-tests.sh    # Full integration tests
```

---

## Use in Your Own Project

To add Cisco AI Defense protection to your own Python application (outside this repo), install the SDK from PyPI:

```bash
# pip
pip install cisco-aidefense-sdk

# or poetry
poetry add cisco-aidefense-sdk
```

Then add protection to your code. The key rule is: **call `agentsec.protect()` BEFORE importing your LLM client**.

```python
import os

# 1. Import and activate protection BEFORE importing LLM clients
from aidefense.runtime import agentsec
agentsec.protect(
    api_mode={
        "llm": {
            "mode": "monitor",    # "enforce" to block violations, "monitor" to log only
            "endpoint": os.environ["AI_DEFENSE_API_MODE_LLM_ENDPOINT"],
            "api_key": os.environ["AI_DEFENSE_API_MODE_LLM_API_KEY"],
        }
    }
)

# 2. Now import your LLM client -- it is automatically patched
from openai import OpenAI
client = OpenAI()

# 3. Use it normally -- every call is inspected by Cisco AI Defense
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

**Minimum credentials** (set as environment variables or in a `.env` file):

| Variable | Description |
|----------|-------------|
| `AI_DEFENSE_API_MODE_LLM_API_KEY` | Your Cisco AI Defense inspection API key |
| `AI_DEFENSE_API_MODE_LLM_ENDPOINT` | Your Cisco AI Defense inspection API endpoint |
| `OPENAI_API_KEY` | Your LLM provider key (OpenAI shown here; any [supported provider](#supported-llm-providers) works) |

For production use, move configuration into an `agentsec.yaml` file (see [Configuration](#configuration) and [CONFIGURATION.md](CONFIGURATION.md)) and call `agentsec.protect(config="agentsec.yaml")`.

---

## Environment Variables Quick Reference

Configuration is split between two concerns:

| Source | Contains | Example |
|--------|----------|---------|
| **`agentsec.yaml`** | Integration modes, gateway URLs, timeouts, inspection modes | `llm_integration_mode: gateway` |
| **Environment variables** | Secrets, credentials, and environment-specific settings | `OPENAI_API_KEY=sk-...` |

### How `agentsec.yaml` References Environment Variables

`agentsec.yaml` can reference environment variables using `${VAR_NAME}` syntax. These are resolved at runtime when `agentsec.protect()` parses the configuration -- keeping secrets out of version control while maintaining a single, readable config file.

```yaml
# agentsec.yaml — references environment variables at runtime
gateway_mode:
  llm_gateways:
    openai-1:
      gateway_url: https://gateway.example.com/openai-conn
      gateway_api_key: ${OPENAI_API_KEY}    # resolved from the environment at runtime
```

How you provision these variables is up to you. Common approaches include:

- **`.env` file** -- place a `.env` alongside `agentsec.yaml` and let the SDK load it automatically (`auto_dotenv=True`, the default)
- **Shell exports** -- `export OPENAI_API_KEY=sk-...` before running your application
- **Secrets manager** -- fetch values from HashiCorp Vault, AWS Secrets Manager, GCP Secret Manager, Azure Key Vault, etc. at startup
- **CI/CD pipeline** -- inject variables via GitHub Actions secrets, GitLab CI variables, or your platform's native mechanism
- **Container orchestration** -- Kubernetes Secrets, ECS task definitions, Cloud Run env config, etc.

The provided `.env.example` lists every variable the examples support. Use it as a **reference** for which keys your integration needs -- it is not a requirement. Only set the variables relevant to your setup.

> **Note**: `protect()` sets `auto_dotenv=True` by default, which loads a `.env` file if one is present in the working directory. Set `auto_dotenv=False` if you manage environment variables through other means and want to avoid implicit file loading.

> **Tip**: Gateway mode uses the same provider API keys as API mode -- no separate gateway-specific keys are needed.

For the complete list of every environment variable, every `agentsec.yaml` parameter (with types, allowed values, and defaults), and every `protect()` kwarg, see **[CONFIGURATION.md](CONFIGURATION.md)**.

### By Example Path

| Example | AI Defense | LLM Provider | Extra |
|---------|------------|--------------|-------|
| `1-simple/basic_protection.py` | API or Gateway | OpenAI | - |
| `1-simple/custom_rules_example.py` | API | OpenAI | Custom inspection rules |
| `1-simple/openai_example.py` | API or Gateway | OpenAI | - |
| `1-simple/streaming_example.py` | API or Gateway | OpenAI | - |
| `1-simple/gateway_mode_example.py` | Gateway | OpenAI | Programmatic config demo |
| `1-simple/skip_inspection_example.py` | API or Gateway | OpenAI | - |
| `1-simple/cohere_example.py` | API or Gateway | Cohere | - |
| `1-simple/mistral_example.py` | API or Gateway | Mistral AI | - |
| `1-simple/simple_strands_bedrock.py` | API or Gateway | Bedrock | - |
| `1-simple/mcp_example.py` | API or Gateway | OpenAI + MCP | MCP server URL |
| `1-simple/multi_gateway_example.py` | API or Gateway | Bedrock (x2) + MCP (x2) | Named gateways, multi-MCP |
| `2-agent-frameworks/*/--openai` | API or Gateway | OpenAI | - |
| `2-agent-frameworks/*/--azure` | API or Gateway | Azure OpenAI | - |
| `2-agent-frameworks/*/--bedrock` | API or Gateway | Bedrock | - |
| `2-agent-frameworks/*/--vertex` | API or Gateway | Vertex AI | - |
| `3-agent-runtimes/microsoft-foundry/` | API or Gateway | Azure OpenAI | Azure Foundry deployment vars |
| `3-agent-runtimes/amazon-bedrock-agentcore/` | API or Gateway | Bedrock | AWS deployment vars |
| `3-agent-runtimes/gcp-vertex-ai-agent-engine/` | API or Gateway | Vertex AI | GCP deployment vars |

> **Tip**: Most `1-simple/` examples use programmatic configuration (inline). `multi_gateway_example.py` uses `agentsec.yaml` to demonstrate named gateways. `3-agent-runtimes/` examples use `agentsec.yaml` for production-like deployments. Check `.env.example` section headers to see which variables each example needs.

---

## Overview

| Category | Description | Examples |
|----------|-------------|----------|
| **1-simple/** | Standalone examples for core features | 11 examples |
| **2-agent-frameworks/** | Agent frameworks with MCP tools | 6 frameworks |
| **3-agent-runtimes/** | Cloud deployment with AI Defense | 3 runtimes, 9 modes |

---

## Core Concepts

### Integration Modes

agentsec supports two ways to integrate with Cisco AI Defense:

| Mode | How It Works | When to Use |
|------|--------------|-------------|
| **API Mode** | SDK inspects requests via AI Defense API, then calls LLM directly | Most deployments; simple setup |
| **Gateway Mode** | SDK routes all traffic through AI Defense Gateway proxy | Centralized policy enforcement |

Set in `agentsec.yaml`:
```yaml
llm_integration_mode: gateway
mcp_integration_mode: api
```

> **Runtime override**: The example scripts read `AGENTSEC_LLM_INTEGRATION_MODE` and `AGENTSEC_MCP_INTEGRATION_MODE` environment variables to override the YAML value at runtime. This lets you switch between API and Gateway mode without editing the YAML file (e.g. `AGENTSEC_LLM_INTEGRATION_MODE=api python my_agent.py`). See [Appendix: Environment Variable Overrides](CONFIGURATION.md#4-appendix-environment-variable-overrides) for the full list.

> **Important — No Silent Fallback**: If gateway mode is enabled but no gateway is configured for the provider (LLM) or URL (MCP), agentsec raises a `SecurityPolicyError` instead of silently falling back to API mode. This prevents accidental changes to your security posture. Either configure a gateway for every provider/URL you use, or explicitly set the integration mode to `api`.

### Supported LLM Providers

agentsec automatically patches these LLM client libraries:

| Provider | Package | Patched Methods |
|----------|---------|-----------------|
| **OpenAI** | `openai` | `chat.completions.create()` |
| **Azure OpenAI** | `openai` | `chat.completions.create()` (with Azure endpoint) |
| **AWS Bedrock** | `boto3` | `converse()`, `converse_stream()` |
| **Google Vertex AI** | `google-cloud-aiplatform` | `GenerativeModel.generate_content()`, `generate_content_async()` |
| **Google GenAI** | `google-genai` | `generate_content()`, `generate_content_async()` (falls back to `vertexai` gateway — see note below) |
| **Cohere** | `cohere` | `V2Client.chat()`, `V2Client.chat_stream()`, `AsyncV2Client.chat()`, `AsyncV2Client.chat_stream()` |
| **Mistral AI** | `mistralai` | `Chat.complete()`, `Chat.stream()`, `Chat.complete_async()`, `Chat.stream_async()` |
| **LiteLLM** | `litellm` | `completion()`, `acompletion()` (catches provider calls that bypass native SDKs, e.g. CrewAI + Vertex AI) |

> **Google GenAI vs. Vertex AI**: Both SDKs target the same Google backend and use the same Vertex AI REST gateway format. From a developer's perspective they are interchangeable for agentsec purposes. If you only configure a `vertexai` gateway in `agentsec.yaml`, the `google-genai` patcher will automatically fall back to it — no separate `google_genai` gateway entry is needed.

### MCP Tool Inspection

agentsec also patches the MCP (Model Context Protocol) client for tool call inspection:

| Package | Patched Methods |
|---------|-----------------|
| `mcp` | `ClientSession.call_tool()`, `get_prompt()`, `read_resource()` |

### Protection Coverage

agentsec inspects both **requests** (user prompts) and **responses** (LLM outputs):

| Inspection | What It Checks | When It Happens |
|------------|----------------|-----------------|
| **LLM Request** | Prompt injection, jailbreak, PII in prompts | Before LLM call |
| **LLM Response** | Sensitive data leakage, harmful content | After LLM response |
| **MCP Request** | Tool call arguments, prompt injection | Before MCP tool call |
| **MCP Response** | Tool response content, data leakage | After MCP tool response |

### Inspection Modes

API mode and Gateway mode have **separate, independent mode controls**. Each mode only applies to its own integration path.

#### API Mode: `off` | `monitor` | `enforce`

When `llm_integration_mode: api`, the SDK sends each request/response to the Cisco AI Defense inspection API, which returns an `allow` or `block` decision. The SDK then acts on that decision locally:

| Mode | Behavior | What Happens on a Violation |
|------|----------|----------------------------|
| `off` | No inspection | Calls go directly to the LLM provider |
| `monitor` | Inspect & log, never block | Decision is logged but the call always proceeds |
| `enforce` | Inspect & block violations | SDK raises `SecurityPolicyError`, preventing the request or response from reaching the app |

Set in `agentsec.yaml`:
```yaml
api_mode:
  llm:
    mode: enforce    # off | monitor | enforce
  mcp:
    mode: monitor    # off | monitor | enforce
```

In `enforce` mode, catch `SecurityPolicyError` to handle blocked requests:
```python
from aidefense.runtime.agentsec.exceptions import SecurityPolicyError

try:
    response = client.chat.completions.create(...)
except SecurityPolicyError as e:
    print(f"Blocked: {e}")
```

#### Gateway Mode: `on` | `off`

When `llm_integration_mode: gateway`, the SDK routes all traffic through the Cisco AI Defense Gateway proxy. **Enforcement is handled server-side by the gateway** -- the SDK does not make local allow/block decisions. Policies are configured in the Cisco AI Defense portal.

| Mode | Behavior |
|------|----------|
| `on` | Traffic is routed through the gateway (default) |
| `off` | Gateway is bypassed; calls go directly to the LLM provider with no inspection |

Set in `agentsec.yaml`:
```yaml
gateway_mode:
  llm_mode: on     # on | off
  mcp_mode: on     # on | off
```

> **Key difference**: In API mode, `monitor` vs `enforce` controls whether the SDK blocks violations locally. In Gateway mode, there is no local enforcement -- the gateway decides whether to allow or block, so the only SDK-side choice is whether to route through the gateway (`on`) or bypass it (`off`).

> **Custom rules** (API mode only): You can restrict which inspection rules are evaluated by
> specifying `api_mode.llm.rules` in `agentsec.yaml` or via `protect()` kwargs.
> When omitted, all rules are evaluated. When specified, only the listed rules
> run. This is useful for reducing false positives (e.g., excluding Prompt
> Injection for agent frameworks). See `1-simple/custom_rules_example.py` and
> [CONFIGURATION.md -- Custom Inspection Rules](CONFIGURATION.md#custom-inspection-rules)
> for details.

### Fail-Open vs. Fail-Closed

When the inspection API or gateway is unreachable (timeout, network error), agentsec can either let the call proceed or block it:

| Setting | Behavior | When to Use |
|---------|----------|-------------|
| `fail_open: true` | Allow the LLM/MCP call if inspection fails | Development, non-critical workloads |
| `fail_open: false` | Block the call and raise an error if inspection fails | Production, high-security environments |

> **Note**: The default value of `fail_open` varies by context: **gateway mode** defaults to `true` (both LLM and MCP), **API mode MCP** defaults to `true`, but **API mode LLM** defaults to `false` (fail-closed). See [CONFIGURATION.md](CONFIGURATION.md) for exact defaults per section.

Set per mode in `agentsec.yaml`:
```yaml
api_mode:
  llm_defaults:
    fail_open: false    # Block on inspection failure
    timeout: 5          # Seconds before timeout
gateway_mode:
  llm_defaults:
    fail_open: true
    timeout: 60         # Gateway proxies to LLM — needs more time
```

### Integration Mode Prerequisites

These prerequisites apply to both **Agent Frameworks** and **Agent Runtimes**.

#### API Mode Prerequisites

| Component | Required | `.env` (secrets) | `agentsec.yaml` (settings) |
|-----------|:--------:|------------------|---------------------------|
| **Cisco AI Defense API** | Yes | `AI_DEFENSE_API_MODE_LLM_API_KEY` | `api_mode.llm.endpoint`, `api_mode.llm.mode` |
| **OpenAI** | If using | `OPENAI_API_KEY` | - |
| **Azure OpenAI** | If using | `AZURE_OPENAI_API_KEY` | Also needs `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT_NAME`, `AZURE_OPENAI_API_VERSION` |
| **AWS Bedrock** | If using | AWS credentials (profile or env vars) | - |
| **Vertex AI** | If using | GCP ADC (`gcloud auth application-default login`) | - |
| **Cohere** | If using | `COHERE_API_KEY` | - |
| **Mistral AI** | If using | `MISTRAL_API_KEY` | - |

> Azure OpenAI also requires `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT_NAME`, and `AZURE_OPENAI_API_VERSION` in `.env`. These are non-secret provider settings, but are kept in `.env` because the Azure OpenAI SDK reads them as environment variables.

#### Gateway Mode Prerequisites

Gateway URLs are configured in `agentsec.yaml` under `gateway_mode.llm_gateways`. The YAML references provider API keys from `.env` via `${VAR_NAME}` syntax -- the same key is used for both API mode and gateway mode.

| Provider | Gateway URL | API Key (`.env`) |
|----------|-------------|------------------|
| **OpenAI** | `agentsec.yaml` | `OPENAI_API_KEY` |
| **Azure OpenAI** | `agentsec.yaml` | `AZURE_OPENAI_API_KEY` |
| **AWS Bedrock** | `agentsec.yaml` | AWS Sig V4 (no API key); per-gateway `aws_region`/`aws_profile`/keys optional |
| **Vertex AI** | `agentsec.yaml` | ADC OAuth2 (no API key); per-gateway `gcp_project`/`gcp_location`/keys optional |
| **Cohere** | `agentsec.yaml` | `COHERE_API_KEY` |
| **Mistral AI** | `agentsec.yaml` | `MISTRAL_API_KEY` |

---

## Integration Pattern

The standard pattern for integrating agentsec:

```python
# 1. Import and enable protection BEFORE importing LLM clients
from aidefense.runtime import agentsec

# Option A: YAML config (recommended for production)
agentsec.protect(config="agentsec.yaml")

# Option B: Inline config (for quick testing)
agentsec.protect(api_mode={"llm": {"mode": "enforce"}, "mcp": {"mode": "enforce"}})

# 2. Import and use LLM clients normally - they're now protected
from openai import OpenAI
client = OpenAI()

# 3. All calls are inspected by AI Defense
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### Gateway Mode Pattern

Gateway mode is best configured via `agentsec.yaml`, which keeps URLs and key references centralized:

```yaml
# agentsec.yaml
llm_integration_mode: gateway

gateway_mode:
  llm_gateways:
    openai-1:
      gateway_url: https://gateway.../openai-conn
      gateway_api_key: ${OPENAI_API_KEY}    # References .env
      auth_mode: api_key
      provider: openai
      default: true
```

```python
from aidefense.runtime import agentsec
agentsec.protect(config="agentsec.yaml")
```

For quick testing, inline configuration is also supported (see [Programmatic Configuration](#programmatic-configuration)).

### Named Gateway Pattern (Multi-Gateway)

Route the same LLM provider through different gateway connections based on context. Define multiple gateways for the same provider in `agentsec.yaml`, marking one as `default: true`, and use `gateway()` (context manager) or `use_gateway()` (decorator) to select a named gateway at runtime:

```yaml
# agentsec.yaml
gateway_mode:
  llm_gateways:
    bedrock-1:
      gateway_url: https://gateway.../bedrock-haiku-conn
      provider: bedrock
      auth_mode: aws_sigv4
      default: true         # Used when no gateway() context is active
      aws_region: us-east-1
      aws_profile: default

    bedrock-2:
      gateway_url: https://gateway.../bedrock-sonnet-conn
      provider: bedrock
      auth_mode: aws_sigv4
      aws_region: eu-west-1
      aws_profile: team-b

    vertexai-1:
      gateway_url: https://gateway.../vertexai-us-conn
      provider: vertexai
      auth_mode: google_adc
      default: true
      gcp_project: my-us-project
      gcp_location: us-central1

    vertexai-2:
      gateway_url: https://gateway.../vertexai-eu-conn
      provider: vertexai
      auth_mode: google_adc
      gcp_project: my-eu-project
      gcp_location: europe-west4
```

```python
import boto3
from aidefense.runtime import agentsec

agentsec.protect(config="agentsec.yaml")
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

# Call 1: Uses bedrock-1 (default) — no context manager needed
response = bedrock.converse(
    modelId="anthropic.claude-3-haiku-20240307-v1:0",
    messages=[{"role": "user", "content": [{"text": "Quick question"}]}],
)

# Call 2: Uses bedrock-2 (named) — wrap with gateway()
with agentsec.gateway("bedrock-2"):
    response = bedrock.converse(
        modelId="anthropic.claude-3-5-sonnet-20241022-v2:0",
        messages=[{"role": "user", "content": [{"text": "Complex question"}]}],
    )

# Alternative: Use @use_gateway() decorator for an entire function
@agentsec.use_gateway("bedrock-2")
def ask_complex_question(prompt: str):
    return bedrock.converse(
        modelId="anthropic.claude-3-5-sonnet-20241022-v2:0",
        messages=[{"role": "user", "content": [{"text": prompt}]}],
    )
```

#### Per-Gateway Credentials (AWS / GCP)

Each gateway can use its own credentials. For `auth_mode: aws_sigv4`, options include named profiles, explicit keys, and cross-account assume-role. For `auth_mode: google_adc`, options include project/location, service account key files, and SA impersonation. All credential fields are optional and fall back to the default credential chain when omitted.

See [CONFIGURATION.md — gateway_mode](CONFIGURATION.md#gateway_mode) for the full list of per-gateway credential parameters (AWS SigV4 fields and GCP ADC fields).

Multiple MCP servers are also supported — each server URL is mapped to its gateway in `agentsec.yaml`:

```yaml
gateway_mode:
  mcp_gateways:
    https://remote.mcpservers.org/fetch/mcp:
      gateway_url: https://gateway.../fetch-mcp-conn

    https://mcp.time.mcpcentral.io:
      gateway_url: https://gateway.../time-mcp-conn
```

See `1-simple/multi_gateway_example.py` for a complete working example.

#### MCP Gateway Authentication

Each MCP gateway entry supports a per-server `auth_mode`. Three modes are available:

| `auth_mode` | Header injected | When to use |
|---|---|---|
| `none` (default) | _none_ | Gateway does not require authentication |
| `api_key` | `api-key: <key>` | Gateway requires an API key |
| `oauth2_client_credentials` | `Authorization: Bearer <token>` | Gateway requires an OAuth 2.0 access token |

**No auth (default):**

```yaml
gateway_mode:
  mcp_gateways:
    https://mcp.example.com:
      gateway_url: https://gateway.../mcp-conn
      auth_mode: none          # default — can be omitted
```

**API Key:**

```yaml
gateway_mode:
  mcp_gateways:
    https://mcp.example.com:
      gateway_url: https://gateway.../mcp-conn
      auth_mode: api_key
      gateway_api_key: ${MCP_GATEWAY_API_KEY}
```

**OAuth 2.0 Client Credentials:**

The SDK automatically fetches and caches access tokens using the Client Credentials grant.

```yaml
gateway_mode:
  mcp_gateways:
    https://secure-mcp.example.com:
      gateway_url: https://gateway.../mcp-conn
      auth_mode: oauth2_client_credentials
      oauth2_token_url: https://auth.example.com/oauth/token
      oauth2_client_id: ${MCP_OAUTH_CLIENT_ID}
      oauth2_client_secret: ${MCP_OAUTH_CLIENT_SECRET}
      oauth2_scopes: "read write"          # optional
```

Store secrets in `.env` and reference them with `${VAR}` syntax (see `.env.example`).

### Skip Inspection Pattern

```python
from aidefense.runtime import agentsec

# Context manager - skip specific calls
with agentsec.skip_inspection():
    response = client.chat.completions.create(...)

# Decorator - skip entire function
@agentsec.no_inspection()
def my_function():
    response = client.chat.completions.create(...)
```

**Key Rule**: Always call `agentsec.protect()` **before** importing LLM client libraries.

---

## Directory Structure

<details>
<summary>Click to expand project layout</summary>

```
ai-defense-python-sdk/
├── scripts/
│   ├── run-unit-tests.sh           # Run all unit tests
│   └── run-integration-tests.sh    # Run integration tests
│
└── examples/agentsec/
    ├── agentsec.yaml               # Configuration (modes, gateways, timeouts)
    ├── .env.example                # Template - copy to .env (secrets + credentials)
    ├── README.md                   # This file
    │
    ├── 1-simple/                   # Standalone examples
    │   ├── basic_protection.py     # Minimal setup
    │   ├── custom_rules_example.py # Custom inspection rules
    │   ├── openai_example.py       # OpenAI client
    │   ├── cohere_example.py       # Cohere v2 client
    │   ├── mistral_example.py      # Mistral AI client
    │   ├── streaming_example.py    # Streaming responses
    │   ├── mcp_example.py          # MCP tool inspection
    │   ├── gateway_mode_example.py # Gateway mode
    │   ├── skip_inspection_example.py  # Per-call exclusion
    │   ├── simple_strands_bedrock.py   # Strands + Bedrock
    │   ├── multi_gateway_example.py    # Multi-gateway + multi-MCP
    │   └── tests/
    │
    ├── 2-agent-frameworks/         # Agent framework examples
    │   ├── run-all-integration-tests.sh  # Run all framework tests
    │   ├── strands-agent/          # AWS Strands SDK
    │   ├── langgraph-agent/        # LangGraph
    │   ├── langchain-agent/        # LangChain
    │   ├── crewai-agent/           # CrewAI
    │   ├── autogen-agent/          # AutoGen
    │   ├── openai-agent/           # OpenAI Agents SDK
    │   └── _shared/                # Shared provider configs & tests
    │
    └── 3-agent-runtimes/           # Cloud runtime examples
        ├── run-all-integration-tests.sh  # Run all runtime tests
        ├── amazon-bedrock-agentcore/
        ├── gcp-vertex-ai-agent-engine/
        └── microsoft-foundry/
```

</details>

---

## 1. Simple Examples

Standalone examples demonstrating core agentsec features without agent frameworks.

> **Prerequisites**: See [Integration Mode Prerequisites](#integration-mode-prerequisites) for API/Gateway configuration.

| Example | Description | Request | Response |
|---------|-------------|:-------:|:--------:|
| `basic_protection.py` | Minimal setup - modes, patched clients | ✅ | ✅ |
| `custom_rules_example.py` | Custom inspection rules - selective rule filtering | ✅ | ✅ |
| `openai_example.py` | OpenAI client with automatic inspection | ✅ | ✅ |
| `cohere_example.py` | Cohere v2 client with automatic inspection | ✅ | ✅ |
| `mistral_example.py` | Mistral AI client with automatic inspection | ✅ | ✅ |
| `streaming_example.py` | Streaming responses with chunk inspection | ✅ | ✅ |
| `mcp_example.py` | MCP tool call inspection (pre & post) | ✅ | ✅ |
| `gateway_mode_example.py` | Gateway mode configuration | ✅ | ✅ |
| `skip_inspection_example.py` | Per-call exclusion with context manager | ✅ | ✅ |
| `simple_strands_bedrock.py` | Strands agent with Bedrock Claude | ✅ | ✅ |
| `multi_gateway_example.py` | Multi-gateway (2 Bedrock LLMs) + multi-MCP (2 servers) | ✅ | ✅ |

### Run Examples

```bash
cd 1-simple
poetry install  # First time only

# Run individual examples
poetry run python basic_protection.py
poetry run python custom_rules_example.py
poetry run python openai_example.py
poetry run python cohere_example.py
poetry run python mistral_example.py
poetry run python streaming_example.py
poetry run python mcp_example.py
poetry run python gateway_mode_example.py
poetry run python skip_inspection_example.py
poetry run python simple_strands_bedrock.py
poetry run python multi_gateway_example.py

# Run integration tests (from repo root)
cd /path/to/ai-defense-python-sdk
./scripts/run-integration-tests.sh --simple
```

---

## 2. Agent Frameworks

Agent framework examples with MCP tool support and multi-provider configuration.

> **Prerequisites**: See [Integration Mode Prerequisites](#integration-mode-prerequisites) for API/Gateway configuration.

### Supported Frameworks

| Framework | Package | Framework Prerequisites |
|-----------|---------|------------------------|
| **Strands** | `strands-agents` | Poetry |
| **LangGraph** | `langgraph` | Poetry |
| **LangChain** | `langchain` | Poetry |
| **CrewAI** | `crewai` | Poetry |
| **AutoGen** | `ag2` | Poetry |
| **OpenAI Agents** | `openai` | Poetry |

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

# Run integration tests (from repo root)
cd /path/to/ai-defense-python-sdk
./scripts/run-integration-tests.sh --agents                # All frameworks, all providers
./scripts/run-integration-tests.sh strands                 # Specific framework
./scripts/run-integration-tests.sh --agents --api          # All frameworks, API mode only
./scripts/run-integration-tests.sh --agents --gateway      # All frameworks, Gateway mode only
./scripts/run-integration-tests.sh strands --gateway       # Specific framework + mode
```

You can also run all framework tests directly from the `2-agent-frameworks/` directory:

```bash
cd examples/agentsec/2-agent-frameworks
./run-all-integration-tests.sh                # All frameworks, all providers, both modes
./run-all-integration-tests.sh --quick        # All frameworks, OpenAI only, both modes
./run-all-integration-tests.sh --api          # API mode only
./run-all-integration-tests.sh langgraph      # Specific framework
```

### Protection Coverage

All agent frameworks support both request and response inspection:

- **LLM Calls**: Every `chat.completions.create()` / `converse()` / `generate_content()` is inspected
- **MCP Tool Calls**: Tool request and response payloads are inspected (when MCP is used)
- **Streaming**: For OpenAI, response chunks are inspected periodically (every N chunks) and once more at stream completion. For other providers (Vertex AI, Cohere, Mistral), chunks are buffered and inspected after the stream completes.

---

## 3. Agent Runtimes

Cloud deployment examples with full AI Defense protection.

> **AI Defense Prerequisites**: In addition to the deploy prerequisites below, see [Integration Mode Prerequisites](#integration-mode-prerequisites) for API/Gateway configuration.

### Test Modes

All agent runtimes support two test modes:

| Mode | Flag | What It Tests | Cloud Required |
|------|------|---------------|----------------|
| **Local** | `--local` | Agent code directly with LLM provider | LLM credentials only |
| **Deploy** | `--deploy` | Full cloud deployment and endpoints | Cloud infrastructure |

### AWS Bedrock AgentCore

Three deployment modes for AWS AgentCore agents:

| Mode | Description | Local Prerequisites | Deploy Prerequisites |
|------|-------------|---------------------|---------------------|
| **Direct Deploy** | Agent with Bedrock | AWS Bedrock credentials | AWS CLI, AgentCore CLI |
| **Container Deploy** | Docker container | AWS Bedrock credentials | Docker, ECR permissions |
| **Lambda Deploy** | AWS Lambda function | AWS Bedrock credentials | Lambda/ECR permissions |

```bash
cd 3-agent-runtimes/amazon-bedrock-agentcore
poetry install

# Run LOCAL tests (default) - no AWS deployment needed
./tests/integration/test-all-modes.sh              # All modes, local
./tests/integration/test-all-modes.sh --local      # Explicit local mode
./tests/integration/test-all-modes.sh --api        # API mode only, local

# Run DEPLOY tests - deploys to AWS and tests real endpoints
./tests/integration/test-all-modes.sh --deploy     # All modes, deploy to AWS
./tests/integration/test-all-modes.sh --deploy direct --api  # Direct deploy, API only
```

### GCP Vertex AI Agent Engine

Three deployment modes for GCP Vertex AI agents:

| Mode | Description | Local Prerequisites | Deploy Prerequisites |
|------|-------------|---------------------|---------------------|
| **Agent Engine** | Google's managed agent service | GCP ADC credentials | gcloud CLI, Vertex AI permissions |
| **Cloud Run** | Serverless containers | GCP ADC credentials | Docker, Cloud Run permissions |
| **GKE** | Kubernetes deployment | GCP ADC credentials | Docker, kubectl, GKE permissions |

**Google AI SDK:**

The GCP Vertex AI runtime supports two LangChain LLM classes, selected by the `sdk` field on the vertexai gateway in `agentsec.yaml` (resolved from `${GOOGLE_AI_SDK}`):

- **`google_genai`** (default): `ChatGoogleGenerativeAI` from `langchain-google-genai`. Uses `google.genai.Client` internally, patched by agentsec's `google_genai` patcher. Recommended forward path for local development.
- **`vertexai`**: `ChatVertexAI` from `langchain-google-vertexai`. Uses `vertexai.GenerativeModel` internally, patched by agentsec's `vertexai` patcher. Required for Agent Engine deployments where the managed SA lacks the `generative-language` scope.

```bash
cd 3-agent-runtimes/gcp-vertex-ai-agent-engine
poetry install

# Run LOCAL tests (default) - no GCP deployment needed
./tests/integration/test-all-modes.sh              # All modes, local
./tests/integration/test-all-modes.sh --local      # Explicit local mode
./tests/integration/test-all-modes.sh --api        # API mode only, local

# Run DEPLOY tests - deploys to GCP and tests real endpoints
./tests/integration/test-all-modes.sh --deploy     # All modes, deploy to GCP
./tests/integration/test-all-modes.sh --deploy --mode cloud-run  # Cloud Run only
./tests/integration/test-all-modes.sh --deploy --cleanup  # Deploy, test, and cleanup
```

### Microsoft Azure AI Foundry

Three deployment modes for Microsoft Azure AI Foundry agents:

| Mode | Description | Local Prerequisites | Deploy Prerequisites |
|------|-------------|---------------------|---------------------|
| **Foundry Agent App** | Azure AI Foundry managed endpoint | Azure OpenAI credentials | Azure CLI, ML extension |
| **Azure Functions** | Serverless functions | Azure OpenAI credentials | Functions Core Tools |
| **Foundry Container** | Container deployment | Azure OpenAI credentials | Docker, ACR permissions |

```bash
cd 3-agent-runtimes/microsoft-foundry
poetry install

# Run LOCAL tests (default) - no Azure deployment needed
./tests/integration/test-all-modes.sh              # All modes, local
./tests/integration/test-all-modes.sh --local      # Explicit local mode
./tests/integration/test-all-modes.sh --local --api # API mode only, local

# Run DEPLOY tests - deploys to Azure and tests real endpoints
./tests/integration/test-all-modes.sh --deploy     # All modes, deploy to Azure
./tests/integration/test-all-modes.sh --deploy agent-app --api  # Agent app, API only
```

> **Note**: All three runtimes default to local mode (`--local`). Use `--deploy` to run against real cloud endpoints.

### Runtime Integration Tests

There are two ways to run runtime integration tests:

**Option 1: Top-level script** (recommended — defaults to local for all runtimes)

```bash
# From the repo root
cd /path/to/ai-defense-python-sdk

./scripts/run-integration-tests.sh --runtimes            # All runtimes
./scripts/run-integration-tests.sh amazon-bedrock-agentcore  # Specific runtime
./scripts/run-integration-tests.sh --runtimes --api      # API mode only
./scripts/run-integration-tests.sh --runtimes --deploy   # Force deploy mode for all
```

**Option 2: Runtimes directory script** (interactive — prompts before running)

```bash
cd examples/agentsec/3-agent-runtimes

# Wrapper default: --deploy for AgentCore/Vertex AI, --local for Foundry
./run-all-integration-tests.sh                     # Default test mode

# Override modes
./run-all-integration-tests.sh --local             # All runtimes, local mode
./run-all-integration-tests.sh --deploy            # All runtimes, deploy mode

# Run specific runtime
./run-all-integration-tests.sh amazon-bedrock-agentcore        # AgentCore only
./run-all-integration-tests.sh --local microsoft-foundry       # Foundry, local mode

# Quick mode (API mode only, 1 test per runtime)
./run-all-integration-tests.sh --quick             # Quick tests for all runtimes
```

> **Note**: Each runtime's own `test-all-modes.sh` defaults to `--local`. The wrapper `run-all-integration-tests.sh` in `3-agent-runtimes/` overrides this for AgentCore and Vertex AI (using `--deploy`), while keeping `--local` for Foundry. Use `--local` or `--deploy` to override for all runtimes.

---

## Configuration

agentsec uses two configuration files:

| File | Purpose | Contents |
|------|---------|----------|
| **`agentsec.yaml`** | All non-secret settings | Integration modes, gateway URLs, endpoints, timeouts, retry policy, inspection modes |
| **`.env`** | Secrets, credentials, and environment-specific settings | API keys, cloud credentials (referenced via `${VAR}` in YAML) |

**Configuration merge order** (highest priority wins):

```
protect() kwargs  >  agentsec.yaml  >  hardcoded defaults
```

This means you can override any YAML setting by passing it directly to `protect()`, which is useful for testing or one-off runs.

### Getting Started

```bash
# Copy the template files
cp .env.example .env
# Edit .env — fill in your API keys and credentials
# Edit agentsec.yaml — configure integration modes, gateway URLs, inspection modes
```

> For the complete reference of every `agentsec.yaml` parameter, every `.env` variable, and every `protect()` kwarg -- with types, allowed values, and defaults -- see **[CONFIGURATION.md](CONFIGURATION.md)**.

### Provider Credentials

See [CONFIGURATION.md — .env Variable Reference](CONFIGURATION.md#2-env-variable-reference) for the complete list of variables per provider. Copy `.env.example` to `.env` and fill in the values for your providers.

Key notes for specific providers:

- **AWS Bedrock**: Uses AWS credential chain (profile, SSO, env vars). Run `aws sso login` or configure `AWS_PROFILE` in `.env`.
- **GCP Vertex AI**: Uses Application Default Credentials. Run `gcloud auth application-default login`.
- **Cohere**: Sign up at [Cohere Dashboard](https://dashboard.cohere.com/welcome/register), go to [API keys](https://dashboard.cohere.com/api-keys), create a key, and copy it to `.env` as `COHERE_API_KEY`.
- **Mistral AI**: Create an account at [Mistral Console](https://console.mistral.ai), open **API Keys**, click **Create new key**, and copy it to `.env` as `MISTRAL_API_KEY` (shown only once).

### Programmatic Configuration

For quick testing or when YAML is not practical, configuration can be provided inline via `protect()` kwargs. This is what the `1-simple/gateway_mode_example.py` demonstrates.

```python
from aidefense.runtime import agentsec
import os

# Example 1: Full gateway mode (LLM + MCP via gateway)
agentsec.protect(
    llm_integration_mode="gateway",
    mcp_integration_mode="gateway",
    gateway_mode={
        "llm_mode": "on",   # "on" (default) or "off" — enforcement is server-side
        "mcp_mode": "on",   # "on" (default) or "off"
        "llm_gateways": {
            "openai-1": {
                "gateway_url": "https://gateway.../openai-conn",
                "gateway_api_key": os.getenv("OPENAI_API_KEY"),
                "auth_mode": "api_key",
                "provider": "openai",
                "default": True,
            },
        },
        "mcp_gateways": {
            "https://remote.mcpservers.org/fetch/mcp": {
                "gateway_url": "https://gateway.../mcp",
                "auth_mode": "none",  # "none" | "api_key" | "oauth2_client_credentials"
            },
        },
    },
    pool_max_connections=20,
    pool_max_keepalive=10,
)

# Example 2: Mixed mode — LLM via gateway, MCP via API
agentsec.protect(
    llm_integration_mode="gateway",
    mcp_integration_mode="api",
    gateway_mode={
        "llm_gateways": {
            "openai-1": {
                "gateway_url": "https://gateway.../openai-conn",
                "gateway_api_key": os.getenv("OPENAI_API_KEY"),
                "auth_mode": "api_key",
                "provider": "openai",
                "default": True,
            },
        },
    },
    api_mode={
        # api_mode settings apply only when the integration mode is "api"
        "mcp": {
            "mode": "enforce",
            "endpoint": "https://preview.api.inspect.aidefense.aiteam.cisco.com/api",
            "api_key": os.getenv("AI_DEFENSE_API_MODE_LLM_API_KEY"),
        },
        "mcp_defaults": {"fail_open": True},
    },
)
```

> **Note**: The `1-simple/` examples use programmatic configuration intentionally — they serve as self-contained demos. The `3-agent-runtimes/` examples use `agentsec.yaml` for production-like deployments.

See [CONFIGURATION.md](CONFIGURATION.md) for a complete configuration parameter reference.

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

## Advanced Usage

### Error Handling

agentsec provides typed exceptions for granular error handling:

```python
from aidefense.runtime.agentsec import (
    AgentsecError,           # Base exception
    SecurityPolicyError,     # Policy violation (blocked content)
    InspectionTimeoutError,  # API timeout
    InspectionNetworkError,  # Network/connection failure
    ConfigurationError,      # Invalid configuration
    ValidationError,         # Input validation failure
)

try:
    response = client.chat.completions.create(...)
except SecurityPolicyError as e:
    print(f"Blocked: {e.decision.reasons}")
except InspectionTimeoutError as e:
    print(f"Timeout after {e.timeout_ms}ms")
except InspectionNetworkError:
    print("Network error - check connectivity")
```

### Request Context

Add metadata to inspection requests for better tracking:

```python
from aidefense.runtime.agentsec import set_metadata

# Set context before LLM calls
set_metadata(
    user="user@example.com",
    src_app="my-chatbot",
    client_transaction_id="txn-12345",
    custom_field="any-value",
)
```

### Inspection Results

When a `SecurityPolicyError` is raised, the attached `Decision` object includes detailed inspection results:

```python
from aidefense.runtime.agentsec import SecurityPolicyError, Decision

try:
    response = client.chat.completions.create(...)
except SecurityPolicyError as e:
    decision = e.decision
    decision.action          # "allow", "block", "sanitize", "monitor_only"
    decision.is_safe         # True if action != "block"
    decision.reasons         # List of reasons (e.g., ["prompt_injection_detected"])
    decision.severity        # "low", "medium", "high", "critical"
    decision.classifications # ["pii", "prompt_injection", ...]
    decision.event_id        # Unique event identifier for tracking/audit
    decision.explanation     # Human-readable explanation
```

### `protect()` API Reference

For the full `protect()` signature with all parameters, types, defaults, and descriptions, see [CONFIGURATION.md — protect() Kwargs Reference](CONFIGURATION.md#3-protect-kwargs-reference).

> `protect()` is idempotent — calling it multiple times has no effect after the first successful call.

---

## Testing

### Test Summary

| Category | Test Type | Test Count | What It Validates |
|----------|-----------|:----------:|-------------------|
| **Core SDK** | Unit | ~750 | Patching, inspection, decisions, config |
| **Simple Examples** | Unit | ~95 | Example file structure, syntax |
| **Simple Examples** | Integration | 22 | 11 examples x 2 modes (API + Gateway) |
| **Agent Frameworks** | Unit | ~210 | Agent setup, provider configs |
| **Agent Frameworks** | Integration | ~40 | 6 frameworks x (2-4 providers) x 2 modes* |
| **AgentCore** | Unit | ~65 | Deploy scripts, protection setup |
| **AgentCore** | Integration | 8 | (3 deploy x 2 modes) + 2 MCP tests |
| **Vertex AI** | Unit | ~50 | Deploy scripts, SDK selection |
| **Vertex AI** | Integration | 16 | (3 deploy x 2 modes) + 2 MCP tests** |
| **Azure AI Foundry** | Unit | ~50 | Deploy scripts, agent factory, endpoints |
| **Azure AI Foundry** | Integration | 8 | (3 deploy x 2 modes) + 2 MCP tests |

**Total: ~1210 unit tests**

*Provider support varies by framework: OpenAI Agents supports 2 providers (openai, azure), others support 4 (openai, azure, vertex, bedrock)

**Vertex AI counts individual check assertions as passed tests

### Run Tests

```bash
# From project root
cd /path/to/ai-defense-python-sdk

# All unit tests (~1210 tests)
./scripts/run-unit-tests.sh

# All integration tests
./scripts/run-integration-tests.sh

# Specific test categories
./scripts/run-integration-tests.sh --simple      # Simple examples only
./scripts/run-integration-tests.sh --agents      # Agent frameworks only
./scripts/run-integration-tests.sh --runtimes    # Agent runtimes only

# Specific mode
./scripts/run-integration-tests.sh --api         # API mode only
./scripts/run-integration-tests.sh --gateway     # Gateway mode only

# Specific framework/runtime
./scripts/run-integration-tests.sh strands       # Strands agent only
./scripts/run-integration-tests.sh amazon-bedrock-agentcore  # AgentCore only
```

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: No module named 'aidefense'` | Run `poetry install` in the example directory |
| `ModuleNotFoundError: No module named 'dotenv'` | Run `poetry add python-dotenv` or `pip install python-dotenv` |
| AWS auth fails | Run `aws sts get-caller-identity` to verify credentials |
| Azure 401 Unauthorized | Check endpoint format: `https://your-resource.openai.azure.com` |
| GCP auth fails | Run `gcloud auth application-default login` |
| OpenAI 401 Unauthorized | Verify key at https://platform.openai.com/api-keys |
| `SecurityPolicyError` raised | Expected in enforce mode when content violates policies |
| `SecurityPolicyError: Gateway mode is active but no gateway configuration found` | Gateway mode is enabled but no gateway is configured for the provider/URL. Add a gateway entry in `agentsec.yaml` or switch to `api` mode. |
| `[BLOCKED] Prompt Injection` | AI Defense detected prompt injection - this is working correctly |
| No inspection happening | Ensure `agentsec.protect()` is called early in your application. Check that the mode is set (e.g. `api_mode.llm.mode: monitor`) and credentials are configured. |
| MCP tool calls not inspected | Ensure `mcp` package is installed and `api_mode.mcp.mode` is set in `agentsec.yaml` |
| Poetry version error | Remove `package-mode = false` from pyproject.toml if using older Poetry |
| Vertex AI gateway 400 `Invalid JSON payload` | Known AI Defense gateway limitation: request bodies larger than ~2700 bytes are corrupted during forwarding. Use `llm_integration_mode: api` for Vertex AI / google-genai until the gateway team resolves this. |
| macOS SSL certificate error (`[SSL: CERTIFICATE_VERIFY_FAILED]`) | Run `/Applications/Python 3.x/Install Certificates.command` (replace `3.x` with your version) or `pip install certifi && python -c "import certifi; print(certifi.where())"` and set `SSL_CERT_FILE` to the output path. See [Python on macOS SSL guide](https://github.com/python/cpython/blob/main/Mac/README.rst). |

### GCP credentials and resources (Vertex tests)

Vertex / Gemini tests use **Application Default Credentials (ADC)**. If Vertex tests fail with `RefreshError: invalid_scope` or worked a few days ago but fail now, ADC has likely **expired** or was created without the scope the client needs.

**GCP resources used:**

| SDK / path | GCP API | Scope required |
|------------|---------|----------------|
| **google_genai** (e.g. `GOOGLE_AI_SDK=google_genai`, LangChain `ChatGoogleGenerativeAI`) | **Generative Language API** (`generativelanguage.googleapis.com`) | `https://www.googleapis.com/auth/generative-language` or `cloud-platform` |
| **vertexai** (e.g. `GOOGLE_AI_SDK=vertexai`, `ChatVertexAI` / `vertexai.GenerativeModel`) | **Vertex AI API** (e.g. `us-central1-aiplatform.googleapis.com`) | `https://www.googleapis.com/auth/cloud-platform` |
| **Gateway mode** (SDK calling AI Defense Gateway) | Gateway uses ADC to call GCP on your behalf | `cloud-platform` (gateway only) |

**Fix — refresh ADC with the right scopes (recommended):**

```bash
gcloud auth application-default login --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/generative-language
```

Then re-run the Vertex tests. This stores credentials that work for both the Generative Language API (google_genai) and Vertex AI (vertexai). If you only use the vertexai SDK, `gcloud auth application-default login` (no extra scopes) is usually enough.

**Alternative:** Use the Vertex AI SDK so only Vertex AI is used: set `GOOGLE_AI_SDK=vertexai` in `.env` (and in `agentsec.yaml` for the vertexai gateway). Then standard ADC (`gcloud auth application-default login`) is sufficient and you do not need the `generative-language` scope.

### Debug Logging

By default, agentsec operates quietly (log level `WARNING`). To see what's happening under the hood - including messages sent to AI Defense, responses received, and inspection decisions - enable debug logging.

#### Logging Configuration

Logging can be configured via `agentsec.yaml`, `protect()` kwargs, or environment variables. For the full logging parameter reference and precedence rules, see [CONFIGURATION.md — logging](CONFIGURATION.md#logging) and [Appendix: Environment Variable Overrides](CONFIGURATION.md#4-appendix-environment-variable-overrides).

#### How to Enable Debug Logging

**Option 1: In `agentsec.yaml` (recommended for projects)**
```yaml
logging:
  level: DEBUG
  format: text
```

**Option 2: Environment variable**
```bash
export AGENTSEC_LOG_LEVEL=DEBUG
python your_agent.py
```

**Option 3: In your code (before `agentsec.protect()`)**
```python
import os
os.environ["AGENTSEC_LOG_LEVEL"] = "DEBUG"

from aidefense.runtime import agentsec
agentsec.protect()
```

**Option 4: Command line (one-off)**
```bash
AGENTSEC_LOG_LEVEL=DEBUG python your_agent.py
```

#### What You'll See with DEBUG Logging

**1. Patched LLM Call Flow**
```
╔══════════════════════════════════════════════════════════════
║ [PATCHED] LLM CALL: gpt-4o-mini
║ Operation: OpenAI.chat.completions.create | LLM Mode: enforce | Integration: api | Provider: openai
╚══════════════════════════════════════════════════════════════
[aidefense.runtime.agentsec] DEBUG: [PATCHED CALL] OpenAI.chat.completions.create - Request inspection (3 messages)
[aidefense.runtime.agentsec] DEBUG: [PATCHED CALL] OpenAI.chat.completions.create - Request decision: allow
```

**2. Request Payload Sent to AI Defense**
```
[aidefense.runtime.agentsec] DEBUG: AI Defense request: 3 messages, metadata=['user', 'src_app', 'transaction_id']
[aidefense.runtime.agentsec] DEBUG: AI Defense request payload: {
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello, how are you?"}
  ],
  "metadata": {"user": "test-user", "src_app": "my-agent"}
}
```

**3. AI Defense Response**
```
[aidefense.runtime.agentsec] DEBUG: AI Defense response: {
  "action": "allow",
  "reasons": [],
  "sanitized_content": null
}
```

**4. Response Inspection**
```
[aidefense.runtime.agentsec] DEBUG: [PATCHED CALL] OpenAI.chat.completions.create - Response inspection (response: 142 chars)
[aidefense.runtime.agentsec] DEBUG: [PATCHED CALL] OpenAI.chat.completions.create - Response decision: allow
[aidefense.runtime.agentsec] DEBUG: [PATCHED CALL] OpenAI.chat.completions.create - complete
```

**5. Gateway Mode (if using)**
```
[aidefense.runtime.agentsec] DEBUG: [GATEWAY] Sending request to openai gateway: https://gateway.example.com/v1/chat/completions
[aidefense.runtime.agentsec] DEBUG: [GATEWAY] Received response from openai gateway
```

**6. MCP Tool Call Inspection**
```
[aidefense.runtime.agentsec] DEBUG: [PATCHED CALL] MCP.call_tool(fetch_url) - Request inspection
[aidefense.runtime.agentsec] DEBUG: [PATCHED CALL] MCP.call_tool(fetch_url) - Request decision: allow
[aidefense.runtime.agentsec] DEBUG: [PATCHED CALL] MCP.call_tool(fetch_url) - Response inspection
[aidefense.runtime.agentsec] DEBUG: [PATCHED CALL] MCP.call_tool(fetch_url) - Response decision: allow
```

**7. Block Decision (when content violates policy)**
```
[aidefense.runtime.agentsec] DEBUG: AI Defense BLOCK response: {
  "action": "block",
  "reasons": ["prompt_injection_detected"],
  "sanitized_content": null
}
[aidefense.runtime.agentsec] WARNING: [BLOCKED] Content blocked by AI Defense: prompt_injection_detected
```

#### JSON Log Format

For production environments or log aggregation systems, use JSON format:

```bash
export AGENTSEC_LOG_LEVEL=DEBUG
export AGENTSEC_LOG_FORMAT=json
```

Output:
```json
{"timestamp": "2025-01-24T10:30:45.123Z", "level": "DEBUG", "logger": "aidefense.runtime.agentsec", "message": "AI Defense response: {'action': 'allow'}"}
```

### Version Compatibility

<!-- TBD: Document the following once stabilized:
  - agentsec SDK version this documentation applies to
  - Minimum supported versions of provider SDKs (e.g. openai >= 1.x, boto3 >= 1.x)
  - Known incompatibilities or version-specific behavior differences
-->

*This section is under development. Check the SDK changelog or release notes
for the latest compatibility information.*

### Getting Help

- Check the individual example READMEs for detailed setup instructions
- See [CONFIGURATION.md](CONFIGURATION.md) for the complete parameter reference (every `agentsec.yaml` key, `.env` variable, and `protect()` kwarg)
- Review the main [README.md](../../README.md) for SDK configuration
- Enable DEBUG logging to trace inspection flow
- Run `./scripts/run-unit-tests.sh` to verify SDK installation
