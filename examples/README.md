# AI Defense Python SDK Examples

This directory contains examples demonstrating how to use the AI Defense Python SDK with various model providers and inspection methods.

## Directory Structure

The examples are organized into three main categories:

```
examples/
├── README.md                # This file
├── chat/                    # Chat inspection examples
│   ├── chat_inspect_conversation.py
│   ├── chat_inspect_multiple_clients.py
│   ├── chat_inspect_prompt.py
│   ├── chat_inspect_response.py
│   └── providers/           # Model provider specific examples
│       ├── chat_inspect_bedrock.py
│       ├── chat_inspect_cohere_prompt_response.py
│       ├── chat_inspect_mistral.py
│       ├── chat_inspect_openai.py
│       └── chat_inspect_vertex_ai.py
├── http/                    # HTTP inspection examples
│   ├── http_inspect_http_api.py
│   ├── http_inspect_multiple_clients.py
│   ├── http_inspect_request.py
│   ├── http_inspect_request_from_http_library.py
│   ├── http_inspect_response.py
│   ├── http_inspect_response_from_http_library.py
│   └── providers/           # Model provider specific examples
│       ├── http_inspect_bedrock_api.py
│       ├── http_inspect_cohere_api.py
│       ├── http_inspect_mistral_api.py
│       ├── http_inspect_openai_api.py
│       └── http_inspect_vertex_ai_api.py
└── advanced/                # Advanced usage examples
    ├── advanced_usage.py
    └── custom_configuration.py
```

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

To run these examples:

1. Install the AI Defense Python SDK: `pip install aidefense-python-sdk`
2. Set your API keys as environment variables (varies by example)
3. Run the example: `python examples/chat/chat_inspect_prompt.py`

For model provider examples, you'll need an API key for both AI Defense and the specific model provider.
