Usage Examples
==============

The AI Defense Python SDK comes with comprehensive examples demonstrating its functionality across different scenarios and AI model providers.

Examples Structure
-----------------

The examples are organized into the following structure:

.. code-block:: text

    examples/
    ├── README.md
    ├── agentsec/                # Runtime protection examples
    │   ├── agentsec.yaml        # Configuration (modes, gateways, timeouts)
    │   ├── .env.example         # Template for environment variables
    │   ├── 1-simple/            # Simple standalone examples
    │   │   ├── basic_protection.py
    │   │   ├── openai_example.py
    │   │   ├── cohere_example.py
    │   │   ├── mistral_example.py
    │   │   ├── streaming_example.py
    │   │   ├── mcp_example.py
    │   │   ├── gateway_mode_example.py
    │   │   ├── multi_gateway_example.py
    │   │   └── skip_inspection_example.py
    │   ├── 2-agent-frameworks/  # Agent framework integrations
    │   │   ├── strands-agent/
    │   │   ├── langchain-agent/
    │   │   ├── langgraph-agent/
    │   │   ├── crewai-agent/
    │   │   ├── autogen-agent/
    │   │   └── openai-agent/
    │   └── 3-agent-runtimes/    # Cloud deployment examples
    │       ├── amazon-bedrock-agentcore/
    │       ├── gcp-vertex-ai-agent-engine/
    │       └── microsoft-foundry/
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

Runtime Protection Examples
--------------------------

Runtime protection automatically patches LLM and MCP clients to inspect all interactions.
See the `agentsec examples README <https://github.com/cisco/ai-defense-python-sdk/tree/main/examples/agentsec>`_ for end-to-end walkthroughs.

YAML Configuration (Recommended)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Use an ``agentsec.yaml`` file for production-grade configuration. The YAML can reference
environment variables using ``${VAR_NAME}`` syntax -- how you provision those variables
(shell exports, secrets manager, CI/CD injection, ``.env`` file, etc.) is up to you.

.. code-block:: python

    from aidefense.runtime import agentsec
    agentsec.protect(config="agentsec.yaml")

    # Import LLM client AFTER protect() -- it's automatically patched
    from openai import OpenAI
    client = OpenAI()

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello!"}]
    )

API Mode (Programmatic)
^^^^^^^^^^^^^^^^^^^^^^^

In API mode, the SDK inspects requests via the AI Defense API, then calls the LLM provider directly.

.. code-block:: python

    import os
    from aidefense.runtime import agentsec

    agentsec.protect(
        llm_integration_mode="api",
        api_mode={
            "llm": {
                "mode": "enforce",
                "endpoint": os.environ["AI_DEFENSE_API_MODE_LLM_ENDPOINT"],
                "api_key": os.environ["AI_DEFENSE_API_MODE_LLM_API_KEY"],
            }
        },
    )

    from openai import OpenAI
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello!"}]
    )

Gateway Mode (Programmatic)
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Route all traffic through the AI Defense Gateway:

.. code-block:: python

    import os
    from aidefense.runtime import agentsec

    agentsec.protect(
        llm_integration_mode="gateway",
        gateway_mode={
            "llm_gateways": {
                "openai-1": {
                    "gateway_url": "https://gateway.aidefense.cisco.com/tenant/conn",
                    "gateway_api_key": os.environ["OPENAI_API_KEY"],
                    "auth_mode": "api_key",
                    "provider": "openai",
                    "default": True,
                },
            },
        },
    )

    from openai import OpenAI
    client = OpenAI()
    response = client.chat.completions.create(...)

Skip Inspection
^^^^^^^^^^^^^^

Exclude specific calls from inspection:

.. code-block:: python

    from aidefense.runtime.agentsec import skip_inspection, no_inspection

    # Context manager
    with skip_inspection():
        response = client.chat.completions.create(...)

    # Decorator
    @no_inspection()
    def health_check():
        return client.chat.completions.create(...)

Supported Clients
^^^^^^^^^^^^^^^^^

agentsec automatically patches the following LLM client libraries:

- **OpenAI** (``openai``) -- ``chat.completions.create()``
- **Azure OpenAI** (``openai``) -- ``chat.completions.create()`` with Azure endpoint
- **AWS Bedrock** (``boto3``) -- ``converse()``, ``converse_stream()``
- **Google Vertex AI** (``google-cloud-aiplatform``) -- ``generate_content()``, ``generate_content_async()``
- **Google GenAI** (``google-genai``) -- ``generate_content()``, ``generate_content_async()``
- **Cohere** (``cohere``) -- ``V2Client.chat()``, ``V2Client.chat_stream()``
- **Mistral AI** (``mistralai``) -- ``Chat.complete()``, ``Chat.stream()``
- **LiteLLM** (``litellm``) -- ``completion()``, ``acompletion()``
- **MCP** (``mcp``) -- ``ClientSession.call_tool()``, ``ClientSession.list_tools()``

Agent Framework Integration
^^^^^^^^^^^^^^^^^^^^^^^^^^

The SDK works with popular agent frameworks:

- AWS Strands
- LangChain / LangGraph
- CrewAI
- AutoGen
- OpenAI Agents SDK

See ``examples/agentsec/2-agent-frameworks/`` for complete examples.

Agent Runtime Deployment
^^^^^^^^^^^^^^^^^^^^^^^

The SDK includes cloud deployment examples for:

- AWS Bedrock AgentCore
- GCP Vertex AI Agent Engine
- Microsoft Azure AI Foundry

See ``examples/agentsec/3-agent-runtimes/`` for deployment walkthroughs.

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
