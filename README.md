# cisco-aidefense-sdk

**Cisco AI Defense Python SDK**
Integrate AI-powered security, privacy, and safety inspections into your Python applications and manage your AI Defense resources with ease.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Quickstart](#quickstart)
  - [Runtime Protection (Recommended)](#runtime-protection-recommended)
  - [Inspection API](#inspection-api)
  - [Model Scanning API](#model-scanning-api)
  - [Management API](#management-api)
- [SDK Structure](#sdk-structure)
- [Usage Examples](#usage-examples)
  - [Runtime Protection](#runtime-protection)
  - [Chat Inspection](#chat-inspection)
  - [HTTP Inspection](#http-inspection)
  - [MCP Inspection](#mcp-inspection)
  - [MCP Server Scanning](#mcp-server-scanning)
  - [Model Scanning](#model-scanning)
  - [Management API Examples](#management-api-examples)
  - [Validation API](#validation-api)
- [Configuration](#configuration)
- [Advanced Usage](#advanced-usage)
- [Error Handling](#error-handling)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

---

## Overview

The `cisco-aidefense-sdk` provides a developer-friendly interface for inspecting chat conversations and HTTP
requests/responses using Cisco's AI Defense API. It also includes a comprehensive Management API client for creating and managing applications, connections, policies, and events.

The SDK enables you to detect security, privacy, and safety risks in real time, with flexible configuration and robust validation, while also providing tools to manage your AI Defense resources programmatically.

---

## Features

- **Runtime Protection**: Auto-patch LLM clients (OpenAI, Azure OpenAI, Bedrock, Vertex AI) and MCP clients with just 2 lines of code. Supports API mode (inspection) and Gateway mode (proxy).
- **Chat Inspection**: Analyze chat prompts, responses, or full conversations for risks.
- **HTTP Inspection**: Inspect HTTP requests and responses, including support for `requests.Request`, `requests.PreparedRequest`, and `requests.Response` objects.
- **MCP Inspection**: Inspect Model Context Protocol (MCP) JSON-RPC 2.0 messages for security, privacy, and safety violations in AI agent tool calls, resource access, and responses.
- **MCP Server Scanning**: Scan MCP servers for security threats and vulnerabilities, manage resource connections, policies, and events.
- **Model Scanning**: Scan AI/ML model files and repositories for security threats, malicious code, and vulnerabilities.
- **Management API**: Create and manage applications, connections, policies, and events through a clean, intuitive API.
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

### Runtime Protection (Recommended)

The easiest way to protect your AI applications is with automatic runtime protection. Just 2 lines of code to secure all LLM and MCP interactions:

```python
from aidefense.runtime import agentsec
agentsec.protect()  # Auto-configures from environment variables

# Import your LLM client — it's automatically protected
from openai import OpenAI
client = OpenAI()

# All calls are now inspected by Cisco AI Defense
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

Configure via environment variables:

```bash
# API Mode (recommended for most deployments)
AGENTSEC_LLM_INTEGRATION_MODE=api
AI_DEFENSE_API_MODE_LLM_ENDPOINT=https://api.inspect.aidefense.cisco.com/api
AI_DEFENSE_API_MODE_LLM_API_KEY=your-api-key
AGENTSEC_API_MODE_LLM=on_enforce  # or on_monitor, off
```

See [Runtime Protection](#runtime-protection) for detailed configuration options.

### Inspection API

```python
from aidefense import ChatInspectionClient, HttpInspectionClient, Config

# Initialize client
client = ChatInspectionClient(api_key="YOUR_INSPECTION_API_KEY")

# Inspect a chat prompt
result = client.inspect_prompt("How do I hack a server?")
print(result.classifications, result.is_safe)
```

### Model Scanning API

```python
from aidefense.modelscan import ModelScanClient
from aidefense.modelscan.models import ScanStatus

# Initialize client
client = ModelScanClient(api_key="YOUR_MANAGEMENT_API_KEY")

# Scan a local model file
result = client.scan_file("/path/to/model.pkl")
if result.status == ScanStatus.COMPLETED:
    for file_info in result.analysis_results.items:
        if file_info.threats.items:
            print(f"⚠️ Threats found in {file_info.name}")
        else:
            print(f"✅ {file_info.name} is clean")
```

### Management API

```python
from aidefense import Config
from aidefense.management import ManagementClient
from aidefense.management.models.application import CreateApplicationRequest
from aidefense.management.models.connection import ConnectionType

# Initialize client
client = ManagementClient(api_key="YOUR_MANAGEMENT_API_KEY")

# Create an application
create_app_request = CreateApplicationRequest(
    application_name="My Test App",
    description="Test application created via SDK",
    connection_type=ConnectionType.API
)
result = client.applications.create_application(create_app_request)
print(f"Created application with ID: {result.application_id}")
```

### Validation API

The Validation API is implemented on top of the Management API stack and is provided as a separate client (`AiValidationClient`). It is not part of the `ManagementClient` aggregator.

```python
from aidefense import Config
from aidefense.management.validation_client import AiValidationClient
from aidefense.management.models.validation import (
    StartAiValidationRequest,
    AssetType,
    AWSRegion,
)

client = AiValidationClient(api_key="YOUR_MANAGEMENT_API_KEY", config=Config())

start_req = StartAiValidationRequest(
    asset_type=AssetType.APPLICATION,
    application_id="your-application-id",
    validation_scan_name="My SDK Scan",
    model_provider="OpenAI",
    model_endpoint_url_model_id="gpt-4",
)

resp = client.start_ai_validation(start_req)
print(resp.task_id)
```

---

## SDK Structure

### Runtime Protection (agentsec)

- `runtime/agentsec/__init__.py` — Main entry point with `protect()` function
- `runtime/agentsec/config.py` — Configuration loading from environment/parameters
- `runtime/agentsec/patchers/` — Auto-patching for LLM clients (OpenAI, Bedrock, Vertex AI, MCP)
- `runtime/agentsec/inspectors/` — API and Gateway mode inspectors for LLM and MCP
- `runtime/agentsec/decision.py` — Decision model for inspection results
- `runtime/agentsec/exceptions.py` — SecurityPolicyError for blocked requests

### Runtime Inspection API

- `runtime/chat_inspect.py` — ChatInspectionClient for chat-related inspection
- `runtime/http_inspect.py` — HttpInspectionClient for HTTP request/response inspection
- `runtime/mcp_inspect.py` — MCPInspectionClient for MCP JSON-RPC 2.0 message inspection
- `runtime/models.py` — Data models and enums for requests, responses, rules, etc.
- `runtime/mcp_models.py` — Data models for MCP messages and inspection responses

### MCP Server Scanning API

- `mcpscan/mcp_scan.py` — MCPScanClient for scanning MCP servers
- `mcpscan/resource_connections.py` — ResourceConnectionClient for managing resource connections
- `mcpscan/policies.py` — MCPPolicyClient for managing MCP Gateway policies
- `mcpscan/events.py` — MCPEventClient for retrieving MCP-related events
- `mcpscan/models.py` — Data models for MCP server scanning, connections, and events

### Model Scanning API

- `modelscan/model_scan.py` — ModelScanClient for high-level file and repository scanning
- `modelscan/model_scan_base.py` — ModelScan base class for granular scan operations
- `modelscan/models.py` — Data models for scan requests, responses, and status information

### Management API

- `management/__init__.py` — ManagementClient for accessing all management APIs
- `management/applications.py` — ApplicationManagementClient for managing applications
- `management/connections.py` — ConnectionManagementClient for managing connections
- `management/policies.py` — PolicyManagementClient for managing policies
- `management/events.py` — EventManagementClient for retrieving events
- `management/models/` — Data models for all management resources
  - `management/validation_client.py` — AiValidationClient for starting/listing validation jobs
  - `management/models/validation.py` — Validation-related request/response models and enums

### Common

- `config.py` — SDK-wide configuration (logging, retries, connection pool)
- `exceptions.py` — Custom exception classes for robust error handling

---

## Usage Examples

### Runtime Protection

Runtime protection automatically patches LLM and MCP clients to inspect all interactions with Cisco AI Defense.

#### API Mode (Default)

In API mode, the SDK inspects requests via the AI Defense API, then calls the LLM provider directly.

```python
from aidefense.runtime import agentsec

agentsec.protect(
    llm_integration_mode="api",
    api_mode_llm="on_enforce",  # on_monitor, on_enforce, or off
    api_mode_llm_endpoint="https://api.inspect.aidefense.cisco.com/api",
    api_mode_llm_api_key="your-api-key",
    api_mode_fail_open_llm=True,  # Allow requests if API is unavailable
)

from openai import OpenAI
client = OpenAI()

# All calls are automatically inspected
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

#### Gateway Mode

In Gateway mode, all traffic is routed through the Cisco AI Defense Gateway proxy.

```python
from aidefense.runtime import agentsec

agentsec.protect(
    llm_integration_mode="gateway",
    gateway_mode_llm="on",
    providers={
        "openai": {
            "gateway_url": "https://gateway.aidefense.cisco.com/tenant/connections/openai-conn",
            "gateway_api_key": "your-gateway-key",
        },
    },
)

from openai import OpenAI
client = OpenAI()

# Calls are routed through the gateway
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

#### Skip Inspection for Specific Calls

```python
from aidefense.runtime import skip_inspection

# Skip inspection for specific calls
with skip_inspection():
    response = client.chat.completions.create(...)

# Or use as a decorator
from aidefense.runtime import no_inspection

@no_inspection()
def health_check():
    return client.chat.completions.create(...)
```

#### Error Handling

```python
from aidefense.runtime import SecurityPolicyError

try:
    response = client.chat.completions.create(...)
except SecurityPolicyError as e:
    print(f"Blocked: {e.decision.action}")
    print(f"Reasons: {e.decision.reasons}")
```

#### Supported Clients

| Client | Package | API Mode | Gateway Mode |
|--------|---------|----------|--------------|
| OpenAI | `openai` | ✅ | ✅ |
| Azure OpenAI | `openai` | ✅ | ✅ |
| AWS Bedrock | `boto3` | ✅ | ✅ |
| Vertex AI | `google-cloud-aiplatform` | ✅ | ✅ |
| MCP | `mcp` | ✅ | ✅ |

### Chat Inspection

```python
from aidefense import ChatInspectionClient

client = ChatInspectionClient(api_key="YOUR_INSPECTION_API_KEY")
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

client = HttpInspectionClient(api_key="YOUR_INSPECTION_API_KEY")

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

### MCP Inspection

The MCP (Model Context Protocol) Inspection API allows you to inspect JSON-RPC 2.0 messages used by AI agents for security, privacy, and safety violations.

```python
from aidefense import MCPInspectionClient, Config
from aidefense.runtime import MCPMessage

# Initialize client
client = MCPInspectionClient(api_key="YOUR_INSPECTION_API_KEY")

# Inspect a tool call request
result = client.inspect_tool_call(
    tool_name="execute_query",
    arguments={"query": "SELECT * FROM users"},
    message_id=1
)
print(f"Is safe: {result.result.is_safe}")

# Inspect a resource read request
result = client.inspect_resource_read(
    uri="file:///etc/passwd",
    message_id=2
)
if result.result and not result.result.is_safe:
    print("Sensitive resource access detected!")

# Inspect a tool response for data leakage (PII, PCI, PHI)
result = client.inspect_response(
    result_data={
        "content": [
            {"type": "text", "text": "User email: john.doe@example.com, SSN: 123-45-6789"}
        ]
    },
    method="tools/call",
    params={"name": "get_user_info", "arguments": {"user_id": "123"}},
    message_id=3
)
if result.result and not result.result.is_safe:
    print("Response contains sensitive data!")
    for rule in result.result.rules or []:
        print(f"  Triggered: {rule.rule_name}")

# Inspect a raw MCP message
message = MCPMessage(
    jsonrpc="2.0",
    method="tools/call",
    params={"name": "search", "arguments": {"query": "confidential data"}},
    id=4
)
result = client.inspect(message)
print(f"Action: {result.result.action}")
```

### MCP Server Scanning

The MCP Server Scanning API allows you to scan MCP servers for security threats and manage resource connections.

```python
from aidefense.mcpscan import MCPScanClient, ResourceConnectionClient
from aidefense.mcpscan.models import (
    StartMCPServerScanRequest,
    TransportType,
    MCPScanStatus,
    CreateResourceConnectionRequest,
    ResourceConnectionType,
)

# Initialize the MCP scan client
client = MCPScanClient(api_key="YOUR_MANAGEMENT_API_KEY")

# Scan an MCP server
request = StartMCPServerScanRequest(
    name="My MCP Server",
    url="https://mcp-server.example.com/sse",
    description="Production MCP server",
    connection_type=TransportType.SSE
)

# Run the scan (waits for completion)
result = client.scan_mcp_server(request)

if result.status == MCPScanStatus.COMPLETED:
    print("✅ Scan completed")
    if result.result and result.result.is_safe:
        print("✅ MCP server is safe")
    else:
        print("⚠️ Security issues detected")

# Manage resource connections
conn_client = ResourceConnectionClient(api_key="YOUR_MANAGEMENT_API_KEY")

# Create a connection
create_request = CreateResourceConnectionRequest(
    connection_name="Production MCP Connection",
    connection_type=ResourceConnectionType.MCP_GATEWAY,
    resource_ids=[]  # Add MCP server IDs after registration
)
response = conn_client.create_connection(create_request)
print(f"Created connection: {response.connection_id}")
```

### Model Scanning

#### Scanning Local Files

```python
from aidefense.modelscan import ModelScanClient
from aidefense.modelscan.models import ScanStatus

# Initialize client
client = ModelScanClient(api_key="YOUR_MANAGEMENT_API_KEY")

# Scan a local model file
result = client.scan_file("/path/to/model.pkl")

# Check the results
if result.status == ScanStatus.COMPLETED:
    print("✅ Scan completed successfully")

    # Check for threats in each file
    for file_info in result.analysis_results.items:
        if file_info.threats.items:
            print(f"⚠️  Threats found in {file_info.name}:")
        else:
            print(f"✅ {file_info.name} is clean")
elif result.status == ScanStatus.FAILED:
    print("❌ Scan failed")
```

#### Scanning Repositories

```python
from aidefense.modelscan import ModelScanClient
from aidefense.modelscan.models import (
    ModelRepoConfig, Auth, HuggingFaceAuth, URLType, ScanStatus
)

# Initialize client
client = ModelScanClient(api_key="YOUR_MANAGEMENT_API_KEY")

# Configure repository scan with authentication
repo_config = ModelRepoConfig(
    url="https://huggingface.co/username/model-name",
    type=URLType.HUGGING_FACE,
    auth=Auth(huggingface=HuggingFaceAuth(access_token="YOUR_HF_TOKEN"))
)

# Scan the repository
result = client.scan_repo(repo_config)

# Process results
if result.status == ScanStatus.COMPLETED:
    print("✅ Repository scan completed")
    print(f"Repository: {result.repository.url}")
    print(f"Files scanned: {result.repository.files_scanned}")

    # Check for threats
    for file_info in result.analysis_results.items:
        if file_info.threats.items:
            print(f"⚠️  Threats in {file_info.name}")
```

#### Listing and Managing Scans

```python
from aidefense.modelscan import ModelScanClient
from aidefense.modelscan.models import (
    ListScansRequest, GetScanStatusRequest
)

client = ModelScanClient(api_key="YOUR_MANAGEMENT_API_KEY")

# List all scans with pagination
request = ListScansRequest(limit=10, offset=0)
response = client.list_scans(request)

print(f"Found {response.scans.paging.total} scans")
for scan in response.scans.items:
    print(f"  • {scan.scan_id}: {scan.name} - {scan.status}")

# Get detailed information about a specific scan
scan_id = response.scans.items[0].scan_id
detail_request = GetScanStatusRequest(file_limit=10, file_offset=0)
detail_response = client.get_scan(scan_id, detail_request)

scan_info = detail_response.scan_status_info
print(f"Scan status: {scan_info.status}")
print(f"Files analyzed: {len(scan_info.analysis_results.items)}")
```

### Management API

#### Managing Applications

```python
from aidefense.management import ManagementClient
from aidefense.management.models.application import CreateApplicationRequest, UpdateApplicationRequest
from aidefense.management.models.connection import ConnectionType

# Initialize client
client = ManagementClient(api_key="YOUR_MANAGEMENT_API_KEY")

# Create an application
create_app_request = CreateApplicationRequest(
    application_name="My Test App",
    description="Test application created via SDK",
    connection_type=ConnectionType.API
)
result = client.applications.create_application(create_app_request)
application_id = result.application_id

# Get application details
application = client.applications.get_application(application_id, expanded=True)
print(f"Application name: {application.application_name}")

# Update an application
update_request = UpdateApplicationRequest(
    application_name="Updated App Name",
    description="Updated description"
)
client.applications.update_application(application_id, update_request)

# Delete an application
client.applications.delete_application(application_id)
```

#### Managing Policies and Connections

```python
from aidefense.management import ManagementClient
from aidefense.management.models.policy import ListPoliciesRequest, AddOrUpdatePolicyConnectionsRequest

# Initialize client
client = ManagementClient(api_key="YOUR_MANAGEMENT_API_KEY")

# List policies
policies = client.policies.list_policies(ListPoliciesRequest(limit=10, expanded=True))
for policy in policies.items:
    print(f"{policy.policy_id}: {policy.name}")

# Associate connections with a policy
policy_id = policies.items[0].policy_id
client.policies.update_policy_connections(
    policy_id,
    AddOrUpdatePolicyConnectionsRequest(
        connections_to_associate=["connection-id-1", "connection-id-2"]
    )
)
```

#### Managing Events

```python
from aidefense.management import ManagementClient
from aidefense.management.models.event import ListEventsRequest
from datetime import datetime, timedelta

# Initialize client
client = ManagementClient(api_key="YOUR_MANAGEMENT_API_KEY")

# List events from the last 24 hours
end_time = datetime.now()
start_time = end_time - timedelta(days=1)

list_events_request = ListEventsRequest(
    limit=5,
    start_date=start_time,
    end_date=end_time,
    expanded=True,
    sort_by="event_timestamp",
    order="desc"
)

events = client.events.list_events(list_events_request)
print(f"Found {events.paging.total} events")

# Get details for an event
if events.items:
    event_id = events.items[0].event_id
    event_detail = client.events.get_event(event_id, expanded=True)
    print(f"Event action: {event_detail.event_action}")

    # Get conversation for the event
    conversation = client.events.get_event_conversation(event_id, expanded=True)
    if "messages" in conversation and conversation["messages"].items:
        print(f"Found {len(conversation['messages'].items)} messages in conversation")
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

# Configuration with custom API endpoints
custom_endpoint_config = Config(
    runtime_base_url="https://custom-runtime-endpoint.example.com",
    management_base_url="https://custom-management-endpoint.example.com",
    logger_params={"level": "INFO"},
    retry_config={"total": 3, "backoff_factor": 2.0},
)

# Initialize clients with custom configuration
chat_client = ChatInspectionClient(api_key="YOUR_INSPECTION_API_KEY", config=custom_endpoint_config)
http_client = HttpInspectionClient(api_key="YOUR_INSPECTION_API_KEY", config=custom_endpoint_config)
management_client = ManagementClient(api_key="YOUR_MANAGEMENT_API_KEY", config=custom_endpoint_config)
validation_client = AiValidationClient(api_key="YOUR_MANAGEMENT_API_KEY", config=custom_endpoint_config)
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
from aidefense.exceptions import ValidationError, ApiError

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
