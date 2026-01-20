"""
Google GenAI SDK (google-genai) client autopatching.

This module provides automatic inspection for the google-genai SDK calls
by patching Models.generate_content() and related methods.

The google-genai SDK is Google's modern unified library for accessing
Gemini models via both the Gemini Developer API and Vertex AI.

Usage:
    from google import genai
    client = genai.Client()
    response = client.models.generate_content(model="gemini-2.0-flash", contents="Hello")

Gateway Mode Support:
When AGENTSEC_LLM_INTEGRATION_MODE=gateway, calls are sent directly
to the provider-specific AI Defense Gateway in native format.
"""

import logging
import threading
from typing import Any, Dict, List, Optional

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

logger = logging.getLogger("aidefense.runtime.agentsec.patchers.google_genai")

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
                # Register for cleanup on shutdown
                from ..inspectors import register_inspector_for_cleanup
                register_inspector_for_cleanup(_inspector)
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
    # Try google_genai first, fall back to vertexai gateway config
    gateway_url = _state.get_provider_gateway_url("google_genai")
    gateway_api_key = _state.get_provider_gateway_api_key("google_genai")
    if not gateway_url:
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


def _extract_model_name(model: Any) -> str:
    """Extract model name from model parameter."""
    if model is None:
        return "unknown"
    if isinstance(model, str):
        return model
    # Model could be an object with name attribute
    if hasattr(model, "name"):
        return model.name
    if hasattr(model, "model_name"):
        return model.model_name
    return str(model)


def _normalize_genai_contents(contents: Any) -> List[Dict[str, Any]]:
    """
    Normalize google-genai contents to standard format.
    
    The google-genai SDK accepts various formats:
    - str: Single user message
    - list of dicts: [{role, parts}, ...]
    - Content objects from genai.types
    
    Returns:
        List of normalized messages: [{"role": str, "content": str}, ...]
    """
    # Use the shared Google normalization
    return normalize_google_messages(contents)


def _extract_genai_response(response: Any) -> str:
    """
    Extract text content from a google-genai GenerateContentResponse.
    
    Response structure:
        response.text (convenience property)
        or response.candidates[0].content.parts[0].text
        
    Args:
        response: GenerateContentResponse object
        
    Returns:
        Extracted text content, or empty string if not found
    """
    if response is None:
        return ""
    
    try:
        # Try the convenience text property first
        if hasattr(response, "text") and response.text is not None:
            return response.text
        
        # Fall back to candidates structure
        result = extract_google_response(response)
        return result if result is not None else ""
        
    except Exception as e:
        logger.debug(f"Error extracting google-genai response: {e}")
    
    return ""


def _handle_google_genai_gateway_call(
    model_name: str,
    contents: Any,
    config: Any = None,
) -> Any:
    """
    Handle google-genai call via AI Defense Gateway with native format.
    
    Sends native request directly to the provider-specific gateway.
    The gateway handles the request in native format - no conversion needed.
    
    Args:
        model_name: Model name (e.g., "gemini-2.0-flash")
        contents: Contents to generate from
        config: Optional GenerateContentConfig
        
    Returns:
        Native response wrapped for attribute access
    """
    import httpx
    
    # Try google_genai gateway first, fall back to vertexai
    gateway_url = _state.get_provider_gateway_url("google_genai")
    gateway_api_key = _state.get_provider_gateway_api_key("google_genai")
    if not gateway_url:
        gateway_url = _state.get_provider_gateway_url("vertexai")
        gateway_api_key = _state.get_provider_gateway_api_key("vertexai")
    
    if not gateway_url or not gateway_api_key:
        logger.warning("Gateway mode enabled but google-genai gateway not configured")
        raise SecurityPolicyError(
            Decision.block(reasons=["google-genai gateway not configured"]),
            "Gateway mode enabled but AGENTSEC_GOOGLE_GENAI_GATEWAY_URL not set"
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
                elif isinstance(item, str):
                    contents_list.append({"role": "user", "parts": [{"text": item}]})
                elif hasattr(item, "role") and hasattr(item, "parts"):
                    parts_list = []
                    for part in item.parts:
                        if hasattr(part, "text"):
                            parts_list.append({"text": part.text})
                    contents_list.append({"role": item.role, "parts": parts_list})
    
    # Build native request
    request_body = {
        "model": model_name,
        "contents": contents_list,
    }
    
    # Extract config settings
    if config:
        config_dict = {}
        if hasattr(config, "temperature") and config.temperature is not None:
            config_dict["temperature"] = config.temperature
        if hasattr(config, "max_output_tokens") and config.max_output_tokens is not None:
            config_dict["maxOutputTokens"] = config.max_output_tokens
        if hasattr(config, "top_p") and config.top_p is not None:
            config_dict["topP"] = config.top_p
        if hasattr(config, "top_k") and config.top_k is not None:
            config_dict["topK"] = config.top_k
        if hasattr(config, "system_instruction") and config.system_instruction:
            if isinstance(config.system_instruction, str):
                request_body["systemInstruction"] = {"parts": [{"text": config.system_instruction}]}
        if config_dict:
            request_body["generationConfig"] = config_dict
    
    logger.debug(f"[GATEWAY] Sending native google-genai request to gateway")
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
        
        logger.debug(f"[GATEWAY] Received native google-genai response from gateway")
        set_inspection_context(decision=Decision.allow(reasons=["Gateway handled inspection"]), done=True)
        
        # Wrap response for attribute access
        return _GoogleGenAIResponseWrapper(response_data)
        
    except httpx.HTTPStatusError as e:
        logger.error(f"[GATEWAY] HTTP error: {e}")
        if _state.get_gateway_mode_fail_open_llm():
            set_inspection_context(decision=Decision.allow(reasons=["Gateway error, fail_open=True"]), done=True)
        raise SecurityPolicyError(
            Decision.block(reasons=["Gateway unavailable"]),
            f"Gateway HTTP error: {e}"
        )
    except Exception as e:
        logger.error(f"[GATEWAY] Error: {e}")
        raise


class _GoogleGenAIResponseWrapper:
    """Wrapper to provide attribute access to native google-genai response dict."""
    
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
    """Wrapper for candidate in response."""
    
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
    """Wrapper for content in response."""
    
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
    """Wrapper for part in response."""
    
    def __init__(self, part_data: Dict):
        self._data = part_data
    
    @property
    def text(self):
        return self._data.get("text", "")


class GoogleGenAIStreamingWrapper:
    """
    Wrapper for google-genai streaming responses that performs inspection
    after collecting all chunks.
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
            text = _extract_genai_response(chunk)
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


class AsyncGoogleGenAIStreamingWrapper:
    """
    Async wrapper for google-genai streaming responses that performs inspection
    after collecting all chunks.
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
            text = _extract_genai_response(chunk)
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


def _wrap_generate_content(wrapped, instance, args, kwargs):
    """
    Wrapper for Models.generate_content().
    
    Supports both API mode (inspection via AI Defense API) and Gateway mode
    (routing through AI Defense Gateway).
    
    The google-genai API signature:
        client.models.generate_content(
            model="gemini-2.0-flash",
            contents="...",
            config=GenerateContentConfig(...)
        )
    """
    # Extract model name from kwargs or args
    model = kwargs.get("model")
    if model is None and args:
        model = args[0]
    model_name = _extract_model_name(model)
    
    if not _should_inspect():
        logger.debug(f"[PATCHED CALL] google-genai.generate_content - inspection skipped (mode=off or already done)")
        return wrapped(*args, **kwargs)
    
    # Extract contents from kwargs
    contents = kwargs.get("contents")
    if contents is None and len(args) > 1:
        contents = args[1]
    
    config = kwargs.get("config")
    
    # Normalize messages
    normalized = _normalize_genai_contents(contents)
    metadata = get_inspection_context().metadata
    metadata["provider"] = "google_genai"
    metadata["model"] = model_name
    
    mode = _state.get_llm_mode()
    integration_mode = _state.get_llm_integration_mode()
    logger.debug(f"")
    logger.debug(f"╔══════════════════════════════════════════════════════════════")
    logger.debug(f"║ [PATCHED] LLM CALL: {model_name}")
    logger.debug(f"║ Operation: google-genai.generate_content | LLM Mode: {mode} | Integration: {integration_mode}")
    logger.debug(f"╚══════════════════════════════════════════════════════════════")
    
    # Gateway mode: route through AI Defense Gateway
    if _should_use_gateway():
        logger.debug(f"[PATCHED CALL] google-genai.generate_content - Gateway mode - routing to AI Defense Gateway")
        return _handle_google_genai_gateway_call(
            model_name=model_name,
            contents=contents,
            config=config,
        )
    
    # API mode (default): use LLMInspector for inspection
    # Pre-call inspection
    if normalized:
        logger.debug(f"[PATCHED CALL] google-genai.generate_content - Request inspection ({len(normalized)} messages)")
        inspector = _get_inspector()
        decision = inspector.inspect_conversation(normalized, metadata)
        logger.debug(f"[PATCHED CALL] google-genai.generate_content - Request decision: {decision.action}")
        set_inspection_context(decision=decision)
        _enforce_decision(decision)
    
    # Call the original
    logger.debug(f"[PATCHED CALL] google-genai.generate_content - calling original method")
    response = wrapped(*args, **kwargs)
    
    # Post-call inspection for non-streaming
    assistant_content = _extract_genai_response(response)
    if assistant_content and normalized:
        logger.debug(f"[PATCHED CALL] google-genai.generate_content - Response inspection (response: {len(assistant_content)} chars)")
        messages_with_response = normalized + [
            {"role": "assistant", "content": assistant_content}
        ]
        inspector = _get_inspector()
        decision = inspector.inspect_conversation(messages_with_response, metadata)
        logger.debug(f"[PATCHED CALL] google-genai.generate_content - Response decision: {decision.action}")
        set_inspection_context(decision=decision, done=True)
        _enforce_decision(decision)
    
    logger.debug(f"[PATCHED CALL] google-genai.generate_content - complete")
    return response


async def _wrap_generate_content_async(wrapped, instance, args, kwargs):
    """
    Async wrapper for Models.generate_content() when called with async client.
    """
    # Extract model name
    model = kwargs.get("model")
    if model is None and args:
        model = args[0]
    model_name = _extract_model_name(model)
    
    if not _should_inspect():
        logger.debug(f"[PATCHED CALL] google-genai.async.generate_content - inspection skipped")
        return await wrapped(*args, **kwargs)
    
    # Extract contents
    contents = kwargs.get("contents")
    if contents is None and len(args) > 1:
        contents = args[1]
    
    config = kwargs.get("config")
    
    # Normalize messages
    normalized = _normalize_genai_contents(contents)
    metadata = get_inspection_context().metadata
    metadata["provider"] = "google_genai"
    metadata["model"] = model_name
    
    mode = _state.get_llm_mode()
    integration_mode = _state.get_llm_integration_mode()
    logger.debug(f"")
    logger.debug(f"╔══════════════════════════════════════════════════════════════")
    logger.debug(f"║ [PATCHED] LLM CALL (async): {model_name}")
    logger.debug(f"║ Operation: google-genai.async.generate_content | LLM Mode: {mode} | Integration: {integration_mode}")
    logger.debug(f"╚══════════════════════════════════════════════════════════════")
    
    # Gateway mode
    if _should_use_gateway():
        logger.debug(f"[PATCHED CALL] google-genai.async - Gateway mode - routing to AI Defense Gateway")
        # For now, use sync gateway call (could be made async)
        return _handle_google_genai_gateway_call(
            model_name=model_name,
            contents=contents,
            config=config,
        )
    
    # API mode: Pre-call inspection
    if normalized:
        logger.debug(f"[PATCHED CALL] google-genai.async - Request inspection ({len(normalized)} messages)")
        inspector = _get_inspector()
        decision = await inspector.ainspect_conversation(normalized, metadata)
        logger.debug(f"[PATCHED CALL] google-genai.async - Request decision: {decision.action}")
        set_inspection_context(decision=decision)
        _enforce_decision(decision)
    
    # Call the original
    logger.debug(f"[PATCHED CALL] google-genai.async - calling original method")
    response = await wrapped(*args, **kwargs)
    
    # Post-call inspection
    assistant_content = _extract_genai_response(response)
    if assistant_content and normalized:
        logger.debug(f"[PATCHED CALL] google-genai.async - Response inspection")
        messages_with_response = normalized + [
            {"role": "assistant", "content": assistant_content}
        ]
        decision = await inspector.ainspect_conversation(messages_with_response, metadata)
        logger.debug(f"[PATCHED CALL] google-genai.async - Response decision: {decision.action}")
        set_inspection_context(decision=decision, done=True)
        _enforce_decision(decision)
    
    logger.debug(f"[PATCHED CALL] google-genai.async - complete")
    return response


def patch_google_genai() -> bool:
    """
    Patch google-genai SDK for automatic inspection.
    
    Patches the Models.generate_content() method to intercept
    all LLM calls for AI Defense inspection.
    
    Returns:
        True if patching was successful, False otherwise
    """
    if is_patched("google_genai"):
        logger.debug("google-genai already patched, skipping")
        return True
    
    # Try to import the google.genai module
    genai = safe_import("google.genai")
    if genai is None:
        return False
    
    try:
        # The google-genai SDK structure:
        # from google import genai
        # client = genai.Client()
        # response = client.models.generate_content(...)
        #
        # We need to patch the Models class's generate_content method
        
        # Try to patch via the models module
        genai_models = safe_import("google.genai.models")
        if genai_models is not None:
            # Patch Models.generate_content
            wrapt.wrap_function_wrapper(
                "google.genai.models",
                "Models.generate_content",
                _wrap_generate_content,
            )
            logger.debug("Patched google.genai.models.Models.generate_content")
        
        # Also try to patch AsyncModels if it exists
        try:
            wrapt.wrap_function_wrapper(
                "google.genai.models",
                "AsyncModels.generate_content",
                _wrap_generate_content_async,
            )
            logger.debug("Patched google.genai.models.AsyncModels.generate_content")
        except Exception as e:
            logger.debug(f"AsyncModels.generate_content not found or failed to patch: {e}")
        
        mark_patched("google_genai")
        logger.info("google-genai patched successfully")
        return True
        
    except Exception as e:
        logger.warning(f"Failed to patch google-genai: {e}")
        return False
