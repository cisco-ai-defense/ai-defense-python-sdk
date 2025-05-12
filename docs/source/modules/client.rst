Base Client
===========

.. automodule:: aidefense.client
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The BaseClient module provides the foundation for all API interactions in the AI Defense SDK. It serves as an abstract base class that establishes core HTTP functionality, authentication, and error handling patterns. All other clients in the SDK ultimately inherit from this base class.

Core Functionality
-----------------

**HTTP Request Handling**

- Low-level HTTP request handling via requests library
- Configurable timeout handling
- HTTP method validation (GET, POST, PUT, DELETE, etc.)
- URL validation

**Standard Headers**

- User-Agent: ``Cisco-AI-Defense-Python-SDK/{version}``
- Content-Type: ``application/json`` (default)
- Custom header support

**Request Tracing**

- ``get_request_id()`` for UUID generation
- ``x-aidefense-request-id`` header for tracing

**Error Handling**

- HTTP status code interpretation
- Request exception handling
- SDK exception hierarchy

SDK Architecture
---------------

The BaseClient forms the foundation of the SDK's client hierarchy:

.. code-block:: text

    BaseClient (Abstract Base Class)
        └── InspectionClient (Abstract Base Class)
                ├── ChatInspectionClient
                └── HttpInspectionClient

The BaseClient handles low-level HTTP functionality, while the InspectionClient adds common inspection logic. The concrete clients (ChatInspectionClient and HttpInspectionClient) then implement endpoint-specific functionality.

BaseClient Implementation
-----------------------

The BaseClient itself is not meant to be instantiated directly, but provides these key capabilities to all derived classes:

.. code-block:: python

    # BaseClient provides these features:

    # 1. HTTP Request handling with consistent headers
    def request(self, method, url, auth, request_id, headers, json_data, timeout):
        # Handles request creation, error management, etc.

    # 2. Request ID generation
    def get_request_id(self):
        # Generates a unique UUID

    # 3. Validation of HTTP methods
    def _validate_method(self, method):
        # Ensures HTTP method is valid

    # 4. URL validation
    def _validate_url(self, url):
        # Ensures URL is properly formatted

Error Handling
-------------

BaseClient establishes the error handling patterns used throughout the SDK:

.. code-block:: python

    from aidefense.client import BaseClient
    from aidefense.exceptions import ValidationError, ApiError, SDKError

    # This illustrates how BaseClient handles errors internally
    try:
        # Validate inputs
        self._validate_method(method)
        self._validate_url(url)

        # Make the actual request
        response = self._session.request(...)

        # Handle HTTP errors
        if 400 <= response.status_code < 500:
            if response.status_code == 401:
                raise SDKError("Authentication failed")
            else:
                raise ValidationError("Invalid request")
        elif response.status_code >= 500:
            raise ApiError("Server error")

    except requests.exceptions.RequestException as e:
        # Convert library exceptions to SDK exceptions
        raise ApiError(f"Request failed: {str(e)}")

Request Tracing
--------------

BaseClient implements request ID generation and propagation:

.. code-block:: python

    # Inside BaseClient
    def get_request_id(self) -> str:
        """Generate a unique request ID."""
        request_id = str(uuid.uuid4())
        self.config.logger.debug(f"get_request_id called | returning: {request_id}")
        return request_id

    def request(self, method, url, auth, request_id=None, ...):
        """Make an HTTP request with error handling."""
        # Use provided request_id or generate a new one
        request_id = request_id or self.get_request_id()

        # Add to headers for tracing
        headers = headers or {}
        headers[REQUEST_ID_HEADER] = request_id

The request ID is propagated through the ``x-aidefense-request-id`` header, which enables correlation between your application logs and AI Defense logs.
