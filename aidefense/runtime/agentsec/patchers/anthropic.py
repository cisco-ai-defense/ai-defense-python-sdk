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

"""Anthropic Messages API autopatching.

Anthropic's API is intentionally handled as a native provider here.  In
particular, ``system`` is a top-level request field, content is a list of
typed blocks, and streaming has both a raw-event API and a stream-manager
helper API.  Reusing the OpenAI patcher would lose tool calls and would return
the wrong object shape in gateway mode.
"""

import json
import logging
import threading
from types import SimpleNamespace
from typing import Any, Dict, Iterable, Iterator, List, Optional

import wrapt

from .. import _state
from .._context import get_inspection_context, set_inspection_context
from ..decision import Decision
from ..exceptions import SecurityPolicyError
from ..inspectors.api_llm import LLMInspector
from . import is_patched, mark_patched
from ._base import resolve_gateway_settings, safe_import

logger = logging.getLogger("aidefense.runtime.agentsec.patchers.anthropic")

_inspector: Optional[LLMInspector] = None
_inspector_lock = threading.Lock()
MAX_STREAMING_BUFFER_SIZE = 1_000_000


def _reset_inspector() -> None:
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


def _get_value(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _json_value(value: Any) -> Any:
    """Convert Anthropic models and content blocks to JSON-compatible values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(v) for v in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _json_value(model_dump(exclude_none=True))
        except TypeError:
            return _json_value(model_dump())
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return _json_value(to_dict())
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        return {
            str(k): _json_value(v)
            for k, v in vars(value).items()
            if not str(k).startswith("_")
        }
    return str(value)


def _block_to_text(block: Any) -> str:
    """Create a security-inspection representation of one Anthropic block."""
    if isinstance(block, str):
        return block
    block_type = _get_value(block, "type", "")
    if block_type == "text":
        return str(_get_value(block, "text", "") or "")
    if block_type in {"thinking", "redacted_thinking"}:
        return str(
            _get_value(block, "thinking", _get_value(block, "data", "")) or ""
        )
    if block_type in {"tool_use", "server_tool_use", "custom_tool_use"}:
        name = _get_value(block, "name", "unknown_tool")
        tool_input = _get_value(block, "input", _get_value(block, "arguments", {}))
        return "[tool_use name={} input={}]".format(
            name, json.dumps(_json_value(tool_input), sort_keys=True)
        )
    if block_type in {"tool_result", "server_tool_result", "custom_tool_result"}:
        tool_id = _get_value(block, "tool_use_id", "")
        content = _get_value(block, "content", "")
        return "[tool_result id={} content={}]".format(
            tool_id, _content_to_text(content)
        )
    if block_type == "image":
        source = _get_value(block, "source", {})
        media_type = _get_value(source, "media_type", "")
        return "[image{}]".format(" " + str(media_type) if media_type else "")
    if block_type:
        return "[{} {}]".format(
            block_type,
            json.dumps(_json_value(block), sort_keys=True),
        )
    return str(_json_value(block))


def _content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, (list, tuple)):
        return "\n".join(
            part for part in (_block_to_text(block) for block in content) if part
        )
    return _block_to_text(content)


def _normalize_messages(messages: Any, system: Any = None) -> List[Dict[str, Any]]:
    """Normalize native Anthropic messages to agentsec's role/content format."""
    result: List[Dict[str, Any]] = []
    system_text = _content_to_text(system)
    if system_text:
        result.append({"role": "system", "content": system_text})

    if not isinstance(messages, (list, tuple)):
        return result
    for message in messages:
        role = _get_value(message, "role", "user") or "user"
        content = _content_to_text(_get_value(message, "content", ""))
        if content:
            result.append({"role": str(role), "content": content})
    return result


def _normalize_kwargs(kwargs: Dict[str, Any]) -> List[Dict[str, Any]]:
    messages = _normalize_messages(kwargs.get("messages", []), kwargs.get("system"))
    tools = kwargs.get("tools")
    if tools:
        messages.append(
            {
                "role": "system",
                "content": "[tool_definitions {}]".format(
                    json.dumps(_json_value(tools), sort_keys=True)
                ),
            }
        )
    return messages


def _extract_assistant_content(response: Any) -> str:
    """Extract all response content, including tool-only responses."""
    if response is None:
        return ""
    content = _get_value(response, "content")
    if content is not None:
        return _content_to_text(content)
    return _content_to_text(response)


def _should_inspect() -> bool:
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
    if decision.action != "block":
        return
    if _state.get_llm_mode() == "enforce":
        raise SecurityPolicyError(decision)
    if _state.get_llm_mode() == "monitor":
        logger.warning(
            "[agentsec] Block decision in monitor mode: reasons=%s, severity=%s, classifications=%s",
            decision.reasons,
            decision.severity,
            decision.classifications,
        )
        callback = _state.get_on_violation()
        if callback is not None:
            try:
                callback(decision)
            except Exception:
                logger.debug("on_violation callback raised an exception", exc_info=True)


def _handle_patcher_error(error: Exception, operation: str) -> Optional[Decision]:
    fail_open = _state.get_api_llm_fail_open()
    logger.warning("[%s] Inspection error: %s: %s", operation, type(error).__name__, error)
    if fail_open:
        return Decision.allow(
            reasons=[f"Inspection error ({type(error).__name__}), fail_open=True"]
        )
    decision = Decision.block(reasons=[f"Inspection error: {type(error).__name__}: {error}"])
    raise SecurityPolicyError(decision, f"Inspection failed and fail_open=False: {error}")


def _inspect_request(messages: List[Dict[str, Any]], metadata: Dict[str, Any]) -> None:
    try:
        decision = _get_inspector().inspect_conversation(messages, metadata)
        set_inspection_context(decision=decision)
        _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as error:
        decision = _handle_patcher_error(error, "Anthropic pre-call")
        if decision:
            set_inspection_context(decision=decision)


async def _inspect_request_async(messages: List[Dict[str, Any]], metadata: Dict[str, Any]) -> None:
    try:
        decision = await _get_inspector().ainspect_conversation(messages, metadata)
        set_inspection_context(decision=decision)
        _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as error:
        decision = _handle_patcher_error(error, "Anthropic async pre-call")
        if decision:
            set_inspection_context(decision=decision)


def _inspect_response(
    messages: List[Dict[str, Any]], metadata: Dict[str, Any], response: Any
) -> None:
    content = _extract_assistant_content(response)
    if not content:
        return
    try:
        decision = _get_inspector().inspect_conversation(
            messages + [{"role": "assistant", "content": content}], metadata
        )
        set_inspection_context(decision=decision, done=True)
        _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as error:
        _handle_patcher_error(error, "Anthropic post-call")


async def _inspect_response_async(
    messages: List[Dict[str, Any]], metadata: Dict[str, Any], response: Any
) -> None:
    content = _extract_assistant_content(response)
    if not content:
        return
    try:
        decision = await _get_inspector().ainspect_conversation(
            messages + [{"role": "assistant", "content": content}], metadata
        )
        set_inspection_context(decision=decision, done=True)
        _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as error:
        _handle_patcher_error(error, "Anthropic async post-call")


def _event_value(event: Any, key: str, default: Any = None) -> Any:
    value = _get_value(event, key, default)
    return value if value is not None else default


def _event_to_text(event: Any) -> str:
    event_type = _event_value(event, "type", "")
    if event_type == "content_block_start":
        return _block_to_text(_event_value(event, "content_block", {}))
    if event_type == "content_block_delta":
        delta = _event_value(event, "delta", {})
        delta_type = _event_value(delta, "type", "")
        if delta_type == "text_delta":
            return str(_event_value(delta, "text", "") or "")
        if delta_type == "thinking_delta":
            return str(_event_value(delta, "thinking", "") or "")
        if delta_type == "input_json_delta":
            return "[tool_input_delta {}]".format(
                _event_value(delta, "partial_json", "")
            )
    return ""


class _AnthropicStreamInspectionWrapper:
    """Preserve the raw Anthropic stream while inspecting the accumulated reply."""

    def __init__(self, stream: Any, messages: List[Dict[str, Any]], metadata: Dict[str, Any]):
        self._stream = stream
        self._messages = messages
        self._metadata = metadata
        self._buffer = ""
        self._final_inspection_done = False

    def __iter__(self):
        return self

    def __next__(self):
        try:
            event = next(self._stream)
        except StopIteration:
            self._perform_final_inspection()
            raise
        except Exception:
            self._perform_final_inspection()
            raise
        if len(self._buffer) < MAX_STREAMING_BUFFER_SIZE:
            text = _event_to_text(event)
            self._buffer += text[: MAX_STREAMING_BUFFER_SIZE - len(self._buffer)]
        return event

    def __enter__(self):
        if hasattr(self._stream, "__enter__"):
            self._stream.__enter__()
        return self

    def __exit__(self, exc_type, exc, exc_tb):
        try:
            if hasattr(self._stream, "__exit__"):
                return self._stream.__exit__(exc_type, exc, exc_tb)
            return None
        finally:
            self._perform_final_inspection()

    def close(self):
        try:
            close = getattr(self._stream, "close", None)
            if callable(close):
                close()
        finally:
            self._perform_final_inspection()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)

    def _perform_final_inspection(self) -> None:
        if self._final_inspection_done:
            return
        self._final_inspection_done = True
        if not self._buffer or not _should_inspect():
            return
        try:
            decision = _get_inspector().inspect_conversation(
                self._messages + [{"role": "assistant", "content": self._buffer}],
                self._metadata,
            )
            set_inspection_context(decision=decision, done=True)
            _enforce_decision(decision)
        except SecurityPolicyError:
            raise
        except Exception as error:
            _handle_patcher_error(error, "Anthropic streaming inspection")


class _AnthropicAsyncStreamInspectionWrapper:
    def __init__(self, stream: Any, messages: List[Dict[str, Any]], metadata: Dict[str, Any]):
        self._stream = stream
        self._messages = messages
        self._metadata = metadata
        self._buffer = ""
        self._final_inspection_done = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            event = await self._stream.__anext__()
        except StopAsyncIteration:
            await self._perform_final_inspection()
            raise
        except Exception:
            await self._perform_final_inspection()
            raise
        if len(self._buffer) < MAX_STREAMING_BUFFER_SIZE:
            text = _event_to_text(event)
            self._buffer += text[: MAX_STREAMING_BUFFER_SIZE - len(self._buffer)]
        return event

    async def aclose(self):
        try:
            close = getattr(self._stream, "aclose", None)
            if callable(close):
                await close()
        finally:
            await self._perform_final_inspection()

    async def __aenter__(self):
        enter = getattr(self._stream, "__aenter__", None)
        if callable(enter):
            await enter()
        return self

    async def __aexit__(self, exc_type, exc, exc_tb):
        try:
            exit_method = getattr(self._stream, "__aexit__", None)
            if callable(exit_method):
                return await exit_method(exc_type, exc, exc_tb)
            return None
        finally:
            await self._perform_final_inspection()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)

    async def _perform_final_inspection(self) -> None:
        if self._final_inspection_done:
            return
        self._final_inspection_done = True
        if not self._buffer or not _should_inspect():
            return
        try:
            decision = await _get_inspector().ainspect_conversation(
                self._messages + [{"role": "assistant", "content": self._buffer}],
                self._metadata,
            )
            set_inspection_context(decision=decision, done=True)
            _enforce_decision(decision)
        except SecurityPolicyError:
            raise
        except Exception as error:
            _handle_patcher_error(error, "Anthropic async streaming inspection")


class _AnthropicMessageStreamProxy:
    """Proxy the high-level MessageStream and retain its public interface."""

    def __init__(self, stream: Any):
        self._stream = stream
        self.text_stream = self._text_stream()

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._stream)

    def _text_stream(self):
        for event in self:
            if _event_value(event, "type", "") != "content_block_delta":
                continue
            delta = _event_value(event, "delta", {})
            if _event_value(delta, "type", "") == "text_delta":
                yield _event_value(delta, "text", "")

    def get_final_message(self):
        return self._stream.get_final_message()

    def get_final_text(self):
        return self._stream.get_final_text()

    def until_done(self):
        return self._stream.until_done()

    def close(self):
        return self._stream.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, exc_tb):
        return self.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)


class _AnthropicAsyncMessageStreamProxy:
    def __init__(self, stream: Any):
        self._stream = stream
        self.text_stream = self._text_stream()

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self._stream.__anext__()

    async def _text_stream(self):
        async for event in self:
            if _event_value(event, "type", "") != "content_block_delta":
                continue
            delta = _event_value(event, "delta", {})
            if _event_value(delta, "type", "") == "text_delta":
                yield _event_value(delta, "text", "")

    async def get_final_message(self):
        return await self._stream.get_final_message()

    async def get_final_text(self):
        return await self._stream.get_final_text()

    async def until_done(self):
        return await self._stream.until_done()

    async def close(self):
        return await self._stream.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, exc_tb):
        return await self.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)


class _AnthropicStreamManagerProxy:
    def __init__(self, manager: Any, messages: List[Dict[str, Any]], metadata: Dict[str, Any]):
        self._manager = manager
        self._messages = messages
        self._metadata = metadata
        self._stream = None
        self._inspection_done = False

    def __enter__(self):
        self._stream = _AnthropicMessageStreamProxy(self._manager.__enter__())
        return self._stream

    def __exit__(self, exc_type, exc, exc_tb):
        try:
            return self._manager.__exit__(exc_type, exc, exc_tb)
        finally:
            self._inspect_final_message()

    def _inspect_final_message(self):
        if self._inspection_done or not _should_inspect():
            return
        self._inspection_done = True
        if self._stream is None:
            return
        try:
            response = self._stream.get_final_message()
            _inspect_response(self._messages, self._metadata, response)
        except SecurityPolicyError:
            raise
        except Exception as error:
            _handle_patcher_error(error, "Anthropic message stream inspection")


class _AnthropicAsyncStreamManagerProxy:
    def __init__(self, manager: Any, messages: List[Dict[str, Any]], metadata: Dict[str, Any]):
        self._manager = manager
        self._messages = messages
        self._metadata = metadata
        self._stream = None
        self._inspection_done = False

    async def __aenter__(self):
        self._stream = _AnthropicAsyncMessageStreamProxy(await self._manager.__aenter__())
        return self._stream

    async def __aexit__(self, exc_type, exc, exc_tb):
        try:
            return await self._manager.__aexit__(exc_type, exc, exc_tb)
        finally:
            await self._inspect_final_message()

    async def _inspect_final_message(self):
        if self._inspection_done or not _should_inspect():
            return
        self._inspection_done = True
        if self._stream is None:
            return
        try:
            response = await self._stream.get_final_message()
            await _inspect_response_async(self._messages, self._metadata, response)
        except SecurityPolicyError:
            raise
        except Exception as error:
            _handle_patcher_error(error, "Anthropic async message stream inspection")


def _gateway_url(settings: Any) -> str:
    url = settings.url.rstrip("/")
    if url.endswith("/messages"):
        return url
    if url.endswith("/v1"):
        return url + "/messages"
    return url + "/v1/messages"


def _gateway_request_body(kwargs: Dict[str, Any], stream: bool) -> Dict[str, Any]:
    excluded = {"extra_headers", "extra_query", "extra_body", "timeout", "stream"}
    body = {
        key: _json_value(value)
        for key, value in kwargs.items()
        if key not in excluded and value is not None
    }
    extra_body = kwargs.get("extra_body")
    if isinstance(extra_body, dict):
        body.update(_json_value(extra_body))
    if stream:
        body["stream"] = True
    return body


def _gateway_headers(settings: Any, kwargs: Dict[str, Any]) -> Dict[str, str]:
    headers = {
        "api-key": settings.api_key or "",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "anthropic-version": "2023-06-01",
    }
    api_key_header = getattr(settings, "api_key_header", "api-key")
    if api_key_header and api_key_header != "api-key":
        headers.pop("api-key", None)
        headers[str(api_key_header)] = settings.api_key or ""
    extra_headers = kwargs.get("extra_headers")
    if isinstance(extra_headers, dict):
        headers.update({str(k): str(v) for k, v in extra_headers.items()})
    return headers


def _as_anthropic_message(data: Dict[str, Any]) -> Any:
    try:
        from anthropic.types import Message

        validator = getattr(Message, "model_validate", None)
        if callable(validator):
            return validator(data)
        return Message(**data)
    except Exception:
        return _namespace_from_dict(data)


def _namespace_from_dict(value: Any) -> Any:
    if isinstance(value, dict):
        return SimpleNamespace(**{k: _namespace_from_dict(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_namespace_from_dict(v) for v in value]
    return value


def _gateway_post_sync(kwargs: Dict[str, Any], settings: Any) -> Any:
    import httpx

    requested_stream = bool(kwargs.get("stream"))
    # The native gateway response is converted to an Anthropic object below.
    # A synthetic native stream is returned when the caller requested stream=True.
    body = _gateway_request_body(kwargs, False)
    try:
        with httpx.Client(timeout=float(settings.timeout)) as client:
            response = client.post(
                _gateway_url(settings),
                json=body,
                headers=_gateway_headers(settings, kwargs),
            )
            response.raise_for_status()
            data = response.json()
        set_inspection_context(
            decision=Decision.allow(reasons=["Gateway handled inspection"]), done=True
        )
        message = _as_anthropic_message(data)
        return _SyntheticStream(message) if requested_stream else message
    except SecurityPolicyError:
        raise
    except Exception as error:
        if settings.fail_open:
            raise
        decision = Decision.block(reasons=[f"Anthropic gateway error: {error}"])
        set_inspection_context(decision=decision, done=True)
        raise SecurityPolicyError(decision, f"Anthropic gateway error: {error}")


async def _gateway_post_async(kwargs: Dict[str, Any], settings: Any) -> Any:
    import httpx

    requested_stream = bool(kwargs.get("stream"))
    body = _gateway_request_body(kwargs, False)
    try:
        async with httpx.AsyncClient(timeout=float(settings.timeout)) as client:
            response = await client.post(
                _gateway_url(settings),
                json=body,
                headers=_gateway_headers(settings, kwargs),
            )
            response.raise_for_status()
            data = response.json()
        set_inspection_context(
            decision=Decision.allow(reasons=["Gateway handled inspection"]), done=True
        )
        message = _as_anthropic_message(data)
        return _SyntheticAsyncStream(message) if requested_stream else message
    except SecurityPolicyError:
        raise
    except Exception as error:
        if settings.fail_open:
            raise
        decision = Decision.block(reasons=[f"Anthropic gateway error: {error}"])
        set_inspection_context(decision=decision, done=True)
        raise SecurityPolicyError(decision, f"Anthropic gateway error: {error}")


def _wrap_create(wrapped, instance, args, kwargs):
    set_inspection_context(done=False)
    if not _should_inspect():
        return wrapped(*args, **kwargs)
    messages = _normalize_kwargs(kwargs)
    metadata = get_inspection_context().metadata
    settings = resolve_gateway_settings("anthropic")
    if settings:
        return _gateway_post_sync(kwargs, settings)
    _inspect_request(messages, metadata)
    response = wrapped(*args, **kwargs)
    if kwargs.get("stream"):
        return _AnthropicStreamInspectionWrapper(response, messages, metadata)
    _inspect_response(messages, metadata, response)
    return response


async def _wrap_create_async(wrapped, instance, args, kwargs):
    set_inspection_context(done=False)
    if not _should_inspect():
        return await wrapped(*args, **kwargs)
    messages = _normalize_kwargs(kwargs)
    metadata = get_inspection_context().metadata
    settings = resolve_gateway_settings("anthropic")
    if settings:
        return await _gateway_post_async(kwargs, settings)
    await _inspect_request_async(messages, metadata)
    response = await wrapped(*args, **kwargs)
    if kwargs.get("stream"):
        return _AnthropicAsyncStreamInspectionWrapper(response, messages, metadata)
    await _inspect_response_async(messages, metadata, response)
    return response


def _wrap_stream(wrapped, instance, args, kwargs):
    set_inspection_context(done=False)
    if not _should_inspect():
        return wrapped(*args, **kwargs)
    messages = _normalize_kwargs(kwargs)
    metadata = get_inspection_context().metadata
    settings = resolve_gateway_settings("anthropic")
    if settings:
        # Gateway mode returns the native Message shape; the manager proxy
        # preserves the Anthropic helper API while the gateway handles policy.
        response = _gateway_post_sync(dict(kwargs, stream=False), settings)
        return _AnthropicStreamManagerProxy(
            _SyntheticStreamManager(response), messages, metadata
        )
    _inspect_request(messages, metadata)
    return _AnthropicStreamManagerProxy(wrapped(*args, **kwargs), messages, metadata)


def _wrap_stream_async(wrapped, instance, args, kwargs):
    set_inspection_context(done=False)
    if not _should_inspect():
        return wrapped(*args, **kwargs)
    messages = _normalize_kwargs(kwargs)
    metadata = get_inspection_context().metadata
    settings = resolve_gateway_settings("anthropic")
    if settings:
        async def request():
            return await _gateway_post_async(dict(kwargs, stream=False), settings)

        return _AnthropicAsyncStreamManagerProxy(
            _LazySyntheticAsyncStreamManager(request), messages, metadata
        )
    return _AnthropicAsyncStreamManagerProxy(
        _InspectedAsyncStreamManager(wrapped(*args, **kwargs), messages, metadata),
        messages,
        metadata,
    )


class _SyntheticStream:
    def __init__(self, response: Any):
        self._response = response
        self._events = iter(
            [
                SimpleNamespace(type="message_start", message=response),
                SimpleNamespace(
                    type="content_block_start",
                    index=0,
                    content_block=SimpleNamespace(type="text", text=""),
                ),
                SimpleNamespace(
                    type="content_block_delta",
                    index=0,
                    delta=SimpleNamespace(
                        type="text_delta", text=_extract_assistant_content(response)
                    ),
                ),
                SimpleNamespace(type="content_block_stop", index=0),
                SimpleNamespace(type="message_stop"),
            ]
        )

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._events)

    def close(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, exc_tb):
        self.close()


class _SyntheticStreamManager:
    def __init__(self, response: Any):
        self._response = response

    def __enter__(self):
        return _SyntheticMessageStream(self._response)

    def __exit__(self, exc_type, exc, exc_tb):
        return None


class _SyntheticMessageStream(_SyntheticStream):
    def __init__(self, response: Any):
        super().__init__(response)
        self.text_stream = iter([_extract_assistant_content(response)])

    def get_final_message(self):
        return self._response

    def get_final_text(self):
        return _extract_assistant_content(self._response)

    def until_done(self):
        for _ in self:
            pass


class _SyntheticAsyncStream:
    def __init__(self, response: Any):
        self._response = response
        self._events = iter(
            [
                SimpleNamespace(type="message_start", message=response),
                SimpleNamespace(
                    type="content_block_delta",
                    index=0,
                    delta=SimpleNamespace(
                        type="text_delta", text=_extract_assistant_content(response)
                    ),
                ),
                SimpleNamespace(type="message_stop"),
            ]
        )

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._events)
        except StopIteration:
            raise StopAsyncIteration

    async def aclose(self):
        return None


class _SyntheticAsyncStreamManager:
    def __init__(self, response: Any):
        self._response = response

    async def __aenter__(self):
        return _SyntheticAsyncMessageStream(self._response)

    async def __aexit__(self, exc_type, exc, exc_tb):
        return None


class _LazySyntheticAsyncStreamManager:
    """Defer the gateway request until an async stream is entered."""

    def __init__(self, request):
        self._request = request
        self._manager = None

    async def __aenter__(self):
        response = await self._request()
        self._manager = _SyntheticAsyncStreamManager(response)
        return await self._manager.__aenter__()

    async def __aexit__(self, exc_type, exc, exc_tb):
        if self._manager is None:
            return None
        return await self._manager.__aexit__(exc_type, exc, exc_tb)


class _InspectedAsyncStreamManager:
    """Run request inspection when the native async stream is entered."""

    def __init__(self, manager, messages, metadata):
        self._manager = manager
        self._messages = messages
        self._metadata = metadata

    async def __aenter__(self):
        await _inspect_request_async(self._messages, self._metadata)
        return await self._manager.__aenter__()

    async def __aexit__(self, exc_type, exc, exc_tb):
        return await self._manager.__aexit__(exc_type, exc, exc_tb)


class _SyntheticAsyncMessageStream(_SyntheticAsyncStream):
    def __init__(self, response: Any):
        super().__init__(response)
        self.text_stream = self._text_stream()

    async def _text_stream(self):
        async for event in self:
            if _event_value(event, "type") == "content_block_delta":
                yield _event_value(_event_value(event, "delta", {}), "text", "")

    async def get_final_message(self):
        return self._response

    async def get_final_text(self):
        return _extract_assistant_content(self._response)

    async def until_done(self):
        async for _ in self:
            pass


def patch_anthropic() -> bool:
    """Patch the official Anthropic Messages API if installed."""
    if is_patched("anthropic"):
        logger.debug("Anthropic already patched, skipping")
        return True
    if safe_import("anthropic") is None:
        return False
    try:
        wrapped_methods = 0
        for module in (
            "anthropic.resources.messages",
            "anthropic.resources.beta.messages",
        ):
            try:
                wrapt.wrap_function_wrapper(module, "Messages.create", _wrap_create)
                wrapt.wrap_function_wrapper(module, "Messages.stream", _wrap_stream)
                wrapt.wrap_function_wrapper(
                    module, "AsyncMessages.create", _wrap_create_async
                )
                wrapt.wrap_function_wrapper(
                    module, "AsyncMessages.stream", _wrap_stream_async
                )
                wrapped_methods += 4
            except (ImportError, AttributeError):
                # Older Anthropic releases may not expose beta Messages.
                continue
        if not wrapped_methods:
            raise ImportError("Anthropic Messages resources are unavailable")
        mark_patched("anthropic")
        logger.info("Anthropic client patched successfully")
        return True
    except Exception as error:
        logger.warning("Failed to patch Anthropic: %s", error)
        return False


__all__ = [
    "patch_anthropic",
    "_normalize_messages",
    "_extract_assistant_content",
    "_wrap_create",
    "_wrap_create_async",
    "_wrap_stream",
    "_wrap_stream_async",
]
