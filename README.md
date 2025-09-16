# cisco-aidefense-sdk

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
- [Enhanced Logging and Resource Management](#enhanced-logging-and-resource-management)
  - [Structured Logging](#structured-logging)
  - [Context Managers for Resource Cleanup](#context-managers-for-resource-cleanup)
  - [Logging Best Practices](#logging-best-practices)
- [Advanced Usage](#advanced-usage)
- [Error Handling](#error-handling)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

---

## Overview

The `cisco-aidefense-sdk` provides a developer-friendly interface for inspecting chat conversations and HTTP 
requests/responses using Cisco's AI Defense API.
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

> **Note:** The PyPI package name is `cisco-aidefense-sdk`, but you import it as `aidefense` in your Python code.

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
from aidefense import Config, ChatInspectionClient

# Create a custom configuration
config = Config(
    region="us",
    timeout=60,
    logger_params={
        "name": "my-app-aidefense",
        "level": "DEBUG",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    },
    retry_config={
        "total": 3,
        "backoff_factor": 0.5,
        "status_forcelist": [429, 500, 502, 503, 504]
    }
)

# Use the configuration with a client
client = ChatInspectionClient(api_key="YOUR_API_KEY", config=config)
```

## Enhanced Logging and Resource Management

The SDK provides comprehensive logging and resource management capabilities to help you monitor and debug your applications.

### Structured Logging

All SDK operations include structured logging with contextual information:

```python
# Configure the SDK with detailed logging
config = Config(
    logger_params={
        "name": "aidefense-app",
        "level": "DEBUG",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(extra)s"
    }
)

# The SDK will now log detailed information about operations
client = ManagementClient(management_api_key="YOUR_API_KEY", config=config)
applications = client.applications.list_applications()
# DEBUG logs will include details about request parameters, response times, and result counts
```

Key logging features:
- **Request/Response Tracking**: Each API request is logged with a unique request ID
- **Performance Metrics**: Response times are logged for performance monitoring
- **Error Context**: Detailed error information including validation errors
- **Operation Context**: Relevant parameters and results for each operation

### Context Managers for Resource Cleanup

All client classes support context managers for automatic resource cleanup:

```python
# Using context managers for automatic cleanup
with ManagementClient(management_api_key="YOUR_API_KEY") as client:
    # All operations within this block
    applications = client.applications.list_applications()
    # Session is automatically closed when exiting the block
```

This ensures that HTTP sessions and other resources are properly cleaned up, even if exceptions occur.

### Logging Best Practices

To get the most out of the SDK's logging capabilities:

1. **Set Appropriate Log Levels**:
   - `INFO`: For tracking normal operations
   - `DEBUG`: For detailed request/response information
   - `WARNING`: For potential issues that don't prevent operation

2. **Use Structured Log Handlers**:
   ```python
   import logging
   import json_log_formatter
   
   formatter = json_log_formatter.JSONFormatter()
   json_handler = logging.FileHandler(filename='aidefense.log')
   json_handler.setFormatter(formatter)
   
   logger = logging.getLogger('aidefense')
   logger.addHandler(json_handler)
   logger.setLevel(logging.DEBUG)
   
   config = Config(logger=logger)
   ```

3. **Monitor Request IDs**: Each request has a unique ID that can be used to trace operations across logs.

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
