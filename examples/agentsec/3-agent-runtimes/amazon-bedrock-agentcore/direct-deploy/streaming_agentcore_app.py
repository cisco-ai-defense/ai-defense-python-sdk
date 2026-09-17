# Copyright 2026 Cisco Systems, Inc. and its affiliates
# SPDX-License-Identifier: Apache-2.0

"""Strands AgentCore entrypoint protected by bidirectional stream inspection.

Required AgentCore secrets/configuration:
  AI_DEFENSE_EVENT_STREAM_ENDPOINT
  AI_DEFENSE_EVENT_STREAM_API_KEY
"""

import os
import sys
import uuid

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from bedrock_agentcore import BedrockAgentCoreApp

from aidefense.runtime import EventStreamClient, StreamContext
from _shared import get_agent


app = BedrockAgentCoreApp()
inspection = EventStreamClient.from_env(
    batch_interval=0.05,
    token_limit=512,
    overlap_tokens=32,
    max_pending_batches=16,
    idle_timeout=30,
    absolute_timeout=300,
)


def _safe_text(event):
    """Return application text from an already-approved Strands event."""

    if isinstance(event, dict) and isinstance(event.get("data"), str):
        return event["data"]
    if isinstance(event, dict):
        delta = (event.get("contentBlockDelta") or {}).get("delta") or {}
        if isinstance(delta.get("text"), str):
            return delta["text"]
    return None


@app.entrypoint
async def invoke(payload: dict):
    """Stream only AI Defense-approved Strands output to AgentCore callers."""

    prompt = str((payload or {}).get("prompt") or "Hello")
    session_id = str((payload or {}).get("runtimeSessionId") or uuid.uuid4())
    context = StreamContext(
        session_id=session_id,
        request_id=str(uuid.uuid4()),
        conversation_id=str((payload or {}).get("conversationId") or session_id),
        actor_id="strands-agentcore",
    )

    response_events = get_agent().stream_async(prompt)
    async for safe_event in inspection.inspect_agentcore(
        prompt,
        response_events,
        context=context,
    ):
        text = _safe_text(safe_event)
        if text:
            yield text


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
