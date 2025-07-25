Models
======

.. automodule:: aidefense.runtime.models
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The Models module defines the core data structures used throughout the AI Defense SDK that directly map to the Cisco AI Defense API specification. These models ensure proper typing and validation for all API interactions.

Key Data Structures
------------------

**API Response Models:**

- **InspectResponse**: Standard response format from all inspection endpoints
  - ``classifications``: List of Classification enums (SECURITY_VIOLATION, PRIVACY_VIOLATION, etc.)
  - ``is_safe``: Boolean indicating whether content is safe
  - ``severity``: Optional severity level (NONE_SEVERITY, LOW, MEDIUM, HIGH)
  - ``rules``: Optional list of triggered rules
  - ``attack_technique``: Optional string describing the attack technique
  - ``explanation``: Optional string explaining the violation
  - ``client_transaction_id``: Optional ID for request tracking
  - ``event_id``: Optional ID generated by AI Defense for violations

**Chat Inspection Models:**

- **Message**: Represents a chat message
  - ``role``: Role of the message sender (user, assistant, system)
  - ``content``: Text content of the message
- **Role**: Enum for message roles (USER, ASSISTANT, SYSTEM)

**HTTP Inspection Models:**

- **HttpReqObject**: HTTP request representation
  - ``method``: HTTP method (GET, POST, etc.)
  - ``headers``: HTTP headers
  - ``body``: Base64-encoded request body
- **HttpResObject**: HTTP response representation
  - ``statusCode``: HTTP status code
  - ``headers``: HTTP response headers
  - ``body``: Base64-encoded response body
- **HttpMetaObject**: Metadata for HTTP requests/responses
  - ``url``: URL of the request/response

**Configuration Models:**

- **Rule**: Represents an inspection rule
  - ``rule_name``: Name of the rule (from RuleName enum)
  - ``entity_types``: Optional list of entity types to detect
  - ``rule_id``: Optional unique identifier
  - ``classification``: Optional classification type
- **RuleName**: Enum of available rules (PII, PROMPT_INJECTION, etc.)
- **Classification**: Enum of violation types aligned with API spec
- **InspectionConfig**: Configuration for inspection requests
  - ``enabled_rules``: List of enabled rules
  - Integration profile parameters (optional)
- **Metadata**: Optional context information
  - Application, user, and network identifiers

Usage Examples
-------------

Working with Chat Inspection
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from aidefense.runtime import Message, Role

    # Create a conversation with multiple messages
    messages = [
        Message(
            role=Role.SYSTEM,
            content="You are a helpful AI assistant focusing on cybersecurity."
        ),
        Message(
            role=Role.USER,
            content="Tell me about AI security"
        ),
        Message(
            role=Role.ASSISTANT,
            content="AI security involves protecting systems from various threats..."
        )
    ]

    # These messages can be passed to chat inspection methods
    # client.inspect_conversation(messages)

Working with Rules and Configurations
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from aidefense.runtime import InspectionConfig, Rule, RuleName

    # Create a configuration with specific enabled rules
    config = InspectionConfig(
        enabled_rules=[
            # Detect personally identifiable information
            Rule(rule_name=RuleName.PII),
            # Detect prompt injection attempts
            Rule(rule_name=RuleName.PROMPT_INJECTION),
            # Detect sexual content
            Rule(rule_name=RuleName.SEXUAL_CONTENT_EXPLOITATION)
        ]
    )

    # PII rule with specific entity types to detect
    pii_rule = Rule(
        rule_name=RuleName.PII,
        entity_types=["Email Address", "Phone Number", "Social Security Number (SSN) (US)"]
    )

    # This configuration can be passed to any inspection method
    # client.inspect_request(..., config=config)

Handling Inspection Responses
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    # The same InspectResponse model is returned by all inspection methods
    result = client.inspect_request(...) # or inspect_prompt, inspect_response, etc.

    # Check if content is safe
    if result.is_safe:
        print("Content is safe")
    else:
        # Access violation classifications (aligned with API specification)
        for classification in result.classifications:
            print(f"Violation type: {classification}")
            # Possible values: SECURITY_VIOLATION, PRIVACY_VIOLATION, etc.

        # Get severity level
        if result.severity:
            print(f"Severity: {result.severity}")  # LOW, MEDIUM, or HIGH

        # Get explanation
        if result.explanation:
            print(f"Explanation: {result.explanation}")

        # Process triggered rules
        if result.rules:
            for rule in result.rules:
                print(f"Rule: {rule.rule_name}")

                # For PII rules, check entity types
                if rule.rule_name == RuleName.PII and rule.entity_types:
                    print(f"Detected entities: {', '.join(rule.entity_types)}")
                    # Possible entities: "Email Address", "Phone Number", etc.

        # For tracking and debugging
        print(f"Transaction ID: {result.client_transaction_id}")
        print(f"Event ID: {result.event_id}")

Adding Context with Metadata
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from aidefense.runtime import Metadata

    # Create metadata with context information
    metadata = Metadata(
        # User identity information
        user="user123",

        # Application information
        src_app="my-chat-application",
        dst_app="openai-api",

        # Network information (helpful for analysis)
        dst_ip="192.0.2.1",
        sni="api.openai.com",
        dst_host="api.openai.com",

        # Request origin information
        user_agent="MyApp/1.0",

        # For request tracing
        client_transaction_id="tx-12345"
    )

    # This metadata can be included with any inspection request
    # client.inspect_prompt(..., metadata=metadata)
