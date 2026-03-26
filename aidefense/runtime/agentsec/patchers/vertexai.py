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
Vertex AI client autopatching.

This module provides automatic inspection for vertexai SDK calls
by patching GenerativeModel.generate_content() and generate_content_async().

It also patches the private _generate_content() method which is called
directly by ChatSession.send_message() (used by AutoGen's GeminiClient),
bypassing the public generate_content() method.

Additionally, it patches the low-level PredictionServiceClient.generate_content()
and stream_generate_content() methods from google-cloud-aiplatform (both v1 and
v1beta1, sync and async).  These are used by LangChain's ChatVertexAI when
GOOGLE_AI_SDK=vertexai, which bypasses GenerativeModel entirely.

Gateway Mode Support:
When llm_integration_mode=gateway, Vertex AI calls are sent directly
to the provider-specific AI Defense Gateway in native format.
"""

import contextvars
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

# Reentrancy guard: when generate_content() wrapper is active, skip the
# _generate_content() wrapper to avoid double inspection.
_vertexai_inspection_active: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "_vertexai_inspection_active", default=False
)

logger = logging.getLogger("aidefense.runtime.agentsec.patchers.vertexai")

# Global inspector instance with thread-safe initialization
_inspector: Optional[LLMInspector] = None
_inspector_lock = threading.Lock()

# Maximum buffer size for streaming inspection (1MB)
# Prevents memory issues with very long streaming responses
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


def _serialize_vertexai_part(part: Any) -> Optional[Dict]:
    """Serialize a Vertex AI Part (proto-plus or dict) to a JSON-compatible dict.

    Handles text, function_call, and function_response parts.
    """
    if isinstance(part, dict):
        return part

    # Try proto-plus to_dict first (vertexai SDK uses proto-plus)
    if hasattr(type(part), "to_dict"):
        try:
            d = type(part).to_dict(part)
            if d:
                return d
        except Exception:
            pass

    # Manual extraction
    result: Dict[str, Any] = {}

    if hasattr(part, "text") and part.text:
        result["text"] = part.text

    if hasattr(part, "function_call") and part.function_call:
        fc = part.function_call
        fc_dict: Dict[str, Any] = {}
        if hasattr(fc, "name") and fc.name:
            fc_dict["name"] = fc.name
        if hasattr(fc, "args") and fc.args is not None:
            args = fc.args
            fc_dict["args"] = dict(args) if hasattr(args, "items") else args
        if fc_dict:
            result["functionCall"] = fc_dict

    if hasattr(part, "function_response") and part.function_response:
        fr = part.function_response
        fr_dict: Dict[str, Any] = {}
        if hasattr(fr, "name") and fr.name:
            fr_dict["name"] = fr.name
        if hasattr(fr, "response") and fr.response is not None:
            resp = fr.response
            fr_dict["response"] = dict(resp) if hasattr(resp, "items") else resp
        if fr_dict:
            result["functionResponse"] = fr_dict

    return result if result else None


def _serialize_vertexai_obj(obj: Any) -> Any:
    """Serialize a Vertex AI SDK object (Tool, ToolConfig, etc.) to JSON-compatible form.

    Handles proto-plus objects, dicts, and lists.  Recursively processes
    dicts so that nested SDK objects are fully converted to plain
    JSON-safe primitives.
    """
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        # Recurse into values – a dict may contain nested SDK objects
        return {k: _serialize_vertexai_obj(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize_vertexai_obj(item) for item in obj]
    # Proto-plus
    if hasattr(type(obj), "to_dict"):
        try:
            return type(obj).to_dict(obj)
        except Exception:
            pass
    # Pydantic
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump(mode="json", by_alias=True, exclude_none=True)
        except (TypeError, Exception):
            try:
                # Keep by_alias=True so field names stay camelCase
                return obj.model_dump(by_alias=True, exclude_none=True)
            except Exception:
                pass
    if hasattr(obj, "dict"):
        try:
            return obj.dict(exclude_none=True)
        except Exception:
            pass
    return obj


def _deep_sanitize_vertexai(obj: Any) -> Any:
    """Recursively convert *obj* to JSON-safe primitives.

    Safety net called when :func:`json.dumps` raises ``TypeError``
    on the assembled Vertex AI request body.
    """
    if obj is None:
        return None
    if isinstance(obj, (bool,)):
        return obj
    if isinstance(obj, (int, float)):
        return obj
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return {str(k): _deep_sanitize_vertexai(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_deep_sanitize_vertexai(v) for v in obj]
    serialized = _serialize_vertexai_obj(obj)
    if serialized is not obj:
        return _deep_sanitize_vertexai(serialized)
    return str(obj)


# ---------------------------------------------------------------------------
# PredictionServiceClient helpers (for ChatVertexAI / GOOGLE_AI_SDK=vertexai)
# ---------------------------------------------------------------------------

_MODEL_RE_SUFFIX = "/models/"


def _extract_model_short_name(fq_model: str) -> str:
    """Extract the short model name from a fully-qualified Vertex AI path.

    ``projects/p/locations/l/publishers/google/models/gemini-2.5-flash``
    -> ``gemini-2.5-flash``
    """
    if _MODEL_RE_SUFFIX in fq_model:
        return fq_model.rsplit(_MODEL_RE_SUFFIX, 1)[-1]
    # Already short
    return fq_model


def _extract_from_prediction_request(args, kwargs):
    """Extract fields from a PredictionServiceClient.generate_content() call.

    The gRPC client accepts either a full ``GenerateContentRequest`` object
    (or dict) via the ``request`` parameter, *or* individual keyword
    arguments (``model``, ``contents``).  We handle both.

    Returns:
        tuple: (request_obj_or_None, model_short_name, contents, fq_model)
    """
    request = kwargs.get("request")
    if request is None and args:
        request = args[0]

    model = kwargs.get("model")
    contents = kwargs.get("contents")

    if request is not None:
        # request can be a GenerateContentRequest proto or dict
        if isinstance(request, dict):
            model = model or request.get("model", "")
            contents = contents or request.get("contents")
        else:
            model = model or getattr(request, "model", "")
            contents = contents or getattr(request, "contents", None)

    fq_model = model or "unknown"
    short_name = _extract_model_short_name(fq_model)
    return request, short_name, contents, fq_model


def _clean_proto_dict(d: Any) -> Any:
    """Remove proto-plus default artifacts from a to_dict() result.

    Proto-plus ``to_dict()`` includes default-value fields like
    ``"thought": false`` and ``"thought_signature": ""``.  The Vertex AI
    gateway chokes on these unknown fields, so strip them.
    """
    if isinstance(d, dict):
        cleaned = {}
        for k, v in d.items():
            # Skip common proto default artifacts
            if k in ("thought", "thoughtSignature", "thought_signature") and not v:
                continue
            cleaned[k] = _clean_proto_dict(v)
        return cleaned
    if isinstance(d, list):
        return [_clean_proto_dict(item) for item in d]
    return d


def _prediction_request_to_body(request, fq_model: str) -> Dict[str, Any]:
    """Convert a GenerateContentRequest proto/dict to a REST-API request body.

    The body is suitable for POSTing to the Vertex AI gateway.
    The ``model`` field is NOT included because it goes in the URL path.

    For proto-plus objects, ``to_json()`` is preferred over ``to_dict()``
    because it produces proper REST-API JSON (camelCase keys, enum strings
    like ``"STRING"`` instead of integers like ``1``).
    """
    if isinstance(request, dict):
        body = {k: v for k, v in request.items() if k != "model" and v}
        return _clean_proto_dict(body)

    # Proto-plus object — prefer to_json() for correct REST field names
    import json as _json
    if hasattr(type(request), "to_json"):
        try:
            json_str = type(request).to_json(request)
            d = _json.loads(json_str)
            d.pop("model", None)
            return _clean_proto_dict(d)
        except Exception as exc:
            logger.debug(f"[PredictionService] to_json() failed: {exc}, trying to_dict()")

    # Fallback: to_dict() (field names may be Python-style snake_case)
    if hasattr(type(request), "to_dict"):
        try:
            d = type(request).to_dict(request)
            d.pop("model", None)
            d = {k: v for k, v in d.items() if v not in (None, "", [], {})}
            return _clean_proto_dict(d)
        except Exception as exc:
            logger.debug(f"[PredictionService] to_dict() failed: {exc}, falling back to manual extraction")

    # Manual fallback
    body: Dict[str, Any] = {}
    if hasattr(request, "contents") and request.contents:
        contents_list = []
        for c in request.contents:
            if hasattr(type(c), "to_json"):
                try:
                    contents_list.append(_json.loads(type(c).to_json(c)))
                    continue
                except Exception:
                    pass
            if hasattr(type(c), "to_dict"):
                contents_list.append(_clean_proto_dict(type(c).to_dict(c)))
            elif isinstance(c, dict):
                contents_list.append(c)
        body["contents"] = contents_list

    for field in ("generation_config", "system_instruction", "tools",
                  "tool_config", "safety_settings"):
        val = getattr(request, field, None)
        if val is not None:
            serialized = _serialize_vertexai_obj(val)
            if serialized:
                camel = "".join(
                    w.capitalize() if i else w
                    for i, w in enumerate(field.split("_"))
                )
                body[camel] = serialized
    return _clean_proto_dict(body)


def _build_prediction_response(response_data: Dict, api_version: str = "v1beta1"):
    """Build a PredictionService GenerateContentResponse from gateway JSON.

    Tries to reconstruct a real proto-plus ``GenerateContentResponse`` so that
    ``ChatVertexAI._gemini_response_to_chat_result()`` works correctly.
    Falls back to the lightweight ``_VertexAIResponseWrapper`` if the proto
    import or parsing fails.
    """
    try:
        if api_version == "v1":
            from google.cloud.aiplatform_v1.types import prediction_service as ps
        else:
            from google.cloud.aiplatform_v1beta1.types import prediction_service as ps

        import json as _json
        # Strip unknown fields that may break proto parsing
        clean = _strip_unknown_fields(response_data)
        resp = ps.GenerateContentResponse.from_json(
            _json.dumps(clean)
        )
        logger.debug(f"[PredictionService GATEWAY] Built GenerateContentResponse proto ({api_version})")
        return resp
    except Exception as exc:
        logger.warning(
            f"[PredictionService GATEWAY] Could not build GenerateContentResponse "
            f"({type(exc).__name__}: {exc}), falling back to wrapper"
        )
        return _VertexAIResponseWrapper(response_data)


def _handle_prediction_gateway_call(
    model_short_name: str,
    fq_model: str,
    request: Any,
    gw_settings: Any,
    api_version: str = "v1beta1",
) -> Any:
    """Route a PredictionServiceClient.generate_content() call through the gateway.

    Args:
        model_short_name: Short model name for URL construction.
        fq_model: Fully-qualified model name for logging.
        request: The original GenerateContentRequest proto/dict.
        gw_settings: Gateway settings from agentsec config.
        api_version: ``"v1"`` or ``"v1beta1"``.

    Returns:
        A ``GenerateContentResponse`` proto (or wrapper fallback).
    """
    import httpx

    if not gw_settings.url:
        raise SecurityPolicyError(
            Decision.block(reasons=["Vertex AI gateway not configured"]),
            "Gateway mode enabled but Vertex AI gateway URL not configured"
        )

    # Auth headers
    if gw_settings.auth_mode == "google_adc":
        from ._google_common import _build_google_auth_header
        auth_headers = _build_google_auth_header(gw_settings)
    else:
        if not gw_settings.api_key:
            raise SecurityPolicyError(
                Decision.block(reasons=["Vertex AI gateway api_key not configured"]),
                "auth_mode=api_key requires gateway_api_key"
            )
        auth_headers = {"Authorization": f"Bearer {gw_settings.api_key}"}

    request_body = _prediction_request_to_body(request, fq_model)

    from ._google_common import (
        build_vertexai_gateway_url,
        vertexai_gateway_post,
        _has_multi_turn_contents,
    )
    try:
        full_url = build_vertexai_gateway_url(
            gw_settings.url, model_short_name, gw_settings, streaming=False,
        )
    except ValueError as exc:
        raise SecurityPolicyError(Decision.block(reasons=[str(exc)]), str(exc))

    logger.debug(f"[PredictionService GATEWAY] URL: {full_url}")
    logger.debug(f"[PredictionService GATEWAY] Model: {model_short_name} (fq: {fq_model})")
    logger.debug(f"[PredictionService GATEWAY] Body keys: {list(request_body.keys())}")

    import json as _json
    try:
        _body_bytes = _json.dumps(request_body).encode("utf-8")
    except TypeError:
        logger.warning("[PredictionService GATEWAY] Applying deep sanitization")
        request_body = _deep_sanitize_vertexai(request_body)
        _body_bytes = _json.dumps(request_body).encode("utf-8")

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"[PredictionService GATEWAY] Body ({len(_body_bytes)} bytes): "
                      f"{_body_bytes[:5000].decode('utf-8', errors='replace')}")

    request_headers = {**auth_headers, "Content-Type": "application/json"}
    try:
        response = vertexai_gateway_post(
            full_url, _body_bytes, request_headers, gw_settings,
        )
        response_data = response.json()

        logger.debug("[PredictionService GATEWAY] Received response")
        set_inspection_context(
            decision=Decision.allow(reasons=["Gateway handled inspection"]),
            done=True,
        )
        return _build_prediction_response(response_data, api_version)

    except httpx.HTTPStatusError as e:
        logger.error(f"[PredictionService GATEWAY] HTTP error: {e}")
        _resp_text = ""
        try:
            _resp_text = e.response.text[:1000] if hasattr(e.response, "text") else ""
            logger.error(f"[PredictionService GATEWAY] HTTP {e.response.status_code} — body: {_resp_text}")
        except Exception:
            pass
        if e.response.status_code == 500 and _has_multi_turn_contents(request_body.get("contents", [])):
            logger.error(
                "[PredictionService GATEWAY] HTTP 500 on multi-turn request. "
                "This is a known gateway bug. See examples/agentsec/KNOWN_ISSUES.md. "
                "Workaround: use llm_integration_mode=api."
            )
        if gw_settings.fail_open:
            logger.warning("[PredictionService GATEWAY] fail_open=True, re-raising")
            set_inspection_context(
                decision=Decision.allow(reasons=["Gateway error, fail_open=True"]),
                done=True,
            )
            raise
        raise SecurityPolicyError(
            Decision.block(reasons=["Gateway unavailable"]),
            f"Gateway HTTP error: {e}",
        )
    except Exception as e:
        logger.error(f"[PredictionService GATEWAY] Error: {e}")
        if gw_settings.fail_open:
            set_inspection_context(
                decision=Decision.allow(reasons=["Gateway error, fail_open=True"]),
                done=True,
            )
            raise
        raise


async def _handle_prediction_gateway_call_async(
    model_short_name: str,
    fq_model: str,
    request: Any,
    gw_settings: Any,
    api_version: str = "v1beta1",
) -> Any:
    """Async variant of _handle_prediction_gateway_call."""
    import httpx

    if not gw_settings.url:
        raise SecurityPolicyError(
            Decision.block(reasons=["Vertex AI gateway not configured"]),
            "Gateway mode enabled but Vertex AI gateway URL not configured"
        )

    if gw_settings.auth_mode == "google_adc":
        from ._google_common import _build_google_auth_header
        auth_headers = _build_google_auth_header(gw_settings)
    else:
        if not gw_settings.api_key:
            raise SecurityPolicyError(
                Decision.block(reasons=["Vertex AI gateway api_key not configured"]),
                "auth_mode=api_key requires gateway_api_key"
            )
        auth_headers = {"Authorization": f"Bearer {gw_settings.api_key}"}

    request_body = _prediction_request_to_body(request, fq_model)

    from ._google_common import (
        build_vertexai_gateway_url,
        vertexai_gateway_post_async,
        _has_multi_turn_contents,
    )
    try:
        full_url = build_vertexai_gateway_url(
            gw_settings.url, model_short_name, gw_settings, streaming=False,
        )
    except ValueError as exc:
        raise SecurityPolicyError(Decision.block(reasons=[str(exc)]), str(exc))

    logger.debug(f"[PredictionService GATEWAY async] URL: {full_url}")

    import json as _json
    try:
        _body_bytes = _json.dumps(request_body).encode("utf-8")
    except TypeError:
        request_body = _deep_sanitize_vertexai(request_body)
        _body_bytes = _json.dumps(request_body).encode("utf-8")

    request_headers = {**auth_headers, "Content-Type": "application/json"}
    try:
        response = await vertexai_gateway_post_async(
            full_url, _body_bytes, request_headers, gw_settings,
        )
        response_data = response.json()

        logger.debug("[PredictionService GATEWAY async] Received response")
        set_inspection_context(
            decision=Decision.allow(reasons=["Gateway handled inspection"]),
            done=True,
        )
        return _build_prediction_response(response_data, api_version)

    except httpx.HTTPStatusError as e:
        logger.error(f"[PredictionService GATEWAY async] HTTP error: {e}")
        if e.response.status_code == 500 and _has_multi_turn_contents(request_body.get("contents", [])):
            logger.error(
                "[PredictionService GATEWAY async] HTTP 500 on multi-turn request. "
                "This is a known gateway bug. See examples/agentsec/KNOWN_ISSUES.md. "
                "Workaround: use llm_integration_mode=api."
            )
        if gw_settings.fail_open:
            set_inspection_context(
                decision=Decision.allow(reasons=["Gateway error, fail_open=True"]),
                done=True,
            )
            raise
        raise SecurityPolicyError(
            Decision.block(reasons=["Gateway unavailable"]),
            f"Gateway HTTP error: {e}",
        )
    except Exception as e:
        logger.error(f"[PredictionService GATEWAY async] Error: {e}")
        if gw_settings.fail_open:
            set_inspection_context(
                decision=Decision.allow(reasons=["Gateway error, fail_open=True"]),
                done=True,
            )
            raise
        raise


# ---------------------------------------------------------------------------
# PredictionServiceClient wrappers
# ---------------------------------------------------------------------------

def _inspect_prediction_sync(wrapped, instance, args, kwargs, entry="generate_content"):
    """Shared sync inspection logic for PredictionServiceClient methods."""
    request, model_short, contents, fq_model = _extract_from_prediction_request(args, kwargs)

    set_inspection_context(done=False)
    if not _should_inspect():
        logger.debug(f"[PATCHED CALL] PredictionService.{entry} - inspection skipped")
        return wrapped(*args, **kwargs)

    normalized = normalize_google_messages(contents)
    metadata = get_inspection_context().metadata
    metadata["provider"] = "vertexai"
    metadata["model"] = model_short

    mode = _state.get_llm_mode()
    integration_mode = _state.get_llm_integration_mode()
    logger.debug("╔══════════════════════════════════════════════════════════════")
    logger.debug(f"║ [PATCHED] LLM CALL: {model_short}")
    logger.debug(f"║ Operation: PredictionService.{entry} | LLM Mode: {mode} | Integration: {integration_mode}")
    logger.debug("╚══════════════════════════════════════════════════════════════")

    # Gateway mode
    gw_settings = resolve_gateway_settings("vertexai")
    if gw_settings:
        logger.debug(f"[PATCHED CALL] PredictionService.{entry} - Gateway mode")
        return _handle_prediction_gateway_call(
            model_short_name=model_short,
            fq_model=fq_model,
            request=request if request is not None else kwargs,
            gw_settings=gw_settings,
        )

    # API mode: pre-inspect request
    if normalized:
        logger.debug(f"[PATCHED CALL] PredictionService.{entry} - Request inspection ({len(normalized)} messages)")
        inspector = _get_inspector()
        decision = inspector.inspect_conversation(normalized, metadata)
        logger.debug(f"[PATCHED CALL] PredictionService.{entry} - Request decision: {decision.action}")
        set_inspection_context(decision=decision)
        _enforce_decision(decision)

    logger.debug(f"[PATCHED CALL] PredictionService.{entry} - calling original method")
    response = wrapped(*args, **kwargs)

    # Post-inspect response
    assistant_content = extract_google_response(response)
    if assistant_content and normalized:
        logger.debug(f"[PATCHED CALL] PredictionService.{entry} - Response inspection ({len(assistant_content)} chars)")
        messages_with_response = normalized + [
            {"role": "assistant", "content": assistant_content}
        ]
        inspector = _get_inspector()
        decision = inspector.inspect_conversation(messages_with_response, metadata)
        logger.debug(f"[PATCHED CALL] PredictionService.{entry} - Response decision: {decision.action}")
        set_inspection_context(decision=decision, done=True)
        _enforce_decision(decision)

    logger.debug(f"[PATCHED CALL] PredictionService.{entry} - complete")
    return response


def _inspect_prediction_stream_sync(wrapped, instance, args, kwargs):
    """Sync inspection for PredictionServiceClient.stream_generate_content()."""
    request, model_short, contents, fq_model = _extract_from_prediction_request(args, kwargs)

    set_inspection_context(done=False)
    if not _should_inspect():
        logger.debug("[PATCHED CALL] PredictionService.stream_generate_content - inspection skipped")
        return wrapped(*args, **kwargs)

    normalized = normalize_google_messages(contents)
    metadata = get_inspection_context().metadata
    metadata["provider"] = "vertexai"
    metadata["model"] = model_short

    mode = _state.get_llm_mode()
    integration_mode = _state.get_llm_integration_mode()
    logger.debug("╔══════════════════════════════════════════════════════════════")
    logger.debug(f"║ [PATCHED] LLM CALL (stream): {model_short}")
    logger.debug(f"║ Operation: PredictionService.stream_generate_content | LLM Mode: {mode} | Integration: {integration_mode}")
    logger.debug("╚══════════════════════════════════════════════════════════════")

    # Gateway mode: non-streaming call, wrap as single-chunk iterator
    gw_settings = resolve_gateway_settings("vertexai")
    if gw_settings:
        logger.debug("[PATCHED CALL] PredictionService.stream_generate_content - Gateway mode (non-streaming proxy)")
        resp = _handle_prediction_gateway_call(
            model_short_name=model_short,
            fq_model=fq_model,
            request=request if request is not None else kwargs,
            gw_settings=gw_settings,
        )
        return iter([resp])

    # API mode: pre-inspect, then wrap stream for post-inspection
    if normalized:
        logger.debug(f"[PATCHED CALL] PredictionService.stream_generate_content - Request inspection ({len(normalized)} messages)")
        inspector = _get_inspector()
        decision = inspector.inspect_conversation(normalized, metadata)
        logger.debug(f"[PATCHED CALL] PredictionService.stream_generate_content - Request decision: {decision.action}")
        set_inspection_context(decision=decision)
        _enforce_decision(decision)

    logger.debug("[PATCHED CALL] PredictionService.stream_generate_content - calling original method")
    original_stream = wrapped(*args, **kwargs)
    return GoogleStreamingInspectionWrapper(original_stream, normalized or [], metadata)


async def _inspect_prediction_async(wrapped, instance, args, kwargs, entry="generate_content"):
    """Shared async inspection logic for PredictionServiceAsyncClient methods."""
    request, model_short, contents, fq_model = _extract_from_prediction_request(args, kwargs)

    set_inspection_context(done=False)
    if not _should_inspect():
        logger.debug(f"[PATCHED CALL] PredictionService.{entry} (async) - inspection skipped")
        return await wrapped(*args, **kwargs)

    normalized = normalize_google_messages(contents)
    metadata = get_inspection_context().metadata
    metadata["provider"] = "vertexai"
    metadata["model"] = model_short

    mode = _state.get_llm_mode()
    integration_mode = _state.get_llm_integration_mode()
    logger.debug("╔══════════════════════════════════════════════════════════════")
    logger.debug(f"║ [PATCHED] LLM CALL (async): {model_short}")
    logger.debug(f"║ Operation: PredictionService.{entry} (async) | LLM Mode: {mode} | Integration: {integration_mode}")
    logger.debug("╚══════════════════════════════════════════════════════════════")

    # Gateway mode
    gw_settings = resolve_gateway_settings("vertexai")
    if gw_settings:
        logger.debug(f"[PATCHED CALL] PredictionService.{entry} (async) - Gateway mode")
        return await _handle_prediction_gateway_call_async(
            model_short_name=model_short,
            fq_model=fq_model,
            request=request if request is not None else kwargs,
            gw_settings=gw_settings,
        )

    # API mode: pre-inspect
    if normalized:
        logger.debug(f"[PATCHED CALL] PredictionService.{entry} (async) - Request inspection ({len(normalized)} messages)")
        inspector = _get_inspector()
        decision = await inspector.ainspect_conversation(normalized, metadata)
        logger.debug(f"[PATCHED CALL] PredictionService.{entry} (async) - Request decision: {decision.action}")
        set_inspection_context(decision=decision)
        _enforce_decision(decision)

    logger.debug(f"[PATCHED CALL] PredictionService.{entry} (async) - calling original method")
    response = await wrapped(*args, **kwargs)

    # Post-inspect response
    assistant_content = extract_google_response(response)
    if assistant_content and normalized:
        messages_with_response = normalized + [
            {"role": "assistant", "content": assistant_content}
        ]
        resp_inspector = _get_inspector()
        decision = await resp_inspector.ainspect_conversation(messages_with_response, metadata)
        logger.debug(f"[PATCHED CALL] PredictionService.{entry} (async) - Response decision: {decision.action}")
        set_inspection_context(decision=decision, done=True)
        _enforce_decision(decision)

    logger.debug(f"[PATCHED CALL] PredictionService.{entry} (async) - complete")
    return response


async def _inspect_prediction_stream_async(wrapped, instance, args, kwargs):
    """Async inspection for PredictionServiceAsyncClient.stream_generate_content()."""
    request, model_short, contents, fq_model = _extract_from_prediction_request(args, kwargs)

    set_inspection_context(done=False)
    if not _should_inspect():
        logger.debug("[PATCHED CALL] PredictionService.stream_generate_content (async) - inspection skipped")
        return await wrapped(*args, **kwargs)

    normalized = normalize_google_messages(contents)
    metadata = get_inspection_context().metadata
    metadata["provider"] = "vertexai"
    metadata["model"] = model_short

    mode = _state.get_llm_mode()
    integration_mode = _state.get_llm_integration_mode()
    logger.debug("╔══════════════════════════════════════════════════════════════")
    logger.debug(f"║ [PATCHED] LLM CALL (async stream): {model_short}")
    logger.debug(f"║ Operation: PredictionService.stream_generate_content (async) | LLM Mode: {mode} | Integration: {integration_mode}")
    logger.debug("╚══════════════════════════════════════════════════════════════")

    # Gateway mode
    gw_settings = resolve_gateway_settings("vertexai")
    if gw_settings:
        logger.debug("[PATCHED CALL] PredictionService.stream_generate_content (async) - Gateway mode")
        resp = await _handle_prediction_gateway_call_async(
            model_short_name=model_short,
            fq_model=fq_model,
            request=request if request is not None else kwargs,
            gw_settings=gw_settings,
        )

        async def _single_chunk():
            yield resp

        return _single_chunk()

    # API mode: pre-inspect, then wrap stream
    if normalized:
        logger.debug(f"[PATCHED CALL] PredictionService.stream_generate_content (async) - Request inspection ({len(normalized)} messages)")
        inspector = _get_inspector()
        decision = await inspector.ainspect_conversation(normalized, metadata)
        logger.debug(f"[PATCHED CALL] PredictionService.stream_generate_content (async) - Request decision: {decision.action}")
        set_inspection_context(decision=decision)
        _enforce_decision(decision)

    logger.debug("[PATCHED CALL] PredictionService.stream_generate_content (async) - calling original method")
    original_stream = await wrapped(*args, **kwargs)
    return AsyncGoogleStreamingInspectionWrapper(original_stream, normalized or [], metadata)


def _wrap_prediction_generate_content(wrapped, instance, args, kwargs):
    """Wrapper for PredictionServiceClient.generate_content()."""
    return _inspect_prediction_sync(wrapped, instance, args, kwargs, entry="generate_content")


def _wrap_prediction_stream_generate_content(wrapped, instance, args, kwargs):
    """Wrapper for PredictionServiceClient.stream_generate_content()."""
    return _inspect_prediction_stream_sync(wrapped, instance, args, kwargs)


async def _wrap_prediction_generate_content_async(wrapped, instance, args, kwargs):
    """Wrapper for PredictionServiceAsyncClient.generate_content()."""
    return await _inspect_prediction_async(wrapped, instance, args, kwargs, entry="generate_content")


async def _wrap_prediction_stream_generate_content_async(wrapped, instance, args, kwargs):
    """Wrapper for PredictionServiceAsyncClient.stream_generate_content()."""
    return await _inspect_prediction_stream_async(wrapped, instance, args, kwargs)


# ---------------------------------------------------------------------------
# GenerativeModel gateway call handler (original)
# ---------------------------------------------------------------------------

def _handle_vertexai_gateway_call(
    model_name: str,
    contents: Any,
    gw_settings: Any,
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
    
    if not gw_settings.url:
        logger.warning("Gateway mode enabled but Vertex AI gateway URL not configured")
        raise SecurityPolicyError(
            Decision.block(reasons=["Vertex AI gateway not configured"]),
            "Gateway mode enabled but Vertex AI gateway not configured (check gateway_mode.llm_gateways for a vertexai provider entry in config)"
        )
    
    # Build auth headers based on auth_mode
    if gw_settings.auth_mode == "google_adc":
        from ._google_common import _build_google_auth_header
        auth_headers = _build_google_auth_header(gw_settings)
    else:
        # api_key mode
        if not gw_settings.api_key:
            logger.warning("Gateway mode enabled but Vertex AI gateway api_key not configured")
            raise SecurityPolicyError(
                Decision.block(reasons=["Vertex AI gateway api_key not configured"]),
                "Gateway mode enabled but Vertex AI gateway api_key not configured (auth_mode=api_key requires gateway_api_key)"
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
                elif hasattr(item, "role") and hasattr(item, "parts"):
                    parts_list = []
                    for part in item.parts:
                        part_dict = _serialize_vertexai_part(part)
                        if part_dict:
                            parts_list.append(part_dict)
                    if parts_list:
                        contents_list.append({"role": item.role, "parts": parts_list})
    
    # Build native Vertex AI request body (model is in URL path, not body)
    request_body = {
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
        request_body["tools"] = _serialize_vertexai_obj(tools)
    if tool_config:
        request_body["toolConfig"] = _serialize_vertexai_obj(tool_config)
    if system_instruction:
        if isinstance(system_instruction, str):
            request_body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        elif hasattr(system_instruction, "parts"):
            parts = [{"text": p.text} for p in system_instruction.parts if hasattr(p, "text")]
            request_body["systemInstruction"] = {"parts": parts}
    
    # Build full Vertex AI gateway URL with API path
    from ._google_common import (
        build_vertexai_gateway_url,
        vertexai_gateway_post,
        _has_multi_turn_contents,
    )
    try:
        full_gateway_url = build_vertexai_gateway_url(
            gw_settings.url, model_name, gw_settings, streaming=False,
        )
    except ValueError as exc:
        raise SecurityPolicyError(
            Decision.block(reasons=[str(exc)]),
            str(exc),
        )
    
    logger.debug(f"[GATEWAY] Sending native Vertex AI request to gateway")
    logger.debug(f"[GATEWAY] URL: {full_gateway_url}")
    logger.debug(f"[GATEWAY] Model: {model_name}")
    logger.debug(f"[GATEWAY] Request body keys: {list(request_body.keys())}")

    # Pre-serialize to catch non-JSON-serializable objects early and
    # ensure the exact bytes we intend are sent to the gateway.
    import json as _json
    try:
        _body_bytes = _json.dumps(request_body).encode("utf-8")
    except TypeError:
        logger.warning("[GATEWAY] request_body contains non-JSON-serializable objects, applying deep sanitization")
        request_body = _deep_sanitize_vertexai(request_body)
        _body_bytes = _json.dumps(request_body).encode("utf-8")

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"[GATEWAY] Full request body ({len(_body_bytes)} bytes): {_body_bytes[:5000].decode('utf-8', errors='replace')}")

    request_headers = {**auth_headers, "Content-Type": "application/json"}
    try:
        response = vertexai_gateway_post(
            full_gateway_url, _body_bytes, request_headers, gw_settings,
        )
        response_data = response.json()
        
        logger.debug(f"[GATEWAY] Received native Vertex AI response from gateway")
        set_inspection_context(decision=Decision.allow(reasons=["Gateway handled inspection"]), done=True)
        
        # Build a proper GenerationResponse (or wrapper fallback) for attribute access
        return _build_vertexai_response(response_data)
        
    except httpx.HTTPStatusError as e:
        logger.error(f"[GATEWAY] HTTP error: {e}")
        _resp_text = ""
        try:
            _resp_text = e.response.text[:1000] if hasattr(e.response, 'text') else ""
            logger.error(f"[GATEWAY] HTTP {e.response.status_code} — body preview: {_resp_text}")
        except Exception:
            pass
        if "Invalid JSON payload" in _resp_text:
            logger.error(
                "[GATEWAY] The AI Defense gateway returned 'Invalid JSON "
                "payload'.  This is a known gateway limitation when the "
                "request body exceeds ~2700 bytes (e.g. requests with "
                "multiple tool declarations).  Workaround: use "
                "llm_integration_mode=api until the gateway team resolves "
                "this issue."
            )
        if gw_settings.fail_open:
            logger.warning(f"[GATEWAY] fail_open=True, re-raising original HTTP error for caller to handle")
            set_inspection_context(decision=Decision.allow(reasons=["Gateway error, fail_open=True"]), done=True)
            raise
        else:
            raise SecurityPolicyError(
                Decision.block(reasons=["Gateway unavailable"]),
                f"Gateway HTTP error: {e}"
            )
    except Exception as e:
        logger.error(f"[GATEWAY] Error: {e}")
        if gw_settings.fail_open:
            logger.warning(f"[GATEWAY] fail_open=True, re-raising original error for caller to handle")
            set_inspection_context(decision=Decision.allow(reasons=["Gateway error, fail_open=True"]), done=True)
            raise
        raise


def _build_vertexai_response(response_data: Dict):
    """Build a response from gateway JSON data.

    Tries to construct a real ``GenerationResponse`` via ``from_dict()`` so
    that frameworks performing ``isinstance`` checks (e.g. AG2/autogen) work
    correctly.  Falls back to the lightweight ``_VertexAIResponseWrapper`` if
    the Vertex AI SDK is unavailable or the dict cannot be parsed.
    """
    try:
        from vertexai.generative_models import GenerationResponse as _GenResp

        # The gateway may return fields (e.g. usageMetadata.trafficType)
        # that are newer than the local protobuf schema.  Strip them to
        # avoid ParseError.
        clean = _strip_unknown_fields(response_data)
        resp = _GenResp.from_dict(clean)
        logger.debug("[GATEWAY] Built native GenerationResponse from gateway data")
        return resp
    except Exception as exc:
        logger.warning(
            f"[GATEWAY] Could not build native GenerationResponse "
            f"({type(exc).__name__}: {exc}), using wrapper instead. "
            f"Response keys: {list(response_data.keys()) if isinstance(response_data, dict) else 'N/A'}"
        )
        return _VertexAIResponseWrapper(response_data)


# Fields that the gateway may include but the local SDK protobuf doesn't know.
_USAGE_METADATA_KNOWN_FIELDS = {
    "promptTokenCount", "candidatesTokenCount", "totalTokenCount",
    "cachedContentTokenCount", "prompt_token_count", "candidates_token_count",
    "total_token_count", "cached_content_token_count",
}


def _strip_unknown_fields(data: Dict) -> Dict:
    """Remove fields from the response dict that are not in the local protobuf schema.

    Only touches ``usageMetadata`` today; extend as needed.
    """
    import copy
    data = copy.deepcopy(data)

    # Clean usageMetadata – keep only known fields
    um_key = "usageMetadata" if "usageMetadata" in data else "usage_metadata"
    if um_key in data and isinstance(data[um_key], dict):
        data[um_key] = {
            k: v for k, v in data[um_key].items()
            if k in _USAGE_METADATA_KNOWN_FIELDS
        }

    return data


class _VertexAIResponseWrapper:
    """Wrapper to provide attribute access to native Vertex AI response dict."""
    
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
    def text(self):
        """Extract text from first candidate's first part."""
        try:
            return self.candidates[0].content.parts[0].text
        except (IndexError, AttributeError):
            return ""
    
    @property
    def usage_metadata(self):
        """Return usage metadata dict (or None) for ChatVertexAI compatibility."""
        return self._data.get("usageMetadata") or self._data.get("usage_metadata")

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
    
    @role.setter
    def role(self, value):
        self._data["role"] = value
    
    @property
    def parts(self):
        if self._parts is None:
            self._parts = [_PartWrapper(p) for p in self._data.get("parts", [])]
        return self._parts


class _PartWrapper:
    """Wrapper for part in Vertex AI response.

    Handles text parts, functionCall parts (model requesting a tool call),
    and functionResponse parts (tool execution results).
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
            return _VertexFunctionCallWrapper(fc_data)
        return None

    @property
    def function_response(self):
        """Return a FunctionResponse-like object if this part is a function response."""
        fr_data = self._data.get("functionResponse") or self._data.get("function_response")
        if fr_data:
            return _VertexFunctionResponseWrapper(fr_data)
        return None


class _VertexFunctionCallWrapper:
    """Wrapper for functionCall in gateway response."""

    def __init__(self, data: Dict):
        self._data = data

    @property
    def name(self) -> str:
        return self._data.get("name", "")

    @property
    def args(self) -> Dict:
        return self._data.get("args", {})


class _VertexFunctionResponseWrapper:
    """Wrapper for functionResponse in gateway response."""

    def __init__(self, data: Dict):
        self._data = data

    @property
    def name(self) -> str:
        return self._data.get("name", "")

    @property
    def response(self) -> Dict:
        return self._data.get("response", {})


def _handle_vertexai_gateway_call_streaming(
    model_name: str,
    contents: Any,
    gw_settings: Any,
    generation_config: Optional[Dict] = None,
    tools: Optional[List] = None,
    tool_config: Optional[Dict] = None,
    system_instruction: Optional[Any] = None,
) -> Any:
    """Handle Vertex AI streaming call via AI Defense Gateway.

    Calls the non-streaming gateway endpoint and wraps the result in a
    fake streaming wrapper that yields the full response as a single chunk,
    following the same pattern used by Bedrock's
    ``_handle_bedrock_gateway_call_streaming``.
    """
    response_wrapper = _handle_vertexai_gateway_call(
        model_name=model_name,
        contents=contents,
        gw_settings=gw_settings,
        generation_config=generation_config,
        tools=tools,
        tool_config=tool_config,
        system_instruction=system_instruction,
    )
    return _VertexAIGatewayStreamWrapper(response_wrapper)


async def _handle_vertexai_gateway_call_streaming_async(
    model_name: str,
    contents: Any,
    gw_settings: Any,
    generation_config: Optional[Dict] = None,
    tools: Optional[List] = None,
    tool_config: Optional[Dict] = None,
    system_instruction: Optional[Any] = None,
) -> Any:
    """Async version of _handle_vertexai_gateway_call_streaming."""
    response_wrapper = await _handle_vertexai_gateway_call_async(
        model_name=model_name,
        contents=contents,
        gw_settings=gw_settings,
        generation_config=generation_config,
        tools=tools,
        tool_config=tool_config,
        system_instruction=system_instruction,
    )
    return _AsyncVertexAIGatewayStreamWrapper(response_wrapper)


class _VertexAIGatewayStreamWrapper:
    """Wrap a non-streaming gateway response as a fake Vertex AI stream.

    Yields the full response as a single chunk so that callers expecting
    an iterable stream work correctly.  The chunk exposes the same
    ``candidates[].content.parts[].text`` attribute path as a real
    Vertex AI streaming chunk.
    """

    def __init__(self, response_wrapper):
        self._response = response_wrapper
        self._yielded = False

    def __iter__(self):
        return self

    def __next__(self):
        if not self._yielded:
            self._yielded = True
            return self._response
        raise StopIteration


class _AsyncVertexAIGatewayStreamWrapper:
    """Async version of _VertexAIGatewayStreamWrapper."""

    def __init__(self, response_wrapper):
        self._response = response_wrapper
        self._yielded = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._yielded:
            self._yielded = True
            return self._response
        raise StopAsyncIteration


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
            
            # Extract text from chunk, with size limit to prevent memory issues
            from ._google_common import extract_streaming_chunk_text
            text = extract_streaming_chunk_text(chunk)
            if text:
                current_size = sum(len(t) for t in self._collected_text)
                if current_size < MAX_STREAMING_BUFFER_SIZE:
                    remaining_capacity = MAX_STREAMING_BUFFER_SIZE - current_size
                    self._collected_text.append(text[:remaining_capacity])
            
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
            # Truncate buffer if it exceeds maximum size to prevent memory issues
            if len(full_response) > MAX_STREAMING_BUFFER_SIZE:
                logger.warning(
                    f"Streaming buffer exceeded {MAX_STREAMING_BUFFER_SIZE} bytes "
                    f"({len(full_response)} bytes), truncating for inspection"
                )
                full_response = full_response[:MAX_STREAMING_BUFFER_SIZE]
            
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
            
            # Extract text from chunk, with size limit to prevent memory issues
            from ._google_common import extract_streaming_chunk_text
            text = extract_streaming_chunk_text(chunk)
            if text:
                current_size = sum(len(t) for t in self._collected_text)
                if current_size < MAX_STREAMING_BUFFER_SIZE:
                    remaining_capacity = MAX_STREAMING_BUFFER_SIZE - current_size
                    self._collected_text.append(text[:remaining_capacity])
            
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
            # Truncate buffer if it exceeds maximum size to prevent memory issues
            if len(full_response) > MAX_STREAMING_BUFFER_SIZE:
                logger.warning(
                    f"Streaming buffer exceeded {MAX_STREAMING_BUFFER_SIZE} bytes "
                    f"({len(full_response)} bytes), truncating for inspection"
                )
                full_response = full_response[:MAX_STREAMING_BUFFER_SIZE]
            
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
    gw_settings: Any,
    generation_config: Optional[Dict] = None,
    tools: Optional[List] = None,
    tool_config: Optional[Dict] = None,
    system_instruction: Optional[Any] = None,
) -> Any:
    """Async version of _handle_vertexai_gateway_call."""
    import httpx
    
    gateway_url = gw_settings.url
    if not gateway_url:
        logger.warning("Gateway mode enabled but Vertex AI gateway URL not configured")
        raise SecurityPolicyError(
            Decision.block(reasons=["Vertex AI gateway not configured"]),
            "Gateway mode enabled but Vertex AI gateway not configured (check gateway_mode.llm_gateways for a vertexai provider entry in config)"
        )
    
    # Build auth headers based on auth_mode
    if gw_settings.auth_mode == "google_adc":
        from ._google_common import _build_google_auth_header
        auth_headers = _build_google_auth_header(gw_settings)
    else:
        if not gw_settings.api_key:
            logger.warning("Gateway mode enabled but Vertex AI gateway api_key not configured")
            raise SecurityPolicyError(
                Decision.block(reasons=["Vertex AI gateway api_key not configured"]),
                "Gateway mode enabled but Vertex AI gateway api_key not configured (auth_mode=api_key requires gateway_api_key)"
            )
        auth_headers = {"Authorization": f"Bearer {gw_settings.api_key}"}
    
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
                        part_dict = _serialize_vertexai_part(part)
                        if part_dict:
                            parts_list.append(part_dict)
                    if parts_list:
                        contents_list.append({"role": item.role, "parts": parts_list})
    
    # Build native Vertex AI request body (model is in URL path, not body)
    request_body = {
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
        request_body["tools"] = _serialize_vertexai_obj(tools)
    if tool_config:
        request_body["toolConfig"] = _serialize_vertexai_obj(tool_config)
    if system_instruction:
        if isinstance(system_instruction, str):
            request_body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        elif hasattr(system_instruction, "parts"):
            parts = [{"text": p.text} for p in system_instruction.parts if hasattr(p, "text")]
            request_body["systemInstruction"] = {"parts": parts}
    
    # Build full Vertex AI gateway URL with API path
    from ._google_common import (
        build_vertexai_gateway_url,
        vertexai_gateway_post_async,
        _has_multi_turn_contents,
    )
    try:
        full_gateway_url = build_vertexai_gateway_url(
            gw_settings.url, model_name, gw_settings, streaming=False,
        )
    except ValueError as exc:
        raise SecurityPolicyError(
            Decision.block(reasons=[str(exc)]),
            str(exc),
        )
    
    logger.debug(f"[GATEWAY] Sending native Vertex AI request to gateway (async)")
    logger.debug(f"[GATEWAY] URL: {full_gateway_url}")
    
    import json as _json
    try:
        _body_bytes = _json.dumps(request_body).encode("utf-8")
    except TypeError:
        request_body = _deep_sanitize_vertexai(request_body)
        _body_bytes = _json.dumps(request_body).encode("utf-8")
    
    request_headers = {**auth_headers, "Content-Type": "application/json"}
    try:
        response = await vertexai_gateway_post_async(
            full_gateway_url, _body_bytes, request_headers, gw_settings,
        )
        response_data = response.json()
        
        logger.debug(f"[GATEWAY] Received native Vertex AI response from gateway (async)")
        set_inspection_context(decision=Decision.allow(reasons=["Gateway handled inspection"]), done=True)
        
        return _build_vertexai_response(response_data)
        
    except httpx.HTTPStatusError as e:
        logger.error(f"[GATEWAY] HTTP error: {e}")
        if e.response.status_code == 500 and _has_multi_turn_contents(contents_list):
            logger.error(
                "[GATEWAY] HTTP 500 on multi-turn request (contents has %d messages). "
                "This is a known gateway bug. See examples/agentsec/KNOWN_ISSUES.md. "
                "Workaround: use llm_integration_mode=api.",
                len(contents_list),
            )
        if gw_settings.fail_open:
            logger.warning(f"[GATEWAY] fail_open=True, re-raising original HTTP error for caller to handle")
            set_inspection_context(decision=Decision.allow(reasons=["Gateway error, fail_open=True"]), done=True)
            raise
        raise SecurityPolicyError(
            Decision.block(reasons=["Gateway unavailable"]),
            f"Gateway HTTP error: {e}"
        )
    except Exception as e:
        logger.error(f"[GATEWAY] Error: {e}")
        if gw_settings.fail_open:
            logger.warning(f"[GATEWAY] fail_open=True, re-raising original error for caller to handle")
            set_inspection_context(decision=Decision.allow(reasons=["Gateway error, fail_open=True"]), done=True)
            raise
        raise


def _wrap_generate_content(wrapped, instance, args, kwargs):
    """Wrapper for GenerativeModel.generate_content().
    
    Supports both API mode (inspection via AI Defense API) and Gateway mode
    (routing through AI Defense Gateway with format conversion).
    
    Sets reentrancy guard so that the private _generate_content() wrapper
    (which generate_content() calls internally) does not double-inspect.
    """
    # Set reentrancy guard to prevent _generate_content wrapper from firing
    token = _vertexai_inspection_active.set(True)
    try:
        return _inspect_vertexai_sync(wrapped, instance, args, kwargs, entry="generate_content")
    finally:
        _vertexai_inspection_active.reset(token)


def _wrap_private_generate_content(wrapped, instance, args, kwargs):
    """Wrapper for GenerativeModel._generate_content() (private method).
    
    This catches calls from ChatSession.send_message() which calls
    _generate_content() directly, bypassing the public generate_content().
    
    If the reentrancy guard is set (meaning we're already inside the
    generate_content wrapper), this is a no-op pass-through.
    """
    if _vertexai_inspection_active.get():
        # Already being inspected by generate_content wrapper
        return wrapped(*args, **kwargs)
    
    # Direct call (e.g., from ChatSession.send_message) - apply inspection
    token = _vertexai_inspection_active.set(True)
    try:
        return _inspect_vertexai_sync(wrapped, instance, args, kwargs, entry="_generate_content")
    finally:
        _vertexai_inspection_active.reset(token)


def _inspect_vertexai_sync(wrapped, instance, args, kwargs, entry="generate_content"):
    """Shared sync inspection logic for both generate_content and _generate_content."""
    # Get model name
    model_name = "unknown"
    if hasattr(instance, "model_name"):
        model_name = instance.model_name
    elif hasattr(instance, "_model_name"):
        model_name = instance._model_name
    
    set_inspection_context(done=False)
    if not _should_inspect():
        logger.debug(f"[PATCHED CALL] VertexAI.{entry} - inspection skipped (mode=off or already done)")
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
    logger.debug(f"╔══════════════════════════════════════════════════════════════")
    logger.debug(f"║ [PATCHED] LLM CALL: {model_name}")
    logger.debug(f"║ Operation: VertexAI.{entry} | LLM Mode: {mode} | Integration: {integration_mode}")
    logger.debug(f"╚══════════════════════════════════════════════════════════════")
    
    # Gateway mode: route through AI Defense Gateway with format conversion
    gw_settings = resolve_gateway_settings("vertexai")
    if gw_settings:
        logger.debug(f"[PATCHED CALL] VertexAI.{entry} - Gateway mode - routing to AI Defense Gateway")
        if not stream:
            return _handle_vertexai_gateway_call(
                model_name=model_name,
                contents=contents,
                gw_settings=gw_settings,
                generation_config=kwargs.get("generation_config"),
                tools=kwargs.get("tools"),
                tool_config=kwargs.get("tool_config"),
                system_instruction=getattr(instance, "system_instruction", None),
            )
        else:
            logger.debug(f"[PATCHED CALL] VertexAI.{entry} - Gateway mode streaming via non-streaming gateway call")
            return _handle_vertexai_gateway_call_streaming(
                model_name=model_name,
                contents=contents,
                gw_settings=gw_settings,
                generation_config=kwargs.get("generation_config"),
                tools=kwargs.get("tools"),
                tool_config=kwargs.get("tool_config"),
                system_instruction=getattr(instance, "system_instruction", None),
            )
    
    # Direct API call (API-mode inspection)
    # Pre-call inspection
    if normalized:
        logger.debug(f"[PATCHED CALL] VertexAI.{entry} - Request inspection ({len(normalized)} messages)")
        inspector = _get_inspector()
        decision = inspector.inspect_conversation(normalized, metadata)
        logger.debug(f"[PATCHED CALL] VertexAI.{entry} - Request decision: {decision.action}")
        set_inspection_context(decision=decision)
        _enforce_decision(decision)
    
    # Call the original
    logger.debug(f"[PATCHED CALL] VertexAI.{entry} - calling original method")
    response = wrapped(*args, **kwargs)
    
    # Handle streaming vs non-streaming
    if stream:
        logger.debug(f"[PATCHED CALL] VertexAI.{entry} - streaming response, wrapping for inspection")
        return GoogleStreamingInspectionWrapper(response, normalized, metadata)
    
    # Post-call inspection for non-streaming
    assistant_content = extract_google_response(response)
    if assistant_content and normalized:
        logger.debug(f"[PATCHED CALL] VertexAI.{entry} - Response inspection (response: {len(assistant_content)} chars)")
        messages_with_response = normalized + [
            {"role": "assistant", "content": assistant_content}
        ]
        inspector = _get_inspector()
        decision = inspector.inspect_conversation(messages_with_response, metadata)
        logger.debug(f"[PATCHED CALL] VertexAI.{entry} - Response decision: {decision.action}")
        set_inspection_context(decision=decision, done=True)
        _enforce_decision(decision)
    
    logger.debug(f"[PATCHED CALL] VertexAI.{entry} - complete")
    return response


async def _wrap_generate_content_async(wrapped, instance, args, kwargs):
    """Async wrapper for GenerativeModel.generate_content_async().
    
    Sets reentrancy guard so that the private _generate_content_async() wrapper
    does not double-inspect.
    """
    token = _vertexai_inspection_active.set(True)
    try:
        return await _inspect_vertexai_async(wrapped, instance, args, kwargs, entry="generate_content_async")
    finally:
        _vertexai_inspection_active.reset(token)


async def _wrap_private_generate_content_async(wrapped, instance, args, kwargs):
    """Async wrapper for GenerativeModel._generate_content_async() (private method).
    
    Catches calls from ChatSession.send_message_async() which calls
    _generate_content_async() directly.
    """
    if _vertexai_inspection_active.get():
        return await wrapped(*args, **kwargs)
    
    token = _vertexai_inspection_active.set(True)
    try:
        return await _inspect_vertexai_async(wrapped, instance, args, kwargs, entry="_generate_content_async")
    finally:
        _vertexai_inspection_active.reset(token)


async def _inspect_vertexai_async(wrapped, instance, args, kwargs, entry="generate_content_async"):
    """Shared async inspection logic for both generate_content_async and _generate_content_async."""
    # Get model name
    model_name = "unknown"
    if hasattr(instance, "model_name"):
        model_name = instance.model_name
    elif hasattr(instance, "_model_name"):
        model_name = instance._model_name
    
    set_inspection_context(done=False)
    if not _should_inspect():
        logger.debug(f"[PATCHED CALL] VertexAI.{entry} - inspection skipped")
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
    logger.debug(f"╔══════════════════════════════════════════════════════════════")
    logger.debug(f"║ [PATCHED] LLM CALL (async): {model_name}")
    logger.debug(f"║ Operation: VertexAI.{entry} | LLM Mode: {mode} | Integration: {integration_mode}")
    logger.debug(f"╚══════════════════════════════════════════════════════════════")
    
    # Gateway mode: route through AI Defense Gateway with format conversion
    gw_settings = resolve_gateway_settings("vertexai")
    if gw_settings:
        logger.debug(f"[PATCHED CALL] VertexAI.{entry} - Gateway mode - routing to AI Defense Gateway")
        if not stream:
            return await _handle_vertexai_gateway_call_async(
                model_name=model_name,
                contents=contents,
                gw_settings=gw_settings,
                generation_config=kwargs.get("generation_config"),
                tools=kwargs.get("tools"),
                tool_config=kwargs.get("tool_config"),
                system_instruction=getattr(instance, "system_instruction", None),
            )
        else:
            logger.debug(f"[PATCHED CALL] VertexAI.{entry} - Gateway mode streaming via non-streaming gateway call (async)")
            return await _handle_vertexai_gateway_call_streaming_async(
                model_name=model_name,
                contents=contents,
                gw_settings=gw_settings,
                generation_config=kwargs.get("generation_config"),
                tools=kwargs.get("tools"),
                tool_config=kwargs.get("tool_config"),
                system_instruction=getattr(instance, "system_instruction", None),
            )
    
    # Direct API call (API-mode inspection)
    # Pre-call inspection
    if normalized:
        logger.debug(f"[PATCHED CALL] VertexAI.{entry} - Request inspection ({len(normalized)} messages)")
        inspector = _get_inspector()
        decision = await inspector.ainspect_conversation(normalized, metadata)
        logger.debug(f"[PATCHED CALL] VertexAI.{entry} - Request decision: {decision.action}")
        set_inspection_context(decision=decision)
        _enforce_decision(decision)
    
    # Call the original
    logger.debug(f"[PATCHED CALL] VertexAI.{entry} - calling original method")
    response = await wrapped(*args, **kwargs)
    
    # Handle streaming
    if stream:
        logger.debug(f"[PATCHED CALL] VertexAI.{entry} - streaming response, wrapping for inspection")
        return AsyncGoogleStreamingInspectionWrapper(response, normalized, metadata)
    
    # Post-call inspection
    assistant_content = extract_google_response(response)
    if assistant_content and normalized:
        logger.debug(f"[PATCHED CALL] VertexAI.{entry} - Response inspection")
        messages_with_response = normalized + [
            {"role": "assistant", "content": assistant_content}
        ]
        resp_inspector = _get_inspector()
        decision = await resp_inspector.ainspect_conversation(messages_with_response, metadata)
        logger.debug(f"[PATCHED CALL] VertexAI.{entry} - Response decision: {decision.action}")
        set_inspection_context(decision=decision, done=True)
        _enforce_decision(decision)
    
    logger.debug(f"[PATCHED CALL] VertexAI.{entry} - complete")
    return response


def patch_vertexai() -> bool:
    """
    Patch vertexai for automatic inspection.
    
    Patches both the public methods (generate_content, generate_content_async)
    and the private methods (_generate_content, _generate_content_async).
    
    The private methods are needed because ChatSession.send_message() (used
    by AutoGen's GeminiClient) calls _generate_content() directly, bypassing
    the public generate_content() method.
    
    A reentrancy guard ensures that calls through generate_content() (which
    internally calls _generate_content()) are only inspected once.
    
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
        # Patch public GenerativeModel.generate_content
        wrapt.wrap_function_wrapper(
            "vertexai.generative_models",
            "GenerativeModel.generate_content",
            _wrap_generate_content,
        )
        
        # Patch public async version
        wrapt.wrap_function_wrapper(
            "vertexai.generative_models",
            "GenerativeModel.generate_content_async",
            _wrap_generate_content_async,
        )
        
        # Patch private _generate_content (called by ChatSession.send_message)
        # This is needed for AutoGen which uses ChatSession.send_message()
        _gm_module = safe_import("vertexai.generative_models._generative_models")
        if _gm_module is not None:
            try:
                wrapt.wrap_function_wrapper(
                    "vertexai.generative_models._generative_models",
                    "GenerativeModel._generate_content",
                    _wrap_private_generate_content,
                )
                logger.debug("Patched GenerativeModel._generate_content (private)")
            except Exception as e:
                logger.debug(f"Could not patch _generate_content: {e}")
            
            try:
                wrapt.wrap_function_wrapper(
                    "vertexai.generative_models._generative_models",
                    "GenerativeModel._generate_content_async",
                    _wrap_private_generate_content_async,
                )
                logger.debug("Patched GenerativeModel._generate_content_async (private)")
            except Exception as e:
                logger.debug(f"Could not patch _generate_content_async: {e}")
        
        # ------------------------------------------------------------------
        # Patch PredictionServiceClient (used by LangChain's ChatVertexAI
        # when GOOGLE_AI_SDK=vertexai).
        # ------------------------------------------------------------------
        _PSC_TARGETS = [
            # (module_path, class.method, wrapper, description)
            (
                "google.cloud.aiplatform_v1beta1.services.prediction_service.client",
                "PredictionServiceClient.generate_content",
                _wrap_prediction_generate_content,
                "v1beta1 PredictionServiceClient.generate_content",
            ),
            (
                "google.cloud.aiplatform_v1beta1.services.prediction_service.client",
                "PredictionServiceClient.stream_generate_content",
                _wrap_prediction_stream_generate_content,
                "v1beta1 PredictionServiceClient.stream_generate_content",
            ),
            (
                "google.cloud.aiplatform_v1.services.prediction_service.client",
                "PredictionServiceClient.generate_content",
                _wrap_prediction_generate_content,
                "v1 PredictionServiceClient.generate_content",
            ),
            (
                "google.cloud.aiplatform_v1.services.prediction_service.client",
                "PredictionServiceClient.stream_generate_content",
                _wrap_prediction_stream_generate_content,
                "v1 PredictionServiceClient.stream_generate_content",
            ),
            # Async clients
            (
                "google.cloud.aiplatform_v1beta1.services.prediction_service.async_client",
                "PredictionServiceAsyncClient.generate_content",
                _wrap_prediction_generate_content_async,
                "v1beta1 PredictionServiceAsyncClient.generate_content",
            ),
            (
                "google.cloud.aiplatform_v1beta1.services.prediction_service.async_client",
                "PredictionServiceAsyncClient.stream_generate_content",
                _wrap_prediction_stream_generate_content_async,
                "v1beta1 PredictionServiceAsyncClient.stream_generate_content",
            ),
            (
                "google.cloud.aiplatform_v1.services.prediction_service.async_client",
                "PredictionServiceAsyncClient.generate_content",
                _wrap_prediction_generate_content_async,
                "v1 PredictionServiceAsyncClient.generate_content",
            ),
            (
                "google.cloud.aiplatform_v1.services.prediction_service.async_client",
                "PredictionServiceAsyncClient.stream_generate_content",
                _wrap_prediction_stream_generate_content_async,
                "v1 PredictionServiceAsyncClient.stream_generate_content",
            ),
        ]

        for mod_path, method_path, wrapper, desc in _PSC_TARGETS:
            try:
                wrapt.wrap_function_wrapper(mod_path, method_path, wrapper)
                logger.debug(f"Patched {desc}")
            except Exception as e:
                logger.debug(f"Could not patch {desc}: {e}")

        mark_patched("vertexai")
        logger.info("VertexAI patched successfully")
        return True
    except Exception as e:
        logger.warning(f"Failed to patch VertexAI: {e}")
        return False


