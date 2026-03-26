MCP Inspection
==============

.. automodule:: aidefense.runtime.mcp_inspect
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The MCP Inspection module provides functionality to inspect MCP (Model Context Protocol) JSON-RPC 2.0 messages for security, privacy, and safety violations. It interfaces with the ``/api/v1/inspect/mcp`` endpoint of the Cisco AI Defense API.

MCP is a standard protocol for communication between AI agents and tool servers. The ``MCPInspectionClient`` allows you to inspect:

- **Tool call requests** -- validate tool calls before execution (e.g., database queries, file access, shell commands).
- **Resource read requests** -- validate resource access (e.g., file URIs, network resources).
- **Tool responses** -- scan tool output for data leakage (PII, credentials, secrets).

This is the low-level inspection client for MCP messages. For automatic, transparent MCP protection integrated into your agent's workflow, use the :doc:`agentsec` Agent Runtime SDK module instead.

Class Hierarchy
---------------

.. code-block:: text

    BaseClient (Abstract Base Class)
        └── InspectionClient (Abstract Base Class)
                ├── ChatInspectionClient
                ├── HttpInspectionClient
                └── MCPInspectionClient

Key Methods
-----------

- ``inspect(message, request_id, timeout)`` -- Inspect a raw ``MCPMessage`` object. Auto-detects message type (request, response, notification) from JSON-RPC structure.
- ``inspect_tool_call(tool_name, arguments, message_id, ...)`` -- Convenience method to inspect an MCP ``tools/call`` request.
- ``inspect_resource_read(uri, message_id, ...)`` -- Convenience method to inspect an MCP ``resources/read`` request.
- ``inspect_response(result_data, method, params, message_id, ...)`` -- Convenience method to inspect an MCP response message (requires original request context).
- ``validate_mcp_message(request_dict)`` -- Validate a message dictionary against JSON-RPC 2.0 and MCP specifications.

All methods return an ``MCPInspectResponse`` object, which wraps the standard ``InspectResponse`` in JSON-RPC 2.0 format.

Usage Examples
--------------

Initialization
^^^^^^^^^^^^^^

.. code-block:: python

    from aidefense import MCPInspectionClient, Config

    # Default configuration
    client = MCPInspectionClient(api_key="YOUR_INSPECTION_API_KEY")

    # Custom configuration
    config = Config(
        runtime_base_url="https://custom-endpoint.example.com/api",
        retry_config={"total": 5, "backoff_factor": 1.0},
    )
    client = MCPInspectionClient(api_key="YOUR_INSPECTION_API_KEY", config=config)

Inspecting Tool Calls
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from aidefense import MCPInspectionClient

    client = MCPInspectionClient(api_key="YOUR_INSPECTION_API_KEY")

    # Inspect a tool call before execution
    result = client.inspect_tool_call(
        tool_name="execute_query",
        arguments={"query": "SELECT * FROM users WHERE role = 'admin'"},
        message_id=1,
    )

    if result.result and result.result.is_safe:
        print("Tool call is safe to execute")
    else:
        print("Tool call flagged!")
        if result.result and result.result.rules:
            for rule in result.result.rules:
                print(f"  Rule triggered: {rule.rule_name}")

Inspecting Resource Access
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from aidefense import MCPInspectionClient

    client = MCPInspectionClient(api_key="YOUR_INSPECTION_API_KEY")

    # Inspect a resource read request
    result = client.inspect_resource_read(
        uri="file:///etc/shadow",
        message_id="read-456",
    )

    if result.result and not result.result.is_safe:
        print("Sensitive resource access detected!")
        print(f"Explanation: {result.result.explanation}")

Inspecting Tool Responses
^^^^^^^^^^^^^^^^^^^^^^^^^

Response inspection requires the original request's method and params for context:

.. code-block:: python

    from aidefense import MCPInspectionClient

    client = MCPInspectionClient(api_key="YOUR_INSPECTION_API_KEY")

    # Inspect a tool response for sensitive data leakage
    result = client.inspect_response(
        result_data={
            "content": [
                {
                    "type": "text",
                    "text": "User SSN: 123-45-6789, Email: john@example.com",
                }
            ]
        },
        method="tools/call",
        params={"name": "get_user_info", "arguments": {"user_id": "123"}},
        message_id=1,
    )

    if result.result and not result.result.is_safe:
        print("Response contains sensitive data!")
        for rule in result.result.rules or []:
            print(f"  Triggered: {rule.rule_name}")

Raw MCPMessage Inspection
^^^^^^^^^^^^^^^^^^^^^^^^^

For full control, construct an ``MCPMessage`` and use the ``inspect()`` method directly:

.. code-block:: python

    from aidefense import MCPInspectionClient
    from aidefense.runtime import MCPMessage
    import uuid

    client = MCPInspectionClient(api_key="YOUR_INSPECTION_API_KEY")

    # Create an MCP tool call request
    message = MCPMessage(
        jsonrpc="2.0",
        method="tools/call",
        params={
            "name": "search_documentation",
            "arguments": {"query": "SSL configuration"},
        },
        id="req-001",
    )

    # Inspect with a unique request ID for tracing
    result = client.inspect(
        message=message,
        request_id=str(uuid.uuid4()),
    )

    if result.result and result.result.is_safe:
        print("MCP message is safe to process")
    elif result.error:
        print(f"Inspection error: {result.error.message}")
    else:
        print(f"Message flagged: {result.result.explanation}")

Error Handling
^^^^^^^^^^^^^^

.. code-block:: python

    from aidefense import MCPInspectionClient
    from aidefense.exceptions import ValidationError, ApiError

    client = MCPInspectionClient(api_key="YOUR_INSPECTION_API_KEY")

    try:
        result = client.inspect_tool_call(
            tool_name="execute_command",
            arguments={"command": "rm -rf /"},
            message_id=1,
        )
    except ValidationError as e:
        print(f"Invalid message: {e}")
    except ApiError as e:
        print(f"API error: {e}")

MCP Message Types
-----------------

The MCP protocol defines three message types, all based on JSON-RPC 2.0:

.. list-table::
   :header-rows: 1
   :widths: 20 40 40

   * - Type
     - Structure
     - Description
   * - Request
     - Has ``method`` + ``id``
     - Client-to-server call expecting a response (e.g., ``tools/call``, ``resources/read``).
   * - Response
     - Has ``result``/``error`` + ``id``
     - Server-to-client reply matching a request ``id``.
   * - Notification
     - Has ``method``, no ``id``
     - One-way message with no expected response.

The ``MCPInspectionClient`` automatically detects the message type from the JSON-RPC structure.

Response Format
---------------

All inspection methods return an ``MCPInspectResponse``:

- ``jsonrpc`` -- Always ``"2.0"``.
- ``result`` -- An ``InspectResponse`` if inspection succeeded (``is_safe``, ``classifications``, ``rules``, ``severity``, ``explanation``).
- ``error`` -- An ``MCPInspectError`` if the inspection request itself failed (``code``, ``message``, ``data``).
- ``id`` -- The JSON-RPC message ID, matching the inspected message.
