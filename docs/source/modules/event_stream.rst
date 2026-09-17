Bidirectional Event Stream Inspection
=====================================

The event-stream client protects incremental LLM and agent output without
requiring applications to construct protobuf frames. It retains application
events locally and releases them only after the server acknowledges their
sequence with a safe ``InspectResponse``. The protocol does not return
``released_events``; release and blocking are SDK responsibilities.

Quick start with Strands and AgentCore
--------------------------------------

Store the connection key in the runtime's secret configuration, rather than in
source code or an invocation payload:

.. code-block:: console

   export AI_DEFENSE_EVENT_STREAM_ENDPOINT="inspect.example.cisco.com:443"
   export AI_DEFENSE_EVENT_STREAM_API_KEY="..."

Then wrap the native Strands asynchronous event stream:

.. code-block:: python

   import uuid

   from aidefense.runtime import EventStreamClient, StreamContext

   client = EventStreamClient.from_env(
       batch_interval=0.05,
       token_limit=512,
       overlap_tokens=32,
       idle_timeout=30,
       absolute_timeout=300,
       max_pending_batches=16,
   )

   context = StreamContext(
       session_id=str(uuid.uuid4()),
       request_id=str(uuid.uuid4()),
       conversation_id=str(uuid.uuid4()),
       actor_id="agentcore-runtime",
   )

   native_events = agent.stream_async(prompt)
   async for safe_event in client.inspect_agentcore(
       prompt,
       native_events,
       context=context,
   ):
       # Unsafe events never reach this line.
       yield safe_event

``inspect_agentcore`` accepts an async Strands stream, a normal iterable, an
awaitable returning either form, a boto3 AgentCore response containing
``response`` or ``payload``, and AgentCore ``chunk.bytes`` events.

Framework-neutral adapters
--------------------------

Transport, batching, overlap, backpressure, acknowledgement handling, and
decisions do not depend on Strands. A vendor integration implements the
``EventStreamAdapter`` protocol and emits ``StreamEvent`` values containing the
generated Pydantic ChatInspect ``Message`` model. The original native event is
retained in ``application_event`` and is what the client yields after a safe
decision.

.. code-block:: python

   from aidefense.runtime import CanonicalMessage, StreamDirection, StreamEvent

   class VendorAdapter:
       source = "vendor-name"

       def __init__(self, message_id):
           self.message_id = message_id

       async def adapt(self, events):
           async for event in events:
               text = event.delta_text
               yield StreamEvent(
                   application_event=event,
                   message=CanonicalMessage(
                       role="assistant",
                       content={"text": text},
                   ),
                   direction=StreamDirection.RESPONSE,
                   message_id=self.message_id,
               )

   async for safe_event in client.inspect(
       vendor_events,
       adapter=VendorAdapter(message_id),
       context=context,
   ):
       yield safe_event

Configuration and limits
------------------------

``EventStreamConfig`` validates all values before opening a channel. The SDK
honors the server's current limits of 256 events per frame, 4,096 retained
events, and 8 MiB retained data. ``token_limit`` controls the inspection window
size and ``overlap_tokens`` controls client-generated overlap. Default token
counting uses a deterministic four-character approximation so it does not add
a tokenizer dependency. Canonical half-open ``SourceRange`` values describe
new content only; overlap is never emitted twice to the application.

``input_queue_size`` bounds framework input waiting for batching, while
``max_pending_batches`` bounds sent content waiting for acknowledgement. Both
queues apply backpressure rather than growing without limit.

Lifecycle and failure behavior
------------------------------

The first frame is generated from ``StreamContext``. Sequence numbers increase
across request and response directions, and are allocated by one stream writer.
The SDK uses the same generated message ID for the request and response of an
``inspect_agentcore`` call unless the caller supplies one.

When the input ends, the SDK marks the last event final and half-closes the send
side. It continues reading until all sent sequences are acknowledged. On normal
completion, block, timeout, connection failure, caller cancellation, or source
failure, worker tasks and the gRPC channel are closed. Cancelling the consuming
task preserves ``asyncio.CancelledError``; remote cancellation raises
``StreamCancelledError``.

Server conversation state exists only for one ``InspectEventStream`` RPC.
Reusing ``conversation_id`` in another API call correlates records but does not
resume server state.

Failures are fail closed and typed:

- ``UnsafeContentError``: content was blocked and was not yielded.
- ``StreamTimeoutError``: idle or absolute deadline expired.
- ``StreamCancelledError``: the remote RPC was cancelled.
- ``StreamConfigurationError``: local validation failed before transmission.
- ``StreamConnectionError``: channel or RPC transport failed.
- ``StreamProtocolError``: acknowledgement or event semantics were invalid.

Observability
-------------

Pass a ``StreamObserver`` with an OpenTelemetry-compatible tracer and a metrics
sink. Spans cover send, acknowledgement, decision, block, timeout, and
cancellation. Metrics callbacks receive active-stream changes, latency, stable
reason codes for decisions/backpressure/configuration/terminal outcomes, and a
random per-stream correlation ID. Logs never include prompts, model output,
credentials, or raw session/conversation/request IDs.

API reference
-------------

.. automodule:: aidefense.runtime.event_stream
   :members:
   :undoc-members:
   :show-inheritance:
