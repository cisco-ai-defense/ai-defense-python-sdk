# Copyright 2025 Cisco Systems, Inc. and its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

"""
Cohere client autopatching.

Patches Cohere v2 client chat and chat_stream (sync and async) so that
conversations are inspected by AI Defense before and after the call.
"""

import logging
import threading
from types import SimpleNamespace
from typing import Any, Dict, Iterator, List, Optional

import wrapt

from .. import _state
from .._context import get_inspection_context, set_inspection_context
from ..decision import Decision
from ..exceptions import SecurityPolicyError
from ..inspectors.api_llm import LLMInspector
from . import is_patched, mark_patched
from ._base import safe_import, resolve_gateway_settings

logger = logging.getLogger("aidefense.runtime.agentsec.patchers.cohere")

_inspector: Optional[LLMInspector] = None
_inspector_lock = threading.Lock()

MAX_STREAMING_BUFFER_SIZE = 1_000_000


def _reset_inspector() -> None:
    """Clear the cached inspector so the next call to _get_inspector() creates a fresh one."""
    global _inspector
    _inspector = None


def _get_inspector() -> LLMInspector:
    global _inspector
    if _inspector is None:
        with _inspector_lock:
            if _inspector is None:
                if not _state.is_initialized():
                    logger.warning("agentsec.protect() not called, using default config")
                _inspector = LLMInspector(
                    fail_open=_state.get_api_llm_fail_open(),
                    default_rules=_state.get_llm_rules(),
                )
                from ..inspectors import register_inspector_for_cleanup
                register_inspector_for_cleanup(_inspector)
    return _inspector


def _normalize_messages(messages: Any) -> List[Dict[str, Any]]:
    """Normalize Cohere v2 messages to [{role, content}, ...] for AI Defense."""
    if not messages or not isinstance(messages, (list, tuple)):
        return []
    result = []
    for m in messages:
        try:
            if isinstance(m, dict):
                role = m.get("role", "user")
                content = m.get("content")
            else:
                role = getattr(m, "role", "user")
                content = getattr(m, "content", None)
            if role == "tool":
                continue
            text = _content_to_string(content)
            if text:
                result.append({"role": role, "content": text})
        except Exception as e:
            logger.debug(f"Skip message during normalize: {e}")
    return result


def _content_to_string(content: Any) -> str:
    """Convert Cohere message content (string, list of blocks, or object) to a single string."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(item.get("text", item.get("content", "")))
            elif hasattr(item, "text"):
                parts.append(getattr(item, "text", "") or "")
            elif hasattr(item, "content"):
                parts.append(_content_to_string(getattr(item, "content")))
        return "\n".join(p for p in parts if p)
    if hasattr(content, "content"):
        return _content_to_string(getattr(content, "content"))
    if hasattr(content, "text"):
        return getattr(content, "text", "") or ""
    return str(content)


def _extract_assistant_content(response: Any) -> str:
    """Extract assistant text from Cohere V2ChatResponse."""
    try:
        message = getattr(response, "message", None)
        if message is None:
            return ""
        content = getattr(message, "content", None)
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if hasattr(item, "text"):
                    parts.append(getattr(item, "text", "") or "")
                elif isinstance(item, dict):
                    parts.append(item.get("text", ""))
                elif isinstance(item, str):
                    parts.append(item)
            return "\n".join(parts)
        return ""
    except Exception as e:
        logger.debug(f"Error extracting Cohere assistant content: {e}")
    return ""


def _should_inspect() -> bool:
    """When mode is None (not configured), inspection is off by default."""
    from .._context import is_llm_skip_active
    if is_llm_skip_active():
        return False
    if _state.get_llm_integration_mode() == "gateway":
        if _state.get_gw_llm_mode() == "off":
            return False
    else:
        mode = _state.get_llm_mode()
        if mode is None or mode == "off":
            return False
    return not get_inspection_context().done


def _enforce_decision(decision: Decision) -> None:
    """Enforce or log a decision based on the current mode."""
    mode = _state.get_llm_mode()
    if decision.action == "block":
        if mode == "enforce":
            raise SecurityPolicyError(decision)
        elif mode == "monitor":
            logger.warning(
                "[agentsec] Block decision in monitor mode: reasons=%s, severity=%s, classifications=%s",
                decision.reasons, decision.severity, decision.classifications,
            )
            callback = _state.get_on_violation()
            if callback is not None:
                try:
                    callback(decision)
                except Exception:
                    logger.debug("on_violation callback raised an exception", exc_info=True)


def _handle_patcher_error(error: Exception, operation: str) -> Optional[Decision]:
    fail_open = _state.get_api_llm_fail_open()
    logger.warning(f"[{operation}] Inspection error: {type(error).__name__}: {error}")
    if fail_open:
        logger.warning("llm_fail_open=True, allowing request despite inspection error")
        return Decision.allow(reasons=[f"Inspection error ({type(error).__name__}), fail_open=True"])
    logger.error("llm_fail_open=False, blocking request due to inspection error")
    raise SecurityPolicyError(
        Decision.block(reasons=[f"Inspection error: {type(error).__name__}: {error}"]),
        f"Inspection failed and fail_open=False: {error}",
    )


def _serialize_messages_for_gateway(messages: Any) -> List[Dict[str, Any]]:
    """Convert Cohere messages to JSON-serializable list for gateway request."""
    if not messages:
        return []
    out = []
    for m in messages:
        if isinstance(m, dict):
            out.append({"role": m.get("role", "user"), "content": m.get("content") or ""})
        else:
            role = getattr(m, "role", "user")
            content = getattr(m, "content", None)
            if hasattr(m, "model_dump"):
                out.append(m.model_dump())
            elif hasattr(m, "dict"):
                out.append(m.dict())
            else:
                out.append({"role": role, "content": _content_to_string(content)})
    return out


def _dict_to_cohere_response(data: Dict[str, Any]) -> Any:
    """Convert gateway JSON response to object with .message.content for caller compatibility."""
    message_data = data.get("message", {})
    content_raw = message_data.get("content")
    if isinstance(content_raw, list):
        content = [SimpleNamespace(text=item.get("text", "")) for item in content_raw if isinstance(item, dict)]
    elif isinstance(content_raw, str):
        content = [SimpleNamespace(text=content_raw)]
    else:
        content = []
    message = SimpleNamespace(role="assistant", content=content)
    return SimpleNamespace(
        id=data.get("id", ""),
        finish_reason=data.get("finish_reason"),
        message=message,
        usage=getattr(data.get("usage"), "__dict__", data.get("usage")),
    )


def _handle_gateway_call_sync(
    kwargs: Dict[str, Any],
    normalized: List[Dict[str, Any]],
    metadata: Dict[str, Any],
    gw_settings: Any,
) -> Any:
    """Route Cohere chat request through AI Defense Gateway (sync). Gateway returns full response; streaming not used."""
    import httpx
    gateway_url = gw_settings.url
    gateway_api_key = gw_settings.api_key
    if not gateway_url or not gateway_api_key:
        logger.warning("Gateway mode enabled but Cohere gateway not configured")
        block_decision = Decision.block(reasons=["Cohere gateway not configured"])
        set_inspection_context(decision=block_decision, done=True)
        raise SecurityPolicyError(
            block_decision,
            "Gateway mode enabled but Cohere gateway not configured (check gateway_mode.llm_gateways for a cohere provider entry in config)",
        )
    messages = kwargs.get("messages", [])
    request_body = {
        "model": kwargs.get("model"),
        "messages": _serialize_messages_for_gateway(messages),
    }
    for key in ["max_tokens", "temperature", "stop_sequences", "seed", "frequency_penalty", "presence_penalty"]:
        if key in kwargs and kwargs[key] is not None:
            request_body[key] = kwargs[key]
    full_url = gateway_url.rstrip("/")
    if "/chat" not in full_url and "/v2" not in full_url:
        full_url = f"{full_url}/v2/chat"
    try:
        with httpx.Client(timeout=float(gw_settings.timeout)) as client:
            response = client.post(
                full_url,
                json=request_body,
                headers={
                    "Authorization": f"Bearer {gateway_api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            response_data = response.json()
        set_inspection_context(decision=Decision.allow(reasons=["Gateway handled inspection"]), done=True)
        return _dict_to_cohere_response(response_data)
    except httpx.HTTPStatusError as e:
        logger.error(f"[GATEWAY] Cohere HTTP error: {e}")
        if gw_settings.fail_open:
            set_inspection_context(decision=Decision.allow(reasons=["Gateway error, fail_open=True"]), done=True)
            raise
        block_decision = Decision.block(reasons=["Gateway unavailable"])
        set_inspection_context(decision=block_decision, done=True)
        raise SecurityPolicyError(block_decision, f"Gateway HTTP error: {e}")
    except SecurityPolicyError:
        raise
    except Exception as e:
        logger.error(f"[GATEWAY] Cohere error: {e}")
        if gw_settings.fail_open:
            set_inspection_context(decision=Decision.allow(reasons=["Gateway error, fail_open=True"]), done=True)
            raise
        block_decision = Decision.block(reasons=[f"Gateway error: {e}"])
        set_inspection_context(decision=block_decision, done=True)
        raise SecurityPolicyError(block_decision, f"Gateway error: {e}")


async def _handle_gateway_call_async(
    kwargs: Dict[str, Any],
    normalized: List[Dict[str, Any]],
    metadata: Dict[str, Any],
    gw_settings: Any,
) -> Any:
    """Route Cohere chat request through AI Defense Gateway (async)."""
    import httpx
    gateway_url = gw_settings.url
    gateway_api_key = gw_settings.api_key
    if not gateway_url or not gateway_api_key:
        logger.warning("Gateway mode enabled but Cohere gateway not configured")
        block_decision = Decision.block(reasons=["Cohere gateway not configured"])
        set_inspection_context(decision=block_decision, done=True)
        raise SecurityPolicyError(
            block_decision,
            "Gateway mode enabled but Cohere gateway not configured (check gateway_mode.llm_gateways for a cohere provider entry in config)",
        )
    messages = kwargs.get("messages", [])
    request_body = {
        "model": kwargs.get("model"),
        "messages": _serialize_messages_for_gateway(messages),
    }
    for key in ["max_tokens", "temperature", "stop_sequences", "seed", "frequency_penalty", "presence_penalty"]:
        if key in kwargs and kwargs[key] is not None:
            request_body[key] = kwargs[key]
    full_url = gateway_url.rstrip("/")
    if "/chat" not in full_url and "/v2" not in full_url:
        full_url = f"{full_url}/v2/chat"
    try:
        async with httpx.AsyncClient(timeout=float(gw_settings.timeout)) as client:
            response = await client.post(
                full_url,
                json=request_body,
                headers={
                    "Authorization": f"Bearer {gateway_api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            response_data = response.json()
        set_inspection_context(decision=Decision.allow(reasons=["Gateway handled inspection"]), done=True)
        return _dict_to_cohere_response(response_data)
    except httpx.HTTPStatusError as e:
        logger.error(f"[GATEWAY] Cohere async HTTP error: {e}")
        if gw_settings.fail_open:
            set_inspection_context(decision=Decision.allow(reasons=["Gateway error, fail_open=True"]), done=True)
            raise
        block_decision = Decision.block(reasons=["Gateway unavailable"])
        set_inspection_context(decision=block_decision, done=True)
        raise SecurityPolicyError(block_decision, f"Gateway HTTP error: {e}")
    except SecurityPolicyError:
        raise
    except Exception as e:
        logger.error(f"[GATEWAY] Cohere async error: {e}")
        if gw_settings.fail_open:
            set_inspection_context(decision=Decision.allow(reasons=["Gateway error, fail_open=True"]), done=True)
            raise
        block_decision = Decision.block(reasons=[f"Gateway error: {e}"])
        set_inspection_context(decision=block_decision, done=True)
        raise SecurityPolicyError(block_decision, f"Gateway error: {e}")


class _CohereStreamingInspectionWrapper:
    """Wraps Cohere chat_stream iterator; buffers content-delta text and runs response inspection at end."""

    def __init__(self, stream: Iterator, messages: List[Dict[str, Any]], metadata: Dict[str, Any]):
        self._stream = stream
        self._messages = messages
        self._metadata = metadata
        self._buffer = ""
        self._inspector = _get_inspector()
        self._final_inspection_done = False

    def __iter__(self):
        return self

    def __next__(self):
        try:
            chunk = next(self._stream)
        except StopIteration:
            self._perform_final_inspection()
            raise
        except Exception as e:
            logger.warning(f"Cohere stream error, performing final inspection: {e}")
            self._perform_final_inspection()
            raise
        # Cohere v2 stream: content-delta chunks have type and delta (delta may have text/delta)
        try:
            chunk_type = getattr(chunk, "type", None) or (chunk.get("type") if isinstance(chunk, dict) else None)
            if chunk_type == "content-delta":
                delta = getattr(chunk, "delta", None) or (chunk.get("delta") if isinstance(chunk, dict) else None)
                if delta is not None:
                    text = getattr(delta, "text", None) or getattr(delta, "delta", None)
                    if isinstance(delta, dict):
                        text = text or delta.get("text") or delta.get("delta")
                    if text and len(self._buffer) < MAX_STREAMING_BUFFER_SIZE:
                        self._buffer += text[: MAX_STREAMING_BUFFER_SIZE - len(self._buffer)]
        except Exception as e:
            logger.debug(f"Cohere stream chunk handling: {e}")
        return chunk

    def _perform_final_inspection(self) -> None:
        if self._final_inspection_done:
            return
        self._final_inspection_done = True
        if not self._buffer or not _should_inspect():
            return
        buf = self._buffer[:MAX_STREAMING_BUFFER_SIZE]
        messages_with_response = self._messages + [{"role": "assistant", "content": buf}]
        try:
            decision = self._inspector.inspect_conversation(messages_with_response, self._metadata)
            set_inspection_context(decision=decision, done=True)
            _enforce_decision(decision)
        except SecurityPolicyError:
            raise
        except Exception as e:
            _handle_patcher_error(e, "Cohere streaming inspection")


class _CohereAsyncStreamingInspectionWrapper:
    """Async wrapper for Cohere chat_stream with end-of-stream response inspection."""

    def __init__(self, stream: Any, messages: List[Dict[str, Any]], metadata: Dict[str, Any]):
        self._stream = stream
        self._messages = messages
        self._metadata = metadata
        self._buffer = ""
        self._inspector = _get_inspector()
        self._final_inspection_done = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            chunk = await self._stream.__anext__()
        except StopAsyncIteration:
            await self._perform_final_inspection()
            raise
        except Exception as e:
            logger.warning(f"Cohere async stream error, performing final inspection: {e}")
            await self._perform_final_inspection()
            raise
        try:
            chunk_type = getattr(chunk, "type", None) or (chunk.get("type") if isinstance(chunk, dict) else None)
            if chunk_type == "content-delta":
                delta = getattr(chunk, "delta", None) or (chunk.get("delta") if isinstance(chunk, dict) else None)
                if delta is not None:
                    text = getattr(delta, "text", None) or getattr(delta, "delta", None)
                    if isinstance(delta, dict):
                        text = text or delta.get("text") or delta.get("delta")
                    if text and len(self._buffer) < MAX_STREAMING_BUFFER_SIZE:
                        self._buffer += text[: MAX_STREAMING_BUFFER_SIZE - len(self._buffer)]
        except Exception as e:
            logger.debug(f"Cohere async stream chunk handling: {e}")
        return chunk

    async def _perform_final_inspection(self) -> None:
        if self._final_inspection_done:
            return
        self._final_inspection_done = True
        if not self._buffer or not _should_inspect():
            return
        buf = self._buffer[:MAX_STREAMING_BUFFER_SIZE]
        messages_with_response = self._messages + [{"role": "assistant", "content": buf}]
        try:
            decision = await self._inspector.ainspect_conversation(messages_with_response, self._metadata)
            set_inspection_context(decision=decision, done=True)
            _enforce_decision(decision)
        except SecurityPolicyError:
            raise
        except Exception as e:
            _handle_patcher_error(e, "Cohere async streaming inspection")


class _CohereFakeStreamWrapper:
    """Yields a single content-delta chunk from a full gateway response (streaming not supported by gateway)."""

    def __init__(self, response: Any):
        self._response = response
        self._yielded = False

    def __iter__(self) -> Iterator[Any]:
        return self

    def __next__(self) -> Any:
        if self._yielded:
            raise StopIteration
        self._yielded = True
        text = _extract_assistant_content(self._response)
        delta = SimpleNamespace(text=text)
        return SimpleNamespace(type="content-delta", index=0, delta=delta)


class _CohereAsyncFakeStreamWrapper:
    """Async: yields a single content-delta chunk from a full gateway response."""

    def __init__(self, response: Any):
        self._response = response
        self._yielded = False

    def __aiter__(self) -> "_CohereAsyncFakeStreamWrapper":
        return self

    async def __anext__(self) -> Any:
        if self._yielded:
            raise StopAsyncIteration
        self._yielded = True
        text = _extract_assistant_content(self._response)
        delta = SimpleNamespace(text=text)
        return SimpleNamespace(type="content-delta", index=0, delta=delta)


def _wrap_chat(wrapped, instance, args, kwargs):
    """Sync wrapper for V2Client.chat. Supports API and gateway integration modes."""
    set_inspection_context(done=False)
    if not _should_inspect():
        return wrapped(*args, **kwargs)
    model = kwargs.get("model", "unknown")
    messages = kwargs.get("messages", [])
    normalized = _normalize_messages(messages)
    metadata = get_inspection_context().metadata

    gw_settings = resolve_gateway_settings("cohere")
    if gw_settings:
        logger.debug(f"[PATCHED] Cohere V2Client.chat gateway mode - routing to AI Defense Gateway")
        return _handle_gateway_call_sync(kwargs, normalized, metadata, gw_settings)

    logger.debug(f"[PATCHED] Cohere V2Client.chat model={model} messages={len(normalized)}")
    try:
        inspector = _get_inspector()
        decision = inspector.inspect_conversation(normalized, metadata)
        set_inspection_context(decision=decision)
        _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as e:
        decision = _handle_patcher_error(e, "Cohere.chat pre-call")
        if decision:
            set_inspection_context(decision=decision)

    response = wrapped(*args, **kwargs)

    try:
        assistant_content = _extract_assistant_content(response)
        if assistant_content:
            messages_with_response = normalized + [{"role": "assistant", "content": assistant_content}]
            inspector = _get_inspector()
            decision = inspector.inspect_conversation(messages_with_response, metadata)
            set_inspection_context(decision=decision, done=True)
            _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as e:
        _handle_patcher_error(e, "Cohere.chat post-call")
    return response


def _wrap_chat_stream(wrapped, instance, args, kwargs):
    """Sync wrapper for V2Client.chat_stream. In gateway mode returns a fake stream of one chunk."""
    set_inspection_context(done=False)
    if not _should_inspect():
        return wrapped(*args, **kwargs)
    model = kwargs.get("model", "unknown")
    messages = kwargs.get("messages", [])
    normalized = _normalize_messages(messages)
    metadata = get_inspection_context().metadata

    gw_settings = resolve_gateway_settings("cohere")
    if gw_settings:
        logger.debug(f"[PATCHED] Cohere V2Client.chat_stream gateway mode - full response as single chunk")
        response = _handle_gateway_call_sync(kwargs, normalized, metadata, gw_settings)
        return _CohereFakeStreamWrapper(response)

    logger.debug(f"[PATCHED] Cohere V2Client.chat_stream model={model} messages={len(normalized)}")
    try:
        inspector = _get_inspector()
        decision = inspector.inspect_conversation(normalized, metadata)
        set_inspection_context(decision=decision)
        _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as e:
        decision = _handle_patcher_error(e, "Cohere.chat_stream pre-call")
        if decision:
            set_inspection_context(decision=decision)

    stream = wrapped(*args, **kwargs)
    return _CohereStreamingInspectionWrapper(stream, normalized, metadata)


async def _wrap_chat_async(wrapped, instance, args, kwargs):
    """Async wrapper for AsyncV2Client.chat. Supports API and gateway integration modes."""
    set_inspection_context(done=False)
    if not _should_inspect():
        return await wrapped(*args, **kwargs)
    model = kwargs.get("model", "unknown")
    messages = kwargs.get("messages", [])
    normalized = _normalize_messages(messages)
    metadata = get_inspection_context().metadata

    gw_settings = resolve_gateway_settings("cohere")
    if gw_settings:
        logger.debug(f"[PATCHED] Cohere AsyncV2Client.chat gateway mode - routing to AI Defense Gateway")
        return await _handle_gateway_call_async(kwargs, normalized, metadata, gw_settings)

    logger.debug(f"[PATCHED] Cohere AsyncV2Client.chat model={model} messages={len(normalized)}")
    try:
        inspector = _get_inspector()
        decision = await inspector.ainspect_conversation(normalized, metadata)
        set_inspection_context(decision=decision)
        _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as e:
        decision = _handle_patcher_error(e, "Cohere.async.chat pre-call")
        if decision:
            set_inspection_context(decision=decision)

    response = await wrapped(*args, **kwargs)

    try:
        assistant_content = _extract_assistant_content(response)
        if assistant_content:
            messages_with_response = normalized + [{"role": "assistant", "content": assistant_content}]
            inspector = _get_inspector()
            decision = await inspector.ainspect_conversation(messages_with_response, metadata)
            set_inspection_context(decision=decision, done=True)
            _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as e:
        _handle_patcher_error(e, "Cohere.async.chat post-call")
    return response


async def _wrap_chat_stream_async(wrapped, instance, args, kwargs):
    """Async wrapper for AsyncV2Client.chat_stream. In gateway mode returns a fake stream of one chunk."""
    set_inspection_context(done=False)
    if not _should_inspect():
        return await wrapped(*args, **kwargs)
    model = kwargs.get("model", "unknown")
    messages = kwargs.get("messages", [])
    normalized = _normalize_messages(messages)
    metadata = get_inspection_context().metadata

    gw_settings = resolve_gateway_settings("cohere")
    if gw_settings:
        logger.debug(f"[PATCHED] Cohere AsyncV2Client.chat_stream gateway mode - full response as single chunk")
        response = await _handle_gateway_call_async(kwargs, normalized, metadata, gw_settings)
        return _CohereAsyncFakeStreamWrapper(response)

    logger.debug(f"[PATCHED] Cohere AsyncV2Client.chat_stream model={model} messages={len(normalized)}")
    try:
        inspector = _get_inspector()
        decision = await inspector.ainspect_conversation(normalized, metadata)
        set_inspection_context(decision=decision)
        _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as e:
        decision = _handle_patcher_error(e, "Cohere.async.chat_stream pre-call")
        if decision:
            set_inspection_context(decision=decision)

    stream = await wrapped(*args, **kwargs)
    return _CohereAsyncStreamingInspectionWrapper(stream, normalized, metadata)


def patch_cohere() -> bool:
    """Patch Cohere v2 client for automatic inspection. Returns True if patching succeeded."""
    if is_patched("cohere"):
        logger.debug("Cohere already patched, skipping")
        return True
    if safe_import("cohere") is None:
        return False
    try:
        wrapt.wrap_function_wrapper("cohere.v2.client", "V2Client.chat", _wrap_chat)
        wrapt.wrap_function_wrapper("cohere.v2.client", "V2Client.chat_stream", _wrap_chat_stream)
        wrapt.wrap_function_wrapper("cohere.v2.client", "AsyncV2Client.chat", _wrap_chat_async)
        wrapt.wrap_function_wrapper("cohere.v2.client", "AsyncV2Client.chat_stream", _wrap_chat_stream_async)
        mark_patched("cohere")
        logger.info("Cohere client patched successfully")
        return True
    except Exception as e:
        logger.warning(f"Failed to patch Cohere: {e}")
        return False
