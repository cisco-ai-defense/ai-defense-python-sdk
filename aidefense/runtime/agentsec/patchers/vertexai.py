"""
Vertex AI client autopatching.

This module provides automatic inspection for vertexai SDK calls
by patching GenerativeModel.generate_content() and generate_content_async().

Gateway Mode Support:
When AGENTSEC_LLM_INTEGRATION_MODE=gateway, Vertex AI calls are sent directly
to the provider-specific AI Defense Gateway in native format.
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
from ._base import safe_import
from ._google_common import (
    normalize_google_messages,
    extract_google_response,
)

logger = logging.getLogger("aidefense.runtime.agentsec.patchers.vertexai")

# Global inspector instance with thread-safe initialization
_inspector: Optional[LLMInspector] = None
_inspector_lock = threading.Lock()


def _get_inspector() -> LLMInspector:
    """Get or create the LLMInspector instance (thread-safe)."""
    global _inspector
    if _inspector is None:
        with _inspector_lock:
            # Double-check pattern for thread safety
            if _inspector is None:
                if not _state.is_initialized():
                    logger.warning("agentsec.protect() not called, using default config")
                _inspector = LLMInspector(
                    fail_open=_state.get_api_mode_fail_open_llm(),
                    default_rules=_state.get_llm_rules(),
                )
    return _inspector


def _is_gateway_mode() -> bool:
    """Check if LLM integration mode is 'gateway'."""
    return _state.get_llm_integration_mode() == "gateway"


def _should_use_gateway() -> bool:
    """Check if we should use gateway mode (gateway mode enabled, configured, and not skipped)."""
    from .._context import is_llm_skip_active
    if is_llm_skip_active():
        return False
    if not _is_gateway_mode():
        return False
    gateway_url = _state.get_provider_gateway_url("vertexai")
    gateway_api_key = _state.get_provider_gateway_api_key("vertexai")
    return bool(gateway_url and gateway_api_key)


def _should_inspect() -> bool:
    """Check if we should inspect (not already done, mode is not off, and not skipped)."""
    from .._context import is_llm_skip_active
    if is_llm_skip_active():
        return False
    mode = _state.get_llm_mode()
    if mode == "off":
        return False
    ctx = get_inspection_context()
    return not ctx.done


def _enforce_decision(decision: Decision) -> None:
    """Enforce a decision if in enforce mode."""
    mode = _state.get_llm_mode()
    if mode == "on_enforce" and decision.action == "block":
        raise SecurityPolicyError(decision)


def _handle_vertexai_gateway_call(
    model_name: str,
    contents: Any,
    generation_config: Optional[Dict] = None,
    tools: Optional[List] = None,
    tool_config: Optional[Dict] = None,
    system_instruction: Optional[Any] = None,
) -> Any:
    """
    Handle Vertex AI call via AI Defense Gateway with native format.
    
    Sends native Vertex AI request directly to the provider-specific gateway.
    The gateway handles the request in native Vertex AI format - no conversion needed.
    
    Args:
        model_name: Vertex AI model name
        contents: Vertex AI contents
        generation_config: Optional generation config
        tools: Optional tools list
        tool_config: Optional tool config
        system_instruction: Optional system instruction
        
    Returns:
        Native Vertex AI response wrapped for attribute access
    """
    import httpx
    
    gateway_url = _state.get_provider_gateway_url("vertexai")
    gateway_api_key = _state.get_provider_gateway_api_key("vertexai")
    
    if not gateway_url or not gateway_api_key:
        logger.warning("Gateway mode enabled but Vertex AI gateway not configured")
        raise SecurityPolicyError(
            Decision.block(reasons=["Vertex AI gateway not configured"]),
            "Gateway mode enabled but AGENTSEC_VERTEXAI_GATEWAY_URL not set"
        )
    
    # Convert contents to dict format for the request
    contents_list = []
    if contents:
        if isinstance(contents, str):
            contents_list = [{"role": "user", "parts": [{"text": contents}]}]
        elif isinstance(contents, list):
            for item in contents:
                if isinstance(item, dict):
                    contents_list.append(item)
                elif hasattr(item, "role") and hasattr(item, "parts"):
                    parts_list = []
                    for part in item.parts:
                        if hasattr(part, "text"):
                            parts_list.append({"text": part.text})
                    contents_list.append({"role": item.role, "parts": parts_list})
    
    # Build native Vertex AI request
    request_body = {
        "model": model_name,
        "contents": contents_list,
    }
    
    if generation_config:
        if isinstance(generation_config, dict):
            request_body["generationConfig"] = generation_config
        else:
            config_dict = {}
            if hasattr(generation_config, "temperature"):
                config_dict["temperature"] = generation_config.temperature
            if hasattr(generation_config, "max_output_tokens"):
                config_dict["maxOutputTokens"] = generation_config.max_output_tokens
            if config_dict:
                request_body["generationConfig"] = config_dict
    
    if tools:
        request_body["tools"] = tools
    if tool_config:
        request_body["toolConfig"] = tool_config
    if system_instruction:
        if isinstance(system_instruction, str):
            request_body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        elif hasattr(system_instruction, "parts"):
            parts = [{"text": p.text} for p in system_instruction.parts if hasattr(p, "text")]
            request_body["systemInstruction"] = {"parts": parts}
    
    logger.debug(f"[GATEWAY] Sending native Vertex AI request to gateway")
    logger.debug(f"[GATEWAY] Model: {model_name}")
    
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                gateway_url,
                json=request_body,
                headers={
                    "Authorization": f"Bearer {gateway_api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            response_data = response.json()
        
        logger.debug(f"[GATEWAY] Received native Vertex AI response from gateway")
        set_inspection_context(decision=Decision.allow(reasons=["Gateway handled inspection"]), done=True)
        
        # Wrap response for attribute access
        return _VertexAIResponseWrapper(response_data)
        
    except httpx.HTTPStatusError as e:
        logger.error(f"[GATEWAY] HTTP error: {e}")
        if _state.get_gateway_mode_fail_open_llm():
            set_inspection_context(decision=Decision.allow(reasons=["Gateway error, fail_open=True"]), done=True)
            raise SecurityPolicyError(
                Decision.block(reasons=["Gateway unavailable"]),
                f"Gateway HTTP error: {e}"
            )
        raise
    except Exception as e:
        logger.error(f"[GATEWAY] Error: {e}")
        raise


class _VertexAIResponseWrapper:
    """Wrapper to provide attribute access to native Vertex AI response dict."""
    
    def __init__(self, response_data: Dict):
        self._data = response_data
        self._candidates = None
    
    @property
    def candidates(self):
        if self._candidates is None:
            self._candidates = [
                _CandidateWrapper(c) for c in self._data.get("candidates", [])
            ]
        return self._candidates
    
    @property
    def text(self):
        """Extract text from first candidate's first part."""
        try:
            return self.candidates[0].content.parts[0].text
        except (IndexError, AttributeError):
            return ""
    
    def to_dict(self):
        return self._data


class _CandidateWrapper:
    """Wrapper for candidate in Vertex AI response."""
    
    def __init__(self, candidate_data: Dict):
        self._data = candidate_data
        self._content = None
    
    @property
    def content(self):
        if self._content is None:
            self._content = _ContentWrapper(self._data.get("content", {}))
        return self._content
    
    @property
    def finish_reason(self):
        return self._data.get("finishReason")


class _ContentWrapper:
    """Wrapper for content in Vertex AI response."""
    
    def __init__(self, content_data: Dict):
        self._data = content_data
        self._parts = None
    
    @property
    def role(self):
        return self._data.get("role", "model")
    
    @property
    def parts(self):
        if self._parts is None:
            self._parts = [_PartWrapper(p) for p in self._data.get("parts", [])]
        return self._parts


class _PartWrapper:
    """Wrapper for part in Vertex AI response."""
    
    def __init__(self, part_data: Dict):
        self._data = part_data
    
    @property
    def text(self):
        return self._data.get("text", "")


class GoogleStreamingInspectionWrapper:
    """
    Wrapper for Google/Vertex AI streaming responses that performs inspection
    after collecting all chunks.
    
    For API mode streaming - collects response then inspects.
    """
    
    def __init__(self, original_iterator, normalized_messages: List[Dict], metadata: Dict):
        self._original = original_iterator
        self._normalized = normalized_messages
        self._metadata = metadata
        self._collected_text = []
        self._chunks = []
        self._inspection_done = False
    
    def __iter__(self):
        return self
    
    def __next__(self):
        try:
            chunk = next(self._original)
            self._chunks.append(chunk)
            
            # Extract text from chunk
            from ._google_common import extract_streaming_chunk_text
            text = extract_streaming_chunk_text(chunk)
            if text:
                self._collected_text.append(text)
            
            return chunk
        except StopIteration:
            # Perform inspection after stream completes
            if not self._inspection_done:
                self._perform_inspection()
            raise
    
    def _perform_inspection(self):
        """Perform post-response inspection."""
        self._inspection_done = True
        
        full_response = "".join(self._collected_text)
        if full_response and self._normalized:
            messages_with_response = self._normalized + [
                {"role": "assistant", "content": full_response}
            ]
            inspector = _get_inspector()
            decision = inspector.inspect_conversation(messages_with_response, self._metadata)
            set_inspection_context(decision=decision, done=True)
            _enforce_decision(decision)


class AsyncGoogleStreamingInspectionWrapper:
    """
    Async wrapper for Google/Vertex AI streaming responses that performs inspection
    after collecting all chunks.
    
    For API mode async streaming - collects response then inspects.
    """
    
    def __init__(self, original_iterator, normalized_messages: List[Dict], metadata: Dict):
        self._original = original_iterator
        self._normalized = normalized_messages
        self._metadata = metadata
        self._collected_text = []
        self._chunks = []
        self._inspection_done = False
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        try:
            chunk = await self._original.__anext__()
            self._chunks.append(chunk)
            
            # Extract text from chunk
            from ._google_common import extract_streaming_chunk_text
            text = extract_streaming_chunk_text(chunk)
            if text:
                self._collected_text.append(text)
            
            return chunk
        except StopAsyncIteration:
            # Perform inspection after stream completes
            if not self._inspection_done:
                await self._perform_inspection()
            raise
    
    async def _perform_inspection(self):
        """Perform post-response inspection."""
        self._inspection_done = True
        
        full_response = "".join(self._collected_text)
        if full_response and self._normalized:
            messages_with_response = self._normalized + [
                {"role": "assistant", "content": full_response}
            ]
            inspector = _get_inspector()
            decision = await inspector.ainspect_conversation(messages_with_response, self._metadata)
            set_inspection_context(decision=decision, done=True)
            _enforce_decision(decision)


async def _handle_vertexai_gateway_call_async(
    model_name: str,
    contents: Any,
    generation_config: Optional[Dict] = None,
    tools: Optional[List] = None,
    tool_config: Optional[Dict] = None,
    system_instruction: Optional[Any] = None,
) -> Any:
    """Async version of _handle_vertexai_gateway_call."""
    import httpx
    
    gateway_url = _state.get_provider_gateway_url("vertexai")
    gateway_api_key = _state.get_provider_gateway_api_key("vertexai")
    
    if not gateway_url or not gateway_api_key:
        logger.warning("Gateway mode enabled but Vertex AI gateway not configured")
        raise SecurityPolicyError(
            Decision.block(reasons=["Vertex AI gateway not configured"]),
            "Gateway mode enabled but AGENTSEC_VERTEXAI_GATEWAY_URL not set"
        )
    
    # Convert contents to dict format
    contents_list = []
    if contents:
        if isinstance(contents, str):
            contents_list = [{"role": "user", "parts": [{"text": contents}]}]
        elif isinstance(contents, list):
            for item in contents:
                if isinstance(item, dict):
                    contents_list.append(item)
                elif hasattr(item, "role") and hasattr(item, "parts"):
                    parts_list = []
                    for part in item.parts:
                        if hasattr(part, "text"):
                            parts_list.append({"text": part.text})
                    contents_list.append({"role": item.role, "parts": parts_list})
    
    # Build native Vertex AI request
    request_body = {
        "model": model_name,
        "contents": contents_list,
    }
    
    if generation_config:
        if isinstance(generation_config, dict):
            request_body["generationConfig"] = generation_config
        else:
            config_dict = {}
            if hasattr(generation_config, "temperature"):
                config_dict["temperature"] = generation_config.temperature
            if hasattr(generation_config, "max_output_tokens"):
                config_dict["maxOutputTokens"] = generation_config.max_output_tokens
            if config_dict:
                request_body["generationConfig"] = config_dict
    
    if tools:
        request_body["tools"] = tools
    if tool_config:
        request_body["toolConfig"] = tool_config
    if system_instruction:
        if isinstance(system_instruction, str):
            request_body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        elif hasattr(system_instruction, "parts"):
            parts = [{"text": p.text} for p in system_instruction.parts if hasattr(p, "text")]
            request_body["systemInstruction"] = {"parts": parts}
    
    logger.debug(f"[GATEWAY] Sending native Vertex AI request to gateway (async)")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                gateway_url,
                json=request_body,
                headers={
                    "Authorization": f"Bearer {gateway_api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            response_data = response.json()
        
        logger.debug(f"[GATEWAY] Received native Vertex AI response from gateway")
        set_inspection_context(decision=Decision.allow(reasons=["Gateway handled inspection"]), done=True)
        
        return _VertexAIResponseWrapper(response_data)
        
    except httpx.HTTPStatusError as e:
        logger.error(f"[GATEWAY] HTTP error: {e}")
        if _state.get_gateway_mode_fail_open_llm():
            set_inspection_context(decision=Decision.allow(reasons=["Gateway error, fail_open=True"]), done=True)
            raise SecurityPolicyError(
                Decision.block(reasons=["Gateway unavailable"]),
                f"Gateway HTTP error: {e}"
            )
        raise
    except Exception as e:
        logger.error(f"[GATEWAY] Error: {e}")
        raise


def _wrap_generate_content(wrapped, instance, args, kwargs):
    """Wrapper for GenerativeModel.generate_content().
    
    Supports both API mode (inspection via AI Defense API) and Gateway mode
    (routing through AI Defense Gateway with format conversion).
    """
    # Get model name
    model_name = "unknown"
    if hasattr(instance, "model_name"):
        model_name = instance.model_name
    elif hasattr(instance, "_model_name"):
        model_name = instance._model_name
    
    if not _should_inspect():
        logger.debug(f"[PATCHED CALL] VertexAI.generate_content - inspection skipped (mode=off or already done)")
        return wrapped(*args, **kwargs)
    
    # Extract contents from args/kwargs
    contents = args[0] if args else kwargs.get("contents")
    stream = kwargs.get("stream", False)
    
    # Normalize messages
    normalized = normalize_google_messages(contents)
    metadata = get_inspection_context().metadata
    metadata["provider"] = "vertexai"
    metadata["model"] = model_name
    
    mode = _state.get_llm_mode()
    integration_mode = _state.get_llm_integration_mode()
    logger.debug(f"")
    logger.debug(f"╔══════════════════════════════════════════════════════════════")
    logger.debug(f"║ [PATCHED] LLM CALL: {model_name}")
    logger.debug(f"║ Operation: VertexAI.generate_content | LLM Mode: {mode} | Integration: {integration_mode}")
    logger.debug(f"╚══════════════════════════════════════════════════════════════")
    
    # Gateway mode: route through AI Defense Gateway with format conversion
    if _should_use_gateway():
        logger.debug(f"[PATCHED CALL] VertexAI.generate_content - Gateway mode - routing to AI Defense Gateway")
        if not stream:  # Non-streaming only for now
            return _handle_vertexai_gateway_call(
                model_name=model_name,
                contents=contents,
                generation_config=kwargs.get("generation_config"),
                tools=kwargs.get("tools"),
                tool_config=kwargs.get("tool_config"),
                system_instruction=getattr(instance, "system_instruction", None),
            )
        else:
            logger.warning(f"[PATCHED CALL] Gateway mode streaming not yet supported for VertexAI, falling back to API mode")
    
    # API mode (default): use LLMInspector for inspection
    # Pre-call inspection
    if normalized:
        logger.debug(f"[PATCHED CALL] VertexAI.generate_content - Request inspection ({len(normalized)} messages)")
        inspector = _get_inspector()
        decision = inspector.inspect_conversation(normalized, metadata)
        logger.debug(f"[PATCHED CALL] VertexAI.generate_content - Request decision: {decision.action}")
        set_inspection_context(decision=decision)
        _enforce_decision(decision)
    
    # Call the original
    logger.debug(f"[PATCHED CALL] VertexAI.generate_content - calling original method")
    response = wrapped(*args, **kwargs)
    
    # Handle streaming vs non-streaming
    if stream:
        logger.debug(f"[PATCHED CALL] VertexAI.generate_content - streaming response, wrapping for inspection")
        return GoogleStreamingInspectionWrapper(response, normalized, metadata)
    
    # Post-call inspection for non-streaming
    assistant_content = extract_google_response(response)
    if assistant_content and normalized:
        logger.debug(f"[PATCHED CALL] VertexAI.generate_content - Response inspection (response: {len(assistant_content)} chars)")
        messages_with_response = normalized + [
            {"role": "assistant", "content": assistant_content}
        ]
        inspector = _get_inspector()
        decision = inspector.inspect_conversation(messages_with_response, metadata)
        logger.debug(f"[PATCHED CALL] VertexAI.generate_content - Response decision: {decision.action}")
        set_inspection_context(decision=decision, done=True)
        _enforce_decision(decision)
    
    logger.debug(f"[PATCHED CALL] VertexAI.generate_content - complete")
    return response


async def _wrap_generate_content_async(wrapped, instance, args, kwargs):
    """Async wrapper for GenerativeModel.generate_content_async().
    
    Supports both API mode (inspection via AI Defense API) and Gateway mode
    (routing through AI Defense Gateway with format conversion).
    """
    # Get model name
    model_name = "unknown"
    if hasattr(instance, "model_name"):
        model_name = instance.model_name
    elif hasattr(instance, "_model_name"):
        model_name = instance._model_name
    
    if not _should_inspect():
        logger.debug(f"[PATCHED CALL] VertexAI.async.generate_content - inspection skipped")
        return await wrapped(*args, **kwargs)
    
    # Extract contents from args/kwargs
    contents = args[0] if args else kwargs.get("contents")
    stream = kwargs.get("stream", False)
    
    # Normalize messages
    normalized = normalize_google_messages(contents)
    metadata = get_inspection_context().metadata
    metadata["provider"] = "vertexai"
    metadata["model"] = model_name
    
    mode = _state.get_llm_mode()
    integration_mode = _state.get_llm_integration_mode()
    logger.debug(f"")
    logger.debug(f"╔══════════════════════════════════════════════════════════════")
    logger.debug(f"║ [PATCHED] LLM CALL (async): {model_name}")
    logger.debug(f"║ Operation: VertexAI.async.generate_content | LLM Mode: {mode} | Integration: {integration_mode}")
    logger.debug(f"╚══════════════════════════════════════════════════════════════")
    
    # Gateway mode: route through AI Defense Gateway with format conversion
    if _should_use_gateway():
        logger.debug(f"[PATCHED CALL] VertexAI.async.generate_content - Gateway mode - routing to AI Defense Gateway")
        if not stream:  # Non-streaming only for now
            return await _handle_vertexai_gateway_call_async(
                model_name=model_name,
                contents=contents,
                generation_config=kwargs.get("generation_config"),
                tools=kwargs.get("tools"),
                tool_config=kwargs.get("tool_config"),
                system_instruction=getattr(instance, "system_instruction", None),
            )
        else:
            logger.warning(f"[PATCHED CALL] Gateway mode streaming not yet supported for VertexAI, falling back to API mode")
    
    # API mode (default): use LLMInspector for inspection
    # Pre-call inspection
    if normalized:
        logger.debug(f"[PATCHED CALL] VertexAI.async - Request inspection ({len(normalized)} messages)")
        inspector = _get_inspector()
        decision = await inspector.ainspect_conversation(normalized, metadata)
        logger.debug(f"[PATCHED CALL] VertexAI.async - Request decision: {decision.action}")
        set_inspection_context(decision=decision)
        _enforce_decision(decision)
    
    # Call the original
    logger.debug(f"[PATCHED CALL] VertexAI.async - calling original method")
    response = await wrapped(*args, **kwargs)
    
    # Handle streaming
    if stream:
        logger.debug(f"[PATCHED CALL] VertexAI.async - streaming response, wrapping for inspection")
        return AsyncGoogleStreamingInspectionWrapper(response, normalized, metadata)
    
    # Post-call inspection
    assistant_content = extract_google_response(response)
    if assistant_content and normalized:
        logger.debug(f"[PATCHED CALL] VertexAI.async - Response inspection")
        messages_with_response = normalized + [
            {"role": "assistant", "content": assistant_content}
        ]
        decision = await inspector.ainspect_conversation(messages_with_response, metadata)
        logger.debug(f"[PATCHED CALL] VertexAI.async - Response decision: {decision.action}")
        set_inspection_context(decision=decision, done=True)
        _enforce_decision(decision)
    
    logger.debug(f"[PATCHED CALL] VertexAI.async - complete")
    return response


def patch_vertexai() -> bool:
    """
    Patch vertexai for automatic inspection.
    
    Returns:
        True if patching was successful, False otherwise
    """
    if is_patched("vertexai"):
        logger.debug("VertexAI already patched, skipping")
        return True
    
    vertexai = safe_import("vertexai.generative_models")
    if vertexai is None:
        return False
    
    try:
        # Patch GenerativeModel.generate_content
        wrapt.wrap_function_wrapper(
            "vertexai.generative_models",
            "GenerativeModel.generate_content",
            _wrap_generate_content,
        )
        
        # Patch async version
        wrapt.wrap_function_wrapper(
            "vertexai.generative_models",
            "GenerativeModel.generate_content_async",
            _wrap_generate_content_async,
        )
        
        mark_patched("vertexai")
        logger.info("VertexAI patched successfully")
        return True
    except Exception as e:
        logger.warning(f"Failed to patch VertexAI: {e}")
        return False
