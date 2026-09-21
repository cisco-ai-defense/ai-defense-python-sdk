Bidirectional Event Stream Inspection
=====================================

This is the complete SDK guide. A shorter package-local integration reference
is available in ``aidefense/runtime/event_stream/README.md``.

Create one ``EventStreamClient`` for the application and reuse it for every LLM
invocation. Each ``inspect`` call opens an independent gRPC stream, so the same
client and adapter are safe for sequential and concurrent API calls. Stream
state, sequence numbers, message IDs, pending content, and parser state are
isolated per invocation.

The SDK sends each response input as its own gRPC event. It does not group
chunks, split tokens, create overlap, or accumulate model output. The service
may inspect several events internally and return one cumulative acknowledgement;
the SDK releases every covered application event in sequence order.

Configuration
-------------

Configuration follows the same API-key plus ``Config`` pattern as ChatInspect:

.. code-block:: python

   import os

   from aidefense import Config
   from aidefense.runtime import EventStreamClient

   inspection = EventStreamClient(
       api_key=os.environ["AI_DEFENSE_API_KEY"],
       config=Config(
           runtime_base_url=os.environ["AI_DEFENSE_RUNTIME_URL"],
           timeout=1800,
           logger_params={"level": "INFO"},
       ),
   )

Alternatively, store the direct gRPC endpoint and connection key in secure
runtime configuration:

.. code-block:: console

   export AI_DEFENSE_EVENT_STREAM_ENDPOINT="inspect.example.cisco.com:443"
   export AI_DEFENSE_EVENT_STREAM_API_KEY="..."
   export AI_DEFENSE_EVENT_STREAM_TLS="true"

.. code-block:: python

   from aidefense.runtime import EventStreamClient

   inspection = EventStreamClient.from_env(
       idle_timeout=30,
       absolute_timeout=1800,
       max_pending_events=32,
   )

An ``https://`` URL enables ordinary server-authenticated TLS. Public users
leave certificate fields unset and gRPC uses its default trust roots. A root
certificate is a trust anchor, not a user identity, and therefore is not enough
for an enterprise endpoint that requires client authentication.

Use the advanced ``EventStreamConfig`` form for private trust and optional
mutual TLS:

.. code-block:: python

   from aidefense.runtime import EventStreamClient, EventStreamConfig

   client = EventStreamClient(EventStreamConfig(
       endpoint="private-inspection.example:443",
       api_key=secret_store["AI_DEFENSE_API_KEY"],
       root_certificates=secret_store["ENTERPRISE_CA_PEM"],
       # Include the leaf certificate followed by any client intermediates.
       client_certificate=secret_store["CLIENT_CERT_CHAIN_PEM"],
       client_private_key=secret_store["CLIENT_PRIVATE_KEY_PEM"],
   ))

The client certificate and key are required only when the endpoint enforces
mTLS and must be supplied together. ``root_certificates`` may contain multiple
PEM certificates. Custom roots replace the default trust set, so provide a
combined bundle if the process must trust private and public issuers.
``tls_server_name`` supports a dial target that differs from the certificate
name. Keep private keys in a secret manager, never in source or telemetry. Set
``tls=False`` only for a trusted local endpoint.

Minimal Strands and Bedrock integration
---------------------------------------

Adapters are reusable and contain no cross-request parser state. Passing the
model invocation as a callable ensures it is not called until the prompt has
received an allowed decision.

.. code-block:: python

   import uuid

   from aidefense.runtime import (
       StrandsBedrockAdapter,
       StreamContext,
   )

   strands = StrandsBedrockAdapter()

   async def protected_response(agent, prompt):
       context = StreamContext(
           session_id=str(uuid.uuid4()),
           request_id=str(uuid.uuid4()),
           conversation_id=str(uuid.uuid4()),
       )
       async for approved in inspection.inspect(
           lambda: agent.stream_async(prompt),
           request=prompt,
           adapter=strands,
           context=context,
       ):
           yield approved

``request`` can be plain text, canonical Pydantic messages, or ordinary message
dictionaries. A complete conversation is sent as one caller-owned request
event and inspected before the response source is consumed:

.. code-block:: python

   conversation = [
       {"role": "system", "content": "Be concise."},
       {"role": "user", "content": "Explain machine learning."},
   ]

   async for approved in inspection.inspect(
       lambda: agent.stream_async(conversation),
       request=conversation,
       adapter=strands,
       context=context,
   ):
       yield approved

Strands AgentCore Runtime integration
-------------------------------------

``StrandsAgentCoreAdapter`` accepts the boto3 invocation callable or response
directly. It unwraps the AgentCore response body and SSE envelopes before
converting Strands/Bedrock events.

.. code-block:: python

   from aidefense.runtime import StrandsAgentCoreAdapter

   agentcore = StrandsAgentCoreAdapter()

   async for approved in inspection.inspect(
       lambda: boto3_client.invoke_agent_runtime(**request_args),
       request=prompt,
       adapter=agentcore,
       context=context,
   ):
       yield approved

Custom frameworks and models
----------------------------

A customer not using Strands implements one small adapter for OpenAI,
LangChain, a custom model server, or any other streaming source. No protobuf
types are needed:

.. code-block:: python

   from aidefense.runtime import (
       CanonicalMessage,
       StreamEvent,
       iter_events,
   )

   class VendorAdapter:
       source = "vendor-name"

       async def adapt(self, events, *, message_id, direction):
           async for event in iter_events(events):
               yield StreamEvent(
                   application_event=event,
                   messages=(CanonicalMessage(
                       role="assistant",
                       content={"text": event.delta_text},
                   ),),
                   direction=direction,
                   message_id=message_id,
               )

   async for approved in inspection.inspect(
       # A callable prevents model invocation until the prompt is allowed.
       lambda: vendor.stream(prompt),
       request=prompt,
       adapter=VendorAdapter(),
       context=context,
   ):
       yield approved

``application_event`` is the original value returned to the application after
an Allow or Monitor decision. ``iter_events`` accepts async iterables and
non-blocking ordinary iterables. Wrap a blocking vendor iterator with its async
client or an async thread/queue bridge so it cannot block acknowledgements and
timeout handling. See ``examples/event_stream/custom_provider.py`` for a
complete runnable example.

Advanced applications can omit ``adapter`` and provide the complete ordered
``StreamEvent`` request/response sequence themselves. This is also where a
caller can implement custom batching or overlap before handing events to the
SDK.

Public models and protocol access
---------------------------------

Normal integrations do not import protobuf classes. The public SDK exports
``CanonicalMessage``, ``CanonicalMessageContent``, ``CanonicalRole``, tool
models, ``StreamEvent``, ``StreamContext``, and decision models. These are
validated Pydantic/runtime types with stable SDK names.

Advanced integrations that need the underlying contract can import validated
Pydantic protocol models from ``aidefense.runtime.event_stream.protocol``.
Generated ``*_pb2`` modules remain an internal transport detail, allowing the
SDK to change serialization without forcing customer integration changes.

Limits, decisions, and lifecycle
--------------------------------

``max_pending_events`` bounds content awaiting acknowledgement and applies
backpressure instead of allowing unbounded memory growth. It must be large
enough for the service inspection window because one server result can cover
multiple sent events. ``max_stream_events`` and ``max_stream_bytes`` enforce
the server limits of 4,096 events and 8 MiB.

Monitor/Allow releases original events. Redact releases the server replacement;
when one decision covers several sequences, the replacement is emitted once.
Block raises ``UnsafeContentError`` and never releases covered content.

On completion, block, timeout, connection failure, cancellation, or source
failure, per-call worker tasks, source iterators, and the call's gRPC channel
are closed. Channel cleanup is bounded. If the application stops iteration
early, it must explicitly call ``await stream.aclose()`` in a ``finally`` block.
The reusable client keeps no conversation state between calls. Reusing
``conversation_id`` correlates records but does not resume server state.

Each call owns its channel, sequences, queue, semaphore, locks, pending events,
and worker tasks. Included adapters also allocate parser state per call. One
client and included adapter are safe for concurrent asyncio tasks and calls
from multiple threads. Custom adapters, ``on_decision`` callbacks, tracer and
metrics sinks, channel factories, and vendor iterators are application-owned;
when shared concurrently, those components must also be concurrency-safe and
honor cancellation.

Observability
-------------

Pass logging, tracing, and metrics through the shared ``Config``. A tracer
exposes ``start_as_current_span``. A metrics sink may expose
``record(reason, attributes)``, ``active_streams(delta)``, and
``latency(seconds, outcome)``. Set the logger level to ``DEBUG`` for lifecycle
diagnostics. SDK telemetry excludes prompts, outputs, credentials, and raw
session/request/conversation IDs.

.. code-block:: python

   import logging

   config = Config(
       runtime_base_url="https://inspect.example",
       timeout=1800,
       logger_params={
           "name": "my_service.aidefense",
           "level": logging.DEBUG,
       },
       tracer=application_tracer,
       metrics=application_metrics,
   )

Each invocation receives a random ``stream_correlation_id`` used only for local
telemetry. Use it to correlate one stream's send, acknowledgement, decision,
and cleanup records without logging the customer's request, session, or
conversation ID.

Lifecycle debug reason codes include:

* ``CHANNEL_OPENING`` and ``CHANNEL_READY`` for transport setup;
* ``WORKERS_STARTED`` for reader/writer startup;
* ``REQUEST_GATE_WAIT`` and ``REQUEST_GATE_OPEN`` for prompt-first inspection;
* ``SOURCE_EXHAUSTED`` and ``STREAM_HALF_CLOSED`` for normal input completion;
* ``RESULT_PARSED`` for a validated single or bulk acknowledgement;
* ``EVENTS_RELEASED`` for ordered application release;
* ``WORKER_FAILED`` for a typed reader or writer failure; and
* ``CLEANUP_STARTED`` and ``CLEANUP_COMPLETED`` for resource shutdown.

Routine and high-volume events (``STREAM_STARTED``, ``EVENT_SENT``,
``ACK_RECEIVED``, ``DECISION_ALLOW``, ``BACKPRESSURE_WAIT``, and
``STREAM_COMPLETED``) log only at DEBUG but continue to emit their metrics and
spans at every log level. ``DECISION_BLOCK``, timeout, cancellation, cleanup
problems, and failures retain normal warning/error visibility. Lifecycle
records emitted through the separate debug-only path do not call
``metrics.record``, so changing the log level cannot change metric volume.
Typical attributes are bounded values such as TLS mode, sequence/count,
pending count, action, timeout, worker name, error reason, and terminal outcome.
No content or secret should be added to custom observer attributes.
Reason codes appear in the log message. Attributes are standard Python
``LogRecord`` extras, so use a structured/JSON handler or a formatter that
selects those fields when they must be rendered.

When diagnosing a stream:

* no ``CHANNEL_READY`` indicates channel/TLS creation failed;
* ``CHANNEL_READY`` without ``START_FRAME_SENT`` indicates that RPC creation,
  connection/TLS handshake, authentication, or the initial write failed;
* ``REQUEST_GATE_WAIT`` without ``REQUEST_GATE_OPEN`` indicates the request is
  awaiting a decision or reached its acknowledgement timeout;
* repeated ``BACKPRESSURE_WAIT`` means the server decision window or consumer
  is slower than production and ``max_pending_events`` is full;
* ``RESULT_PARSED`` without ``EVENTS_RELEASED`` can be valid for a sparse bulk
  result waiting on an earlier sequence; and
* ``CLEANUP_FAILED`` identifies the failed cleanup stage while the overall
  cleanup remains bounded.

Failures are typed as ``UnsafeContentError``, ``StreamTimeoutError``,
``StreamCancelledError``, ``StreamConnectionError``, ``StreamSourceError``, ``StreamProtocolError``,
``StreamBackpressureError``, or ``StreamConfigurationError`` so applications
can handle terminal outcomes without parsing error strings.

API reference
-------------

.. automodule:: aidefense.runtime.event_stream
   :members:
   :undoc-members:
   :show-inheritance:
