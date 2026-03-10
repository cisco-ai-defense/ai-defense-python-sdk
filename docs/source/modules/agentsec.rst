Runtime Protection (agentsec)
=============================

.. automodule:: aidefense.runtime.agentsec
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The ``agentsec`` module is the primary entry point for runtime protection of LLM and MCP interactions. It automatically monkey-patches supported client libraries so that every request and response is inspected by Cisco AI Defense -- with just two lines of code.

Call ``protect()`` once, **before** importing any LLM clients, and the SDK handles the rest: configuration loading, client patching, inspection, and enforcement.

``agentsec`` supports two integration modes:

- **API mode** -- the SDK inspects requests via the AI Defense Inspection API, then passes them through to the LLM provider.
- **Gateway mode** -- the SDK routes requests through the AI Defense Gateway, which handles both inspection and proxying.

Quick Start
-----------

.. code-block:: python

    from aidefense.runtime import agentsec
    agentsec.protect(config="agentsec.yaml")

    # Import LLM client AFTER protect() -- it is automatically patched
    from openai import OpenAI
    client = OpenAI()

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello!"}]
    )

protect() Function
------------------

.. autofunction:: aidefense.runtime.agentsec.protect

``protect()`` is the main entry point. It is **idempotent** -- calling it more than once has no effect after the first successful call.

**Parameters:**

- ``patch_clients`` *(bool)* -- Whether to auto-patch LLM clients. Default: ``True``.
- ``auto_dotenv`` *(bool)* -- Load ``.env`` before YAML parsing so ``${VAR}`` references resolve. Default: ``True``.
- ``config`` *(str, optional)* -- Path to an ``agentsec.yaml`` configuration file.
- ``llm_integration_mode`` *(str, optional)* -- ``"api"`` or ``"gateway"``.
- ``mcp_integration_mode`` *(str, optional)* -- ``"api"`` or ``"gateway"``.
- ``gateway_mode`` *(dict, optional)* -- Dict matching the ``gateway_mode`` YAML section.
- ``api_mode`` *(dict, optional)* -- Dict matching the ``api_mode`` YAML section.
- ``pool_max_connections`` *(int, optional)* -- Max HTTP connections (global).
- ``pool_max_keepalive`` *(int, optional)* -- Max keepalive connections (global).
- ``custom_logger`` *(logging.Logger, optional)* -- Custom logger instance.
- ``log_file`` *(str, optional)* -- Log file path.
- ``log_format`` *(str, optional)* -- ``"text"`` or ``"json"``.

**Raises:**

- ``FileNotFoundError`` -- If config file path does not exist.
- ``ConfigurationError`` -- If config file contains invalid YAML, wrong root type, or invalid values.
- ``ValueError`` -- If ``log_format`` is not a supported value.

Configuration
-------------

YAML Configuration (Recommended)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Use an ``agentsec.yaml`` file for production configuration. The YAML can reference
environment variables with ``${VAR_NAME}`` syntax:

.. code-block:: yaml

    llm_integration_mode: api

    api_mode:
      llm:
        mode: enforce
        endpoint: ${AI_DEFENSE_API_MODE_LLM_ENDPOINT}
        api_key: ${AI_DEFENSE_API_MODE_LLM_API_KEY}

    gateway_mode:
      llm_gateways:
        openai-1:
          gateway_url: https://gateway.aidefense.cisco.com/tenant/conn
          gateway_api_key: ${OPENAI_API_KEY}
          auth_mode: api_key
          provider: openai
          default: true

How you provision environment variables is up to you: ``.env`` files, shell exports, secrets managers, CI/CD injection, or container orchestration.

.. code-block:: python

    from aidefense.runtime import agentsec
    agentsec.protect(config="agentsec.yaml")

API Mode (Programmatic)
^^^^^^^^^^^^^^^^^^^^^^^

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

Gateway Mode (Programmatic)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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

Decision Class
--------------

.. autoclass:: aidefense.runtime.agentsec.decision.Decision
   :members:
   :undoc-members:
   :show-inheritance:

The ``Decision`` class represents the result of a security inspection performed by agentsec. It is returned internally by inspectors and is attached to ``SecurityPolicyError`` when a request is blocked.

**Attributes:**

- ``action`` -- The action taken: ``"allow"``, ``"block"``, ``"sanitize"``, or ``"monitor_only"``.
- ``is_safe`` *(property)* -- ``True`` if the action is not ``"block"``.
- ``reasons`` -- List of strings explaining the decision.
- ``sanitized_content`` -- Modified content if action is ``"sanitize"``.
- ``severity`` -- Severity level (e.g., ``"low"``, ``"medium"``, ``"high"``, ``"critical"``).
- ``classifications`` -- List of violation classifications (e.g., ``["pii", "prompt_injection"]``).
- ``rules`` -- List of rules that were triggered.
- ``explanation`` -- Human-readable explanation.
- ``event_id`` -- Unique identifier for this inspection event (for correlation and audit).
- ``raw_response`` -- The raw response from the inspection API.

**Factory methods:**

- ``Decision.allow(...)`` -- Create an allow decision.
- ``Decision.block(reasons, ...)`` -- Create a block decision.
- ``Decision.sanitize(reasons, sanitized_content, ...)`` -- Create a sanitize decision.
- ``Decision.monitor_only(reasons, ...)`` -- Create a monitor-only decision.

**Example:**

.. code-block:: python

    from aidefense.runtime.agentsec import SecurityPolicyError

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "..."}]
        )
    except SecurityPolicyError as e:
        print(f"Blocked: {e}")
        if e.decision:
            print(f"Action: {e.decision.action}")
            print(f"Reasons: {e.decision.reasons}")
            print(f"Severity: {e.decision.severity}")

Context Managers and Decorators
-------------------------------

skip_inspection
^^^^^^^^^^^^^^^

Context manager to temporarily skip AI Defense inspection for LLM and/or MCP calls. Works with both sync and async code.

.. code-block:: python

    from aidefense.runtime.agentsec import skip_inspection

    # Skip all inspection
    with skip_inspection():
        response = client.chat.completions.create(...)

    # Async
    async with skip_inspection():
        response = await client.chat.completions.create(...)

    # Granular: skip LLM only, still inspect MCP
    with skip_inspection(llm=True, mcp=False):
        response = client.chat.completions.create(...)

no_inspection
^^^^^^^^^^^^^

Decorator to skip AI Defense inspection for all calls within a function. Works with or without parentheses, and with both sync and async functions.

.. code-block:: python

    from aidefense.runtime.agentsec import no_inspection

    @no_inspection
    def health_check():
        return client.chat.completions.create(...)

    @no_inspection()
    def health_check_explicit():
        return client.chat.completions.create(...)

    @no_inspection(llm=True, mcp=False)
    def skip_llm_only():
        return client.chat.completions.create(...)

    @no_inspection
    async def async_health_check():
        return await client.chat.completions.create(...)

gateway
^^^^^^^

Context manager to route LLM calls through a named gateway. The gateway name must correspond to a key in ``gateway_mode.llm_gateways`` in the configuration.

.. code-block:: python

    from aidefense.runtime import agentsec

    agentsec.protect(config="agentsec.yaml")

    with agentsec.gateway("math-gateway"):
        response = client.chat.completions.create(...)

    # Async
    async with agentsec.gateway("math-gateway"):
        response = await client.chat.completions.create(...)

    # Nesting supported -- innermost gateway wins
    with agentsec.gateway("outer"):
        with agentsec.gateway("inner"):
            # uses "inner"
            ...
        # back to "outer"

use_gateway
^^^^^^^^^^^

Decorator to route all LLM calls within a function through a named gateway.

.. code-block:: python

    from aidefense.runtime import agentsec

    @agentsec.use_gateway("math-gateway")
    def solve_math(problem: str):
        return client.chat.completions.create(...)

    @agentsec.use_gateway("english-gateway")
    async def translate(text: str):
        return await client.chat.completions.create(...)

set_metadata
^^^^^^^^^^^^

Set metadata for the current inspection context. The metadata is included in inspection API requests for correlation and audit purposes.

.. code-block:: python

    import uuid
    from aidefense.runtime import agentsec

    agentsec.set_metadata(
        user="user-123",
        src_app="my-agent",
        client_transaction_id=str(uuid.uuid4()),
    )

    # Subsequent LLM calls include this metadata
    response = client.chat.completions.create(...)

get_patched_clients
^^^^^^^^^^^^^^^^^^^

Returns a list of successfully patched client names.

.. code-block:: python

    from aidefense.runtime import agentsec

    agentsec.protect(config="agentsec.yaml")
    print(agentsec.get_patched_clients())
    # e.g. ['openai', 'bedrock', 'mcp']

Supported Clients
-----------------

``agentsec`` automatically patches the following LLM and MCP client libraries:

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Provider
     - Package
     - Patched Methods
   * - OpenAI
     - ``openai``
     - ``chat.completions.create()``, ``responses.create()``
   * - Azure OpenAI
     - ``openai``
     - ``chat.completions.create()``, ``responses.create()`` (with Azure endpoint)
   * - AWS Bedrock
     - ``boto3``
     - ``converse()``, ``converse_stream()``
   * - Google Vertex AI
     - ``google-cloud-aiplatform``
     - ``generate_content()``, ``generate_content_async()``
   * - Google GenAI
     - ``google-genai``
     - ``generate_content()``, ``generate_content_async()``
   * - Cohere
     - ``cohere``
     - ``V2Client.chat()``, ``V2Client.chat_stream()``
   * - Mistral AI
     - ``mistralai``
     - ``Chat.complete()``, ``Chat.stream()``
   * - LiteLLM
     - ``litellm``
     - ``completion()``, ``acompletion()``
   * - Azure AI Inference
     - ``azure-ai-inference``
     - ``ChatCompletionsClient.complete()``
   * - MCP
     - ``mcp``
     - ``ClientSession.call_tool()``, ``ClientSession.get_prompt()``, ``ClientSession.read_resource()``

Exceptions
----------

.. automodule:: aidefense.runtime.agentsec.exceptions
   :members:
   :undoc-members:
   :show-inheritance:

All agentsec exceptions inherit from ``AgentsecError``, allowing broad error handling with a single ``except`` clause.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Exception
     - Description
   * - ``AgentsecError``
     - Base exception for all agentsec errors.
   * - ``ConfigurationError``
     - Raised when ``protect()`` configuration is invalid (bad YAML, missing fields, invalid values).
   * - ``ValidationError``
     - Raised when invalid input is passed to inspection methods.
   * - ``InspectionTimeoutError``
     - Raised when the inspection API times out (has ``timeout_ms`` attribute).
   * - ``InspectionNetworkError``
     - Raised on network errors during inspection (connection refused, DNS failure).
   * - ``SecurityPolicyError``
     - Raised in enforce mode when a request/response violates security policies (has ``decision`` and ``message`` attributes).

**Error handling example:**

.. code-block:: python

    from aidefense.runtime.agentsec import (
        AgentsecError,
        ConfigurationError,
        SecurityPolicyError,
        InspectionTimeoutError,
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello!"}]
        )
    except SecurityPolicyError as e:
        print(f"Blocked by policy: {e}")
        if e.decision:
            print(f"Severity: {e.decision.severity}")
            print(f"Classifications: {e.decision.classifications}")
    except InspectionTimeoutError as e:
        print(f"Inspection timed out after {e.timeout_ms}ms")
    except AgentsecError as e:
        print(f"Agentsec error: {e}")

GatewaySettings
---------------

.. autoclass:: aidefense.runtime.agentsec.gateway_settings.GatewaySettings
   :members:
   :undoc-members:
   :show-inheritance:

``GatewaySettings`` is the resolved configuration for a single gateway connection, used internally by patchers. It supports multiple authentication modes:

- ``"none"`` -- No authentication (default for MCP gateways).
- ``"api_key"`` -- API key in a configurable header (default for LLM gateways).
- ``"aws_sigv4"`` -- AWS Signature V4 signing.
- ``"google_adc"`` -- Google Application Default Credentials.
- ``"oauth2_client_credentials"`` -- OAuth 2.0 Client Credentials grant.
- ``"client"`` -- Forward the client's own auth headers to the gateway.

Architecture
------------

.. code-block:: text

    protect() ──► Load config (YAML + env + kwargs)
                  ──► Setup logging
                  ──► Validate configuration
                  ──► Store state
                  ──► Apply client patches

    Patched client call ──► Patcher intercepts call
                            ──► [API mode]     Inspector ──► AI Defense API ──► Decision
                            ──► [Gateway mode] Gateway client ──► AI Defense Gateway ──► Response
                            ──► If Decision.action == "block" and mode == "enforce":
                                    raise SecurityPolicyError(decision)
                            ──► Otherwise: proceed with original/proxied call
