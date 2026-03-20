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
Google GenAI SDK (google-genai) client autopatching.

This module provides automatic inspection for the google-genai SDK calls
by patching Models.generate_content(), Models.generate_content_stream(),
and their async counterparts.

The google-genai SDK is Google's modern unified library for accessing
Gemini models via both the Gemini Developer API and Vertex AI.

Usage:
    from google import genai
    client = genai.Client()
    response = client.models.generate_content(model="gemini-2.0-flash", contents="Hello")

Gateway Mode Support:
When llm_integration_mode=gateway, calls are sent directly
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
from ._base import safe_import, resolve_gateway_settings
from ._google_common import (
    normalize_google_messages,
    extract_google_response,
)

logger = logging.getLogger("aidefense.runtime.agentsec.patchers.google_genai")

# Maximum streaming buffer size (1MB) to prevent unbounded memory usage
MAX_STREAMING_BUFFER_SIZE = 1_000_000

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
            # Double-check pattern for thread safety
            if _inspector is None:
                if not _state.is_initialized():
                    logger.warning("agentsec.protect() not called, using default config")
                _inspector = LLMInspector(
                    fail_open=_state.get_api_llm_fail_open(),
                    default_rules=_state.get_llm_rules(),
                )
                # Register for cleanup on shutdown
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


def _serialize_part(part: Any) -> Optional[Dict]:
    """Serialize a google-genai Part object to dict for gateway request.

    Handles text, function_call, and function_response parts.
    The google-genai SDK uses Pydantic v2 models; we try model_dump first,
    then fall back to manual attribute extraction.

    Args:
        part: A Part object (Pydantic model, dict, or proto-plus object)

    Returns:
        A JSON-compatible dict representing the part, or None if empty
    """
    if isinstance(part, dict):
        return part

    # Try Pydantic serialization first (google-genai SDK uses Pydantic v2)
    if hasattr(part, "model_dump"):
        try:
            dumped = part.model_dump(mode="json", by_alias=True, exclude_none=True)
            if dumped:
                return dumped
        except (TypeError, Exception):
            try:
                # Keep by_alias=True so field names stay camelCase
                # (e.g. "functionCall" not "function_call")
                dumped = part.model_dump(by_alias=True, exclude_none=True)
                if dumped:
                    return dumped
            except Exception:
                pass

    # Manual extraction for each known part type
    result: Dict[str, Any] = {}

    # Text part
    if hasattr(part, "text") and part.text is not None and part.text != "":
        result["text"] = part.text

    # Function call part (model requesting a tool call)
    if hasattr(part, "function_call") and part.function_call is not None:
        fc = part.function_call
        fc_dict: Dict[str, Any] = {}
        if hasattr(fc, "name") and fc.name:
            fc_dict["name"] = fc.name
        if hasattr(fc, "args") and fc.args is not None:
            args = fc.args
            # args may be a dict, proto MapComposite, or Pydantic object
            if isinstance(args, dict):
                fc_dict["args"] = args
            elif hasattr(args, "items"):
                fc_dict["args"] = dict(args)
            else:
                fc_dict["args"] = args
        if fc_dict:
            result["functionCall"] = fc_dict

    # Function response part (tool execution result)
    if hasattr(part, "function_response") and part.function_response is not None:
        fr = part.function_response
        fr_dict: Dict[str, Any] = {}
        if hasattr(fr, "name") and fr.name:
            fr_dict["name"] = fr.name
        if hasattr(fr, "response") and fr.response is not None:
            resp = fr.response
            if isinstance(resp, dict):
                fr_dict["response"] = resp
            elif hasattr(resp, "items"):
                fr_dict["response"] = dict(resp)
            else:
                fr_dict["response"] = {"result": str(resp)}
        if fr_dict:
            result["functionResponse"] = fr_dict

    return result if result else None


def _serialize_sdk_object(obj: Any) -> Any:
    """Serialize a google-genai SDK object (Tool, ToolConfig, etc.) to a JSON-compatible dict.

    Recursively processes dicts and lists so that nested SDK objects
    (e.g. a dict whose values are Pydantic models) are fully converted
    to plain JSON-safe primitives.
    """
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        # Recurse into values – a dict may contain nested SDK objects
        return {k: _serialize_sdk_object(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize_sdk_object(item) for item in obj]
    # Pydantic v2
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump(mode="json", by_alias=True, exclude_none=True)
        except (TypeError, Exception):
            try:
                # Keep by_alias=True so field names stay camelCase
                # (e.g. "functionDeclarations" not "function_declarations")
                return obj.model_dump(by_alias=True, exclude_none=True)
            except Exception:
                pass
    # Pydantic v1
    if hasattr(obj, "dict"):
        try:
            return obj.dict(exclude_none=True)
        except Exception:
            pass
    # Proto-plus
    if hasattr(type(obj), "to_dict"):
        try:
            return type(obj).to_dict(obj)
        except Exception:
            pass
    return obj


def _deep_sanitize(obj: Any) -> Any:
    """Recursively convert *obj* to JSON-safe primitives.

    This is the safety net called when :func:`json.dumps` raises
    ``TypeError`` on the assembled request body.  It walks every value
    and applies :func:`_serialize_sdk_object` to non-primitive leaves.
    """
    if obj is None:
        return None
    if isinstance(obj, (bool,)):          # bool before int (bool ⊂ int)
        return obj
    if isinstance(obj, (int, float)):
        return obj
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return {str(k): _deep_sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_deep_sanitize(v) for v in obj]
    # Unknown type – try SDK serialization, then fall back to str()
    serialized = _serialize_sdk_object(obj)
    if serialized is not obj:             # serialization produced a new object
        return _deep_sanitize(serialized)
    return str(obj)


def _handle_google_genai_gateway_call(
    model_name: str,
    contents: Any,
    config: Any = None,
    gw_settings: Any = None,
) -> Any:
    """
    Handle google-genai call via AI Defense Gateway with native format.
    
    Sends native request directly to the provider-specific gateway.
    The gateway handles the request in native format - no conversion needed.
    
    Args:
        model_name: Model name (e.g., "gemini-2.0-flash")
        contents: Contents to generate from
        config: Optional GenerateContentConfig
        gw_settings: Resolved gateway settings (url, api_key, fail_open)
        
    Returns:
        Native response wrapped for attribute access
    """
    from ._google_common import (
        build_vertexai_gateway_url,
        vertexai_gateway_post,
        _has_multi_turn_contents,
    )

    if not gw_settings or not gw_settings.url:
        logger.warning("Gateway mode enabled but google-genai gateway URL not configured")
        raise SecurityPolicyError(
            Decision.block(reasons=["google-genai gateway not configured"]),
            "Gateway mode enabled but google-genai gateway not configured (check gateway_mode.llm_gateways for a google_genai or vertexai provider entry in config)"
        )
    
    # Build auth headers based on auth_mode
    if gw_settings.auth_mode == "google_adc":
        from ._google_common import _build_google_auth_header
        auth_headers = _build_google_auth_header(gw_settings)
    else:
        # api_key mode
        if not gw_settings.api_key:
            logger.warning("Gateway mode enabled but google-genai gateway api_key not configured")
            raise SecurityPolicyError(
                Decision.block(reasons=["google-genai gateway api_key not configured"]),
                "Gateway mode enabled but google-genai gateway api_key not configured (auth_mode=api_key requires gateway_api_key)"
            )
        auth_headers = {"Authorization": f"Bearer {gw_settings.api_key}"}
    
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
                        part_dict = _serialize_part(part)
                        if part_dict:
                            parts_list.append(part_dict)
                    if parts_list:
                        contents_list.append({"role": item.role, "parts": parts_list})
    
    # Build native request body (model is in URL path, not body, for Vertex AI)
    request_body = {
        "contents": contents_list,
    }
    
    # Extract config settings.
    # config may be a GenerateContentConfig SDK object (attribute access) or
    # a plain dict (e.g. from to_json_dict(), as Strands passes it).
    if config:
        if isinstance(config, dict):
            # Dict configs are already in REST API camelCase format.
            # Merge relevant top-level keys directly into request_body.
            _DICT_TOP_LEVEL_KEYS = (
                "systemInstruction", "tools", "toolConfig", "safetySettings",
            )
            for key in _DICT_TOP_LEVEL_KEYS:
                if key in config and config[key]:
                    request_body[key] = config[key]
            # Build generationConfig from dict keys
            gen_config: Dict[str, Any] = {}
            _GEN_CONFIG_DICT_KEYS = [
                "temperature", "maxOutputTokens", "topP", "topK",
                "candidateCount", "stopSequences", "responseMimeType",
                "presencePenalty", "frequencyPenalty", "seed", "responseSchema",
            ]
            for key in _GEN_CONFIG_DICT_KEYS:
                if key in config and config[key] is not None:
                    gen_config[key] = config[key]
            if gen_config:
                request_body["generationConfig"] = gen_config
            if "tools" in request_body:
                logger.debug(f"[GATEWAY] Including {len(request_body['tools'])} tool(s) in request (from dict config)")
        else:
            # SDK object config — extract via attribute access.
            # === Generation Config (goes inside "generationConfig" in the REST body) ===
            gen_config_obj: Dict[str, Any] = {}
            _GEN_CONFIG_ATTRS = [
                ("temperature", "temperature"),
                ("max_output_tokens", "maxOutputTokens"),
                ("top_p", "topP"),
                ("top_k", "topK"),
                ("candidate_count", "candidateCount"),
                ("stop_sequences", "stopSequences"),
                ("response_mime_type", "responseMimeType"),
                ("presence_penalty", "presencePenalty"),
                ("frequency_penalty", "frequencyPenalty"),
                ("seed", "seed"),
            ]
            for attr, camel_key in _GEN_CONFIG_ATTRS:
                val = getattr(config, attr, None)
                if val is not None:
                    gen_config_obj[camel_key] = val

            # response_schema may be a Pydantic model that needs serialization
            rs = getattr(config, "response_schema", None)
            if rs is not None:
                serialized_rs = _serialize_sdk_object(rs)
                if serialized_rs is not None:
                    gen_config_obj["responseSchema"] = serialized_rs

            if gen_config_obj:
                request_body["generationConfig"] = gen_config_obj

            # === System Instruction (top-level in the REST body) ===
            si = getattr(config, "system_instruction", None)
            if si is not None:
                if isinstance(si, str):
                    request_body["systemInstruction"] = {"parts": [{"text": si}]}
                elif hasattr(si, "parts"):
                    # Content object — serialize each part
                    parts = []
                    for p in si.parts:
                        sd = _serialize_part(p)
                        if sd:
                            parts.append(sd)
                    if parts:
                        request_body["systemInstruction"] = {"parts": parts}
                elif isinstance(si, list):
                    # List of strings or Content objects
                    parts = []
                    for item in si:
                        if isinstance(item, str):
                            parts.append({"text": item})
                        elif hasattr(item, "text"):
                            parts.append({"text": item.text})
                        else:
                            sd = _serialize_sdk_object(item)
                            if sd:
                                parts.append(sd)
                    if parts:
                        request_body["systemInstruction"] = {"parts": parts}
                else:
                    # Try generic serialization (dict, Pydantic, etc.)
                    serialized_si = _serialize_sdk_object(si)
                    if serialized_si:
                        request_body["systemInstruction"] = serialized_si

            # === Tools (top-level in the REST body) ===
            if hasattr(config, "tools") and config.tools:
                tools_list = []
                for tool in config.tools:
                    serialized = _serialize_sdk_object(tool)
                    if serialized:
                        tools_list.append(serialized)
                if tools_list:
                    request_body["tools"] = tools_list
                    logger.debug(f"[GATEWAY] Including {len(tools_list)} tool(s) in request")

            # === Tool Config (top-level in the REST body) ===
            if hasattr(config, "tool_config") and config.tool_config:
                serialized_tc = _serialize_sdk_object(config.tool_config)
                if serialized_tc:
                    request_body["toolConfig"] = serialized_tc

            # === Safety Settings (top-level in the REST body) ===
            if hasattr(config, "safety_settings") and config.safety_settings:
                serialized_ss = _serialize_sdk_object(config.safety_settings)
                if serialized_ss:
                    request_body["safetySettings"] = serialized_ss

    # Build the full Vertex AI gateway URL with API path
    # The Vertex AI gateway expects: {base}/v1/projects/{p}/locations/{l}/publishers/google/models/{m}:generateContent
    try:
        full_gateway_url = build_vertexai_gateway_url(
            gw_settings.url, model_name, gw_settings, streaming=False,
        )
    except ValueError as exc:
        raise SecurityPolicyError(
            Decision.block(reasons=[str(exc)]),
            str(exc),
        )
    
    logger.debug(f"[GATEWAY] Sending native google-genai request to gateway")
    logger.debug(f"[GATEWAY] URL: {full_gateway_url}")
    logger.debug(f"[GATEWAY] Model: {model_name}")
    logger.debug(f"[GATEWAY] Request body keys: {list(request_body.keys())}")

    # Pre-serialize to catch non-JSON-serializable objects early and
    # ensure the exact bytes we intend are sent to the gateway.
    import json as _json
    try:
        _body_bytes = _json.dumps(request_body).encode("utf-8")
    except TypeError:
        # Fallback: deep-sanitize then serialize
        logger.warning("[GATEWAY] request_body contains non-JSON-serializable objects, applying deep sanitization")
        request_body = _deep_sanitize(request_body)
        _body_bytes = _json.dumps(request_body).encode("utf-8")

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"[GATEWAY] Full request body ({len(_body_bytes)} bytes): {_body_bytes[:5000].decode('utf-8', errors='replace')}")

    request_headers = {**auth_headers, "Content-Type": "application/json"}
    try:
        response = vertexai_gateway_post(
            full_gateway_url, _body_bytes, request_headers, gw_settings,
        )
        response_data = response.json()

        logger.debug(f"[GATEWAY] Received native google-genai response from gateway")
        set_inspection_context(decision=Decision.allow(reasons=["Gateway handled inspection"]), done=True)
        
        # Wrap response for attribute access
        return _GoogleGenAIResponseWrapper(response_data)
        
    except Exception as e:
        import httpx as _httpx
        if isinstance(e, _httpx.HTTPStatusError):
            logger.error(f"[GATEWAY] HTTP error: {e}")
            _resp_text = ""
            try:
                _resp_text = e.response.text[:1000] if hasattr(e.response, "text") else ""
                logger.error(f"[GATEWAY] HTTP {e.response.status_code} — body preview: {_resp_text}")
            except Exception:
                pass
            # Detect gateway body-size corruption
            if "Invalid JSON payload" in _resp_text:
                logger.error(
                    "[GATEWAY] The AI Defense gateway returned 'Invalid JSON "
                    "payload'.  This is a known gateway limitation when the "
                    "request body exceeds ~2700 bytes (e.g. requests with "
                    "multiple tool declarations).  Workaround: use "
                    "llm_integration_mode=api until the gateway team resolves "
                    "this issue."
                )
            # Detect multi-turn 500: known gateway bug (Issue #4)
            if e.response.status_code == 500 and _has_multi_turn_contents(contents_list):
                logger.error(
                    "[GATEWAY] HTTP 500 on multi-turn request (contents has %d messages). "
                    "This is a known gateway bug: the AI Defense gateway returns 500 on "
                    "any multi-turn Vertex AI request (including functionCall/functionResponse). "
                    "See examples/agentsec/KNOWN_ISSUES.md. Workaround: use llm_integration_mode=api.",
                    len(contents_list),
                )
        else:
            logger.error(f"[GATEWAY] Error: {e}")
        if gw_settings.fail_open:
            logger.warning(f"[GATEWAY] fail_open=True, re-raising original error for caller to handle")
            set_inspection_context(decision=Decision.allow(reasons=["Gateway error, fail_open=True"]), done=True)
            raise
        if isinstance(e, _httpx.HTTPStatusError):
            raise SecurityPolicyError(
                Decision.block(reasons=["Gateway unavailable"]),
                f"Gateway HTTP error: {e}",
            )
        raise


class _PromptFeedbackWrapper:
    """Wrapper for prompt_feedback in gateway responses.

    Provides the attributes that ``langchain_google_genai`` and other
    frameworks inspect (``block_reason``, ``safety_ratings``).  When the
    gateway response does not include explicit feedback the wrapper returns
    safe defaults so that truthiness checks (``if response.prompt_feedback``)
    evaluate to ``False``.
    """

    def __init__(self, data: Optional[Dict] = None):
        self._data = data or {}

    @property
    def block_reason(self):
        return self._data.get("blockReason") or self._data.get("block_reason") or 0

    @property
    def safety_ratings(self):
        return self._data.get("safetyRatings") or self._data.get("safety_ratings") or []

    def __bool__(self):
        # ``langchain_google_genai`` does ``if response.prompt_feedback``
        return bool(self.block_reason)


class _UsageMetadataWrapper:
    """Wrapper for usageMetadata in gateway responses."""

    def __init__(self, data: Optional[Dict] = None):
        self._data = data or {}

    @property
    def prompt_token_count(self):
        return self._data.get("promptTokenCount") or self._data.get("prompt_token_count") or 0

    @property
    def candidates_token_count(self):
        return self._data.get("candidatesTokenCount") or self._data.get("candidates_token_count") or 0

    @property
    def total_token_count(self):
        return self._data.get("totalTokenCount") or self._data.get("total_token_count") or 0


class _GoogleGenAIResponseWrapper:
    """Wrapper to provide attribute access to native google-genai response dict.

    Exposes all attributes that framework integrations (LangChain, LangGraph,
    CrewAI, etc.) access on the ``GenerateContentResponse`` object returned by
    the Google GenAI SDK, including ``candidates``, ``prompt_feedback``,
    ``usage_metadata``, and ``text``.
    """
    
    def __init__(self, response_data: Dict):
        if not isinstance(response_data, dict):
            logger.warning(f"Invalid gateway response type: {type(response_data)}, expected dict")
            raise ValueError(f"Invalid gateway response: expected dict, got {type(response_data)}")
        self._data = response_data
        self._candidates = None
    
    @property
    def candidates(self):
        if self._candidates is None:
            try:
                self._candidates = [
                    _CandidateWrapper(c) for c in self._data.get("candidates", [])
                ]
            except (TypeError, KeyError, AttributeError) as e:
                logger.warning(f"Error parsing candidates from gateway response: {e}")
                self._candidates = []
        return self._candidates

    @property
    def prompt_feedback(self):
        """Return prompt feedback (block reason / safety ratings).

        ``langchain_google_genai`` checks ``if response.prompt_feedback`` to
        decide whether the prompt was blocked.  Our wrapper returns a falsy
        object when no blocking occurred so the check passes cleanly.
        """
        fb = self._data.get("promptFeedback") or self._data.get("prompt_feedback")
        return _PromptFeedbackWrapper(fb)

    @property
    def usage_metadata(self):
        um = self._data.get("usageMetadata") or self._data.get("usage_metadata")
        return _UsageMetadataWrapper(um)
    
    @property
    def model_version(self):
        """Model version string from the response."""
        return self._data.get("modelVersion") or self._data.get("model_version") or ""

    @property
    def response_id(self):
        """Response ID if provided by the gateway."""
        return self._data.get("responseId") or self._data.get("response_id") or ""
    
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
        return self._data.get("finishReason") or self._data.get("finish_reason")

    @property
    def safety_ratings(self):
        return self._data.get("safetyRatings") or self._data.get("safety_ratings") or []

    @property
    def index(self):
        return self._data.get("index", 0)

    @property
    def citation_metadata(self):
        return self._data.get("citationMetadata") or self._data.get("citation_metadata") or None

    @property
    def grounding_metadata(self):
        return self._data.get("groundingMetadata") or self._data.get("grounding_metadata") or None

    @property
    def avg_logprobs(self):
        return self._data.get("avgLogprobs") or self._data.get("avg_logprobs") or None

    @property
    def token_count(self):
        return self._data.get("tokenCount") or self._data.get("token_count") or 0


class _ContentWrapper:
    """Wrapper for content in response."""
    
    def __init__(self, content_data: Dict):
        self._data = content_data
        self._parts = None
    
    @property
    def role(self):
        return self._data.get("role", "model")
    
    @role.setter
    def role(self, value):
        self._data["role"] = value
    
    @property
    def parts(self):
        if self._parts is None:
            self._parts = [_PartWrapper(p) for p in self._data.get("parts", [])]
        return self._parts


class _PartWrapper:
    """Wrapper for part in response.

    Handles text parts, functionCall parts (model requesting a tool call),
    and functionResponse parts (tool execution results).

    Also exposes stub attributes (``inline_data``, ``executable_code``, etc.)
    that ``langchain_google_genai`` and other integrations probe via truthiness
    checks.
    """
    
    def __init__(self, part_data: Dict):
        self._data = part_data
    
    @property
    def text(self):
        return self._data.get("text", "")

    @property
    def function_call(self):
        """Return a FunctionCall-like object if this part is a function call."""
        fc_data = self._data.get("functionCall") or self._data.get("function_call")
        if fc_data:
            return _FunctionCallWrapper(fc_data)
        return None

    @property
    def function_response(self):
        """Return a FunctionResponse-like object if this part is a function response."""
        fr_data = self._data.get("functionResponse") or self._data.get("function_response")
        if fr_data:
            return _FunctionResponseWrapper(fr_data)
        return None

    # --- Stub attributes for framework compatibility ---
    # ``langchain_google_genai`` checks these with truthiness tests;
    # returning None / falsy makes those checks pass cleanly.

    @property
    def inline_data(self):
        return self._data.get("inlineData") or self._data.get("inline_data") or None

    @property
    def executable_code(self):
        return self._data.get("executableCode") or self._data.get("executable_code") or None

    @property
    def code_execution_result(self):
        return self._data.get("codeExecutionResult") or self._data.get("code_execution_result") or None

    @property
    def file_data(self):
        return self._data.get("fileData") or self._data.get("file_data") or None

    @property
    def video_metadata(self):
        return self._data.get("videoMetadata") or self._data.get("video_metadata") or None

    @property
    def thought(self):
        return self._data.get("thought") or None


class _FunctionCallWrapper:
    """Wrapper for functionCall in gateway response."""

    def __init__(self, data: Dict):
        self._data = data

    @property
    def id(self) -> Optional[str]:
        return self._data.get("id")

    @property
    def name(self) -> str:
        return self._data.get("name", "")

    @property
    def args(self) -> Dict:
        return self._data.get("args", {})

    def __repr__(self):
        return f"FunctionCall(id={self.id!r}, name={self.name!r}, args={self.args!r})"


class _FunctionResponseWrapper:
    """Wrapper for functionResponse in gateway response."""

    def __init__(self, data: Dict):
        self._data = data

    @property
    def name(self) -> str:
        return self._data.get("name", "")

    @property
    def response(self) -> Dict:
        return self._data.get("response", {})


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
            
            # Extract text from chunk (with buffer size cap)
            text = _extract_genai_response(chunk)
            if text:
                current_size = sum(len(t) for t in self._collected_text)
                if current_size < MAX_STREAMING_BUFFER_SIZE:
                    remaining = MAX_STREAMING_BUFFER_SIZE - current_size
                    self._collected_text.append(text[:remaining])
            
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
        if len(full_response) > MAX_STREAMING_BUFFER_SIZE:
            logger.warning(
                f"Streaming buffer exceeded {MAX_STREAMING_BUFFER_SIZE} bytes, truncating for inspection"
            )
            full_response = full_response[:MAX_STREAMING_BUFFER_SIZE]
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
            
            # Extract text from chunk (with buffer size cap)
            text = _extract_genai_response(chunk)
            if text:
                current_size = sum(len(t) for t in self._collected_text)
                if current_size < MAX_STREAMING_BUFFER_SIZE:
                    remaining = MAX_STREAMING_BUFFER_SIZE - current_size
                    self._collected_text.append(text[:remaining])
            
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
        if len(full_response) > MAX_STREAMING_BUFFER_SIZE:
            logger.warning(
                f"Streaming buffer exceeded {MAX_STREAMING_BUFFER_SIZE} bytes, truncating for inspection"
            )
            full_response = full_response[:MAX_STREAMING_BUFFER_SIZE]
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
    
    set_inspection_context(done=False)
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
    logger.debug(f"╔══════════════════════════════════════════════════════════════")
    logger.debug(f"║ [PATCHED] LLM CALL: {model_name}")
    logger.debug(f"║ Operation: google-genai.generate_content | LLM Mode: {mode} | Integration: {integration_mode}")
    logger.debug(f"╚══════════════════════════════════════════════════════════════")
    
    # Gateway mode: route through AI Defense Gateway
    # Try google_genai gateway first; fall back to vertexai gateway since
    # google-genai and Vertex AI share the same backend.  If neither is
    # configured the second call will raise SecurityPolicyError, which is
    # correct -- we must not silently degrade to API mode.
    try:
        gw_settings = resolve_gateway_settings("google_genai")
    except SecurityPolicyError:
        logger.warning(
            "[PATCHED CALL] google-genai.generate_content - No gateway "
            "configured for 'google_genai', trying 'vertexai' gateway "
            "as fallback"
        )
        # This will raise SecurityPolicyError if vertexai is also missing.
        gw_settings = resolve_gateway_settings("vertexai")
    if gw_settings:
        logger.debug(f"[PATCHED CALL] google-genai.generate_content - Gateway mode - routing to AI Defense Gateway")
        return _handle_google_genai_gateway_call(
            model_name=model_name,
            contents=contents,
            config=config,
            gw_settings=gw_settings,
        )
    
    # Direct API call (API-mode inspection)
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


def _wrap_generate_content_stream(wrapped, instance, args, kwargs):
    """
    Wrapper for Models.generate_content_stream().

    For API mode: pre-inspects the request, calls the original streaming
    method, and wraps the returned iterator in GoogleGenAIStreamingWrapper
    so that the complete response is inspected after the stream finishes.

    For Gateway mode: routes through the AI Defense Gateway as a
    non-streaming call and yields the full response as a single chunk.
    """
    model = kwargs.get("model")
    if model is None and args:
        model = args[0]
    model_name = _extract_model_name(model)

    set_inspection_context(done=False)
    if not _should_inspect():
        logger.debug("[PATCHED CALL] google-genai.generate_content_stream - inspection skipped")
        return wrapped(*args, **kwargs)

    contents = kwargs.get("contents")
    if contents is None and len(args) > 1:
        contents = args[1]

    config = kwargs.get("config")

    normalized = _normalize_genai_contents(contents)
    metadata = get_inspection_context().metadata
    metadata["provider"] = "google_genai"
    metadata["model"] = model_name

    mode = _state.get_llm_mode()
    integration_mode = _state.get_llm_integration_mode()
    logger.debug("╔══════════════════════════════════════════════════════════════")
    logger.debug(f"║ [PATCHED] LLM CALL (stream): {model_name}")
    logger.debug(f"║ Operation: google-genai.generate_content_stream | LLM Mode: {mode} | Integration: {integration_mode}")
    logger.debug("╚══════════════════════════════════════════════════════════════")

    # Gateway mode
    try:
        gw_settings = resolve_gateway_settings("google_genai")
    except SecurityPolicyError:
        logger.warning(
            "[PATCHED CALL] google-genai.generate_content_stream - No gateway "
            "configured for 'google_genai', trying 'vertexai' gateway as fallback"
        )
        gw_settings = resolve_gateway_settings("vertexai")
    if gw_settings:
        logger.debug("[PATCHED CALL] google-genai.generate_content_stream - Gateway mode - routing to AI Defense Gateway")
        gateway_response = _handle_google_genai_gateway_call(
            model_name=model_name,
            contents=contents,
            config=config,
            gw_settings=gw_settings,
        )
        return iter([gateway_response])

    # API mode: pre-inspect, then wrap the stream for post-inspection
    if normalized:
        logger.debug(f"[PATCHED CALL] google-genai.generate_content_stream - Request inspection ({len(normalized)} messages)")
        inspector = _get_inspector()
        decision = inspector.inspect_conversation(normalized, metadata)
        logger.debug(f"[PATCHED CALL] google-genai.generate_content_stream - Request decision: {decision.action}")
        set_inspection_context(decision=decision)
        _enforce_decision(decision)

    logger.debug("[PATCHED CALL] google-genai.generate_content_stream - calling original method")
    original_stream = wrapped(*args, **kwargs)
    return GoogleGenAIStreamingWrapper(original_stream, normalized or [], metadata)


async def _wrap_generate_content_stream_async(wrapped, instance, args, kwargs):
    """
    Async wrapper for AsyncModels.generate_content_stream().

    Same strategy as the sync variant but yields from the async iterator.
    """
    model = kwargs.get("model")
    if model is None and args:
        model = args[0]
    model_name = _extract_model_name(model)

    set_inspection_context(done=False)
    if not _should_inspect():
        logger.debug("[PATCHED CALL] google-genai.async.generate_content_stream - inspection skipped")
        return await wrapped(*args, **kwargs)

    contents = kwargs.get("contents")
    if contents is None and len(args) > 1:
        contents = args[1]

    config = kwargs.get("config")

    normalized = _normalize_genai_contents(contents)
    metadata = get_inspection_context().metadata
    metadata["provider"] = "google_genai"
    metadata["model"] = model_name

    mode = _state.get_llm_mode()
    integration_mode = _state.get_llm_integration_mode()
    logger.debug("╔══════════════════════════════════════════════════════════════")
    logger.debug(f"║ [PATCHED] LLM CALL (async stream): {model_name}")
    logger.debug(f"║ Operation: google-genai.async.generate_content_stream | LLM Mode: {mode} | Integration: {integration_mode}")
    logger.debug("╚══════════════════════════════════════════════════════════════")

    # Gateway mode
    try:
        gw_settings = resolve_gateway_settings("google_genai")
    except SecurityPolicyError:
        logger.warning(
            "[PATCHED CALL] google-genai.async.generate_content_stream - No gateway "
            "configured for 'google_genai', trying 'vertexai' gateway as fallback"
        )
        gw_settings = resolve_gateway_settings("vertexai")
    if gw_settings:
        logger.debug("[PATCHED CALL] google-genai.async.generate_content_stream - Gateway mode")
        import asyncio
        gateway_response = await asyncio.to_thread(
            _handle_google_genai_gateway_call,
            model_name=model_name,
            contents=contents,
            config=config,
            gw_settings=gw_settings,
        )

        async def _single_chunk():
            yield gateway_response

        return _single_chunk()

    # API mode: pre-inspect, then wrap the stream
    if normalized:
        logger.debug(f"[PATCHED CALL] google-genai.async.generate_content_stream - Request inspection ({len(normalized)} messages)")
        inspector = _get_inspector()
        decision = await inspector.ainspect_conversation(normalized, metadata)
        logger.debug(f"[PATCHED CALL] google-genai.async.generate_content_stream - Request decision: {decision.action}")
        set_inspection_context(decision=decision)
        _enforce_decision(decision)

    logger.debug("[PATCHED CALL] google-genai.async.generate_content_stream - calling original method")
    original_stream = await wrapped(*args, **kwargs)
    return AsyncGoogleGenAIStreamingWrapper(original_stream, normalized or [], metadata)


async def _wrap_generate_content_async(wrapped, instance, args, kwargs):
    """
    Async wrapper for Models.generate_content() when called with async client.
    """
    # Extract model name
    model = kwargs.get("model")
    if model is None and args:
        model = args[0]
    model_name = _extract_model_name(model)
    
    set_inspection_context(done=False)
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
    logger.debug(f"╔══════════════════════════════════════════════════════════════")
    logger.debug(f"║ [PATCHED] LLM CALL (async): {model_name}")
    logger.debug(f"║ Operation: google-genai.async.generate_content | LLM Mode: {mode} | Integration: {integration_mode}")
    logger.debug(f"╚══════════════════════════════════════════════════════════════")
    
    # Gateway mode — same google_genai → vertexai fallback as the sync path.
    try:
        gw_settings = resolve_gateway_settings("google_genai")
    except SecurityPolicyError:
        logger.warning(
            "[PATCHED CALL] google-genai.async - No gateway configured "
            "for 'google_genai', trying 'vertexai' gateway as fallback"
        )
        gw_settings = resolve_gateway_settings("vertexai")
    if gw_settings:
        logger.debug(f"[PATCHED CALL] google-genai.async - Gateway mode - routing to AI Defense Gateway")
        import asyncio
        return await asyncio.to_thread(
            _handle_google_genai_gateway_call,
            model_name=model_name,
            contents=contents,
            config=config,
            gw_settings=gw_settings,
        )
    
    # Direct API call (API-mode inspection)
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
        inspector = _get_inspector()
        decision = await inspector.ainspect_conversation(messages_with_response, metadata)
        logger.debug(f"[PATCHED CALL] google-genai.async - Response decision: {decision.action}")
        set_inspection_context(decision=decision, done=True)
        _enforce_decision(decision)
    
    logger.debug(f"[PATCHED CALL] google-genai.async - complete")
    return response


def patch_google_genai() -> bool:
    """
    Patch google-genai SDK for automatic inspection.
    
    Patches Models.generate_content(), Models.generate_content_stream(),
    and their async counterparts to intercept all LLM calls for AI Defense
    inspection.
    
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
        
        # Patch streaming variants so frameworks that use streaming
        # (e.g. Strands) are also inspected.
        try:
            wrapt.wrap_function_wrapper(
                "google.genai.models",
                "Models.generate_content_stream",
                _wrap_generate_content_stream,
            )
            logger.debug("Patched google.genai.models.Models.generate_content_stream")
        except Exception as e:
            logger.debug(f"Models.generate_content_stream not found or failed to patch: {e}")

        try:
            wrapt.wrap_function_wrapper(
                "google.genai.models",
                "AsyncModels.generate_content_stream",
                _wrap_generate_content_stream_async,
            )
            logger.debug("Patched google.genai.models.AsyncModels.generate_content_stream")
        except Exception as e:
            logger.debug(f"AsyncModels.generate_content_stream not found or failed to patch: {e}")

        mark_patched("google_genai")
        logger.info("google-genai patched successfully")
        return True
        
    except Exception as e:
        logger.warning(f"Failed to patch google-genai: {e}")
        return False
