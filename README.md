# aidefense-sdk

**Cisco AI Defense Python SDK**
Integrate AI-powered security, privacy, and safety inspections into your Python applications with ease.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Quickstart](#quickstart)
- [SDK Structure](#sdk-structure)
- [Usage Examples](#usage-examples)
  - [Chat Inspection](#chat-inspection)
  - [HTTP Inspection](#http-inspection)
- [Configuration](#configuration)
- [Advanced Usage](#advanced-usage)
- [Error Handling](#error-handling)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

---

## Overview

The `aidefense-sdk` provides a developer-friendly interface for inspecting chat conversations and HTTP requests/responses using Cisco's AI Defense API.
It enables you to detect security, privacy, and safety risks in real time, with flexible configuration and robust validation.

---

## Features

- **Chat Inspection**: Analyze chat prompts, responses, or full conversations for risks.
- **HTTP Inspection**: Inspect HTTP requests and responses, including support for `requests.Request`, `requests.PreparedRequest`, and `requests.Response` objects.
- **Strong Input Validation**: Prevent malformed requests and catch errors early.
- **Flexible Configuration**: Easily customize logging, retry policies, and connection pooling.
- **Extensible Models**: Typed data models for all API request/response structures.
- **Customizable Entities**: Override default PII/PCI/PHI entity lists for granular control.
- **Robust Error Handling**: Typed exceptions for all error scenarios.

---

## Installation

```bash
pip install cisco-aidefense-sdk
```

> **Note:** The PyPI package name is `aidefense-sdk`, but you import it as `aidefense` in your Python code.

Or, for local development:

```bash
git clone https://github.com/cisco-ai-defense/ai-defense-python-sdk
cd aidefense-python-sdk

pip install -e .
```

---

## Dependency Management

This project uses [Poetry](https://python-poetry.org/) for dependency management and packaging.

- **Python Version:** Requires Python 3.9 or newer.
- **Install dependencies:**
  ```bash
  poetry install
  ```
- **Add dependencies:**
  ```bash
  poetry add <package>
  ```
- **Add dev dependencies:**
  ```bash
  poetry add --group dev <package>
  ```
- **Editable install (for development):**
  ```bash
  pip install -e .
  # or use poetry install (recommended)
  ```
- **Lock dependencies:**
  ```bash
  poetry lock --no-update
  ```
- **Activate Poetry shell:**
  ```bash
  poetry shell
  ```

See [pyproject.toml](./pyproject.toml) for the full list of dependencies and Python compatibility.

---

## Quickstart

```python
from aidefense import ChatInspectionClient, HttpInspectionClient, Config

# Initialize client
client = ChatInspectionClient(api_key="YOUR_API_KEY")

# Inspect a chat prompt
result = client.inspect_prompt("How do I hack a server?")
print(result.classifications, result.is_safe)
```

---

## SDK Structure

- `runtime/chat_inspect.py` — ChatInspectionClient for chat-related inspection
- `runtime/http_inspect.py` — HttpInspectionClient for HTTP request/response inspection
- `runtime/models.py` — Data models and enums for requests, responses, rules, etc.
- `config.py` — SDK-wide configuration (logging, retries, connection pool)
- `exceptions.py` — Custom exception classes for robust error handling

---

## Usage Examples

### Chat Inspection

```python
from aidefense_python_sdk import ChatInspectionClient

client = ChatInspectionClient(api_key="YOUR_API_KEY")
response = client.inspect_prompt("What is your credit card number?")
print(response.is_safe)
for rule in response.rules or []:
    print(rule.rule_name, rule.classification)
```

### HTTP Inspection

```python
from aidefense import HttpInspectionClient
from aidefense.runtime.models import Message, Role
import requests
import json

client = HttpInspectionClient(api_key="YOUR_API_KEY")

# Inspect a request with dictionary body (automatically JSON-serialized)
payload = {
    "model": "gpt-4",
    "messages": [
        {"role": "user", "content": "Tell me about security"}
    ]
}
result = client.inspect_request(
    method="POST",
    url="https://api.example.com/v1/chat/completions",
    headers={"Content-Type": "application/json"},
    body=payload,  # Dictionary is automatically serialized to JSON
)
print(result.is_safe)

# Inspect using raw bytes or string
json_bytes = json.dumps({"key": "value"}).encode()
result = client.inspect_request(
    method="POST",
    url="https://example.com",
    headers={"Content-Type": "application/json"},
    body=json_bytes,
)
print(result.is_safe)

# Inspect a requests.Request or PreparedRequest
req = requests.Request("GET", "https://example.com").prepare()
result = client.inspect_request_from_http_library(req)
print(result.is_safe)
```

---

## Configuration

The SDK uses a `Config` object for global settings:

- **Logger**: Pass a custom logger or logger parameters.
- **Retry Policy**: Customize retry attempts, backoff, and status codes.
- **Connection Pool**: Control HTTP connection pooling for performance.

```python
from aidefense import Config

# Basic configuration
config = Config(
    logger_params={"level": "DEBUG"},
    retry_config={"total": 5, "backoff_factor": 1.0},
)

# Configuration with custom API endpoint
custom_endpoint_config = Config(
    runtime_base_url="https://custom-api-endpoint.example.com",
    logger_params={"level": "INFO"},
    retry_config={"total": 3, "backoff_factor": 2.0},
)

# Initialize clients with custom configuration
chat_client = ChatInspectionClient(api_key="YOUR_API_KEY", config=custom_endpoint_config)
http_client = HttpInspectionClient(api_key="YOUR_API_KEY", config=custom_endpoint_config)
```

---

## Advanced Usage

- **Custom Inspection Rules**: Pass an `InspectionConfig` to inspection methods to enable/disable specific rules.
- **Entity Types**: For rules like PII/PCI/PHI, specify entity types for granular inspection.
- **Override Default Entities**: Pass a custom `entities_map` to HTTP inspection for full control.
- **Utility Functions**: Use `aidefense.utils.to_base64_bytes` to easily encode HTTP bodies for inspection.
- **Async Support**: (Coming soon) Planned support for async HTTP inspection.

---

## Error Handling

All SDK errors derive from `SDKError` in `exceptions.py`.
Specific exceptions include `ValidationError` (input issues) and `ApiError` (API/server issues).

```python
from aidefense_python_sdk.exceptions import ValidationError, ApiError

try:
    client.inspect_prompt(Message(role=Role.USER, content="..."))
except ValidationError as ve:
    print("Validation error:", ve)
except ApiError as ae:
    print("API error:", ae)
```

---

## Contributing

Contributions are welcome! Please open issues or pull requests for bug fixes, new features, or documentation improvements.

---

## Support

For help or questions, please open an issue.
