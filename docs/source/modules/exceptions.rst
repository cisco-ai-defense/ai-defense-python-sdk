Exceptions
==========

.. automodule:: aidefense.exceptions
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The Exceptions module defines specialized exception classes used throughout the AI Defense SDK for precise error handling and reporting.

Key Exception Classes
-------------------

- **SDKError**: Base exception class for all AI Defense SDK errors
- **ValidationError**: Raised when input validation fails (inherits from SDKError)
- **ApiError**: Raised when an API call returns an error response (inherits from SDKError)

Usage Examples
-------------

Handling Validation Errors
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from aidefense import HttpInspectionClient
    from aidefense.exceptions import ValidationError

    client = HttpInspectionClient(api_key="YOUR_API_KEY")

    try:
        result = client.inspect_request(
            method="POST",
            url="invalid-url",  # Invalid URL format
            body="test data"
        )
    except ValidationError as e:
        print(f"Validation error: {e}")
        # Handle the validation error appropriately

Handling API Errors
^^^^^^^^^^^^^^^^^

.. code-block:: python

    from aidefense import ChatInspectionClient
    from aidefense.exceptions import ApiError, SDKError

    client = ChatInspectionClient(api_key="possibly-invalid-key")

    try:
        result = client.inspect_prompt("Test prompt")
    except ApiError as e:
        print(f"API error occurred: {e}")
        print(f"Status code: {e.status_code}")
        print(f"Request ID: {e.request_id}")
        # Handle API errors specifically
    except SDKError as e:
        print(f"General SDK error: {e}")
        # Handle any other SDK errors
