"""Extended tests for the Mistral patcher -- covers gaps not in test_mistral_patcher.py.

Specifically: _should_inspect, _enforce_decision, _handle_patcher_error,
_dict_to_mistral_response, _handle_gateway_call_sync, _wrap_stream,
_wrap_complete fail_open paths, and _MistralFakeStreamWrapper.
"""

import httpx
import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from aidefense.runtime.agentsec.patchers.mistral import (
    _extract_assistant_content,
    _handle_patcher_error,
    _should_inspect,
    _dict_to_mistral_response,
    _handle_gateway_call_sync,
    _wrap_complete,
    _wrap_stream,
    _MistralFakeStreamWrapper,
    _MistralStreamingInspectionWrapper,
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
    import aidefense.runtime.agentsec.patchers.mistral as mistral_module
    mistral_module._inspector = None
    yield
    _state.reset()
    reset_registry()
    clear_inspection_context()
    mistral_module._inspector = None


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

class TestMistralHandlePatcherError:
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
# _dict_to_mistral_response()
# ===========================================================================

class TestDictToMistralResponse:
    def test_valid_gateway_json(self):
        data = {
            "id": "chat-123",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hi"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3},
        }
        resp = _dict_to_mistral_response(data)
        assert resp.choices[0].message.content == "Hi"
        assert resp.choices[0].message.role == "assistant"
        assert resp.id == "chat-123"

    def test_empty_choices(self):
        data = {"choices": []}
        resp = _dict_to_mistral_response(data)
        assert len(resp.choices) == 0

    def test_missing_message_content(self):
        data = {"choices": [{"message": {}}]}
        resp = _dict_to_mistral_response(data)
        assert resp.choices[0].message.content == ""


# ===========================================================================
# _handle_gateway_call_sync()
# ===========================================================================

class TestMistralHandleGatewayCallSync:
    def _make_gw_settings(self, url="https://gw.example.com", api_key="key", fail_open=True, timeout=30):
        return SimpleNamespace(url=url, api_key=api_key, fail_open=fail_open, timeout=timeout)

    def test_missing_url_raises(self):
        gw = self._make_gw_settings(url="", api_key="key")
        with pytest.raises(SecurityPolicyError, match="not configured"):
            _handle_gateway_call_sync(
                {"model": "mistral-large", "messages": []}, [], {}, False, gw,
            )

    def test_missing_api_key_raises(self):
        gw = self._make_gw_settings(url="https://gw.example.com", api_key="")
        with pytest.raises(SecurityPolicyError, match="not configured"):
            _handle_gateway_call_sync(
                {"model": "mistral-large", "messages": []}, [], {}, False, gw,
            )

    @patch("httpx.Client")
    def test_success_returns_response(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hello"}, "finish_reason": "stop"}],
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
            {"model": "mistral-large", "messages": [{"role": "user", "content": "Hi"}]},
            [{"role": "user", "content": "Hi"}], {}, False, gw,
        )
        assert result.choices[0].message.content == "Hello"

    @patch("httpx.Client")
    def test_success_stream_returns_fake_wrapper(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Streamed"}, "finish_reason": "stop"}],
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
            {"model": "mistral-large", "messages": []}, [], {}, True, gw,
        )
        assert isinstance(result, _MistralFakeStreamWrapper)

    @patch("httpx.Client")
    def test_http_error_fail_open_true_reraises(self, mock_client_cls):
        request = httpx.Request("POST", "https://gw.example.com")
        response = httpx.Response(500, request=request)
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = MagicMock()
        mock_client.post.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=request, response=response,
        )
        mock_client_cls.return_value = mock_client

        _state.set_state(initialized=True, api_mode={"llm": {"mode": "monitor"}})
        clear_inspection_context()

        gw = self._make_gw_settings(fail_open=True)
        with pytest.raises(httpx.HTTPStatusError):
            _handle_gateway_call_sync(
                {"model": "mistral-large", "messages": []}, [], {}, False, gw,
            )

    @patch("httpx.Client")
    def test_http_error_fail_open_false_raises_security_error(self, mock_client_cls):
        request = httpx.Request("POST", "https://gw.example.com")
        response = httpx.Response(500, request=request)
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = MagicMock()
        mock_client.post.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=request, response=response,
        )
        mock_client_cls.return_value = mock_client

        _state.set_state(initialized=True, api_mode={"llm": {"mode": "monitor"}})
        clear_inspection_context()

        gw = self._make_gw_settings(fail_open=False)
        with pytest.raises(SecurityPolicyError):
            _handle_gateway_call_sync(
                {"model": "mistral-large", "messages": []}, [], {}, False, gw,
            )


# ===========================================================================
# _wrap_stream() — sync
# ===========================================================================

class TestMistralWrapStream:
    @patch("aidefense.runtime.agentsec.patchers.mistral._get_inspector")
    @patch("aidefense.runtime.agentsec.patchers.mistral.resolve_gateway_settings", return_value=None)
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

        result = _wrap_stream(
            mock_wrapped, MagicMock(), (),
            {"model": "mistral-large", "messages": [{"role": "user", "content": "Hi"}]},
        )
        assert isinstance(result, _MistralStreamingInspectionWrapper)

    @patch("aidefense.runtime.agentsec.patchers.mistral._should_inspect", return_value=False)
    def test_passthrough_when_skip(self, _mock_inspect):
        sentinel = object()
        mock_wrapped = MagicMock(return_value=sentinel)
        result = _wrap_stream(
            mock_wrapped, MagicMock(), (),
            {"model": "mistral-large", "messages": []},
        )
        assert result is sentinel

    @patch("aidefense.runtime.agentsec.patchers.mistral._handle_gateway_call_sync")
    @patch("aidefense.runtime.agentsec.patchers.mistral.resolve_gateway_settings")
    def test_gateway_mode_delegates(self, mock_resolve_gw, mock_gw_call):
        gw_settings = SimpleNamespace(url="https://gw.example.com", api_key="key", fail_open=True, timeout=30)
        mock_resolve_gw.return_value = gw_settings
        mock_gw_call.return_value = MagicMock()

        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            api_mode={"llm": {"mode": "monitor"}},
        )
        clear_inspection_context()

        _wrap_stream(
            MagicMock(), MagicMock(), (),
            {"model": "mistral-large", "messages": [{"role": "user", "content": "Hi"}]},
        )
        mock_gw_call.assert_called_once()


# ===========================================================================
# _wrap_complete() — fail_open paths
# ===========================================================================

class TestMistralWrapCompleteFailOpen:
    @patch("aidefense.runtime.agentsec.patchers.mistral._get_inspector")
    @patch("aidefense.runtime.agentsec.patchers.mistral.resolve_gateway_settings", return_value=None)
    def test_inspector_error_fail_open_true_still_calls_wrapped(self, _mock_gw, mock_get_inspector):
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.side_effect = RuntimeError("inspector down")
        mock_get_inspector.return_value = mock_inspector

        _state.set_state(
            initialized=True,
            api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}},
        )
        clear_inspection_context()

        mock_wrapped = MagicMock()
        mock_wrapped.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=""))])

        result = _wrap_complete(
            mock_wrapped, MagicMock(), (),
            {"model": "mistral-large", "messages": [{"role": "user", "content": "Hi"}]},
        )
        # Original should still be called despite inspector error
        mock_wrapped.assert_called_once()

    @patch("aidefense.runtime.agentsec.patchers.mistral._get_inspector")
    @patch("aidefense.runtime.agentsec.patchers.mistral.resolve_gateway_settings", return_value=None)
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
            _wrap_complete(
                mock_wrapped, MagicMock(), (),
                {"model": "mistral-large", "messages": [{"role": "user", "content": "Hi"}]},
            )
        mock_wrapped.assert_not_called()


# ===========================================================================
# _MistralFakeStreamWrapper
# ===========================================================================

class TestMistralFakeStreamWrapper:
    def test_yields_one_chunk_then_stops(self):
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Hello"))])
        wrapper = _MistralFakeStreamWrapper(response)
        chunks = list(wrapper)
        assert len(chunks) == 1
        assert chunks[0].data.choices[0].delta.content == "Hello"


# ===========================================================================
# _MistralStreamingInspectionWrapper
# ===========================================================================

class TestMistralStreamingInspectionWrapper:
    @patch("aidefense.runtime.agentsec.patchers.mistral._get_inspector")
    def test_buffers_content_and_performs_final_inspection(self, mock_get_inspector):
        """Iterating through stream buffers content; final inspection runs at StopIteration."""
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = Decision.allow(reasons=[])
        mock_get_inspector.return_value = mock_inspector

        _state.set_state(
            initialized=True,
            api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}},
        )
        clear_inspection_context()

        # Build fake chunks with data.choices[0].delta.content
        chunk1 = SimpleNamespace(data=SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content="Hello "))],
        ))
        chunk2 = SimpleNamespace(data=SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content="world"))],
        ))
        stream = iter([chunk1, chunk2])

        wrapper = _MistralStreamingInspectionWrapper(
            stream,
            [{"role": "user", "content": "Hi"}],
            {},
        )
        chunks = list(wrapper)
        assert len(chunks) == 2
        # Final inspection should have been called
        assert mock_inspector.inspect_conversation.called

    @patch("aidefense.runtime.agentsec.patchers.mistral._get_inspector")
    def test_no_final_inspection_when_buffer_empty(self, mock_get_inspector):
        """If no content was buffered, final inspection is skipped."""
        mock_inspector = MagicMock()
        mock_get_inspector.return_value = mock_inspector

        _state.set_state(
            initialized=True,
            api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}},
        )
        clear_inspection_context()

        # Chunks with no content
        chunk = SimpleNamespace(data=SimpleNamespace(choices=[]))
        stream = iter([chunk])

        wrapper = _MistralStreamingInspectionWrapper(stream, [], {})
        list(wrapper)
        mock_inspector.inspect_conversation.assert_not_called()


# ===========================================================================
# patch_mistral() — success path
# ===========================================================================

class TestMistralPatchSuccess:
    def test_successful_patch_marks_patched(self):
        from aidefense.runtime.agentsec.patchers.mistral import patch_mistral
        with patch("aidefense.runtime.agentsec.patchers.mistral.safe_import", return_value=MagicMock()), \
             patch("aidefense.runtime.agentsec.patchers.mistral.is_patched", return_value=False), \
             patch("aidefense.runtime.agentsec.patchers.mistral.wrapt") as mock_wrapt, \
             patch("aidefense.runtime.agentsec.patchers.mistral.mark_patched") as mock_mark:
            assert patch_mistral() is True
            mock_mark.assert_called_once_with("mistral")
            assert mock_wrapt.wrap_function_wrapper.call_count >= 4  # complete, stream, complete_async, stream_async

    def test_patch_failure_returns_false(self):
        from aidefense.runtime.agentsec.patchers.mistral import patch_mistral
        with patch("aidefense.runtime.agentsec.patchers.mistral.safe_import", return_value=MagicMock()), \
             patch("aidefense.runtime.agentsec.patchers.mistral.is_patched", return_value=False), \
             patch("aidefense.runtime.agentsec.patchers.mistral.wrapt") as mock_wrapt:
            mock_wrapt.wrap_function_wrapper.side_effect = Exception("wrap fail")
            assert patch_mistral() is False


# ===========================================================================
# _serialize_messages_for_gateway
# ===========================================================================

class TestMistralSerializeMessages:
    def test_normalizes_dict_messages(self):
        from aidefense.runtime.agentsec.patchers.mistral import _serialize_messages_for_gateway
        msgs = [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi"}]
        result = _serialize_messages_for_gateway(msgs)
        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "Hello"}


# ===========================================================================
# _normalize_messages — object-style and list content
# ===========================================================================

class TestMistralNormalizeExtended:
    def test_normalize_object_messages(self):
        from aidefense.runtime.agentsec.patchers.mistral import _normalize_messages
        m = MagicMock()
        m.role = "user"
        m.content = "object content"
        result = _normalize_messages([m])
        assert len(result) == 1
        assert result[0] == {"role": "user", "content": "object content"}

    def test_normalize_list_content_with_text_blocks(self):
        from aidefense.runtime.agentsec.patchers.mistral import _normalize_messages
        msgs = [{"role": "user", "content": [{"text": "block1"}, {"content": "block2"}]}]
        result = _normalize_messages(msgs)
        assert len(result) == 1
        assert "block1" in result[0]["content"]
        assert "block2" in result[0]["content"]

    def test_normalize_list_content_with_string_blocks(self):
        from aidefense.runtime.agentsec.patchers.mistral import _normalize_messages
        msgs = [{"role": "user", "content": ["plain text"]}]
        result = _normalize_messages(msgs)
        assert len(result) == 1
        assert result[0]["content"] == "plain text"

    def test_normalize_list_content_with_object_blocks(self):
        from aidefense.runtime.agentsec.patchers.mistral import _normalize_messages
        obj = MagicMock()
        obj.text = "from obj"
        msgs = [{"role": "user", "content": [obj]}]
        result = _normalize_messages(msgs)
        assert len(result) == 1
        assert "from obj" in result[0]["content"]

    def test_normalize_skips_function_role(self):
        from aidefense.runtime.agentsec.patchers.mistral import _normalize_messages
        msgs = [
            {"role": "function", "content": "fn result"},
            {"role": "user", "content": "Hello"},
        ]
        result = _normalize_messages(msgs)
        assert len(result) == 1
        assert result[0]["role"] == "user"


# ===========================================================================
# _extract_assistant_content — edge cases
# ===========================================================================

class TestMistralExtractExtended:
    def test_extract_text_attribute_on_choice(self):
        choice = SimpleNamespace(text="via text attr")
        response = SimpleNamespace(choices=[choice])
        assert _extract_assistant_content(response) == "via text attr"


# ===========================================================================
# patch_mistral — fallback path when mistralai.client.chat fails
# ===========================================================================

class TestMistralPatchFallback:
    def test_patch_falls_back_to_mistralai_chat(self):
        from aidefense.runtime.agentsec.patchers.mistral import patch_mistral
        call_count = [0]

        def mock_wrap(module, attr, fn):
            call_count[0] += 1
            if call_count[0] <= 4 and "client.chat" in module:
                raise ImportError("no client.chat")

        with patch("aidefense.runtime.agentsec.patchers.mistral.safe_import", return_value=MagicMock()), \
             patch("aidefense.runtime.agentsec.patchers.mistral.is_patched", return_value=False), \
             patch("aidefense.runtime.agentsec.patchers.mistral.wrapt") as mock_wrapt, \
             patch("aidefense.runtime.agentsec.patchers.mistral.mark_patched"):
            mock_wrapt.wrap_function_wrapper.side_effect = mock_wrap
            assert patch_mistral() is True
