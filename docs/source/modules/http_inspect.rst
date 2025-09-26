HTTP Inspection
==============

.. automodule:: aidefense.runtime.http_inspect
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The HTTP Inspection module provides functionality to analyze HTTP requests and responses for security, privacy, and policy violations. It interfaces with the ``/api/v1/inspect/http`` endpoint of the Cisco AI Defense API and is particularly useful for inspecting API calls to AI service providers.

Key Methods
----------

- **High-level methods**:
  - ``inspect_request(method, url, headers, body, ...)``: Inspect an HTTP request with direct parameters
  - ``inspect_response(status_code, url, headers, body, request_method, request_headers, request_body, ...)``: Inspect an HTTP response with optional request context
  - ``inspect_request_from_http_library(request, ...)``: Inspect a request from the requests library
  - ``inspect_response_from_http_library(response, ...)``: Inspect a response from the requests library

- **Low-level method**:
  - ``inspect(http_req, http_res, http_meta, metadata, config, ...)``: Direct interface to the API

All methods support:

- Multiple body types (string, bytes, dictionary - with automatic JSON serialization)
- Request contextual analysis
- Flexible configuration via InspectionConfig
- Advanced metadata for detailed analysis
- Custom request IDs for tracing

Usage Examples
-------------

High-Level Request Inspection (with Dictionary Body)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from aidefense import HttpInspectionClient

    client = HttpInspectionClient(api_key="YOUR_INSPECTION_API_KEY")

    # Using dictionary body (automatically JSON-serialized)
    result = client.inspect_request(
        method="POST",
        url="https://api.example.com/v1/chat/completions",
        headers={"Content-Type": "application/json"},
        body={
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": "Tell me about AI security"}
            ]
        }
    )

    if result.is_safe:
        print("Request is safe to send")
    else:
        print(f"Request contains issues: {result.classifications}")

HTTP Response Inspection (with Request Context)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    # Inspect an API response with request context
    result = client.inspect_response(
        status_code=200,
        url="https://api.example.com/v1/chat/completions",
        headers={"Content-Type": "application/json"},
        body={
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "AI security involves..."
                    }
                }
            ]
        },
        # Include request context for better analysis
        request_method="POST",
        request_headers={"Content-Type": "application/json"},
        request_body={
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": "Tell me about AI security"}
            ]
        }
    )

    if not result.is_safe:
        print(f"Response contains sensitive information: {result.classifications}")

Direct Integration with requests Library
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    import requests
    from aidefense import HttpInspectionClient

    client = HttpInspectionClient(api_key="YOUR_INSPECTION_API_KEY")

    # Create a request using the requests library
    req = requests.Request(
        "POST",
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer YOUR_OPENAI_KEY"
        },
        json={
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": "Tell me about security vulnerabilities"}
            ]
        }
    ).prepare()

    # Inspect the request directly
    result = client.inspect_request_from_http_library(req)

    if result.is_safe:
        # Execute the request
        response = requests.Session().send(req)

        # Inspect the response with the original request context
        resp_result = client.inspect_response_from_http_library(response)

        if not resp_result.is_safe:
            print(f"Response contains sensitive information: {resp_result.classifications}")

Low-Level Inspection API
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    import base64
    import json
    from aidefense import HttpInspectionClient

    client = HttpInspectionClient(api_key="YOUR_INSPECTION_API_KEY")

    # Manually prepare HTTP request with base64 encoded body
    body_dict = {
        "query": "What are password best practices?"
    }
    body_json = json.dumps(body_dict)
    body_base64 = base64.b64encode(body_json.encode()).decode()

    # Create raw request dict
    http_req = {
        "method": "POST",
        "headers": {"Content-Type": "application/json"},
        "body": body_base64
    }

    # Create metadata dict
    http_meta = {"url": "https://api.example.com/v1/query"}

    # Use the low-level inspect method
    result = client.inspect(
        http_req=http_req,
        http_meta=http_meta
    )

    print(f"Request is safe: {result.is_safe}")

Inspection with Custom Rules Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from aidefense import HttpInspectionClient
    from aidefense.runtime import InspectionConfig, Rule, RuleName

    client = HttpInspectionClient(api_key="YOUR_INSPECTION_API_KEY")

    # Create a configuration focusing on PII detection
    config = InspectionConfig(
        enabled_rules=[
            Rule(rule_name=RuleName.PII),
            Rule(rule_name=RuleName.PROMPT_INJECTION)
        ]
    )

    # Inspect with custom rules configuration
    result = client.inspect_request(
        method="POST",
        url="https://api.example.com/v1/users",
        headers={"Content-Type": "application/json"},
        body={
            "name": "John Doe",
            "email": "john.doe@example.com",
            "phone": "555-123-4567"
        },
        config=config
    )

    if not result.is_safe:
        for rule in result.rules or []:
            print(f"Rule triggered: {rule.rule_name}")
            if hasattr(rule, "entity_types") and rule.entity_types:
                print(f"Entity types found: {rule.entity_types}")

Provider-Specific Examples
^^^^^^^^^^^^^^^^^^^^^^^^^

The SDK includes examples for interacting with various AI model providers:

.. code-block:: python

    # Example for OpenAI API
    result = client.inspect_request(
        method="POST",
        url="https://api.openai.com/v1/chat/completions",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer YOUR_OPENAI_KEY"
        },
        body={
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": "Tell me about AI security"}
            ]
        }
    )

The SDK includes a well-organized set of examples for HTTP inspection in the `/examples/http/providers/` directory, covering major AI providers:

- OpenAI (`http_inspect_openai_api.py`)
- Vertex AI (`http_inspect_vertex_ai_api.py`)
- Amazon Bedrock (`http_inspect_bedrock_api.py`)
- Mistral AI (`http_inspect_mistral_api.py`)
- Cohere (`http_inspect_cohere_api.py`)

These examples demonstrate how to use the HTTP inspection capabilities with different AI model providers, including the use of dictionary bodies with automatic JSON serialization.
