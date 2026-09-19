Bidirectional Event Stream Inspection
=====================================

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

Store the connection key in runtime secret configuration and construct the
client once:

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

TLS is enabled by default. A private CA or mutual TLS can be configured with
``root_certificates``, ``client_certificate``, and ``client_private_key`` byte
values. ``tls_server_name`` supports a dial target that differs from the
certificate name. Set ``tls=False`` only for a trusted local endpoint.

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

A custom adapter implements one small protocol and can be reused across calls:

.. code-block:: python

   from aidefense.runtime.event_stream import iter_events

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
       vendor_events,
       request=prompt,
       adapter=VendorAdapter(),
       context=context,
   ):
       yield approved

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
are closed. The reusable client keeps no conversation state between calls.
Reusing ``conversation_id`` correlates records but does not resume server state.

API reference
-------------

.. automodule:: aidefense.runtime.event_stream
   :members:
   :undoc-members:
   :show-inheritance:
