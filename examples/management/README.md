# AI Defense Management API Examples

This directory contains examples demonstrating how to use the AI Defense Management API through the Python SDK. The Management API allows you to programmatically manage your AI Defense resources, including applications, connections, policies, and events.

## Prerequisites

Before running these examples, you need:

1. An AI Defense account with API access
2. An API key with appropriate permissions
3. The AI Defense Python SDK installed

```bash
pip install ai-defense-python-sdk
```

## Setting Up

Set your API key as an environment variable:

```bash
export MANAGEMENT_API_KEY="your-api-management-key"
```

## Examples

### Management Client Usage

The [`management_client_usage.py`](./management_client_usage.py) script demonstrates the core functionality of the Management API:

- Initializing the ManagementClient
- Listing and creating applications
- Listing and creating connections
- Listing and viewing policies
- Listing and viewing events

To run this example:

```bash
python management_client_usage.py
```

## API Resources

The Management API provides access to the following resources:

### Applications

Applications represent AI systems that you want to protect with AI Defense. You can:

- List applications
- Create an application
- Get application details
- Update application
- Delete application

### Connections

Connections link your applications to AI Defense. You can:

- List connections
- Create a connection
- Get connection details
- Delete connection
- Manage API keys for connections

### Policies

Policies define the security rules applied to your applications. You can:

- List policies
- Get policy details
- Update policy
- Delete policy
- Add or update connections for a policy

### Events

Events are security incidents detected by AI Defense. You can:

- List events
- Get event details
- Get event conversation history

### Validation (under Management stack)

The Validation API is implemented on top of the Management API stack and is provided as a separate client (`AiValidationClient`). It is not part of the `ManagementClient` aggregator.

- Start an AI validation job
- Get job status/details
- List all validation configs
- Get a specific validation config by task_id

See the example: [`validation_client_usage.py`](./validation_client_usage.py)

Imports you will need:

```python
from aidefense.management.validation_client import AiValidationClient
from aidefense.management.models.validation import (
    StartAiValidationRequest,
    AssetType,
    AWSRegion,
    Header,
)
```

Run the example:

```bash
python validation_client_usage.py
```

## Best Practices

1. **Resource Management**: Always close the ManagementClient when you're done to release resources:

```python
client = ManagementClient(api_key=api_key)
try:
    # Use the client
finally:
    client.close()
```

2. **Error Handling**: Handle API errors appropriately:

```python
from aidefense.exceptions import ValidationError, ApiError

try:
    client.applications.create_application(...)
except ValidationError as e:
    print(f"Invalid request: {e}")
except ApiError as e:
    print(f"API error: {e}")
```

3. **Pagination**: For list operations, use the `limit` and `offset` parameters to paginate through results:

```python
# Get first page
response = client.applications.list_applications(limit=10, offset=0)
# Get second page
response = client.applications.list_applications(limit=10, offset=10)
```

## Additional Resources

- [AI Defense SDK Documentation](https://github.com/cisco-ai-defense/ai-defense-python-sdk)
- [AI Defense Management API Reference](https://api.security.cisco.com/api/ai-defense/v1)
