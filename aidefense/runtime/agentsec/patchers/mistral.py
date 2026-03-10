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
Mistral client autopatching.

Patches Mistral AI SDK chat.complete, chat.complete_async, chat.stream, and
chat.stream_async so that conversations are inspected by AI Defense before and
after the call. Supports both API mode (inspect then call) and gateway mode
(route through AI Defense Gateway).
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

logger = logging.getLogger("aidefense.runtime.agentsec.patchers.mistral")

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
    """Normalize Mistral/OpenAI-style messages to [{role, content}, ...] for AI Defense."""
    if not messages or not isinstance(messages, (list, tuple)):
        return []
    result = []
    for m in messages:
        try:
            if isinstance(m, dict):
                role = m.get("role", "user")
                content = m.get("content") or ""
            else:
                role = getattr(m, "role", "user")
                content = getattr(m, "content", None) or ""
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict):
                        text_parts.append(block.get("text", block.get("content", "")))
                    elif isinstance(block, str):
                        text_parts.append(block)
                    elif hasattr(block, "text"):
                        text_parts.append(getattr(block, "text", "") or "")
                content = "\n".join(p for p in text_parts if p)
            if role in ("tool", "function"):
                continue
            if content:
                result.append({"role": role, "content": content})
        except Exception as e:
            logger.debug(f"Skip message during normalize: {e}")
    return result


def _extract_assistant_content(response: Any) -> str:
    """Extract assistant text from Mistral ChatCompletionResponse (OpenAI-compatible)."""
    try:
        if hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            if hasattr(choice, "message"):
                return (getattr(choice.message, "content", None) or "") or ""
            if hasattr(choice, "text"):
                return (getattr(choice, "text", None) or "") or ""
    except Exception as e:
        logger.debug(f"Error extracting Mistral assistant content: {e}")
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
    """Convert messages to JSON-serializable list for gateway request."""
    normalized = _normalize_messages(messages)
    return [{"role": m["role"], "content": m["content"]} for m in normalized]


def _dict_to_mistral_response(data: Dict[str, Any]) -> Any:
    """Convert gateway JSON (OpenAI-style) to object with .choices[0].message.content."""
    choices = data.get("choices", [])
    if not choices:
        return SimpleNamespace(choices=[])
    c = choices[0]
    msg = c.get("message", {})
    content = msg.get("content") or ""
    message = SimpleNamespace(content=content, role=msg.get("role", "assistant"))
    choice = SimpleNamespace(message=message, index=c.get("index", 0), finish_reason=c.get("finish_reason"))
    return SimpleNamespace(
        id=data.get("id", ""),
        choices=[choice],
        usage=getattr(data.get("usage"), "__dict__", data.get("usage")),
    )


def _handle_gateway_call_sync(
    kwargs: Dict[str, Any],
    normalized: List[Dict[str, Any]],
    metadata: Dict[str, Any],
    stream: bool,
    gw_settings: Any,
) -> Any:
    """Route Mistral chat request through AI Defense Gateway (sync)."""
    import httpx
    gateway_url = gw_settings.url
    gateway_api_key = gw_settings.api_key
    if not gateway_url or not gateway_api_key:
        logger.warning("Gateway mode enabled but Mistral gateway not configured")
        block_decision = Decision.block(reasons=["Mistral gateway not configured"])
        set_inspection_context(decision=block_decision, done=True)
        raise SecurityPolicyError(
            block_decision,
            "Gateway mode enabled but Mistral gateway not configured (check gateway_mode.llm_gateways for a mistral provider entry in config)",
        )
    request_body = {
        "model": kwargs.get("model"),
        "messages": _serialize_messages_for_gateway(kwargs.get("messages", [])),
    }
    for key in ["temperature", "max_tokens", "stream", "stop", "top_p", "presence_penalty", "frequency_penalty"]:
        if key in kwargs and kwargs[key] is not None:
            request_body[key] = kwargs[key]
    full_url = gateway_url.rstrip("/")
    if "/chat/completions" not in full_url:
        full_url = f"{full_url}/v1/chat/completions"
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
        obj = _dict_to_mistral_response(response_data)
        if stream:
            return _MistralFakeStreamWrapper(obj)
        return obj
    except httpx.HTTPStatusError as e:
        logger.error(f"[GATEWAY] Mistral HTTP error: {e}")
        if gw_settings.fail_open:
            set_inspection_context(decision=Decision.allow(reasons=["Gateway error, fail_open=True"]), done=True)
            raise
        block_decision = Decision.block(reasons=["Gateway unavailable"])
        set_inspection_context(decision=block_decision, done=True)
        raise SecurityPolicyError(block_decision, f"Gateway HTTP error: {e}")
    except SecurityPolicyError:
        raise
    except Exception as e:
        logger.error(f"[GATEWAY] Mistral error: {e}")
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
    stream: bool,
    gw_settings: Any,
) -> Any:
    """Route Mistral chat request through AI Defense Gateway (async)."""
    import httpx
    gateway_url = gw_settings.url
    gateway_api_key = gw_settings.api_key
    if not gateway_url or not gateway_api_key:
        logger.warning("Gateway mode enabled but Mistral gateway not configured")
        block_decision = Decision.block(reasons=["Mistral gateway not configured"])
        set_inspection_context(decision=block_decision, done=True)
        raise SecurityPolicyError(
            block_decision,
            "Gateway mode enabled but Mistral gateway not configured (check gateway_mode.llm_gateways for a mistral provider entry in config)",
        )
    request_body = {
        "model": kwargs.get("model"),
        "messages": _serialize_messages_for_gateway(kwargs.get("messages", [])),
    }
    for key in ["temperature", "max_tokens", "stream", "stop", "top_p", "presence_penalty", "frequency_penalty"]:
        if key in kwargs and kwargs[key] is not None:
            request_body[key] = kwargs[key]
    full_url = gateway_url.rstrip("/")
    if "/chat/completions" not in full_url:
        full_url = f"{full_url}/v1/chat/completions"
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
        obj = _dict_to_mistral_response(response_data)
        if stream:
            return _MistralAsyncFakeStreamWrapper(obj)
        return obj
    except httpx.HTTPStatusError as e:
        logger.error(f"[GATEWAY] Mistral async HTTP error: {e}")
        if gw_settings.fail_open:
            set_inspection_context(decision=Decision.allow(reasons=["Gateway error, fail_open=True"]), done=True)
            raise
        block_decision = Decision.block(reasons=["Gateway unavailable"])
        set_inspection_context(decision=block_decision, done=True)
        raise SecurityPolicyError(block_decision, f"Gateway HTTP error: {e}")
    except SecurityPolicyError:
        raise
    except Exception as e:
        logger.error(f"[GATEWAY] Mistral async error: {e}")
        if gw_settings.fail_open:
            set_inspection_context(decision=Decision.allow(reasons=["Gateway error, fail_open=True"]), done=True)
            raise
        block_decision = Decision.block(reasons=[f"Gateway error: {e}"])
        set_inspection_context(decision=block_decision, done=True)
        raise SecurityPolicyError(block_decision, f"Gateway error: {e}")


class _MistralStreamingInspectionWrapper:
    """Wraps Mistral stream iterator; buffers content and runs response inspection at end."""

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
            logger.warning(f"Mistral stream error, performing final inspection: {e}")
            self._perform_final_inspection()
            raise
        try:
            if hasattr(chunk, "data") and hasattr(chunk.data, "choices") and chunk.data.choices:
                delta = getattr(chunk.data.choices[0], "delta", None)
                if delta and getattr(delta, "content", None):
                    text = delta.content
                    if text and len(self._buffer) < MAX_STREAMING_BUFFER_SIZE:
                        self._buffer += text[: MAX_STREAMING_BUFFER_SIZE - len(self._buffer)]
        except Exception as e:
            logger.debug(f"Mistral stream chunk handling: {e}")
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
            _handle_patcher_error(e, "Mistral streaming inspection")


class _MistralAsyncStreamingInspectionWrapper:
    """Async wrapper for Mistral stream with end-of-stream response inspection."""

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
            logger.warning(f"Mistral async stream error, performing final inspection: {e}")
            await self._perform_final_inspection()
            raise
        try:
            if hasattr(chunk, "data") and hasattr(chunk.data, "choices") and chunk.data.choices:
                delta = getattr(chunk.data.choices[0], "delta", None)
                if delta and getattr(delta, "content", None):
                    text = delta.content
                    if text and len(self._buffer) < MAX_STREAMING_BUFFER_SIZE:
                        self._buffer += text[: MAX_STREAMING_BUFFER_SIZE - len(self._buffer)]
        except Exception as e:
            logger.debug(f"Mistral async stream chunk handling: {e}")
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
            _handle_patcher_error(e, "Mistral async streaming inspection")


class _MistralFakeStreamWrapper:
    """Yields a single chunk from a full gateway response (streaming not supported by gateway)."""

    def __init__(self, response: Any):
        self._response = response
        self._yielded = False

    def __iter__(self) -> Iterator[Any]:
        return self

    def __next__(self) -> Any:
        if self._yielded:
            raise StopIteration
        self._yielded = True
        content = _extract_assistant_content(self._response)
        delta = SimpleNamespace(content=content)
        choice = SimpleNamespace(delta=delta, index=0, finish_reason="stop")
        return SimpleNamespace(data=SimpleNamespace(choices=[choice]))


class _MistralAsyncFakeStreamWrapper:
    def __init__(self, response: Any):
        self._response = response
        self._yielded = False

    def __aiter__(self) -> "_MistralAsyncFakeStreamWrapper":
        return self

    async def __anext__(self) -> Any:
        if self._yielded:
            raise StopAsyncIteration
        self._yielded = True
        content = _extract_assistant_content(self._response)
        delta = SimpleNamespace(content=content)
        choice = SimpleNamespace(delta=delta, index=0, finish_reason="stop")
        return SimpleNamespace(data=SimpleNamespace(choices=[choice]))


def _wrap_complete(wrapped, instance, args, kwargs):
    """Sync wrapper for Chat.complete."""
    set_inspection_context(done=False)
    if not _should_inspect():
        return wrapped(*args, **kwargs)
    model = kwargs.get("model", "unknown")
    messages = kwargs.get("messages", [])
    normalized = _normalize_messages(messages)
    metadata = get_inspection_context().metadata
    stream = kwargs.get("stream", False)

    gw_settings = resolve_gateway_settings("mistral")
    if gw_settings:
        logger.debug("[PATCHED] Mistral Chat.complete gateway mode - routing to AI Defense Gateway")
        return _handle_gateway_call_sync(kwargs, normalized, metadata, stream, gw_settings)

    logger.debug(f"[PATCHED] Mistral Chat.complete model={model} messages={len(normalized)}")
    try:
        inspector = _get_inspector()
        decision = inspector.inspect_conversation(normalized, metadata)
        set_inspection_context(decision=decision)
        _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as e:
        decision = _handle_patcher_error(e, "Mistral.chat.complete pre-call")
        if decision:
            set_inspection_context(decision=decision)

    response = wrapped(*args, **kwargs)

    if stream:
        return _MistralStreamingInspectionWrapper(response, normalized, metadata)

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
        _handle_patcher_error(e, "Mistral.chat.complete post-call")
    return response


def _wrap_stream(wrapped, instance, args, kwargs):
    """Sync wrapper for Chat.stream."""
    set_inspection_context(done=False)
    if not _should_inspect():
        return wrapped(*args, **kwargs)
    model = kwargs.get("model", "unknown")
    messages = kwargs.get("messages", [])
    normalized = _normalize_messages(messages)
    metadata = get_inspection_context().metadata

    gw_settings = resolve_gateway_settings("mistral")
    if gw_settings:
        logger.debug("[PATCHED] Mistral Chat.stream gateway mode - full response as single chunk")
        return _handle_gateway_call_sync({**kwargs, "stream": True}, normalized, metadata, True, gw_settings)

    logger.debug(f"[PATCHED] Mistral Chat.stream model={model} messages={len(normalized)}")
    try:
        inspector = _get_inspector()
        decision = inspector.inspect_conversation(normalized, metadata)
        set_inspection_context(decision=decision)
        _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as e:
        decision = _handle_patcher_error(e, "Mistral.chat.stream pre-call")
        if decision:
            set_inspection_context(decision=decision)

    stream = wrapped(*args, **kwargs)
    return _MistralStreamingInspectionWrapper(stream, normalized, metadata)


async def _wrap_complete_async(wrapped, instance, args, kwargs):
    """Async wrapper for Chat.complete_async."""
    set_inspection_context(done=False)
    if not _should_inspect():
        return await wrapped(*args, **kwargs)
    model = kwargs.get("model", "unknown")
    messages = kwargs.get("messages", [])
    normalized = _normalize_messages(messages)
    metadata = get_inspection_context().metadata
    stream = kwargs.get("stream", False)

    gw_settings = resolve_gateway_settings("mistral")
    if gw_settings:
        logger.debug("[PATCHED] Mistral Chat.complete_async gateway mode - routing to AI Defense Gateway")
        return await _handle_gateway_call_async(kwargs, normalized, metadata, stream, gw_settings)

    logger.debug(f"[PATCHED] Mistral Chat.complete_async model={model} messages={len(normalized)}")
    try:
        inspector = _get_inspector()
        decision = await inspector.ainspect_conversation(normalized, metadata)
        set_inspection_context(decision=decision)
        _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as e:
        decision = _handle_patcher_error(e, "Mistral.chat.complete_async pre-call")
        if decision:
            set_inspection_context(decision=decision)

    response = await wrapped(*args, **kwargs)

    if stream:
        return _MistralAsyncStreamingInspectionWrapper(response, normalized, metadata)

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
        _handle_patcher_error(e, "Mistral.chat.complete_async post-call")
    return response


async def _wrap_stream_async(wrapped, instance, args, kwargs):
    """Async wrapper for Chat.stream_async."""
    set_inspection_context(done=False)
    if not _should_inspect():
        return await wrapped(*args, **kwargs)
    model = kwargs.get("model", "unknown")
    messages = kwargs.get("messages", [])
    normalized = _normalize_messages(messages)
    metadata = get_inspection_context().metadata

    gw_settings = resolve_gateway_settings("mistral")
    if gw_settings:
        logger.debug("[PATCHED] Mistral Chat.stream_async gateway mode - full response as single chunk")
        return await _handle_gateway_call_async({**kwargs, "stream": True}, normalized, metadata, True, gw_settings)

    logger.debug(f"[PATCHED] Mistral Chat.stream_async model={model} messages={len(normalized)}")
    try:
        inspector = _get_inspector()
        decision = await inspector.ainspect_conversation(normalized, metadata)
        set_inspection_context(decision=decision)
        _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as e:
        decision = _handle_patcher_error(e, "Mistral.chat.stream_async pre-call")
        if decision:
            set_inspection_context(decision=decision)

    stream = await wrapped(*args, **kwargs)
    return _MistralAsyncStreamingInspectionWrapper(stream, normalized, metadata)


def patch_mistral() -> bool:
    """Patch Mistral AI client for automatic inspection. Returns True if patching succeeded."""
    if is_patched("mistral"):
        logger.debug("Mistral already patched, skipping")
        return True
    if safe_import("mistralai") is None:
        return False
    # Mistral SDK: Chat lives in mistralai.client.chat (repo layout) or mistralai.chat (some installs)
    try:
        module_path = "mistralai.client.chat"
        try:
            wrapt.wrap_function_wrapper(module_path, "Chat.complete", _wrap_complete)
            wrapt.wrap_function_wrapper(module_path, "Chat.stream", _wrap_stream)
            wrapt.wrap_function_wrapper(module_path, "Chat.complete_async", _wrap_complete_async)
            wrapt.wrap_function_wrapper(module_path, "Chat.stream_async", _wrap_stream_async)
        except (ImportError, AttributeError):
            module_path = "mistralai.chat"
            wrapt.wrap_function_wrapper(module_path, "Chat.complete", _wrap_complete)
            wrapt.wrap_function_wrapper(module_path, "Chat.stream", _wrap_stream)
            wrapt.wrap_function_wrapper(module_path, "Chat.complete_async", _wrap_complete_async)
            wrapt.wrap_function_wrapper(module_path, "Chat.stream_async", _wrap_stream_async)
        mark_patched("mistral")
        logger.info("Mistral client patched successfully")
        return True
    except Exception as e:
        logger.warning(f"Failed to patch Mistral: {e}")
        return False
