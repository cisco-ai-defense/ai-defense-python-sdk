"""Extended tests for the Cohere patcher -- covers gaps not in test_cohere_patcher.py.

Specifically: _should_inspect, _enforce_decision, _handle_patcher_error,
_dict_to_cohere_response, _serialize_messages_for_gateway,
_handle_gateway_call_sync, _wrap_chat_stream, _wrap_chat fail_open paths,
and _CohereFakeStreamWrapper.
"""

import httpx
import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from aidefense.runtime.agentsec.patchers.cohere import (
    _handle_patcher_error,
    _should_inspect,
    _dict_to_cohere_response,
    _serialize_messages_for_gateway,
    _handle_gateway_call_sync,
    _wrap_chat,
    _wrap_chat_stream,
    _CohereFakeStreamWrapper,
    _CohereStreamingInspectionWrapper,
)
from aidefense.runtime.agentsec.exceptions import SecurityPolicyError
from aidefense.runtime.agentsec.decision import Decision
from aidefense.runtime.agentsec import _state
from aidefense.runtime.agentsec._context import clear_inspection_context
from aidefense.runtime.agentsec.patchers import reset_registry


@pytest.fixture(autouse=True)
def reset_state():
    _state.reset()
    reset_registry()
    clear_inspection_context()
    import aidefense.runtime.agentsec.patchers.cohere as cohere_module
    cohere_module._inspector = None
    yield
    _state.reset()
    reset_registry()
    clear_inspection_context()
    cohere_module._inspector = None


# ===========================================================================
# _should_inspect() — gateway mode tests
# ===========================================================================

class TestShouldInspectGatewayMode:
    def test_true_when_gateway_on(self):
        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            gateway_mode={"llm_mode": "on"},
        )
        clear_inspection_context()
        assert _should_inspect() is True

    def test_false_when_gateway_off(self):
        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            gateway_mode={"llm_mode": "off"},
        )
        clear_inspection_context()
        assert _should_inspect() is False

    def test_gateway_mode_ignores_api_mode_off(self):
        """When integration is gateway and gw_llm_mode is on, api_mode off is irrelevant."""
        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            gateway_mode={"llm_mode": "on"},
            api_mode={"llm": {"mode": "off"}},
        )
        clear_inspection_context()
        assert _should_inspect() is True


# ===========================================================================
# _handle_patcher_error()
# ===========================================================================

class TestCohereHandlePatcherError:
    def test_fail_open_true_returns_allow(self):
        _state.set_state(
            initialized=True,
            api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}},
        )
        decision = _handle_patcher_error(RuntimeError("boom"), "test")
        assert decision.action == "allow"

    def test_fail_open_false_raises(self):
        _state.set_state(
            initialized=True,
            api_mode={"llm_defaults": {"fail_open": False}, "llm": {"mode": "monitor"}},
        )
        with pytest.raises(SecurityPolicyError):
            _handle_patcher_error(RuntimeError("boom"), "test")


# ===========================================================================
# _dict_to_cohere_response()
# ===========================================================================

class TestDictToCohereResponse:
    def test_list_content(self):
        data = {
            "id": "resp-1",
            "message": {"content": [{"text": "Hello"}, {"text": "world"}]},
            "finish_reason": "COMPLETE",
        }
        resp = _dict_to_cohere_response(data)
        assert resp.message.role == "assistant"
        assert len(resp.message.content) == 2
        assert resp.message.content[0].text == "Hello"
        assert resp.message.content[1].text == "world"

    def test_string_content(self):
        data = {
            "id": "resp-2",
            "message": {"content": "Just text"},
        }
        resp = _dict_to_cohere_response(data)
        assert len(resp.message.content) == 1
        assert resp.message.content[0].text == "Just text"

    def test_empty_message(self):
        data = {"message": {}}
        resp = _dict_to_cohere_response(data)
        assert len(resp.message.content) == 0


# ===========================================================================
# _serialize_messages_for_gateway()
# ===========================================================================

class TestSerializeMessagesForGateway:
    def test_dict_messages(self):
        messages = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ]
        result = _serialize_messages_for_gateway(messages)
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hi"

    def test_object_messages_with_model_dump(self):
        m = MagicMock()
        m.model_dump.return_value = {"role": "user", "content": "from object"}
        # Not a dict, has model_dump
        result = _serialize_messages_for_gateway([m])
        assert result[0] == {"role": "user", "content": "from object"}

    def test_empty_returns_empty(self):
        assert _serialize_messages_for_gateway([]) == []
        assert _serialize_messages_for_gateway(None) == []


# ===========================================================================
# _handle_gateway_call_sync()
# ===========================================================================

class TestCohereHandleGatewayCallSync:
    def _make_gw_settings(self, url="https://gw.example.com", api_key="key", fail_open=True, timeout=30):
        return SimpleNamespace(url=url, api_key=api_key, fail_open=fail_open, timeout=timeout)

    def test_missing_url_raises(self):
        gw = self._make_gw_settings(url="")
        with pytest.raises(SecurityPolicyError, match="not configured"):
            _handle_gateway_call_sync(
                {"model": "command-a", "messages": []}, [], {}, gw,
            )

    def test_missing_api_key_raises(self):
        gw = self._make_gw_settings(api_key="")
        with pytest.raises(SecurityPolicyError, match="not configured"):
            _handle_gateway_call_sync(
                {"model": "command-a", "messages": []}, [], {}, gw,
            )

    @patch("httpx.Client")
    def test_success_returns_cohere_response(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "resp-1",
            "message": {"content": [{"text": "Hello from gateway"}]},
        }
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        _state.set_state(initialized=True, api_mode={"llm": {"mode": "monitor"}})
        clear_inspection_context()

        gw = self._make_gw_settings()
        result = _handle_gateway_call_sync(
            {"model": "command-a", "messages": [{"role": "user", "content": "Hi"}]},
            [{"role": "user", "content": "Hi"}], {}, gw,
        )
        assert result.message.content[0].text == "Hello from gateway"

    @patch("httpx.Client")
    def test_http_error_fail_open_true_reraises(self, mock_client_cls):
        request = httpx.Request("POST", "https://gw.example.com")
        response = httpx.Response(502, request=request)
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = MagicMock()
        mock_client.post.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "502", request=request, response=response,
        )
        mock_client_cls.return_value = mock_client

        _state.set_state(initialized=True, api_mode={"llm": {"mode": "monitor"}})
        clear_inspection_context()

        gw = self._make_gw_settings(fail_open=True)
        with pytest.raises(httpx.HTTPStatusError):
            _handle_gateway_call_sync(
                {"model": "command-a", "messages": []}, [], {}, gw,
            )

    @patch("httpx.Client")
    def test_http_error_fail_open_false_raises_security_error(self, mock_client_cls):
        request = httpx.Request("POST", "https://gw.example.com")
        response = httpx.Response(502, request=request)
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = MagicMock()
        mock_client.post.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "502", request=request, response=response,
        )
        mock_client_cls.return_value = mock_client

        _state.set_state(initialized=True, api_mode={"llm": {"mode": "monitor"}})
        clear_inspection_context()

        gw = self._make_gw_settings(fail_open=False)
        with pytest.raises(SecurityPolicyError):
            _handle_gateway_call_sync(
                {"model": "command-a", "messages": []}, [], {}, gw,
            )


# ===========================================================================
# _wrap_chat_stream() — sync
# ===========================================================================

class TestCohereWrapChatStream:
    @patch("aidefense.runtime.agentsec.patchers.cohere._get_inspector")
    @patch("aidefense.runtime.agentsec.patchers.cohere.resolve_gateway_settings", return_value=None)
    def test_api_mode_returns_streaming_wrapper(self, _mock_gw, mock_get_inspector):
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = Decision.allow(reasons=[])
        mock_get_inspector.return_value = mock_inspector

        _state.set_state(
            initialized=True,
            api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}},
        )
        clear_inspection_context()

        mock_stream = iter([MagicMock()])
        mock_wrapped = MagicMock(return_value=mock_stream)

        result = _wrap_chat_stream(
            mock_wrapped, MagicMock(), (),
            {"model": "command-a", "messages": [{"role": "user", "content": "Hi"}]},
        )
        assert isinstance(result, _CohereStreamingInspectionWrapper)

    @patch("aidefense.runtime.agentsec.patchers.cohere._handle_gateway_call_sync")
    @patch("aidefense.runtime.agentsec.patchers.cohere.resolve_gateway_settings")
    def test_gateway_mode_returns_fake_stream(self, mock_resolve_gw, mock_gw_call):
        gw_settings = SimpleNamespace(url="https://gw.example.com", api_key="key", fail_open=True, timeout=30)
        mock_resolve_gw.return_value = gw_settings
        # Gateway returns a response object (not a stream)
        mock_gw_call.return_value = SimpleNamespace(
            message=SimpleNamespace(content=[SimpleNamespace(text="GW reply")])
        )

        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            api_mode={"llm": {"mode": "monitor"}},
        )
        clear_inspection_context()

        result = _wrap_chat_stream(
            MagicMock(), MagicMock(), (),
            {"model": "command-a", "messages": [{"role": "user", "content": "Hi"}]},
        )
        assert isinstance(result, _CohereFakeStreamWrapper)

    @patch("aidefense.runtime.agentsec.patchers.cohere._should_inspect", return_value=False)
    def test_passthrough_when_skip(self, _mock_inspect):
        sentinel = object()
        mock_wrapped = MagicMock(return_value=sentinel)
        result = _wrap_chat_stream(
            mock_wrapped, MagicMock(), (),
            {"model": "command-a", "messages": []},
        )
        assert result is sentinel


# ===========================================================================
# _wrap_chat() — fail_open paths
# ===========================================================================

class TestCohereWrapChatFailOpen:
    @patch("aidefense.runtime.agentsec.patchers.cohere._get_inspector")
    @patch("aidefense.runtime.agentsec.patchers.cohere.resolve_gateway_settings", return_value=None)
    def test_inspector_error_fail_open_true_still_calls_wrapped(self, _mock_gw, mock_get_inspector):
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.side_effect = RuntimeError("inspector down")
        mock_get_inspector.return_value = mock_inspector

        _state.set_state(
            initialized=True,
            api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}},
        )
        clear_inspection_context()

        mock_response = MagicMock()
        mock_response.message = MagicMock(content=[])
        mock_wrapped = MagicMock(return_value=mock_response)

        result = _wrap_chat(
            mock_wrapped, MagicMock(), (),
            {"model": "command-a", "messages": [{"role": "user", "content": "Hi"}]},
        )
        mock_wrapped.assert_called_once()

    @patch("aidefense.runtime.agentsec.patchers.cohere._get_inspector")
    @patch("aidefense.runtime.agentsec.patchers.cohere.resolve_gateway_settings", return_value=None)
    def test_inspector_error_fail_open_false_raises(self, _mock_gw, mock_get_inspector):
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.side_effect = RuntimeError("inspector down")
        mock_get_inspector.return_value = mock_inspector

        _state.set_state(
            initialized=True,
            api_mode={"llm_defaults": {"fail_open": False}, "llm": {"mode": "monitor"}},
        )
        clear_inspection_context()

        mock_wrapped = MagicMock()

        with pytest.raises(SecurityPolicyError):
            _wrap_chat(
                mock_wrapped, MagicMock(), (),
                {"model": "command-a", "messages": [{"role": "user", "content": "Hi"}]},
            )
        mock_wrapped.assert_not_called()


# ===========================================================================
# _CohereFakeStreamWrapper
# ===========================================================================

class TestCohereFakeStreamWrapper:
    def test_yields_one_chunk_then_stops(self):
        response = SimpleNamespace(
            message=SimpleNamespace(content=[SimpleNamespace(text="Hello")])
        )
        wrapper = _CohereFakeStreamWrapper(response)
        chunks = list(wrapper)
        assert len(chunks) == 1
        assert chunks[0].type == "content-delta"
        assert chunks[0].delta.text == "Hello"


# ===========================================================================
# _CohereStreamingInspectionWrapper
# ===========================================================================

class TestCohereStreamingInspectionWrapper:
    @patch("aidefense.runtime.agentsec.patchers.cohere._get_inspector")
    def test_buffers_content_delta_and_performs_final_inspection(self, mock_get_inspector):
        """Iterating through stream buffers content-delta text; final inspection runs at end."""
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = Decision.allow(reasons=[])
        mock_get_inspector.return_value = mock_inspector

        _state.set_state(
            initialized=True,
            api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}},
        )
        clear_inspection_context()

        chunk1 = SimpleNamespace(type="content-delta", delta=SimpleNamespace(text="Hello "))
        chunk2 = SimpleNamespace(type="content-delta", delta=SimpleNamespace(text="world"))
        stream = iter([chunk1, chunk2])

        wrapper = _CohereStreamingInspectionWrapper(
            stream,
            [{"role": "user", "content": "Hi"}],
            {},
        )
        chunks = list(wrapper)
        assert len(chunks) == 2
        assert mock_inspector.inspect_conversation.called

    @patch("aidefense.runtime.agentsec.patchers.cohere._get_inspector")
    def test_no_final_inspection_when_buffer_empty(self, mock_get_inspector):
        """If no content-delta text was buffered, final inspection is skipped."""
        mock_inspector = MagicMock()
        mock_get_inspector.return_value = mock_inspector

        _state.set_state(
            initialized=True,
            api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}},
        )
        clear_inspection_context()

        chunk = SimpleNamespace(type="message-start", delta=None)
        stream = iter([chunk])

        wrapper = _CohereStreamingInspectionWrapper(stream, [], {})
        list(wrapper)
        mock_inspector.inspect_conversation.assert_not_called()


# ===========================================================================
# patch_cohere() — success + failure paths
# ===========================================================================

class TestCoherePatchSuccess:
    def test_successful_patch_marks_patched(self):
        from aidefense.runtime.agentsec.patchers.cohere import patch_cohere
        with patch("aidefense.runtime.agentsec.patchers.cohere.safe_import", return_value=MagicMock()), \
             patch("aidefense.runtime.agentsec.patchers.cohere.is_patched", return_value=False), \
             patch("aidefense.runtime.agentsec.patchers.cohere.wrapt") as mock_wrapt, \
             patch("aidefense.runtime.agentsec.patchers.cohere.mark_patched") as mock_mark:
            assert patch_cohere() is True
            mock_mark.assert_called_once_with("cohere")
            assert mock_wrapt.wrap_function_wrapper.call_count >= 4  # chat, chat_stream, chat_async, chat_stream_async

    def test_patch_failure_returns_false(self):
        from aidefense.runtime.agentsec.patchers.cohere import patch_cohere
        with patch("aidefense.runtime.agentsec.patchers.cohere.safe_import", return_value=MagicMock()), \
             patch("aidefense.runtime.agentsec.patchers.cohere.is_patched", return_value=False), \
             patch("aidefense.runtime.agentsec.patchers.cohere.wrapt") as mock_wrapt:
            mock_wrapt.wrap_function_wrapper.side_effect = Exception("wrap fail")
            assert patch_cohere() is False


# ===========================================================================
# _wrap_chat() — gateway mode
# ===========================================================================

class TestCohereWrapChatGateway:
    @patch("aidefense.runtime.agentsec.patchers.cohere._handle_gateway_call_sync")
    @patch("aidefense.runtime.agentsec.patchers.cohere.resolve_gateway_settings")
    def test_gateway_mode_delegates_to_gateway_handler(self, mock_resolve_gw, mock_gw_call):
        gw_settings = SimpleNamespace(url="https://gw.example.com", api_key="key", fail_open=True, timeout=30)
        mock_resolve_gw.return_value = gw_settings
        mock_gw_call.return_value = SimpleNamespace(
            message=SimpleNamespace(content=[SimpleNamespace(text="GW reply")])
        )

        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            api_mode={"llm": {"mode": "monitor"}},
        )
        clear_inspection_context()

        result = _wrap_chat(
            MagicMock(), MagicMock(), (),
            {"model": "command-a", "messages": [{"role": "user", "content": "Hi"}]},
        )
        mock_gw_call.assert_called_once()


# ===========================================================================
# _normalize_messages & _content_to_string — edge cases
# ===========================================================================

class TestCohereNormalizeExtended:
    def test_content_to_string_nested_content_attribute(self):
        from aidefense.runtime.agentsec.patchers.cohere import _content_to_string
        inner = MagicMock()
        inner.content = "deep text"
        outer = MagicMock(spec=[])  # no text, no content attr — force str()
        # object with .content attribute
        wrapper = SimpleNamespace(content=inner)
        # Test recursive content resolution
        assert _content_to_string(wrapper) == "deep text"

    def test_content_to_string_fallback_str(self):
        from aidefense.runtime.agentsec.patchers.cohere import _content_to_string
        assert _content_to_string(42) == "42"

    def test_content_to_string_list_with_content_item(self):
        from aidefense.runtime.agentsec.patchers.cohere import _content_to_string
        item = SimpleNamespace(content="inner content")
        # item has .content but no .text
        result = _content_to_string([item])
        assert "inner content" in result

    def test_normalize_skips_tool_role_objects(self):
        from aidefense.runtime.agentsec.patchers.cohere import _normalize_messages
        m = SimpleNamespace(role="tool", content="tool result")
        result = _normalize_messages([m])
        assert result == []


# ===========================================================================
# _serialize_messages_for_gateway — object edge cases
# ===========================================================================

class TestCohereSerializeExtended:
    def test_object_messages_with_dict_method(self):
        from aidefense.runtime.agentsec.patchers.cohere import _serialize_messages_for_gateway
        m = MagicMock(spec=["role", "content", "dict"])  # has .dict but not .model_dump
        m.role = "user"
        m.content = "test"
        m.dict.return_value = {"role": "user", "content": "from dict"}
        # Remove model_dump to test .dict() fallback
        del m.model_dump
        result = _serialize_messages_for_gateway([m])
        assert result[0] == {"role": "user", "content": "from dict"}

    def test_object_messages_fallback_to_content_to_string(self):
        from aidefense.runtime.agentsec.patchers.cohere import _serialize_messages_for_gateway
        m = SimpleNamespace(role="user", content="plain text")
        result = _serialize_messages_for_gateway([m])
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "plain text"


# ===========================================================================
# _extract_assistant_content — more edge cases
# ===========================================================================

class TestCohereExtractExtended:
    def test_extract_from_dict_items_in_list(self):
        from aidefense.runtime.agentsec.patchers.cohere import _extract_assistant_content
        msg = SimpleNamespace(content=[{"text": "dict item"}])
        response = SimpleNamespace(message=msg)
        assert _extract_assistant_content(response) == "dict item"

    def test_extract_from_string_items_in_list(self):
        from aidefense.runtime.agentsec.patchers.cohere import _extract_assistant_content
        msg = SimpleNamespace(content=["string item"])
        response = SimpleNamespace(message=msg)
        assert _extract_assistant_content(response) == "string item"

    def test_extract_content_none_returns_empty(self):
        from aidefense.runtime.agentsec.patchers.cohere import _extract_assistant_content
        response = SimpleNamespace(message=SimpleNamespace(content=None))
        assert _extract_assistant_content(response) == ""
