# Copyright 2026 Cisco Systems, Inc. and its affiliates
# SPDX-License-Identifier: Apache-2.0

"""Adapters from Strands and AgentCore event shapes to ChatInspect messages."""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import AsyncIterable, AsyncIterator, Iterable
from typing import Any, AsyncIterator as TypingAsyncIterator, Dict, Optional, Protocol

from aidefense.pydantic.runtime.ai_defense.inspection.v1.inspection_pydantic import (
    MessageContent,
    Role,
    ToolFunction,
)

from .exceptions import StreamProtocolError
from .models import CanonicalMessage, StreamDirection, StreamEvent, ToolCall


_SKIP_EVENT = object()
_ITERATOR_END = object()


def _next_or_end(iterator: Any) -> Any:
    try:
        return next(iterator)
    except StopIteration:
        return _ITERATOR_END


async def _agentcore_sse_lines(body: Any) -> AsyncIterator[Any]:
    """Read boto3's blocking StreamingBody without blocking the asyncio loop."""

    iterator = iter(body.iter_lines(chunk_size=1024))
    try:
        while True:
            line = await asyncio.to_thread(_next_or_end, iterator)
            if line is _ITERATOR_END:
                return
            yield line
    finally:
        close = getattr(body, "close", None)
        if close is not None:
            await asyncio.to_thread(close)


def _message(
    role: str,
    content: str = "",
    *,
    tool_calls: tuple = (),
    tool_call_id: str = "",
) -> CanonicalMessage:
    try:
        canonical_role = Role(role)
    except ValueError as exc:
        raise StreamProtocolError(f"unsupported ChatInspect role: {role!r}") from exc
    return CanonicalMessage(
        role=canonical_role,
        content=MessageContent(text=content),
        tool_calls=list(tool_calls),
        tool_call_id=tool_call_id,
    )


async def as_async_iterable(events: Any) -> AsyncIterator[Any]:
    """Normalize Strands, AgentCore, sync iterables, and awaitable responses."""

    if callable(events):
        events = events()
    if inspect.isawaitable(events):
        events = await events
    if hasattr(events, "__aiter__"):
        try:
            async for event in events:
                yield event
        finally:
            close = getattr(events, "aclose", None)
            if close is not None:
                await close()
        return
    if hasattr(events, "__iter__") and not isinstance(events, (str, bytes, dict)):
        try:
            for event in events:
                yield event
        finally:
            close = getattr(events, "close", None)
            if close is not None:
                close()
        return
    raise StreamProtocolError(
        "event source must be callable, awaitable, async iterable, or iterable"
    )


# Stable public helper for custom adapters. Keep the original internal name for
# compatibility with integrations built during the preview.
iter_events = as_async_iterable


class EventStreamAdapter(Protocol):
    """Extension point for LLM vendors and agent frameworks."""

    source: str

    def adapt(
        self,
        events: Any,
        *,
        message_id: Optional[str] = None,
        direction: StreamDirection = StreamDirection.RESPONSE,
    ) -> TypingAsyncIterator[StreamEvent]:
        """Convert native events while retaining each application event."""
        ...


def _mapping(value: Any) -> Optional[Dict[str, Any]]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dumped if isinstance(dumped, dict) else None
    if hasattr(value, "to_dict"):
        dumped = value.to_dict()
        return dumped if isinstance(dumped, dict) else None
    return None


def _text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = []
    for item in content:
        data = _mapping(item)
        if data and isinstance(data.get("text"), str):
            parts.append(data["text"])
    return "".join(parts)


def _complete_message(
    message: Dict[str, Any], default_role: str
) -> Optional[CanonicalMessage]:
    role = str(message.get("role") or default_role)
    content = message.get("content")
    text = _text_content(content)
    if text:
        return _message(role=role, content=text)
    if isinstance(content, list):
        results = []
        call_id = ""
        for item in content:
            data = _mapping(item) or {}
            result = _mapping(data.get("toolResult"))
            if result:
                call_id = call_id or str(result.get("toolUseId", ""))
                value = _text_content(result.get("content"))
                if value:
                    results.append(value)
        if results:
            return _message(role="tool", content="".join(results), tool_call_id=call_id)
    return None


class StrandsEventAdapter:
    """Convert Strands/Bedrock streaming events without requiring Strands imports."""

    def __init__(
        self,
        *,
        message_id: Optional[str] = None,
        direction: StreamDirection = StreamDirection.RESPONSE,
        source: str = "strands",
        max_tool_argument_chars: int = 8192,
    ) -> None:
        if message_id == "":
            raise StreamProtocolError("message_id must not be empty")
        self.message_id = message_id
        self.direction = direction
        self.source = source
        if max_tool_argument_chars < 1:
            raise StreamProtocolError("max_tool_argument_chars must be positive")
        self.max_tool_argument_chars = max_tool_argument_chars
        self._role = "assistant" if direction is StreamDirection.RESPONSE else "user"
        self._tools: Dict[int, Dict[str, str]] = {}
        self._streamed_text = False

    async def adapt(
        self,
        events: Any,
        *,
        message_id: Optional[str] = None,
        direction: Optional[StreamDirection] = None,
    ) -> AsyncIterator[StreamEvent]:
        resolved_message_id = message_id or self.message_id
        if not resolved_message_id:
            raise StreamProtocolError("message_id must not be empty")
        resolved_direction = direction or self.direction
        # Parsing state belongs to one invocation. A configured adapter can be
        # safely reused by concurrent EventStreamClient calls.
        parser = StrandsEventAdapter(
            message_id=resolved_message_id,
            direction=resolved_direction,
            source=self.source,
            max_tool_argument_chars=self.max_tool_argument_chars,
        )
        async for original in as_async_iterable(events):
            converted = parser.convert(original)
            # Lifecycle envelopes do not contain inspectable application
            # content. Keep the transport API canonical and do not manufacture
            # empty gRPC events for them.
            if converted.messages:
                yield converted

    def convert(self, original: Any) -> StreamEvent:
        data = _mapping(original)
        if data is None:
            if isinstance(original, bytes):
                try:
                    original = original.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise StreamProtocolError(
                        "AgentCore emitted non-UTF-8 content"
                    ) from exc
            if isinstance(original, str):
                self._streamed_text = True
                return self._event(original, _message(self._role, original))
            raise StreamProtocolError(
                f"unsupported Strands event type: {type(original).__name__}"
            )

        # Some AgentCore runtimes wrap Bedrock events in an `event` member.
        event = _mapping(data.get("event")) or data
        message_start = _mapping(event.get("messageStart"))
        if message_start and isinstance(message_start.get("role"), str):
            self._role = message_start["role"]

        delta_event = _mapping(event.get("contentBlockDelta"))
        if delta_event:
            delta = _mapping(delta_event.get("delta")) or {}
            text = delta.get("text")
            if isinstance(text, str) and text:
                self._streamed_text = True
                return self._event(original, _message(self._role, text))
            tool_delta = _mapping(delta.get("toolUse"))
            if tool_delta:
                index = int(delta_event.get("contentBlockIndex", 0))
                state = self._tools.setdefault(
                    index, {"id": "", "name": "", "arguments": ""}
                )
                value = tool_delta.get("input", "")
                if isinstance(value, str):
                    state["arguments"] += value
                elif value is not None:
                    state["arguments"] += json.dumps(value, separators=(",", ":"))
                if len(state["arguments"]) > self.max_tool_argument_chars:
                    self._tools.pop(index, None)
                    raise StreamProtocolError(
                        "Strands tool arguments exceed the configured size limit"
                    )

        start_event = _mapping(event.get("contentBlockStart"))
        if start_event:
            start = _mapping(start_event.get("start")) or {}
            tool = _mapping(start.get("toolUse"))
            if tool:
                index = int(start_event.get("contentBlockIndex", 0))
                if index not in self._tools and len(self._tools) >= 128:
                    raise StreamProtocolError("too many unfinished Strands tool calls")
                self._tools[index] = {
                    "id": str(tool.get("toolUseId", "")),
                    "name": str(tool.get("name", "")),
                    "arguments": "",
                }

        stop_event = _mapping(event.get("contentBlockStop"))
        if stop_event:
            index = int(stop_event.get("contentBlockIndex", 0))
            tool = self._tools.pop(index, None)
            if tool is not None:
                if not tool["name"] and tool["arguments"]:
                    # Preserve inspection coverage when structured extraction
                    # would reject a nameless call on the server.
                    return self._event(
                        original,
                        _message(role="assistant", content=tool["arguments"]),
                    )
                call = ToolCall(
                    id=tool["id"],
                    type="function",
                    function=ToolFunction(
                        name=tool["name"], arguments_json=tool["arguments"]
                    ),
                )
                return self._event(
                    original,
                    _message(role="assistant", tool_calls=(call,)),
                )

        # Strands Agent.stream_async commonly emits token text in `data`.
        text = data.get("data")
        if isinstance(text, str) and text:
            self._streamed_text = True
            return self._event(original, _message(self._role, text))

        # A complete Strands message is useful for non-streaming AgentCore
        # responses, but is skipped after deltas to avoid inspecting it twice.
        message = _mapping(data.get("message"))
        if message is None and "role" in data and "content" in data:
            message = data
        if message and not self._streamed_text:
            canonical = _complete_message(message, self._role)
            if canonical is not None:
                return self._event(original, canonical)

        return self._event(original, None)

    def _event(
        self, application_event: Any, message: Optional[CanonicalMessage]
    ) -> StreamEvent:
        if self.message_id is None:
            raise StreamProtocolError("message_id must not be empty")
        return StreamEvent(
            application_event=application_event,
            messages=() if message is None else (message,),
            direction=self.direction,
            message_id=self.message_id,
        )


async def agentcore_events(body: Any) -> AsyncIterator[Any]:
    """Extract events from AgentCore Runtime response and invocation shapes."""

    if callable(body):
        body = body()
    if inspect.isawaitable(body):
        body = await body
    data = _mapping(body)
    is_sse = False
    if data is not None:
        content_type = data.get("contentType") or data.get("content_type") or ""
        is_sse = "text/event-stream" in str(content_type).lower()
        for key in ("response", "payload", "body", "eventStream", "stream"):
            if key in data:
                body = data[key]
                break
    if is_sse and hasattr(body, "iter_lines"):
        body = _agentcore_sse_lines(body)
    if not is_sse and hasattr(body, "read"):
        body = await asyncio.to_thread(body.read)
        if inspect.isawaitable(body):
            body = await body
    if is_sse and isinstance(body, (str, bytes)):
        body = body.splitlines()
    if isinstance(body, bytes):
        body = body.decode("utf-8")
    if isinstance(body, str):
        try:
            decoded = json.loads(body)
        except json.JSONDecodeError:
            yield body
            return
        if isinstance(decoded, dict):
            for key in ("result", "response", "completion", "content", "text"):
                value = decoded.get(key)
                if isinstance(value, str) or _mapping(value) is not None:
                    yield value
                    return
        yield decoded
        return
    async for event in as_async_iterable(body):
        data = _mapping(event)
        if data is not None:
            chunk = _mapping(data.get("chunk"))
            if chunk is not None and "bytes" in chunk:
                event = chunk["bytes"]
        if isinstance(event, bytes):
            try:
                event = event.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise StreamProtocolError(
                    "AgentCore emitted non-UTF-8 content"
                ) from exc
        if isinstance(event, str):
            stripped = event.strip()
            if is_sse:
                event = _decode_sse_line(stripped)
                if event is _SKIP_EVENT:
                    continue
            elif stripped:
                try:
                    decoded = json.loads(stripped)
                except json.JSONDecodeError:
                    pass
                else:
                    event = decoded
        yield event


def _decode_sse_line(line: str) -> Any:
    """Decode one AgentCore SSE data line without exposing envelope text."""

    if not line or line.startswith(":"):
        return _SKIP_EVENT
    if line.startswith(("event:", "id:", "retry:")):
        return _SKIP_EVENT
    if line.startswith("data:"):
        line = line[5:].lstrip()
    if not line or line == "[DONE]":
        return _SKIP_EVENT
    try:
        decoded = json.loads(line)
    except json.JSONDecodeError:
        # BedrockAgentCoreApp falls back to ``repr`` for native Strands
        # convenience events containing Agent/Trace objects. The same model
        # delta has already arrived as a JSON-serializable Bedrock protocol
        # event, so retaining this Python-dict representation would inspect
        # and release every token twice. It is not a portable application
        # event and cannot be reconstructed safely.
        if line.startswith(("{'", "[{'")):
            return _SKIP_EVENT
        return line
    if isinstance(decoded, str) and decoded.startswith(("{'", "[{'")):
        return _SKIP_EVENT
    return decoded


class StrandsBedrockAdapter(StrandsEventAdapter):
    """Reusable adapter for native Strands/Bedrock response events."""

    def __init__(self, *, max_tool_argument_chars: int = 8192) -> None:
        super().__init__(
            source="strands-bedrock",
            max_tool_argument_chars=max_tool_argument_chars,
        )


class StrandsAgentCoreAdapter(StrandsEventAdapter):
    """Reusable adapter for boto3 Bedrock AgentCore Runtime responses."""

    def __init__(self, *, max_tool_argument_chars: int = 8192) -> None:
        super().__init__(
            source="strands-agentcore",
            max_tool_argument_chars=max_tool_argument_chars,
        )

    async def adapt(
        self,
        events: Any,
        *,
        message_id: Optional[str] = None,
        direction: Optional[StreamDirection] = None,
    ) -> AsyncIterator[StreamEvent]:
        async for converted in super().adapt(
            agentcore_events(events),
            message_id=message_id,
            direction=direction,
        ):
            yield converted
