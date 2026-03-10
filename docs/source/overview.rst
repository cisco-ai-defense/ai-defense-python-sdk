Overview
========

The AI Defense Python SDK is designed to provide developers with tools to detect security, privacy, and safety risks in real-time. It offers multiple integration approaches:

* **Runtime Protection (agentsec)**: Auto-patch LLM and MCP clients with 2 lines of code — supports API mode and Gateway mode
* **Chat Inspection**: Analyze chat prompts and responses
* **HTTP Inspection**: Inspect HTTP requests and responses
* **MCP Inspection**: Inspect Model Context Protocol messages
* **MCP Server Scanning**: Scan MCP servers for security threats
* **Model Scanning**: Scan AI/ML models for threats
* **Management API**: Manage applications, connections, and policies

Quick Start
-----------

Installation
~~~~~~~~~~~~

.. code-block:: bash

   pip install cisco-aidefense-sdk

Basic Usage
~~~~~~~~~~~

Runtime Protection (Recommended)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The easiest way to protect your AI applications is with ``agentsec.protect()``.
Configure all settings (API keys, gateway URLs, modes) in an ``agentsec.yaml`` file
and reference environment variables with ``${VAR_NAME}`` syntax:

.. code-block:: python

   from aidefense.runtime import agentsec
   agentsec.protect(config="agentsec.yaml")

   # Import your LLM client AFTER protect() — it's automatically patched
   from openai import OpenAI
   client = OpenAI()

   # All calls are now inspected by Cisco AI Defense
   response = client.chat.completions.create(
       model="gpt-4o-mini",
       messages=[{"role": "user", "content": "Hello!"}]
   )

Or configure programmatically:

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

Chat Inspection
^^^^^^^^^^^^^^^

.. code-block:: python

   from aidefense import ChatInspectionClient

   # Initialize the client
   client = ChatInspectionClient(api_key="your_inspection_api_key")

   # Inspect a chat message
   result = client.inspect_prompt(
       prompt="Tell me how to hack into a computer"
   )

   # Check if any violations were detected
   if not result.is_safe:
       print(f"Violations detected: {result.classifications}")
   else:
       print("No violations detected")

HTTP Inspection
^^^^^^^^^^^^^^^

.. code-block:: python

   from aidefense import HttpInspectionClient

   # Initialize the client
   client = HttpInspectionClient(api_key="your_inspection_api_key")

   # Inspect an HTTP request/response pair
   result = client.inspect_request(
       method="POST",
       url="https://api.example.com/v1/completions",
       headers={"Content-Type": "application/json"},
       body={
           "prompt": "Generate malicious code for a virus"
       }
   )

   # Process the inspection results
   print(f"Is safe: {result.is_safe}")

For more detailed examples, see the :doc:`examples` section.

SDK Architecture
---------------

The SDK is structured around several layers:

* **Runtime Protection (agentsec)**: Automatic monkey-patching of LLM and MCP client libraries
* **Inspection Clients**: Low-level clients for chat, HTTP, and MCP message inspection
* **MCP Server Scanning**: Scan and manage MCP servers for security threats
* **Common**: Shared configuration, authentication, retry, and error-handling primitives

Key Components
-------------

Runtime Protection (agentsec)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- ``runtime/agentsec/__init__.py`` — Main entry point (``protect()``, ``skip_inspection()``, ``no_inspection()``)
- ``runtime/agentsec/config.py`` — Configuration loading from YAML, environment, and kwargs
- ``runtime/agentsec/patchers/`` — Auto-patching for LLM clients (OpenAI, Azure OpenAI, Bedrock, Vertex AI, GenAI, Cohere, Mistral, LiteLLM, MCP)
- ``runtime/agentsec/inspectors/`` — API mode and Gateway mode inspectors
- ``runtime/agentsec/exceptions.py`` — ``SecurityPolicyError`` raised in enforce mode

Inspection Clients
~~~~~~~~~~~~~~~~~~

- ``runtime/chat_inspect.py`` — ``ChatInspectionClient`` for chat-related inspection
- ``runtime/http_inspect.py`` — ``HttpInspectionClient`` for HTTP request/response inspection
- ``runtime/mcp_inspect.py`` — ``MCPInspectionClient`` for MCP message inspection
- ``runtime/models.py`` — Data models and enums for requests, responses, rules, etc.

MCP Server Scanning
~~~~~~~~~~~~~~~~~~~

- ``mcpscan/`` — ``MCPScanClient``, ``ResourceConnectionClient``, ``PolicyClient`` for MCP server scanning and management

Common
~~~~~~

- ``config.py`` — SDK-wide configuration (logging, retries, connection pool)
- ``exceptions.py`` — Custom exception classes for robust error handling

Supported LLM Clients
--------------------

agentsec automatically patches the following client libraries:

* **OpenAI** / **Azure OpenAI** (``openai``)
* **AWS Bedrock** (``boto3``)
* **Google Vertex AI** (``google-cloud-aiplatform``)
* **Google GenAI** (``google-genai``)
* **Cohere** (``cohere``)
* **Mistral AI** (``mistralai``)
* **LiteLLM** (``litellm``)
* **MCP** (``mcp``)

HTTP Inspection Features
----------------------

The HTTP inspection module supports multiple body types:

* **String** content for JSON or plain text
* **Bytes** for binary data (auto base64-encoded)
* **Dictionary** bodies that are automatically JSON-serialized
* **Dataclass / Enum** objects that are auto-converted via ``convert()``

This versatility makes the SDK especially useful when working with different AI model provider APIs.
