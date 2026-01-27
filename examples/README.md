# AI Defense Python SDK Examples

This directory contains examples demonstrating how to use the AI Defense Python SDK with various model providers and inspection methods.

## Directory Structure

The examples are organized into the following categories:

```
examples/
├── README.md                    # This file
├── agentsec/                    # Runtime protection examples (RECOMMENDED)
│   ├── 1_simple/                # Simple standalone examples
│   │   ├── basic_protection.py
│   │   ├── openai_example.py
│   │   ├── streaming_example.py
│   │   ├── mcp_example.py
│   │   ├── gateway_mode_example.py
│   │   └── skip_inspection_example.py
│   └── 2_agent-frameworks/      # Agent framework integrations
│       ├── strands-agent/       # AWS Strands + MCP
│       ├── langchain-agent/     # LangChain with tool calling
│       ├── langgraph-agent/     # LangGraph + MCP
│       ├── crewai-agent/        # CrewAI + MCP
│       ├── autogen-agent/       # AutoGen + MCP
│       └── openai-agent/        # OpenAI Agents SDK
├── chat/                        # Chat inspection examples
│   ├── chat_inspect_conversation.py
│   ├── chat_inspect_multiple_clients.py
│   ├── chat_inspect_prompt.py
│   ├── chat_inspect_response.py
│   └── providers/               # Model provider specific examples
│       ├── chat_inspect_bedrock.py
│       ├── chat_inspect_cohere_prompt_response.py
│       ├── chat_inspect_mistral.py
│       ├── chat_inspect_openai.py
│       └── chat_inspect_vertex_ai.py
├── http/                        # HTTP inspection examples
│   ├── http_inspect_http_api.py
│   ├── http_inspect_multiple_clients.py
│   ├── http_inspect_request.py
│   ├── http_inspect_request_from_http_library.py
│   ├── http_inspect_response.py
│   ├── http_inspect_response_from_http_library.py
│   └── providers/               # Model provider specific examples
│       ├── http_inspect_bedrock_api.py
│       ├── http_inspect_cohere_api.py
│       ├── http_inspect_mistral_api.py
│       ├── http_inspect_openai_api.py
│       └── http_inspect_vertex_ai_api.py
└── advanced/                    # Advanced usage examples
    ├── advanced_usage.py
    └── custom_configuration.py
```

## Runtime Protection Examples (Recommended)

Runtime protection automatically patches LLM and MCP clients with just 2 lines of code. This is the **recommended** approach for most applications.

### Quick Start

```python
from aidefense.runtime import agentsec
agentsec.protect()  # Auto-configures from environment

from openai import OpenAI
client = OpenAI()

# All calls are now inspected by Cisco AI Defense
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### Simple Examples

| Example | Description |
|---------|-------------|
| [basic_protection.py](./agentsec/1_simple/basic_protection.py) | Minimal 2-line protection example |
| [openai_example.py](./agentsec/1_simple/openai_example.py) | OpenAI client with protection |
| [streaming_example.py](./agentsec/1_simple/streaming_example.py) | Streaming responses |
| [mcp_example.py](./agentsec/1_simple/mcp_example.py) | MCP tool inspection |
| [gateway_mode_example.py](./agentsec/1_simple/gateway_mode_example.py) | Gateway mode configuration |
| [skip_inspection_example.py](./agentsec/1_simple/skip_inspection_example.py) | Per-call exclusion |

### Agent Framework Examples

| Framework | Directory | Description |
|-----------|-----------|-------------|
| AWS Strands | [strands-agent/](./agentsec/2_agent-frameworks/strands-agent/) | Strands agent with MCP tools |
| LangChain | [langchain-agent/](./agentsec/2_agent-frameworks/langchain-agent/) | LangChain with tool calling |
| LangGraph | [langgraph-agent/](./agentsec/2_agent-frameworks/langgraph-agent/) | LangGraph agent with MCP |
| CrewAI | [crewai-agent/](./agentsec/2_agent-frameworks/crewai-agent/) | CrewAI multi-agent with MCP |
| AutoGen | [autogen-agent/](./agentsec/2_agent-frameworks/autogen-agent/) | AutoGen conversational agent |
| OpenAI Agents | [openai-agent/](./agentsec/2_agent-frameworks/openai-agent/) | OpenAI Agents SDK |

### Supported LLM Clients

| Client | Package | API Mode | Gateway Mode |
|--------|---------|----------|--------------|
| OpenAI | `openai` | ✅ | ✅ |
| Azure OpenAI | `openai` | ✅ | ✅ |
| AWS Bedrock | `boto3` | ✅ | ✅ |
| Vertex AI | `google-cloud-aiplatform` | ✅ | ✅ |
| MCP | `mcp` | ✅ | ✅ |

### Environment Variables

```bash
# API Mode (default)
AGENTSEC_LLM_INTEGRATION_MODE=api
AI_DEFENSE_API_MODE_LLM_ENDPOINT=https://api.inspect.aidefense.cisco.com/api
AI_DEFENSE_API_MODE_LLM_API_KEY=your-api-key
AGENTSEC_API_MODE_LLM=on_enforce  # on_monitor, on_enforce, or off

# Gateway Mode
AGENTSEC_LLM_INTEGRATION_MODE=gateway
AGENTSEC_OPENAI_GATEWAY_URL=https://gateway.aidefense.cisco.com/tenant/connections/openai-conn
AGENTSEC_OPENAI_GATEWAY_API_KEY=your-gateway-key
```

---

## Chat Inspection Examples

These examples use `ChatInspectionClient` to inspect chat prompts, responses, and conversations.

| Example | Description |
|---------|-------------|
| [chat_inspect_prompt.py](./chat/chat_inspect_prompt.py) | Basic example of prompt inspection |
| [chat_inspect_response.py](./chat/chat_inspect_response.py) | Basic example of response inspection |
| [chat_inspect_conversation.py](./chat/chat_inspect_conversation.py) | Basic example of conversation inspection |
| [chat_inspect_multiple_clients.py](./chat/chat_inspect_multiple_clients.py) | Using multiple chat inspection clients |

### Chat Inspection with Model Providers

| Model Provider | Example |
|----------------|---------|
| Cohere | [chat_inspect_cohere_prompt_response.py](./chat/providers/chat_inspect_cohere_prompt_response.py) |
| OpenAI | [chat_inspect_openai.py](./chat/providers/chat_inspect_openai.py) |
| Vertex AI | [chat_inspect_vertex_ai.py](./chat/providers/chat_inspect_vertex_ai.py) |
| Amazon Bedrock | [chat_inspect_bedrock.py](./chat/providers/chat_inspect_bedrock.py) |
| Mistral AI | [chat_inspect_mistral.py](./chat/providers/chat_inspect_mistral.py) |

## HTTP Inspection Examples

These examples use `HttpInspectionClient` to inspect HTTP requests and responses.

| Example | Description |
|---------|-------------|
| [http_inspect_request.py](./http/http_inspect_request.py) | Basic example of HTTP request inspection |
| [http_inspect_response.py](./http/http_inspect_response.py) | Basic example of HTTP response inspection |
| [http_inspect_request_from_http_library.py](./http/http_inspect_request_from_http_library.py) | Inspecting requests.Request objects |
| [http_inspect_response_from_http_library.py](./http/http_inspect_response_from_http_library.py) | Inspecting requests.Response objects |
| [http_inspect_http_api.py](./http/http_inspect_http_api.py) | Inspecting general HTTP API interactions |
| [http_inspect_multiple_clients.py](./http/http_inspect_multiple_clients.py) | Using multiple HTTP inspection clients |

### HTTP Inspection with Model Providers

| Model Provider | Example |
|----------------|---------|
| Cohere | [http_inspect_cohere_api.py](./http/providers/http_inspect_cohere_api.py) |
| OpenAI | [http_inspect_openai_api.py](./http/providers/http_inspect_openai_api.py) |
| Vertex AI | [http_inspect_vertex_ai_api.py](./http/providers/http_inspect_vertex_ai_api.py) |
| Amazon Bedrock | [http_inspect_bedrock_api.py](./http/providers/http_inspect_bedrock_api.py) |
| Mistral AI | [http_inspect_mistral_api.py](./http/providers/http_inspect_mistral_api.py) |

## Advanced Examples

| Example | Description |
|---------|-------------|
| [advanced_usage.py](./advanced/advanced_usage.py) | Advanced usage patterns including custom rules, error handling, and result processing |
| [custom_configuration.py](./advanced/custom_configuration.py) | Custom configuration options including logging, retry policies, and API endpoints |

## Running the Examples

### Runtime Protection Examples

```bash
# Install the SDK
pip install cisco-aidefense-sdk

# Set environment variables
export AGENTSEC_LLM_INTEGRATION_MODE=api
export AI_DEFENSE_API_MODE_LLM_ENDPOINT=https://api.inspect.aidefense.cisco.com/api
export AI_DEFENSE_API_MODE_LLM_API_KEY=your-api-key
export AGENTSEC_API_MODE_LLM=on_enforce
export OPENAI_API_KEY=your-openai-key

# Run simple examples
python examples/agentsec/1_simple/basic_protection.py
python examples/agentsec/1_simple/openai_example.py

# Run agent examples (with provider selection)
./examples/agentsec/2_agent-frameworks/strands-agent/scripts/run.sh --openai
./examples/agentsec/2_agent-frameworks/strands-agent/scripts/run.sh --bedrock
```

### Inspection Examples

```bash
# Install the SDK
pip install cisco-aidefense-sdk

# Set your API key
export AI_DEFENSE_INSPECTION_API_KEY=your-api-key

# Run chat inspection example
python examples/chat/chat_inspect_prompt.py

# Run HTTP inspection example
python examples/http/http_inspect_request.py
```

For model provider examples, you'll need an API key for both AI Defense and the specific model provider.
