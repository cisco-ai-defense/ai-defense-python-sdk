Usage Examples
==============

The AI Defense Python SDK comes with comprehensive examples demonstrating its functionality across different scenarios and AI model providers.

Examples Structure
-----------------

The examples are organized into the following structure:

.. code-block:: text

    examples/
    ├── README.md
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
    │   ├── http_inspect_api.py
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
    ├── mcp/                     # MCP inspection examples
    │   ├── mcp_inspect_message.py
    │   ├── mcp_inspect_response.py
    │   └── mcp_inspect_tool_call.py
    ├── mcpscan/                 # MCP server scanning examples
    │   ├── manage_mcp_policies.py
    │   ├── manage_mcp_servers.py
    │   ├── manage_resource_connections.py
    │   ├── register_mcp_server.py
    │   └── scan_mcp_server_async.py
    └── advanced/                # Advanced usage examples
        ├── advanced_usage.py
        └── custom_configuration.py

MCP Inspection Examples
------------------------

The MCP (Model Context Protocol) Inspection API allows you to inspect JSON-RPC 2.0 messages
for security, privacy, and safety. See ``examples/mcp/`` for runnable examples.

MCP Server Scanning Examples
-----------------------------

The MCP Server Scanning API allows you to scan MCP servers for security threats and manage
policies and resource connections. See ``examples/mcpscan/`` for runnable examples.

Chat Inspection Examples
-----------------------

Basic Chat Inspection
^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from aidefense import ChatInspectionClient

    # Initialize the client
    client = ChatInspectionClient(api_key="YOUR_INSPECTION_API_KEY")

    # Inspect a prompt
    prompt_result = client.inspect_prompt("What is your credit card number?")
    print(f"Prompt safety: {prompt_result.is_safe}")

    # Check classification if unsafe
    if not prompt_result.is_safe:
        print(f"Classifications: {prompt_result.classifications}")
        for rule in prompt_result.rules or []:
            print(f"Rule: {rule.rule_name}, Classification: {rule.classification}")

Provider-Specific Chat Inspection
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The SDK includes examples for multiple AI model providers:

- OpenAI
- Vertex AI (Google)
- Amazon Bedrock
- Mistral AI
- Cohere

HTTP Inspection Examples
-----------------------

HTTP Request Inspection
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from aidefense import HttpInspectionClient
    import json

    # Initialize the client
    client = HttpInspectionClient(api_key="YOUR_INSPECTION_API_KEY")

    # Example with dictionary body (automatically JSON-serialized)
    payload = {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": "Tell me about AI security"}
        ]
    }

    # Inspect the request
    result = client.inspect_request(
        method="POST",
        url="https://api.openai.com/v1/chat/completions",
        headers={"Content-Type": "application/json"},
        body=payload
    )

    print(f"Request is safe: {result.is_safe}")

Provider-Specific HTTP Inspection
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The SDK includes HTTP inspection examples for multiple AI model providers:

- OpenAI
- Vertex AI (Google)
- Amazon Bedrock
- Mistral AI
- Cohere

MCP Inspection Examples
-----------------------

The MCP (Model Context Protocol) Inspection API allows you to inspect JSON-RPC 2.0 messages
used by AI agents for security, privacy, and safety violations.

Basic MCP Inspection
^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from aidefense import MCPInspectionClient, Config
    from aidefense.runtime import MCPMessage

    # Initialize the client
    client = MCPInspectionClient(api_key="YOUR_INSPECTION_API_KEY")

    # Inspect a tool call request
    result = client.inspect_tool_call(
        tool_name="execute_query",
        arguments={"query": "SELECT * FROM users"},
        message_id=1
    )
    print(f"Is safe: {result.result.is_safe}")

    # Check triggered rules if unsafe
    if result.result and not result.result.is_safe:
        for rule in result.result.rules or []:
            print(f"Rule: {rule.rule_name}")

MCP Response Inspection
^^^^^^^^^^^^^^^^^^^^^^

Inspect tool responses for data leakage such as PII, PCI, or PHI:

.. code-block:: python

    from aidefense import MCPInspectionClient

    client = MCPInspectionClient(api_key="YOUR_INSPECTION_API_KEY")

    # Inspect a tool response for sensitive data
    result = client.inspect_response(
        result_data={
            "content": [
                {"type": "text", "text": "User SSN: 123-45-6789, Email: john@example.com"}
            ]
        },
        method="tools/call",
        params={"name": "get_user_info", "arguments": {"user_id": "123"}},
        message_id=1
    )

    if result.result and not result.result.is_safe:
        print("Response contains sensitive data!")
        for rule in result.result.rules or []:
            print(f"  Triggered: {rule.rule_name}")

MCP Server Scanning Examples
---------------------------

The MCP Server Scanning API allows you to scan MCP servers for security threats
and manage resource connections, policies, and events.

Basic MCP Server Scanning
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from aidefense.mcpscan import MCPScanClient
    from aidefense.mcpscan.models import (
        StartMCPServerScanRequest,
        TransportType,
        MCPScanStatus
    )

    # Initialize the client
    client = MCPScanClient(api_key="YOUR_MANAGEMENT_API_KEY")

    # Create scan request
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

Managing Resource Connections
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from aidefense.mcpscan import ResourceConnectionClient
    from aidefense.mcpscan.models import (
        CreateResourceConnectionRequest,
        FilterResourceConnectionsRequest,
        ResourceConnectionType
    )

    client = ResourceConnectionClient(api_key="YOUR_MANAGEMENT_API_KEY")

    # Create a connection
    request = CreateResourceConnectionRequest(
        connection_name="Production MCP Connection",
        connection_type=ResourceConnectionType.MCP_GATEWAY,
        resource_ids=[]
    )
    response = client.create_connection(request)
    print(f"Created: {response.connection_id}")

    # List connections
    filter_request = FilterResourceConnectionsRequest(limit=25)
    connections = client.filter_connections(filter_request)
    for conn in connections.connections.items:
        print(f"  - {conn.connection_name}: {conn.connection_status}")

Advanced Examples
---------------

The SDK also includes advanced usage examples demonstrating:

- Custom configurations
- Advanced retry policies
- Multiple clients in the same application
- Custom logging setups

See the `examples/` directory in the repository for the complete set of examples.
