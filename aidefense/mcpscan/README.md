# AI Defense MCPScan Module

The AI Defense MCPScan module provides security scanning capabilities for MCP (Model Context Protocol) servers. It allows you to scan MCP servers for security threats and vulnerabilities without requiring prior registration.

## Features

- **On-Demand Scanning**: Scan MCP servers without pre-registration
- **Multiple Transport Types**: Support for SSE, Streamable, and STDIO connections
- **Authentication Support**: API Key and OAuth authentication options
- **Async Support**: Both synchronous and asynchronous scanning workflows

## Installation

```bash
pip install cisco-aidefense-sdk
```

## Quick Start

### Basic MCP Server Scanning

```python
from aidefense.mcpscan import MCPScanClient
from aidefense.mcpscan.models import (
    StartMCPServerScanRequest, TransportType, MCPScanStatus
)
from aidefense import Config

# Initialize the client
client = MCPScanClient(
    api_key="YOUR_MANAGEMENT_API_KEY",
    config=Config(management_base_url="https://api.security.cisco.com")
)

# Create scan request
request = StartMCPServerScanRequest(
    name="My MCP Server",
    url="https://mcp-server.example.com/sse",
    description="Production MCP server for AI assistant",
    connection_type=TransportType.SSE
)

# Run the scan (waits for completion by default)
result = client.scan_mcp_server(request)

# Check the results
if result.status == MCPScanStatus.COMPLETED:
    print("✅ Scan completed successfully")
    if result.result:
        if result.result.is_safe:
            print("✅ MCP server is safe")
        else:
            print("⚠️ Security issues detected")
elif result.status == MCPScanStatus.FAILED:
    print(f"❌ Scan failed: {result.error_message}")
```

### Scanning with API Key Authentication

```python
from aidefense.mcpscan.models import AuthConfig, AuthType, ApiKeyConfig

# Configure authentication for the MCP server
auth_config = AuthConfig(
    auth_type=AuthType.API_KEY,
    api_key=ApiKeyConfig(
        header_name="X-API-Key",
        api_key="your_mcp_server_api_key_here"
    )
)

# Create scan request with authentication
request = StartMCPServerScanRequest(
    name="Authenticated MCP Server",
    url="https://secure-mcp-server.example.com/sse",
    connection_type=TransportType.SSE,
    auth_config=auth_config
)

result = client.scan_mcp_server(request)
```

### Asynchronous Scanning

```python
import time

# Start scan without waiting
scan_id = client.scan_mcp_server_async(request)
print(f"Scan started with ID: {scan_id}")

# Poll for completion
while True:
    status = client.get_scan_status(scan_id)
    if status.status == MCPScanStatus.COMPLETED:
        print("✅ Scan completed!")
        break
    elif status.status == MCPScanStatus.FAILED:
        print(f"❌ Scan failed: {status.error_message}")
        break
    time.sleep(5)
```

### Get Scan Status

```python
# Get status of a previously started scan
status = client.get_scan_status("your-scan-id")
print(f"Status: {status.status}")
if status.result:
    print(f"Is Safe: {status.result.is_safe}")
```

## Transport Types

| Transport    | Description        | Use Case                    |
| ------------ | ------------------ | --------------------------- |
| `SSE`        | Server-Sent Events | Web-based MCP servers       |
| `STREAMABLE` | Streamable HTTP    | Modern HTTP streaming       |
| `STDIO`      | Standard I/O       | Local process-based servers |

## Scan Status Reference

| Status        | Description                      |
| ------------- | -------------------------------- |
| `QUEUED`      | Scan is waiting to be processed  |
| `IN_PROGRESS` | Scan is currently running        |
| `COMPLETED`   | Scan finished successfully       |
| `FAILED`      | Scan encountered an error        |
| `CANCELLED`   | Scan was manually cancelled      |
| `CANCELLING`  | Scan cancellation is in progress |

## Error Handling

```python
from aidefense.exceptions import ApiError, ValidationError, SDKError

try:
    result = client.scan_mcp_server(request, max_wait_time=300)
except TimeoutError as e:
    print(f"Scan timed out: {e}")
except ValidationError as e:
    print(f"Invalid request: {e}")
except ApiError as e:
    print(f"API error: {e}")
except SDKError as e:
    print(f"SDK error: {e}")
```
