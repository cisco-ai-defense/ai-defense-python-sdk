# Copyright 2026 Cisco Systems, Inc. and its affiliates
# SPDX-License-Identifier: Apache-2.0

"""Framework-neutral bidirectional event-stream inspection example.

Replace ``vendor_stream`` with any async model/framework response iterator.
No protobuf construction or Strands dependency is required.
"""

import asyncio
import os
import uuid

from aidefense import Config
from aidefense.runtime import (
    CanonicalMessage,
    EventStreamClient,
    StreamConnectionError,
    StreamContext,
    StreamDirection,
    StreamEvent,
    StreamTimeoutError,
    UnsafeContentError,
    iter_events,
)


class TextChunkAdapter:
    """Convert this example provider's text chunks into canonical SDK events."""

    source = "custom-text-provider"

    async def adapt(self, events, *, message_id, direction):
        async for chunk in iter_events(events):
            if not isinstance(chunk, str):
                raise TypeError("the custom provider must yield text chunks")
            yield StreamEvent(
                # The SDK yields this original value only after it is allowed.
                application_event=chunk,
                messages=(
                    CanonicalMessage(
                        role="assistant",
                        content={"text": chunk},
                    ),
                ),
                direction=direction,
                message_id=message_id,
            )


async def vendor_stream(prompt: str):
    """Stand-in for an OpenAI, Bedrock, LangChain, or other async stream."""

    for chunk in ("This ", "is ", "a streamed response to: ", prompt):
        await asyncio.sleep(0)
        yield chunk


def report_decision(result):
    """Observe decisions without logging prompts, outputs, or credentials."""

    print(
        "inspection:",
        result.decision.action,
        "sequences:",
        result.through_sequences,
        "directions:",
        [direction.value for direction in result.directions],
    )


async def main():
    prompt = input("Prompt: ")
    client = EventStreamClient(
        api_key=os.environ["AI_DEFENSE_API_KEY"],
        config=Config(
            # Use the HTTPS runtime URL supplied for your AI Defense tenant.
            # Public TLS certificates use the operating-system trust store.
            runtime_base_url=os.environ["AI_DEFENSE_RUNTIME_URL"],
            timeout=1800,
            logger_params={"level": "INFO"},
        ),
        on_decision=report_decision,
    )
    context = StreamContext(
        session_id=str(uuid.uuid4()),
        request_id=str(uuid.uuid4()),
        conversation_id=str(uuid.uuid4()),
    )

    try:
        async for safe_chunk in client.inspect(
            # A callable prevents model invocation until the prompt is allowed.
            lambda: vendor_stream(prompt),
            request=prompt,
            adapter=TextChunkAdapter(),
            context=context,
        ):
            print(safe_chunk, end="", flush=True)
        print()
    except UnsafeContentError as exc:
        print(f"blocked: {exc.reason_code}")
    except StreamTimeoutError as exc:
        print(f"timed out: {exc.reason_code}")
    except StreamConnectionError as exc:
        print(f"connection failed: {exc.reason_code}")


if __name__ == "__main__":
    asyncio.run(main())
