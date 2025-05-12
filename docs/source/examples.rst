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
    └── advanced/                # Advanced usage examples
        ├── advanced_usage.py
        └── custom_configuration.py

Chat Inspection Examples
-----------------------

Basic Chat Inspection
^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from aidefense import ChatInspectionClient

    # Initialize the client
    client = ChatInspectionClient(api_key="YOUR_API_KEY")

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
    client = HttpInspectionClient(api_key="YOUR_API_KEY")

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

Advanced Examples
---------------

The SDK also includes advanced usage examples demonstrating:

- Custom configurations
- Advanced retry policies
- Multiple clients in the same application
- Custom logging setups

See the `examples/` directory in the repository for the complete set of examples.
