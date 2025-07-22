Overview
========

The AI Defense Python SDK is designed to provide developers with tools to detect security, privacy, and safety risks in real-time through chat and HTTP inspection.

Quick Start
-----------

Installation
~~~~~~~~~~~~

.. code-block:: bash

   pip install cisco-aidefense-sdk

Basic Usage
~~~~~~~~~~~

Chat Inspection
^^^^^^^^^^^^^^^

.. code-block:: python

   from aidefense import ChatInspectionClient

   # Initialize the client
   client = ChatInspectionClient(api_key="your_api_key")

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
   client = HttpInspectionClient(api_key="your_api_key")

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

The SDK is structured around two primary inspection clients:

* **ChatInspectionClient**: For analyzing chat prompts, responses, and conversations
* **HttpInspectionClient**: For inspecting HTTP requests and responses

Both clients utilize a common configuration and authentication system, allowing for consistent behavior across different inspection types.

Key Components
-------------

- ``runtime/chat_inspect.py`` — ChatInspectionClient for chat-related inspection
- ``runtime/http_inspect.py`` — HttpInspectionClient for HTTP request/response inspection
- ``runtime/models.py`` — Data models and enums for requests, responses, rules, etc.
- ``config.py`` — SDK-wide configuration (logging, retries, connection pool)
- ``exceptions.py`` — Custom exception classes for robust error handling

HTTP Inspection Features
----------------------

The HTTP inspection module supports multiple body types:

* **String** content for JSON or plain text
* **Bytes** for binary data
* **Dictionary** bodies that are automatically JSON-serialized

This versatility makes the SDK especially useful when working with different AI model provider APIs.
