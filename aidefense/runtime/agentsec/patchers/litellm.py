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
LiteLLM autopatching.

This module provides automatic inspection for LiteLLM calls by patching
litellm.completion() and litellm.acompletion().

LiteLLM is an abstraction layer used by CrewAI (and others) that supports
multiple LLM providers. For some providers (notably Vertex AI), LiteLLM
makes direct HTTP calls bypassing the provider-specific SDK, so our
provider-specific patchers (vertexai, google_genai) cannot intercept them.

This patcher catches those calls at the LiteLLM level. It checks
whether a provider-specific patcher has already handled the call
(via the inspection context) and only inspects if needed.

Supports both API mode (inspection via AI Defense API) and Gateway mode
(routing through AI Defense Gateway).
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

logger = logging.getLogger("aidefense.runtime.agentsec.patchers.litellm")

# Global inspector instance with thread-safe initialization
_inspector: Optional[LLMInspector] = None
_inspector_lock = threading.Lock()


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


# Maximum buffer size for streaming inspection (1MB)
MAX_STREAMING_BUFFER_SIZE = 1_000_000


class _LiteLLMStreamingInspectionWrapper:
    """Wraps a LiteLLM streaming response for incremental + final inspection.

    LiteLLM streaming chunks use OpenAI-compatible format:
    ``chunk.choices[0].delta.content``
    """

    def __init__(
        self,
        stream: Iterator,
        messages: List[Dict[str, Any]],
        metadata: Dict[str, Any],
    ):
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
        except Exception as e:
            logger.warning("LiteLLM stream error, performing final inspection: %s", e)
            self._perform_final_inspection()
            raise

        try:
            if hasattr(chunk, "choices") and chunk.choices:
                delta = chunk.choices[0].delta
                content = getattr(delta, "content", None)
                if content:
                    if len(self._buffer) < MAX_STREAMING_BUFFER_SIZE:
                        remaining = MAX_STREAMING_BUFFER_SIZE - len(self._buffer)
                        self._buffer += content[:remaining]
                    self._chunk_count += 1
                    if self._chunk_count % self._inspect_interval == 0:
                        self._inspect_buffer()
        except Exception as e:
            logger.warning("Error processing LiteLLM streaming chunk: %s", e)

        return chunk

    def _perform_final_inspection(self) -> None:
        if self._final_inspection_done:
            return
        self._final_inspection_done = True
        if self._buffer:
            self._inspect_buffer()
        set_inspection_context(done=True)

    def _inspect_buffer(self) -> None:
        if not self._buffer or not _should_inspect():
            return

        buffer_to_inspect = self._buffer[:MAX_STREAMING_BUFFER_SIZE]
        messages_with_response = self._messages + [
            {"role": "assistant", "content": buffer_to_inspect}
        ]
        try:
            decision = self._inspector.inspect_conversation(
                messages_with_response, self._metadata,
            )
            set_inspection_context(decision=decision)
            _enforce_decision(decision)
        except SecurityPolicyError:
            raise
        except Exception as e:
            _handle_patcher_error(e, "LiteLLM streaming inspection")


class _AsyncLiteLLMStreamingInspectionWrapper:
    """Async wrapper for LiteLLM streaming responses."""

    def __init__(
        self,
        stream: Any,
        messages: List[Dict[str, Any]],
        metadata: Dict[str, Any],
    ):
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
        except Exception as e:
            logger.warning("LiteLLM async stream error, performing final inspection: %s", e)
            await self._perform_final_inspection()
            raise

        try:
            if hasattr(chunk, "choices") and chunk.choices:
                delta = chunk.choices[0].delta
                content = getattr(delta, "content", None)
                if content:
                    if len(self._buffer) < MAX_STREAMING_BUFFER_SIZE:
                        remaining = MAX_STREAMING_BUFFER_SIZE - len(self._buffer)
                        self._buffer += content[:remaining]
                    self._chunk_count += 1
                    if self._chunk_count % self._inspect_interval == 0:
                        await self._inspect_buffer()
        except Exception as e:
            logger.warning("Error processing LiteLLM async streaming chunk: %s", e)

        return chunk

    async def _perform_final_inspection(self) -> None:
        if self._final_inspection_done:
            return
        self._final_inspection_done = True
        if self._buffer:
            await self._inspect_buffer()
        set_inspection_context(done=True)

    async def _inspect_buffer(self) -> None:
        if not self._buffer or not _should_inspect():
            return

        buffer_to_inspect = self._buffer[:MAX_STREAMING_BUFFER_SIZE]
        messages_with_response = self._messages + [
            {"role": "assistant", "content": buffer_to_inspect}
        ]
        try:
            decision = await self._inspector.ainspect_conversation(
                messages_with_response, self._metadata,
            )
            set_inspection_context(decision=decision)
            _enforce_decision(decision)
        except SecurityPolicyError:
            raise
        except Exception as e:
            _handle_patcher_error(e, "LiteLLM async streaming inspection")


def _handle_patcher_error(error: Exception, operation: str) -> Optional[Decision]:
    """Handle errors in patcher inspection calls."""
    fail_open = _state.get_api_llm_fail_open()
    error_type = type(error).__name__
    logger.warning(f"[{operation}] Inspection error: {error_type}: {error}")

    if fail_open:
        logger.warning("llm_fail_open=True, allowing request despite inspection error")
        return Decision.allow(reasons=[f"Inspection error ({error_type}), llm_fail_open=True"])
    else:
        logger.error("fail_open=False, blocking request due to inspection error")
        decision = Decision.block(reasons=[f"Inspection error: {error_type}: {error}"])
        raise SecurityPolicyError(decision, f"Inspection failed and fail_open=False: {error}")


def _detect_provider(model: str) -> str:
    """Detect the LLM provider from the LiteLLM model string.
    
    LiteLLM uses prefixed model names like:
    - vertex_ai/gemini-2.5-flash-lite
    - azure/gpt-4
    - bedrock/anthropic.claude-3-haiku
    - gpt-4 (OpenAI, no prefix)
    """
    if not model:
        return "unknown"
    model_lower = model.lower()
    if model_lower.startswith("vertex_ai/") or model_lower.startswith("vertex_ai_beta/"):
        return "vertexai"
    if model_lower.startswith("azure/"):
        return "azure_openai"
    if model_lower.startswith("bedrock/") or model_lower.startswith("anthropic."):
        return "bedrock"
    if model_lower.startswith("gemini/") or model_lower.startswith("google/"):
        return "google_genai"
    # Default: OpenAI (no prefix)
    return "openai"


def _extract_response_text(response: Any) -> str:
    """Extract text content from a LiteLLM ModelResponse.
    
    LiteLLM returns a ModelResponse object with OpenAI-compatible structure:
        response.choices[0].message.content
    """
    try:
        if hasattr(response, 'choices') and response.choices:
            choice = response.choices[0]
            if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                return choice.message.content or ""
        # Try dict access
        if isinstance(response, dict):
            choices = response.get('choices', [])
            if choices:
                return choices[0].get('message', {}).get('content', '')
    except (IndexError, AttributeError, TypeError) as e:
        logger.debug(f"Error extracting response text: {e}")
    return ""


def _openai_messages_to_vertexai(messages: List[Dict]) -> tuple:
    """Convert OpenAI-format messages to Vertex AI contents format.

    Returns:
        (contents_list, system_instruction) where system_instruction may be None.
    """
    contents: List[Dict] = []
    system_instruction = None

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if role == "system":
            system_instruction = content
            continue

        # Map OpenAI roles → Vertex AI roles
        vertex_role = "model" if role == "assistant" else "user"

        # Handle tool_calls in assistant messages
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            parts = []
            if content:
                parts.append({"text": content})
            for tc in tool_calls:
                fn = tc.get("function", {})
                import json as _json
                args_val = fn.get("arguments", "{}")
                if isinstance(args_val, str):
                    try:
                        args_val = _json.loads(args_val)
                    except (ValueError, TypeError):
                        args_val = {}
                parts.append({
                    "functionCall": {
                        "name": fn.get("name", ""),
                        "args": args_val,
                    }
                })
            contents.append({"role": vertex_role, "parts": parts})
            continue

        # Handle tool response messages
        if role == "tool":
            tool_name = msg.get("name", msg.get("tool_call_id", "unknown"))
            import json as _json
            try:
                resp_val = _json.loads(content) if isinstance(content, str) else content
            except (ValueError, TypeError):
                resp_val = {"result": content}
            contents.append({
                "role": "user",
                "parts": [{
                    "functionResponse": {
                        "name": tool_name,
                        "response": resp_val if isinstance(resp_val, dict) else {"result": resp_val},
                    }
                }],
            })
            continue

        # Standard text message
        if content:
            contents.append({
                "role": vertex_role,
                "parts": [{"text": str(content)}],
            })

    return contents, system_instruction


def _vertexai_response_to_litellm(response_data: Dict, model: str):
    """Convert Vertex AI JSON response to a litellm-compatible ModelResponse.

    Uses ``litellm.ModelResponse`` when available, falls back to a plain dict.
    """
    # Extract text from candidates
    text = ""
    tool_calls_list = []
    finish_reason = "stop"

    candidates = response_data.get("candidates", [])
    if candidates:
        candidate = candidates[0]
        finish_reason = (candidate.get("finishReason") or "STOP").lower()
        if finish_reason == "stop":
            finish_reason = "stop"
        content = candidate.get("content", {})
        parts = content.get("parts", [])
        for part in parts:
            if "text" in part:
                text += part["text"]
            elif "functionCall" in part:
                fc = part["functionCall"]
                import json as _json
                tool_calls_list.append({
                    "id": f"call_{fc.get('name', 'unknown')}",
                    "type": "function",
                    "function": {
                        "name": fc.get("name", ""),
                        "arguments": _json.dumps(fc.get("args", {})),
                    },
                })

    # Build usage info
    usage_data = response_data.get("usageMetadata", {})

    try:
        import litellm
        from litellm.types.utils import ModelResponse, Choices, Message, Usage

        message_kwargs = {"content": text or None, "role": "assistant"}
        if tool_calls_list:
            from litellm.types.utils import Function, ChatCompletionMessageToolCall
            tc_objects = []
            for tc in tool_calls_list:
                fn = tc["function"]
                tc_objects.append(
                    ChatCompletionMessageToolCall(
                        id=tc["id"],
                        type="function",
                        function=Function(name=fn["name"], arguments=fn["arguments"]),
                    )
                )
            message_kwargs["tool_calls"] = tc_objects

        resp = ModelResponse(
            id=response_data.get("responseId", "chatcmpl-gateway"),
            choices=[Choices(
                index=0,
                message=Message(**message_kwargs),
                finish_reason=finish_reason,
            )],
            model=model,
            usage=Usage(
                prompt_tokens=usage_data.get("promptTokenCount", 0),
                completion_tokens=usage_data.get("candidatesTokenCount", 0),
                total_tokens=usage_data.get("totalTokenCount", 0),
            ),
        )
        return resp
    except Exception as e:
        logger.debug(f"Failed to construct litellm ModelResponse, using dict fallback: {e}")
        # Fallback: construct a dict that litellm can work with
        return {
            "id": response_data.get("responseId", "chatcmpl-gateway"),
            "object": "chat.completion",
            "model": model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": text or None,
                    "tool_calls": tool_calls_list or None,
                },
                "finish_reason": finish_reason,
            }],
            "usage": {
                "prompt_tokens": usage_data.get("promptTokenCount", 0),
                "completion_tokens": usage_data.get("candidatesTokenCount", 0),
                "total_tokens": usage_data.get("totalTokenCount", 0),
            },
        }


def _litellm_vertexai_gateway_call(model, messages, kwargs, gw_settings):
    """Make a direct Vertex AI gateway call for litellm.completion().

    Converts OpenAI-format messages to Vertex AI format, sends via httpx,
    and converts the response back to a litellm ModelResponse.
    """
    import httpx

    # Build auth headers
    if gw_settings.auth_mode == "google_adc":
        from ._google_common import _build_google_auth_header
        auth_headers = _build_google_auth_header(gw_settings)
    else:
        if not gw_settings.api_key:
            raise SecurityPolicyError(
                Decision.block(reasons=["gateway api_key not configured"]),
                "Gateway api_key not configured for Vertex AI litellm call",
            )
        auth_headers = {"Authorization": f"Bearer {gw_settings.api_key}"}

    # Convert messages
    contents, system_instruction = _openai_messages_to_vertexai(messages)

    # Build request body
    request_body: Dict[str, Any] = {"contents": contents}
    if system_instruction:
        request_body["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    # Extract generation config from kwargs
    gen_config: Dict[str, Any] = {}
    if kwargs.get("temperature") is not None:
        gen_config["temperature"] = kwargs["temperature"]
    if kwargs.get("max_tokens") is not None:
        gen_config["maxOutputTokens"] = kwargs["max_tokens"]
    if kwargs.get("top_p") is not None:
        gen_config["topP"] = kwargs["top_p"]
    if gen_config:
        request_body["generationConfig"] = gen_config

    # Extract tools from kwargs (litellm OpenAI format → Vertex AI format)
    tools = kwargs.get("tools")
    if tools:
        vertex_tools = _convert_openai_tools_to_vertexai(tools)
        if vertex_tools:
            request_body["tools"] = vertex_tools

    # Build full gateway URL
    from ._google_common import build_vertexai_gateway_url
    full_url = build_vertexai_gateway_url(
        gw_settings.url, model, gw_settings, streaming=False,
    )

    logger.debug(f"[GATEWAY] litellm Vertex AI direct call to: {full_url}")

    with httpx.Client(timeout=float(gw_settings.timeout)) as client:
        response = client.post(
            full_url,
            json=request_body,
            headers={**auth_headers, "Content-Type": "application/json"},
        )
        response.raise_for_status()
        response_data = response.json()

    logger.debug(f"[GATEWAY] litellm Vertex AI response received")
    return _vertexai_response_to_litellm(response_data, model)


async def _litellm_vertexai_gateway_call_async(model, messages, kwargs, gw_settings):
    """Async version of _litellm_vertexai_gateway_call."""
    import httpx

    # Build auth headers
    if gw_settings.auth_mode == "google_adc":
        from ._google_common import _build_google_auth_header
        auth_headers = _build_google_auth_header(gw_settings)
    else:
        if not gw_settings.api_key:
            raise SecurityPolicyError(
                Decision.block(reasons=["gateway api_key not configured"]),
                "Gateway api_key not configured for Vertex AI litellm call",
            )
        auth_headers = {"Authorization": f"Bearer {gw_settings.api_key}"}

    # Convert messages
    contents, system_instruction = _openai_messages_to_vertexai(messages)

    # Build request body
    request_body: Dict[str, Any] = {"contents": contents}
    if system_instruction:
        request_body["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    gen_config: Dict[str, Any] = {}
    if kwargs.get("temperature") is not None:
        gen_config["temperature"] = kwargs["temperature"]
    if kwargs.get("max_tokens") is not None:
        gen_config["maxOutputTokens"] = kwargs["max_tokens"]
    if kwargs.get("top_p") is not None:
        gen_config["topP"] = kwargs["top_p"]
    if gen_config:
        request_body["generationConfig"] = gen_config

    tools = kwargs.get("tools")
    if tools:
        vertex_tools = _convert_openai_tools_to_vertexai(tools)
        if vertex_tools:
            request_body["tools"] = vertex_tools

    from ._google_common import build_vertexai_gateway_url
    full_url = build_vertexai_gateway_url(
        gw_settings.url, model, gw_settings, streaming=False,
    )

    logger.debug(f"[GATEWAY] litellm Vertex AI async direct call to: {full_url}")

    async with httpx.AsyncClient(timeout=float(gw_settings.timeout)) as client:
        response = await client.post(
            full_url,
            json=request_body,
            headers={**auth_headers, "Content-Type": "application/json"},
        )
        response.raise_for_status()
        response_data = response.json()

    logger.debug(f"[GATEWAY] litellm Vertex AI async response received")
    return _vertexai_response_to_litellm(response_data, model)


def _convert_openai_tools_to_vertexai(tools: List[Dict]) -> List[Dict]:
    """Convert OpenAI-format tools to Vertex AI format.

    OpenAI: [{"type": "function", "function": {"name": ..., "parameters": ...}}]
    Vertex AI: [{"functionDeclarations": [{"name": ..., "parameters": ...}]}]
    """
    declarations = []
    for tool in tools:
        if isinstance(tool, dict) and tool.get("type") == "function":
            fn = tool.get("function", {})
            decl: Dict[str, Any] = {"name": fn.get("name", "")}
            if fn.get("description"):
                decl["description"] = fn["description"]
            if fn.get("parameters"):
                decl["parameters"] = fn["parameters"]
            declarations.append(decl)
    if declarations:
        return [{"functionDeclarations": declarations}]
    return []


def _wrap_completion(wrapped, instance, args, kwargs):
    """Wrapper for litellm.completion().
    
    Intercepts LiteLLM completion calls for AI Defense inspection.
    Checks if a provider-specific patcher already handled the call.
    """
    model = kwargs.get("model") or (args[0] if args else "unknown")
    messages = kwargs.get("messages") or (args[1] if len(args) > 1 else [])
    
    set_inspection_context(done=False)
    if not _should_inspect():
        logger.debug(f"[PATCHED CALL] litellm.completion - inspection skipped (mode=off or already done)")
        return wrapped(*args, **kwargs)
    
    provider = _detect_provider(model)
    
    # Normalize messages (LiteLLM uses OpenAI format already)
    normalized = []
    if isinstance(messages, list):
        for msg in messages:
            if isinstance(msg, dict):
                normalized.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                })
    
    metadata = get_inspection_context().metadata
    metadata["provider"] = provider
    metadata["model"] = model
    metadata["source"] = "litellm"
    
    mode = _state.get_llm_mode()
    integration_mode = _state.get_llm_integration_mode()
    logger.debug(f"╔══════════════════════════════════════════════════════════════")
    logger.debug(f"║ [PATCHED] LLM CALL: {model}")
    logger.debug(f"║ Operation: litellm.completion | Provider: {provider} | LLM Mode: {mode} | Integration: {integration_mode}")
    logger.debug(f"╚══════════════════════════════════════════════════════════════")
    
    # Gateway mode: attempt to redirect via gateway
    gw_settings = resolve_gateway_settings(provider)
    if gw_settings:
        logger.debug(f"[PATCHED CALL] litellm.completion - Gateway mode for {provider}")
        
        # For Vertex AI: litellm uses its own URL construction which doesn't
        # match the gateway's expected format.  Make a direct HTTP call
        # in native Vertex AI format instead.
        if provider == "vertexai":
            logger.debug(f"[PATCHED CALL] litellm.completion - direct Vertex AI gateway call")
            try:
                response = _litellm_vertexai_gateway_call(model, messages, kwargs, gw_settings)
                set_inspection_context(
                    decision=Decision.allow(reasons=["Gateway handled inspection"]),
                    done=True,
                )
                return response
            except SecurityPolicyError:
                raise
            except Exception as e:
                logger.error(f"[GATEWAY] litellm.completion Vertex AI error: {e}")
                if gw_settings.fail_open:
                    logger.warning(f"[GATEWAY] fail_open=True, re-raising for caller to handle")
                    set_inspection_context(
                        decision=Decision.allow(reasons=["Gateway error, fail_open=True"]),
                        done=True,
                    )
                    raise
                raise SecurityPolicyError(
                    Decision.block(reasons=["Gateway error"]),
                    f"LiteLLM gateway error: {e}",
                )
        
        # For other providers: redirect via api_base
        kwargs["api_base"] = gw_settings.url
        kwargs["api_key"] = gw_settings.api_key
        logger.debug(f"[PATCHED CALL] litellm.completion - Redirecting to gateway: {gw_settings.url}")
        
        try:
            response = wrapped(*args, **kwargs)
            set_inspection_context(
                decision=Decision.allow(reasons=["Gateway handled inspection"]),
                done=True,
            )
            return response
        except Exception as e:
            logger.error(f"[GATEWAY] litellm.completion error: {e}")
            if gw_settings.fail_open:
                logger.warning(f"[GATEWAY] fail_open=True, re-raising for caller to handle")
                set_inspection_context(
                    decision=Decision.allow(reasons=["Gateway error, fail_open=True"]),
                    done=True,
                )
                raise
            raise SecurityPolicyError(
                Decision.block(reasons=["Gateway error"]),
                f"LiteLLM gateway error: {e}",
            )
    
    stream = kwargs.get("stream", False)

    # API mode: use LLMInspector for inspection
    # Pre-call inspection
    if normalized:
        logger.debug(f"[PATCHED CALL] litellm.completion - Request inspection ({len(normalized)} messages)")
        inspector = _get_inspector()
        decision = inspector.inspect_conversation(normalized, metadata)
        logger.debug(f"[PATCHED CALL] litellm.completion - Request decision: {decision.action}")
        set_inspection_context(decision=decision)
        _enforce_decision(decision)
    
    # Call the original
    logger.debug(f"[PATCHED CALL] litellm.completion - calling original method (stream={stream})")
    response = wrapped(*args, **kwargs)
    
    # Streaming: wrap the response iterator for incremental inspection
    if stream and normalized:
        logger.debug("[PATCHED CALL] litellm.completion - wrapping streaming response for inspection")
        return _LiteLLMStreamingInspectionWrapper(response, normalized, metadata)

    # Non-streaming: post-call inspection
    assistant_content = _extract_response_text(response)
    if assistant_content and normalized:
        logger.debug(f"[PATCHED CALL] litellm.completion - Response inspection (response: {len(assistant_content)} chars)")
        messages_with_response = normalized + [
            {"role": "assistant", "content": assistant_content}
        ]
        inspector = _get_inspector()
        decision = inspector.inspect_conversation(messages_with_response, metadata)
        logger.debug(f"[PATCHED CALL] litellm.completion - Response decision: {decision.action}")
        set_inspection_context(decision=decision, done=True)
        _enforce_decision(decision)
    
    logger.debug(f"[PATCHED CALL] litellm.completion - complete")
    return response


async def _wrap_acompletion(wrapped, instance, args, kwargs):
    """Async wrapper for litellm.acompletion()."""
    model = kwargs.get("model") or (args[0] if args else "unknown")
    messages = kwargs.get("messages") or (args[1] if len(args) > 1 else [])
    
    set_inspection_context(done=False)
    if not _should_inspect():
        logger.debug(f"[PATCHED CALL] litellm.acompletion - inspection skipped")
        return await wrapped(*args, **kwargs)
    
    provider = _detect_provider(model)
    
    # Normalize messages
    normalized = []
    if isinstance(messages, list):
        for msg in messages:
            if isinstance(msg, dict):
                normalized.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                })
    
    metadata = get_inspection_context().metadata
    metadata["provider"] = provider
    metadata["model"] = model
    metadata["source"] = "litellm"
    
    mode = _state.get_llm_mode()
    integration_mode = _state.get_llm_integration_mode()
    logger.debug(f"╔══════════════════════════════════════════════════════════════")
    logger.debug(f"║ [PATCHED] LLM CALL (async): {model}")
    logger.debug(f"║ Operation: litellm.acompletion | Provider: {provider} | LLM Mode: {mode} | Integration: {integration_mode}")
    logger.debug(f"╚══════════════════════════════════════════════════════════════")
    
    # Gateway mode: attempt to redirect via gateway
    gw_settings = resolve_gateway_settings(provider)
    if gw_settings:
        logger.debug(f"[PATCHED CALL] litellm.acompletion - Gateway mode for {provider}")
        
        # For Vertex AI: direct HTTP call in native format
        if provider == "vertexai":
            logger.debug(f"[PATCHED CALL] litellm.acompletion - direct Vertex AI gateway call (async)")
            try:
                response = await _litellm_vertexai_gateway_call_async(model, messages, kwargs, gw_settings)
                set_inspection_context(
                    decision=Decision.allow(reasons=["Gateway handled inspection"]),
                    done=True,
                )
                return response
            except SecurityPolicyError:
                raise
            except Exception as e:
                logger.error(f"[GATEWAY] litellm.acompletion Vertex AI error: {e}")
                if gw_settings.fail_open:
                    logger.warning(f"[GATEWAY] fail_open=True, re-raising for caller to handle")
                    set_inspection_context(
                        decision=Decision.allow(reasons=["Gateway error, fail_open=True"]),
                        done=True,
                    )
                    raise
                raise SecurityPolicyError(
                    Decision.block(reasons=["Gateway error"]),
                    f"LiteLLM gateway error: {e}",
                )
        
        # For other providers: redirect via api_base
        kwargs["api_base"] = gw_settings.url
        kwargs["api_key"] = gw_settings.api_key
        logger.debug(f"[PATCHED CALL] litellm.acompletion - Redirecting to gateway: {gw_settings.url}")
        
        try:
            response = await wrapped(*args, **kwargs)
            set_inspection_context(
                decision=Decision.allow(reasons=["Gateway handled inspection"]),
                done=True,
            )
            return response
        except Exception as e:
            logger.error(f"[GATEWAY] litellm.acompletion error: {e}")
            if gw_settings.fail_open:
                logger.warning(f"[GATEWAY] fail_open=True, re-raising for caller to handle")
                set_inspection_context(
                    decision=Decision.allow(reasons=["Gateway error, fail_open=True"]),
                    done=True,
                )
                raise
            raise SecurityPolicyError(
                Decision.block(reasons=["Gateway error"]),
                f"LiteLLM gateway error: {e}",
            )
    
    stream = kwargs.get("stream", False)

    # API mode: Pre-call inspection
    if normalized:
        logger.debug(f"[PATCHED CALL] litellm.acompletion - Request inspection ({len(normalized)} messages)")
        inspector = _get_inspector()
        decision = await inspector.ainspect_conversation(normalized, metadata)
        logger.debug(f"[PATCHED CALL] litellm.acompletion - Request decision: {decision.action}")
        set_inspection_context(decision=decision)
        _enforce_decision(decision)
    
    # Call the original
    logger.debug(f"[PATCHED CALL] litellm.acompletion - calling original method (stream={stream})")
    response = await wrapped(*args, **kwargs)
    
    # Streaming: wrap the async response iterator for incremental inspection
    if stream and normalized:
        logger.debug("[PATCHED CALL] litellm.acompletion - wrapping async streaming response for inspection")
        return _AsyncLiteLLMStreamingInspectionWrapper(response, normalized, metadata)

    # Non-streaming: post-call inspection
    assistant_content = _extract_response_text(response)
    if assistant_content and normalized:
        logger.debug(f"[PATCHED CALL] litellm.acompletion - Response inspection")
        messages_with_response = normalized + [
            {"role": "assistant", "content": assistant_content}
        ]
        inspector = _get_inspector()
        decision = await inspector.ainspect_conversation(messages_with_response, metadata)
        logger.debug(f"[PATCHED CALL] litellm.acompletion - Response decision: {decision.action}")
        set_inspection_context(decision=decision, done=True)
        _enforce_decision(decision)
    
    logger.debug(f"[PATCHED CALL] litellm.acompletion - complete")
    return response


def patch_litellm() -> bool:
    """
    Patch LiteLLM for automatic inspection.
    
    Patches litellm.completion() and litellm.acompletion() to intercept
    all LLM calls made through LiteLLM (used by CrewAI and others).
    
    Returns:
        True if patching was successful, False otherwise
    """
    if is_patched("litellm"):
        logger.debug("LiteLLM already patched, skipping")
        return True
    
    litellm = safe_import("litellm")
    if litellm is None:
        return False
    
    try:
        # Patch litellm.completion
        wrapt.wrap_function_wrapper(
            "litellm",
            "completion",
            _wrap_completion,
        )
        logger.debug("Patched litellm.completion")
        
        # Patch litellm.acompletion
        try:
            wrapt.wrap_function_wrapper(
                "litellm",
                "acompletion",
                _wrap_acompletion,
            )
            logger.debug("Patched litellm.acompletion")
        except Exception as e:
            logger.debug(f"Could not patch litellm.acompletion: {e}")
        
        mark_patched("litellm")
        logger.info("LiteLLM patched successfully (completion, acompletion)")
        return True
    except Exception as e:
        logger.warning(f"Failed to patch LiteLLM: {e}")
        return False
