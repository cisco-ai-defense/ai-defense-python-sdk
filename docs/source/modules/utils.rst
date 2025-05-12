Utilities
=========

.. automodule:: aidefense.runtime.utils
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The Utils module provides helper functions and utilities used throughout the AI Defense SDK, particularly for data encoding, conversion, and validation.

Key Functions
------------

- **to_base64_bytes**: Converts various data types to base64-encoded bytes
- **convert**: Converts objects to different types based on target type specification
- **ensure_base64_body**: Ensures that HTTP bodies are properly base64 encoded
- **Data conversion helpers**: Functions to standardize data formats across the SDK
- **Validation utilities**: Helpers to ensure data meets requirements

Usage Examples
-------------

Working with Base64 Encoding
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from aidefense.runtime.utils import to_base64_bytes

    # Encode string data to base64
    data = "Example string data"
    encoded = to_base64_bytes(data)

    # Use in HTTP inspection
    from aidefense import HttpInspectionClient

    client = HttpInspectionClient(api_key="YOUR_API_KEY")
    result = client.inspect(
        http_req={
            "method": "POST",
            "headers": {"Content-Type": "text/plain"},
            "body": encoded
        },
        http_meta={"url": "https://example.com"}
    )

Type Conversion Utilities
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from aidefense.runtime.utils import convert

    # Convert int to string
    str_value = convert(42, str)  # "42"

    # Convert string to float
    float_value = convert("3.14", float)  # 3.14

    # Convert dict to string (JSON serialization)
    json_str = convert({"key": "value"}, str)  # '{"key": "value"}'

Working with HTTP Bodies
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from aidefense.runtime.utils import ensure_base64_body
    import json

    # Dictionary data that needs to be encoded for HTTP inspection
    data = {"query": "What is your credit card number?"}

    # Convert to JSON string first
    json_data = json.dumps(data)

    # Ensure it's properly base64 encoded
    base64_body = ensure_base64_body(json_data)

    # Now it can be used in an HTTP request for inspection
    # The body is properly formatted according to API requirements
