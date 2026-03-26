# Copyright 2026 Cisco Systems, Inc. and its affiliates
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
Azure AI Inference client autopatching.

This module provides automatic inspection for Azure AI Inference SDK calls
by patching ``ChatCompletionsClient.complete()``.

CrewAI uses its own native Azure integration via the ``azure-ai-inference``
SDK (``azure.ai.inference.ChatCompletionsClient``) instead of the OpenAI SDK
or litellm.  This patcher ensures those calls are intercepted by AI Defense.

Coverage includes:
- ``azure.ai.inference.ChatCompletionsClient.complete()``     (sync)
- ``azure.ai.inference.aio.ChatCompletionsClient.complete()``  (async)
"""

import logging
import threading
from typing import Any, Dict, Iterator, List, Optional

import wrapt

from .. import _state
from .._context import get_inspection_context, set_inspection_context
from ..decision import Decision
from ..exceptions import SecurityPolicyError
from ..inspectors.api_llm import LLMInspector
from . import is_patched, mark_patched
from ._base import safe_import, resolve_gateway_settings

logger = logging.getLogger("aidefense.runtime.agentsec.patchers.azure_ai_inference")

_inspector: Optional[LLMInspector] = None
_inspector_lock = threading.Lock()

MAX_STREAMING_BUFFER_SIZE = 1_000_000


def _reset_inspector() -> None:
    """Clear the cached inspector so the next call to _get_inspector() creates a fresh one."""
    global _inspector
    _inspector = None


def _get_inspector() -> LLMInspector:
    """Get or create the LLMInspector instance (thread-safe)."""
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


def _should_inspect() -> bool:
    """Check if we should inspect (not already done, mode is not off, and not skipped).

    When mode is None (not configured), inspection is off by default.
    """
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
    ctx = get_inspection_context()
    return not ctx.done


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


def _normalize_messages(messages: Any) -> List[Dict[str, Any]]:
    """Normalize Azure AI Inference messages to standard format for AI Defense API.

    The ``azure-ai-inference`` SDK accepts messages as dicts or
    ``ChatRequestMessage`` objects.  Both support dict-like access.
    """
    if not isinstance(messages, (list, tuple)):
        return []

    result: List[Dict[str, Any]] = []
    for m in messages:
        if isinstance(m, dict):
            role = m.get("role", "user")
            content = m.get("content") or ""
        elif hasattr(m, "role"):
            role = getattr(m, "role", "user")
            content = getattr(m, "content", "") or ""
        else:
            continue

        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text" and "text" in block:
                        text_parts.append(block["text"])
                    elif "text" in block:
                        text_parts.append(block["text"])
                elif isinstance(block, str):
                    text_parts.append(block)
            content = "\n".join(text_parts)

        if role in ("tool", "function"):
            continue

        if role == "assistant":
            tool_calls = None
            if isinstance(m, dict):
                tool_calls = m.get("tool_calls")
            elif hasattr(m, "tool_calls"):
                tool_calls = getattr(m, "tool_calls", None)
            if tool_calls:
                tool_names = []
                for tc in tool_calls:
                    if isinstance(tc, dict):
                        fn = tc.get("function", {})
                        tool_names.append(fn.get("name", "unknown"))
                    elif hasattr(tc, "function"):
                        fn = getattr(tc, "function", None)
                        tool_names.append(getattr(fn, "name", "unknown") if fn else "unknown")
                tool_info = f"[Called tools: {', '.join(tool_names)}]"
                content = f"{content} {tool_info}" if content else tool_info

        if content:
            result.append({"role": str(role), "content": str(content)})

    return result


def _extract_assistant_content(response: Any) -> str:
    """Extract assistant content from an Azure AI Inference ``ChatCompletions``."""
    try:
        choices = getattr(response, "choices", None) or (response.get("choices") if isinstance(response, dict) else None)
        if choices:
            choice = choices[0]
            message = getattr(choice, "message", None) or (choice.get("message") if isinstance(choice, dict) else None)
            if message:
                return getattr(message, "content", None) or (message.get("content", "") if isinstance(message, dict) else "") or ""
    except Exception as e:
        logger.debug(f"Error extracting assistant content: {e}")
    return ""


def _handle_patcher_error(error: Exception, operation: str) -> Optional[Decision]:
    """Handle errors in patcher inspection calls."""
    fail_open = _state.get_api_llm_fail_open()
    error_type = type(error).__name__
    logger.warning(f"[{operation}] Inspection error: {error_type}: {error}")
    if fail_open:
        logger.warning("llm_fail_open=True, allowing request despite inspection error")
        return Decision.allow(reasons=[f"Inspection error ({error_type}), fail_open=True"])
    else:
        logger.error("llm_fail_open=False, blocking request due to inspection error")
        decision = Decision.block(reasons=[f"Inspection error: {error_type}: {error}"])
        raise SecurityPolicyError(decision, f"Inspection failed and fail_open=False: {error}")


def _extract_model_from_instance(instance: Any) -> str:
    """Try to extract the model identifier from the client or endpoint URL."""
    try:
        endpoint = getattr(instance, "_config", None)
        if endpoint and hasattr(endpoint, "endpoint"):
            url = str(endpoint.endpoint)
            import re
            match = re.search(r'/deployments/([^/]+)', url)
            if match:
                return match.group(1)
    except Exception:
        pass
    return "azure-ai-inference"


def _extract_api_version(instance: Any) -> Optional[str]:
    """Extract the API version from the client configuration."""
    try:
        config = getattr(instance, "_config", None)
        if config and hasattr(config, "api_version"):
            return str(config.api_version)
    except Exception:
        pass
    return None


# =========================================================================
# Gateway call handling
# =========================================================================

def _handle_gateway_call_sync(
    model: str,
    messages: Any,
    kwargs: Dict[str, Any],
    normalized: List[Dict],
    metadata: Dict,
    gw_settings: Any,
    azure_api_version: Optional[str] = None,
) -> Any:
    """Route the request through the Azure OpenAI AI Defense Gateway."""
    import httpx

    gateway_url = gw_settings.url
    gateway_api_key = gw_settings.api_key

    model_name = gw_settings.gateway_model or model
    request_body: Dict[str, Any] = {
        "model": model_name,
        "messages": _messages_to_dicts(messages),
    }

    for param in ["temperature", "max_tokens", "top_p", "stop", "tools",
                  "tool_choice", "response_format", "seed",
                  "frequency_penalty", "presence_penalty"]:
        val = kwargs.get(param)
        if val is not None:
            request_body[param] = val

    stream = kwargs.get("stream")
    if stream:
        logger.debug("[GATEWAY] Streaming requested but gateway returns JSON - will convert response")

    try:
        full_url = gateway_url.rstrip("/")
        deployment_name = gw_settings.gateway_model or model
        if "chat/completions" not in full_url:
            full_url = f"{full_url}/openai/deployments/{deployment_name}/chat/completions"
            if azure_api_version:
                full_url = f"{full_url}?api-version={azure_api_version}"

        auth_headers = {
            "api-key": gateway_api_key or "",
            "Content-Type": "application/json",
        }

        logger.debug(f"[GATEWAY] Sending request to azure_ai_inference gateway: {full_url}")
        logger.debug(f"[GATEWAY] Request body model={request_body.get('model')}, keys={list(request_body.keys())}")

        with httpx.Client(timeout=float(gw_settings.timeout)) as client:
            response = client.post(full_url, json=request_body, headers=auth_headers)
            if response.status_code >= 400:
                logger.error(f"[GATEWAY] azure gateway returned {response.status_code}: {response.text[:500]}")
            response.raise_for_status()
            response_data = response.json()

        logger.debug("[GATEWAY] Received response from azure gateway")
        set_inspection_context(decision=Decision.allow(reasons=["Gateway handled inspection"]), done=True)
        return _dict_to_azure_response(response_data)

    except SecurityPolicyError:
        raise
    except Exception as e:
        logger.error(f"[GATEWAY] HTTP error: {e}")
        if gw_settings.fail_open:
            logger.warning("[GATEWAY] fail_open=True, re-raising original HTTP error for caller to handle")
            set_inspection_context(decision=Decision.allow(reasons=["Gateway error, fail_open=True"]), done=True)
            raise
        raise SecurityPolicyError(
            Decision.block(reasons=["Gateway unavailable"]),
            f"Gateway HTTP error: {e}",
        )


async def _handle_gateway_call_async(
    model: str,
    messages: Any,
    kwargs: Dict[str, Any],
    normalized: List[Dict],
    metadata: Dict,
    gw_settings: Any,
    azure_api_version: Optional[str] = None,
) -> Any:
    """Async gateway call for Azure AI Inference."""
    import httpx

    gateway_url = gw_settings.url
    gateway_api_key = gw_settings.api_key

    model_name = gw_settings.gateway_model or model
    request_body: Dict[str, Any] = {
        "model": model_name,
        "messages": _messages_to_dicts(messages),
    }

    for param in ["temperature", "max_tokens", "top_p", "stop", "tools",
                  "tool_choice", "response_format", "seed",
                  "frequency_penalty", "presence_penalty"]:
        val = kwargs.get(param)
        if val is not None:
            request_body[param] = val

    try:
        full_url = gateway_url.rstrip("/")
        deployment_name = gw_settings.gateway_model or model
        if "chat/completions" not in full_url:
            full_url = f"{full_url}/openai/deployments/{deployment_name}/chat/completions"
            if azure_api_version:
                full_url = f"{full_url}?api-version={azure_api_version}"

        auth_headers = {
            "api-key": gateway_api_key or "",
            "Content-Type": "application/json",
        }

        logger.debug(f"[GATEWAY] Sending async request to azure_ai_inference gateway: {full_url}")

        async with httpx.AsyncClient(timeout=float(gw_settings.timeout)) as client:
            response = await client.post(full_url, json=request_body, headers=auth_headers)
            if response.status_code >= 400:
                logger.error(f"[GATEWAY] azure gateway returned {response.status_code}: {response.text[:500]}")
            response.raise_for_status()
            response_data = response.json()

        logger.debug("[GATEWAY] Received async response from azure gateway")
        set_inspection_context(decision=Decision.allow(reasons=["Gateway handled inspection"]), done=True)
        return _dict_to_azure_response(response_data)

    except SecurityPolicyError:
        raise
    except Exception as e:
        logger.error(f"[GATEWAY] Async HTTP error: {e}")
        if gw_settings.fail_open:
            logger.warning("[GATEWAY] fail_open=True, re-raising original HTTP error for caller to handle")
            set_inspection_context(decision=Decision.allow(reasons=["Gateway error, fail_open=True"]), done=True)
            raise
        raise SecurityPolicyError(
            Decision.block(reasons=["Gateway unavailable"]),
            f"Gateway HTTP error: {e}",
        )


# =========================================================================
# Helpers
# =========================================================================

def _messages_to_dicts(messages: Any) -> List[Dict[str, Any]]:
    """Convert Azure AI Inference messages to plain dicts for the gateway."""
    result: List[Dict[str, Any]] = []
    if not messages:
        return result
    for m in messages:
        if isinstance(m, dict):
            result.append(dict(m))
        elif hasattr(m, "as_dict"):
            result.append(m.as_dict())
        elif hasattr(m, "__dict__"):
            result.append(m.__dict__)
        else:
            result.append({"role": "user", "content": str(m)})
    return result


class _AzureResponseWrapper:
    """Wraps a gateway dict response to look like ``ChatCompletions``."""

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        return self._data.get(name)

    def __getitem__(self, key):
        return self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)

    @property
    def choices(self):
        raw_choices = self._data.get("choices", [])
        return [_ChoiceWrapper(c) for c in raw_choices]

    @property
    def id(self):
        return self._data.get("id", "")

    @property
    def model(self):
        return self._data.get("model", "")

    @property
    def usage(self):
        usage_data = self._data.get("usage")
        if usage_data:
            return _UsageWrapper(usage_data)
        return None


class _ChoiceWrapper:
    def __init__(self, data: Dict[str, Any]):
        self._data = data

    @property
    def finish_reason(self):
        return self._data.get("finish_reason", "stop")

    @property
    def index(self):
        return self._data.get("index", 0)

    @property
    def message(self):
        msg = self._data.get("message", {})
        return _MessageWrapper(msg)


class _MessageWrapper:
    def __init__(self, data: Dict[str, Any]):
        self._data = data

    @property
    def role(self):
        return self._data.get("role", "assistant")

    @property
    def content(self):
        return self._data.get("content")

    @property
    def tool_calls(self):
        return self._data.get("tool_calls")


class _UsageWrapper:
    def __init__(self, data: Dict[str, Any]):
        self._data = data

    @property
    def prompt_tokens(self):
        return self._data.get("prompt_tokens", 0)

    @property
    def completion_tokens(self):
        return self._data.get("completion_tokens", 0)

    @property
    def total_tokens(self):
        return self._data.get("total_tokens", 0)


def _dict_to_azure_response(data: Dict[str, Any]) -> Any:
    """Convert a gateway dict response to an Azure-AI-Inference-like object.

    Tries to build a real ``ChatCompletions`` first; falls back to a wrapper.
    """
    try:
        from azure.ai.inference.models import ChatCompletions
        return ChatCompletions(data)
    except Exception:
        pass
    return _AzureResponseWrapper(data)


# =========================================================================
# Streaming wrappers
# =========================================================================

class _StreamingInspectionWrapper:
    """Wraps a streaming response for inspection."""

    def __init__(self, stream: Iterator, messages: List[Dict[str, Any]], metadata: Dict[str, Any]):
        self._stream = stream
        self._messages = messages
        self._metadata = metadata
        self._buffer = ""
        self._inspector = _get_inspector()
        self._chunk_count = 0
        self._inspect_interval = 10
        self._final_inspection_done = False

    def __iter__(self):
        return self

    def __next__(self):
        try:
            chunk = next(self._stream)
        except StopIteration:
            self._perform_final_inspection()
            raise
        except Exception:
            self._perform_final_inspection()
            raise

        try:
            choices = getattr(chunk, "choices", None)
            if choices:
                delta = getattr(choices[0], "delta", None)
                if delta:
                    content = getattr(delta, "content", None)
                    if content and len(self._buffer) < MAX_STREAMING_BUFFER_SIZE:
                        remaining = MAX_STREAMING_BUFFER_SIZE - len(self._buffer)
                        self._buffer += content[:remaining]
                    self._chunk_count += 1
                    if self._chunk_count % self._inspect_interval == 0:
                        self._inspect_buffer()
        except Exception as e:
            logger.warning(f"Error processing streaming chunk: {e}")

        return chunk

    def _perform_final_inspection(self):
        if self._final_inspection_done:
            return
        self._final_inspection_done = True
        if self._buffer:
            self._inspect_buffer()
        set_inspection_context(done=True)

    def _inspect_buffer(self):
        if not self._buffer or not _should_inspect():
            return
        messages_with_response = self._messages + [
            {"role": "assistant", "content": self._buffer[:MAX_STREAMING_BUFFER_SIZE]}
        ]
        try:
            decision = self._inspector.inspect_conversation(messages_with_response, self._metadata)
            set_inspection_context(decision=decision)
            _enforce_decision(decision)
        except SecurityPolicyError:
            raise
        except Exception as e:
            _handle_patcher_error(e, "azure_ai_inference streaming inspection")


class _AsyncStreamingInspectionWrapper:
    """Async streaming inspection wrapper."""

    def __init__(self, stream: Any, messages: List[Dict[str, Any]], metadata: Dict[str, Any]):
        self._stream = stream
        self._messages = messages
        self._metadata = metadata
        self._buffer = ""
        self._inspector = _get_inspector()
        self._chunk_count = 0
        self._inspect_interval = 10
        self._final_inspection_done = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            chunk = await self._stream.__anext__()
        except StopAsyncIteration:
            await self._perform_final_inspection()
            raise
        except Exception:
            await self._perform_final_inspection()
            raise

        try:
            choices = getattr(chunk, "choices", None)
            if choices:
                delta = getattr(choices[0], "delta", None)
                if delta:
                    content = getattr(delta, "content", None)
                    if content and len(self._buffer) < MAX_STREAMING_BUFFER_SIZE:
                        remaining = MAX_STREAMING_BUFFER_SIZE - len(self._buffer)
                        self._buffer += content[:remaining]
                    self._chunk_count += 1
                    if self._chunk_count % self._inspect_interval == 0:
                        await self._inspect_buffer()
        except Exception as e:
            logger.warning(f"Error processing async streaming chunk: {e}")

        return chunk

    async def _perform_final_inspection(self):
        if self._final_inspection_done:
            return
        self._final_inspection_done = True
        if self._buffer:
            await self._inspect_buffer()
        set_inspection_context(done=True)

    async def _inspect_buffer(self):
        if not self._buffer or not _should_inspect():
            return
        messages_with_response = self._messages + [
            {"role": "assistant", "content": self._buffer[:MAX_STREAMING_BUFFER_SIZE]}
        ]
        try:
            decision = await self._inspector.ainspect_conversation(messages_with_response, self._metadata)
            set_inspection_context(decision=decision)
            _enforce_decision(decision)
        except SecurityPolicyError:
            raise
        except Exception as e:
            _handle_patcher_error(e, "azure_ai_inference async streaming inspection")


# =========================================================================
# Wrapper functions
# =========================================================================

def _wrap_complete(wrapped, instance, args, kwargs):
    """Wrapper for ``ChatCompletionsClient.complete()`` (sync)."""
    model = kwargs.get("model") or _extract_model_from_instance(instance)
    messages = kwargs.get("messages") or (kwargs.get("body") or {}).get("messages", [])
    stream = kwargs.get("stream", False)

    set_inspection_context(done=False)
    if not _should_inspect():
        logger.debug("[PATCHED CALL] azure_ai_inference.complete - inspection skipped (mode=off or already done)")
        return wrapped(*args, **kwargs)

    normalized = _normalize_messages(messages)
    metadata = get_inspection_context().metadata
    metadata["provider"] = "azure_openai"
    metadata["model"] = model
    metadata["source"] = "azure_ai_inference"

    mode = _state.get_llm_mode()
    integration_mode = _state.get_llm_integration_mode()
    logger.debug("╔══════════════════════════════════════════════════════════════")
    logger.debug(f"║ [PATCHED] LLM CALL: {model}")
    logger.debug(f"║ Operation: azure_ai_inference.complete | LLM Mode: {mode} | Integration: {integration_mode}")
    logger.debug("╚══════════════════════════════════════════════════════════════")

    gw_settings = resolve_gateway_settings("azure_openai")
    if gw_settings:
        logger.debug("[PATCHED CALL] Gateway mode (azure_openai) - routing to AI Defense Gateway")
        azure_api_version = _extract_api_version(instance)
        return _handle_gateway_call_sync(
            model=model, messages=messages, kwargs=kwargs,
            normalized=normalized, metadata=metadata,
            gw_settings=gw_settings, azure_api_version=azure_api_version,
        )

    # API mode: pre-call inspection
    try:
        logger.debug(f"[PATCHED CALL] azure_ai_inference.complete - Request inspection ({len(normalized)} messages)")
        inspector = _get_inspector()
        decision = inspector.inspect_conversation(normalized, metadata)
        logger.debug(f"[PATCHED CALL] azure_ai_inference.complete - Request decision: {decision.action}")
        set_inspection_context(decision=decision)
        _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as e:
        decision = _handle_patcher_error(e, "azure_ai_inference.complete pre-call")
        if decision:
            set_inspection_context(decision=decision)

    logger.debug("[PATCHED CALL] azure_ai_inference.complete - calling original method")
    response = wrapped(*args, **kwargs)

    # Handle streaming
    if stream:
        return _StreamingInspectionWrapper(response, normalized, metadata)

    # Post-call inspection
    assistant_content = _extract_assistant_content(response)
    if assistant_content and normalized:
        try:
            logger.debug(f"[PATCHED CALL] azure_ai_inference.complete - Response inspection ({len(assistant_content)} chars)")
            messages_with_response = normalized + [{"role": "assistant", "content": assistant_content}]
            inspector = _get_inspector()
            decision = inspector.inspect_conversation(messages_with_response, metadata)
            logger.debug(f"[PATCHED CALL] azure_ai_inference.complete - Response decision: {decision.action}")
            set_inspection_context(decision=decision, done=True)
            _enforce_decision(decision)
        except SecurityPolicyError:
            raise
        except Exception as e:
            decision = _handle_patcher_error(e, "azure_ai_inference.complete post-call")
            if decision:
                set_inspection_context(decision=decision, done=True)

    logger.debug("[PATCHED CALL] azure_ai_inference.complete - complete")
    return response


async def _wrap_complete_async(wrapped, instance, args, kwargs):
    """Wrapper for ``ChatCompletionsClient.complete()`` (async)."""
    model = kwargs.get("model") or _extract_model_from_instance(instance)
    messages = kwargs.get("messages") or (kwargs.get("body") or {}).get("messages", [])
    stream = kwargs.get("stream", False)

    set_inspection_context(done=False)
    if not _should_inspect():
        logger.debug("[PATCHED CALL] azure_ai_inference.async.complete - inspection skipped")
        return await wrapped(*args, **kwargs)

    normalized = _normalize_messages(messages)
    metadata = get_inspection_context().metadata
    metadata["provider"] = "azure_openai"
    metadata["model"] = model
    metadata["source"] = "azure_ai_inference"

    mode = _state.get_llm_mode()
    integration_mode = _state.get_llm_integration_mode()
    logger.debug("╔══════════════════════════════════════════════════════════════")
    logger.debug(f"║ [PATCHED] LLM CALL (async): {model}")
    logger.debug(f"║ Operation: azure_ai_inference.async.complete | LLM Mode: {mode} | Integration: {integration_mode}")
    logger.debug("╚══════════════════════════════════════════════════════════════")

    gw_settings = resolve_gateway_settings("azure_openai")
    if gw_settings:
        logger.debug("[PATCHED CALL] Gateway mode (azure_openai) - routing to AI Defense Gateway")
        azure_api_version = _extract_api_version(instance)
        return await _handle_gateway_call_async(
            model=model, messages=messages, kwargs=kwargs,
            normalized=normalized, metadata=metadata,
            gw_settings=gw_settings, azure_api_version=azure_api_version,
        )

    # API mode: pre-call inspection
    try:
        logger.debug(f"[PATCHED CALL] azure_ai_inference.async.complete - Request inspection ({len(normalized)} messages)")
        inspector = _get_inspector()
        decision = await inspector.ainspect_conversation(normalized, metadata)
        logger.debug(f"[PATCHED CALL] azure_ai_inference.async.complete - Request decision: {decision.action}")
        set_inspection_context(decision=decision)
        _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as e:
        decision = _handle_patcher_error(e, "azure_ai_inference.async.complete pre-call")
        if decision:
            set_inspection_context(decision=decision)

    logger.debug("[PATCHED CALL] azure_ai_inference.async.complete - calling original method")
    response = await wrapped(*args, **kwargs)

    # Handle streaming
    if stream:
        return _AsyncStreamingInspectionWrapper(response, normalized, metadata)

    # Post-call inspection
    assistant_content = _extract_assistant_content(response)
    if assistant_content and normalized:
        try:
            logger.debug(f"[PATCHED CALL] azure_ai_inference.async.complete - Response inspection ({len(assistant_content)} chars)")
            messages_with_response = normalized + [{"role": "assistant", "content": assistant_content}]
            inspector = _get_inspector()
            decision = await inspector.ainspect_conversation(messages_with_response, metadata)
            logger.debug(f"[PATCHED CALL] azure_ai_inference.async.complete - Response decision: {decision.action}")
            set_inspection_context(decision=decision, done=True)
            _enforce_decision(decision)
        except SecurityPolicyError:
            raise
        except Exception as e:
            decision = _handle_patcher_error(e, "azure_ai_inference.async.complete post-call")
            if decision:
                set_inspection_context(decision=decision, done=True)

    logger.debug("[PATCHED CALL] azure_ai_inference.async.complete - complete")
    return response


# =========================================================================
# Patch entry point
# =========================================================================

def patch_azure_ai_inference() -> bool:
    """Patch Azure AI Inference SDK for automatic inspection.

    Patches ``ChatCompletionsClient.complete()`` (sync and async) to
    intercept all LLM calls made through the Azure AI Inference SDK.

    Returns:
        True if patching was successful, False otherwise
    """
    if is_patched("azure_ai_inference"):
        logger.debug("Azure AI Inference already patched, skipping")
        return True

    mod = safe_import("azure.ai.inference")
    if mod is None:
        return False

    patched_any = False

    try:
        wrapt.wrap_function_wrapper(
            "azure.ai.inference",
            "ChatCompletionsClient.complete",
            _wrap_complete,
        )
        logger.debug("Patched azure.ai.inference.ChatCompletionsClient.complete")
        patched_any = True
    except Exception as e:
        logger.debug(f"Could not patch sync ChatCompletionsClient.complete: {e}")

    try:
        wrapt.wrap_function_wrapper(
            "azure.ai.inference.aio",
            "ChatCompletionsClient.complete",
            _wrap_complete_async,
        )
        logger.debug("Patched azure.ai.inference.aio.ChatCompletionsClient.complete (async)")
        patched_any = True
    except Exception as e:
        logger.debug(f"Could not patch async ChatCompletionsClient.complete: {e}")

    if patched_any:
        mark_patched("azure_ai_inference")
        logger.info("Azure AI Inference patched successfully")
        return True

    logger.warning("Failed to patch Azure AI Inference")
    return False
