"""Extended tests for the OpenAI patcher.

Covers _detect_provider, _get_azure_api_version, _get_azure_deployment_name,
_normalize_messages, _extract_assistant_content, _content_to_text,
_resolve_response_for_inspection, _normalize_kwargs_for_strict_openai_compat,
_should_inspect, _enforce_decision, _handle_patcher_error, _handle_gateway_call_sync,
_FakeStreamWrapper, _dict_to_openai_response, _create_stream_chunk_from_response,
_wrap_chat_completions_create, _wrap_responses_create, StreamingInspectionWrapper,
_get_inspector, and patch_openai.
"""

import httpx
import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from aidefense.runtime.agentsec.patchers.openai import (
    _detect_provider,
    _get_azure_api_version,
    _get_azure_deployment_name,
    _normalize_messages,
    _content_to_text,
    _resolve_response_for_inspection,
    _extract_assistant_content,
    _normalize_kwargs_for_strict_openai_compat,
    _should_inspect,
    _enforce_decision,
    _handle_patcher_error,
    _handle_gateway_call_sync,
    _FakeStreamWrapper,
    _dict_to_openai_response,
    _create_stream_chunk_from_response,
    _wrap_chat_completions_create,
    _wrap_responses_create,
    StreamingInspectionWrapper,
    patch_openai,
)
from aidefense.runtime.agentsec.exceptions import SecurityPolicyError
from aidefense.runtime.agentsec.decision import Decision
from aidefense.runtime.agentsec import _state
from aidefense.runtime.agentsec._context import clear_inspection_context, set_inspection_context
from aidefense.runtime.agentsec.patchers import reset_registry


@pytest.fixture(autouse=True)
def reset_state():
    _state.reset()
    reset_registry()
    clear_inspection_context()
    import aidefense.runtime.agentsec.patchers.openai as openai_module
    openai_module._inspector = None
    yield
    _state.reset()
    reset_registry()
    clear_inspection_context()
    openai_module._inspector = None


# ===========================================================================
# _detect_provider()
# ===========================================================================

class TestDetectProvider:
    def test_azure_by_client_type(self):
        client = type("AzureOpenAI", (), {})()
        instance = SimpleNamespace(_client=client)
        assert _detect_provider(instance) == "azure_openai"

    def test_azure_by_base_url(self):
        client = SimpleNamespace(base_url="https://myresource.openai.azure.com/")
        instance = SimpleNamespace(_client=client)
        assert _detect_provider(instance) == "azure_openai"

    def test_openai_default(self):
        client = type("OpenAI", (), {"base_url": "https://api.openai.com"})()
        instance = SimpleNamespace(_client=client)
        assert _detect_provider(instance) == "openai"

    def test_no_client_returns_openai(self):
        assert _detect_provider(SimpleNamespace()) == "openai"

    def test_exception_returns_openai(self):
        instance = MagicMock()
        instance._client = property(lambda self: (_ for _ in ()).throw(RuntimeError))
        assert _detect_provider(instance) == "openai"


# ===========================================================================
# _get_azure_api_version()
# ===========================================================================

class TestGetAzureApiVersion:
    def test_from_api_version_attr(self):
        client = SimpleNamespace(_api_version="2024-02-15")
        instance = SimpleNamespace(_client=client)
        assert _get_azure_api_version(instance) == "2024-02-15"

    def test_from_default_query(self):
        client = SimpleNamespace(_default_query={"api-version": "2024-01-01"})
        instance = SimpleNamespace(_client=client)
        assert _get_azure_api_version(instance) == "2024-01-01"

    def test_none_when_not_available(self):
        client = SimpleNamespace()
        instance = SimpleNamespace(_client=client)
        assert _get_azure_api_version(instance) is None

    def test_none_when_no_client(self):
        assert _get_azure_api_version(SimpleNamespace()) is None


# ===========================================================================
# _get_azure_deployment_name()
# ===========================================================================

class TestGetAzureDeploymentName:
    def test_from_kwargs_model(self):
        assert _get_azure_deployment_name(SimpleNamespace(), {"model": "gpt-4"}) == "gpt-4"

    def test_from_azure_deployment_attr(self):
        client = SimpleNamespace(_azure_deployment="my-deploy")
        instance = SimpleNamespace(_client=client)
        assert _get_azure_deployment_name(instance, {}) == "my-deploy"

    def test_from_base_url(self):
        client = SimpleNamespace(base_url="https://x.openai.azure.com/openai/deployments/gpt35/")
        instance = SimpleNamespace(_client=client)
        assert _get_azure_deployment_name(instance, {}) == "gpt35"

    def test_none_when_not_available(self):
        instance = SimpleNamespace(_client=SimpleNamespace())
        assert _get_azure_deployment_name(instance, {}) is None


# ===========================================================================
# _normalize_kwargs_for_strict_openai_compat()
# ===========================================================================

class TestNormalizeKwargsForStrictOpenAICompat:
    def test_mistral_rewrites_max_completion_tokens(self):
        client = SimpleNamespace(base_url="https://api.mistral.ai/v1")
        instance = SimpleNamespace(_client=client)
        kwargs = {"model": "mistral-large", "max_completion_tokens": 100}
        result = _normalize_kwargs_for_strict_openai_compat(instance, kwargs)
        assert result.get("max_tokens") == 100
        assert "max_completion_tokens" not in result

    def test_mistral_drops_penalty_params(self):
        client = SimpleNamespace(base_url="https://api.mistral.ai/")
        instance = SimpleNamespace(_client=client)
        kwargs = {"model": "mistral", "presence_penalty": 0.5, "frequency_penalty": 0.2}
        result = _normalize_kwargs_for_strict_openai_compat(instance, kwargs)
        assert "presence_penalty" not in result
        assert "frequency_penalty" not in result

    def test_non_mistral_passes_through(self):
        client = SimpleNamespace(base_url="https://api.openai.com/v1")
        instance = SimpleNamespace(_client=client)
        kwargs = {"model": "gpt-4", "max_completion_tokens": 50, "presence_penalty": 0.1}
        result = _normalize_kwargs_for_strict_openai_compat(instance, kwargs)
        assert result == kwargs

    def test_no_client_returns_kwargs(self):
        instance = SimpleNamespace()
        kwargs = {"model": "test", "max_completion_tokens": 100}
        result = _normalize_kwargs_for_strict_openai_compat(instance, kwargs)
        assert result == kwargs

    def test_mistral_both_max_tokens_replaced(self):
        client = SimpleNamespace(base_url="https://api.MISTRAL.ai/v1")
        instance = SimpleNamespace(_client=client)
        kwargs = {"max_tokens": 50, "max_completion_tokens": 100}
        result = _normalize_kwargs_for_strict_openai_compat(instance, kwargs)
        assert result["max_tokens"] == 100
        assert "max_completion_tokens" not in result


# ===========================================================================
# _normalize_messages()
# ===========================================================================

class TestNormalizeMessages:
    def test_basic_messages(self):
        msgs = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}]
        result = _normalize_messages(msgs)
        assert len(result) == 2

    def test_list_content_blocks(self):
        msgs = [{"role": "user", "content": [{"type": "text", "text": "block1"}, {"text": "block2"}]}]
        result = _normalize_messages(msgs)
        assert len(result) == 1
        assert "block1" in result[0]["content"]
        assert "block2" in result[0]["content"]

    def test_string_content_in_list(self):
        msgs = [{"role": "user", "content": ["plain text"]}]
        result = _normalize_messages(msgs)
        assert result[0]["content"] == "plain text"

    def test_skips_tool_and_function_roles(self):
        msgs = [
            {"role": "tool", "content": "result"},
            {"role": "function", "content": "result"},
            {"role": "user", "content": "Hello"},
        ]
        assert len(_normalize_messages(msgs)) == 1

    def test_assistant_with_tool_calls(self):
        msgs = [{"role": "assistant", "content": "Calling tool",
                 "tool_calls": [{"function": {"name": "get_weather"}}]}]
        result = _normalize_messages(msgs)
        assert "get_weather" in result[0]["content"]

    def test_non_list_returns_empty(self):
        assert _normalize_messages("not a list") == []
        assert _normalize_messages(None) == []


# ===========================================================================
# _extract_assistant_content()
# ===========================================================================

class TestContentToText:
    """Tests for _content_to_text (block-based content flattening)."""

    def test_none_returns_empty(self):
        assert _content_to_text(None) == ""

    def test_string_passthrough(self):
        assert _content_to_text("hello") == "hello"

    def test_block_with_text_key(self):
        content = [{"type": "text", "text": "Hello"}]
        assert _content_to_text(content) == "Hello"

    def test_block_with_content_key(self):
        content = [{"type": "text", "content": "Hi from content"}]
        assert _content_to_text(content) == "Hi from content"

    def test_block_text_precedence_over_content(self):
        content = [{"text": "a", "content": "b"}]
        assert _content_to_text(content) == "a"

    def test_multiple_blocks(self):
        content = [{"text": "line1"}, {"text": "line2"}, {"content": "line3"}]
        assert _content_to_text(content) == "line1\nline2\nline3"

    def test_object_with_text_attr(self):
        block = SimpleNamespace(text="via attr")
        assert _content_to_text([block]) == "via attr"

    def test_string_in_list(self):
        assert _content_to_text(["plain"]) == "plain"


class TestResolveResponseForInspection:
    """Tests for _resolve_response_for_inspection (raw wrapper parsing)."""

    def test_has_choices_returns_unchanged(self):
        response = SimpleNamespace(choices=[1], parse=lambda: None)
        assert _resolve_response_for_inspection(response) is response

    def test_no_choices_calls_parse(self):
        parsed = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="OK"))])
        raw = SimpleNamespace(parse=lambda: parsed)
        result = _resolve_response_for_inspection(raw)
        assert result is parsed
        assert result.choices[0].message.content == "OK"

    def test_parse_returns_none_keeps_response(self):
        raw = SimpleNamespace(parse=lambda: None)
        assert _resolve_response_for_inspection(raw) is raw


class TestExtractAssistantContent:
    def test_from_message_content(self):
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Hi"))])
        assert _extract_assistant_content(response) == "Hi"

    def test_from_text_attr(self):
        choice = SimpleNamespace(text="via text")
        response = SimpleNamespace(choices=[choice])
        assert _extract_assistant_content(response) == "via text"

    def test_empty_when_no_choices(self):
        assert _extract_assistant_content(SimpleNamespace(choices=[])) == ""

    def test_empty_on_exception(self):
        assert _extract_assistant_content(object()) == ""

    def test_dict_response_with_message_content(self):
        response = {"choices": [{"message": {"content": "from dict"}}]}
        assert _extract_assistant_content(response) == "from dict"

    def test_dict_response_with_text(self):
        response = {"choices": [{"text": "dict text"}]}
        assert _extract_assistant_content(response) == "dict text"

    def test_raw_wrapper_with_parse(self):
        parsed = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="parsed"))])
        raw = SimpleNamespace(parse=lambda: parsed)
        assert _extract_assistant_content(raw) == "parsed"

    def test_block_based_content_in_message(self):
        content = [{"type": "text", "text": "block text"}]
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )
        assert _extract_assistant_content(response) == "block text"

    def test_block_based_content_key(self):
        content = [{"type": "text", "content": "from content key"}]
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )
        assert _extract_assistant_content(response) == "from content key"


# ===========================================================================
# _should_inspect() / _enforce_decision()
# ===========================================================================

class TestShouldInspect:
    def test_false_when_skip_active(self):
        with patch("aidefense.runtime.agentsec._context.is_llm_skip_active", return_value=True):
            assert _should_inspect() is False

    def test_false_when_mode_off(self):
        _state.set_state(initialized=True, api_mode={"llm": {"mode": "off"}})
        assert _should_inspect() is False

    def test_false_when_done(self):
        _state.set_state(initialized=True, api_mode={"llm": {"mode": "monitor"}})
        set_inspection_context(done=True)
        assert _should_inspect() is False

    def test_true_when_active(self):
        _state.set_state(initialized=True, api_mode={"llm": {"mode": "monitor"}})
        clear_inspection_context()
        assert _should_inspect() is True

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


class TestEnforceDecision:
    def test_enforce_block_raises(self):
        _state.set_state(initialized=True, api_mode={"llm": {"mode": "enforce"}})
        with pytest.raises(SecurityPolicyError):
            _enforce_decision(Decision.block(reasons=["bad"]))

    def test_monitor_block_no_raise(self):
        _state.set_state(initialized=True, api_mode={"llm": {"mode": "monitor"}})
        _enforce_decision(Decision.block(reasons=["bad"]))


# ===========================================================================
# _handle_patcher_error()
# ===========================================================================

class TestHandlePatcherError:
    def test_fail_open_true_returns_allow(self):
        _state.set_state(initialized=True, api_mode={"llm_defaults": {"fail_open": True}})
        d = _handle_patcher_error(RuntimeError("boom"), "test")
        assert d.action == "allow"

    def test_fail_open_false_raises(self):
        _state.set_state(initialized=True, api_mode={"llm_defaults": {"fail_open": False}})
        with pytest.raises(SecurityPolicyError):
            _handle_patcher_error(RuntimeError("boom"), "test")


# ===========================================================================
# _dict_to_openai_response()
# ===========================================================================

class TestDictToOpenaiResponse:
    def test_valid_response(self):
        data = {
            "id": "chatcmpl-1",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hello"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
        }
        resp = _dict_to_openai_response(data)
        assert resp.choices[0].message.content == "Hello"
        assert resp.usage.total_tokens == 7
        assert resp.id == "chatcmpl-1"

    def test_message_with_tool_calls(self):
        data = {
            "choices": [{
                "message": {
                    "role": "assistant", "content": None,
                    "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "foo", "arguments": "{}"}}],
                },
            }],
        }
        resp = _dict_to_openai_response(data)
        assert resp.choices[0].message.tool_calls[0].function.name == "foo"

    def test_parse_returns_self(self):
        data = {"choices": [{"message": {"content": "x"}}]}
        resp = _dict_to_openai_response(data)
        assert resp.parse() is resp

    def test_model_dump_returns_dict(self):
        data = {"choices": [{"message": {"content": "x"}}]}
        resp = _dict_to_openai_response(data)
        assert resp.model_dump() is data

    def test_message_dict_interface(self):
        data = {"choices": [{"message": {"role": "assistant", "content": "x"}}]}
        resp = _dict_to_openai_response(data)
        msg = resp.choices[0].message
        assert "role" in msg.keys()
        assert msg["content"] == "x"
        assert msg.get("content") == "x"


# ===========================================================================
# _create_stream_chunk_from_response()
# ===========================================================================

class TestCreateStreamChunk:
    def test_creates_chunk_with_content(self):
        data = {"choices": [{"message": {"content": "Hello"}, "finish_reason": "stop"}]}
        resp = _dict_to_openai_response(data)
        chunk = _create_stream_chunk_from_response(resp)
        assert chunk.choices[0].delta.content == "Hello"
        assert chunk.choices[0].finish_reason == "stop"

    def test_creates_chunk_with_tool_calls(self):
        data = {"choices": [{"message": {"content": None, "tool_calls": [{"id": "c1", "function": {"name": "f", "arguments": "{}"}}]}}]}
        resp = _dict_to_openai_response(data)
        chunk = _create_stream_chunk_from_response(resp)
        assert chunk.choices[0].delta.tool_calls is not None


# ===========================================================================
# _FakeStreamWrapper
# ===========================================================================

class TestFakeStreamWrapper:
    def test_yields_one_chunk_then_stops(self):
        data = {"choices": [{"message": {"content": "Hi"}}]}
        resp = _dict_to_openai_response(data)
        wrapper = _FakeStreamWrapper(resp)
        chunks = list(wrapper)
        assert len(chunks) == 1
        assert chunks[0].choices[0].delta.content == "Hi"


# ===========================================================================
# _handle_gateway_call_sync()
# ===========================================================================

class TestHandleGatewayCallSync:
    def _gw(self, url="https://gw.example.com", api_key="key", fail_open=True, timeout=30, gateway_model=None):
        return SimpleNamespace(url=url, api_key=api_key, fail_open=fail_open, timeout=timeout, gateway_model=gateway_model)

    @patch("httpx.Client")
    def test_success_non_streaming(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": "GW"}}]}
        mock_resp.raise_for_status = MagicMock()
        mock_resp.status_code = 200
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        clear_inspection_context()
        result = _handle_gateway_call_sync(
            {"model": "gpt-4", "messages": [{"role": "user", "content": "Hi"}]},
            False, [{"role": "user", "content": "Hi"}], {}, "openai", self._gw(),
        )
        assert result.choices[0].message.content == "GW"

    @patch("httpx.Client")
    def test_success_streaming_returns_fake_wrapper(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": "GW"}}]}
        mock_resp.raise_for_status = MagicMock()
        mock_resp.status_code = 200
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        clear_inspection_context()
        result = _handle_gateway_call_sync(
            {"model": "gpt-4", "messages": []}, True, [], {}, "openai", self._gw(),
        )
        assert isinstance(result, _FakeStreamWrapper)

    @patch("httpx.Client")
    def test_http_error_fail_open_true_reraises(self, mock_client_cls):
        request = httpx.Request("POST", "https://gw.example.com")
        response = httpx.Response(500, request=request)
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = MagicMock(status_code=500)
        mock_client.post.return_value.raise_for_status.side_effect = httpx.HTTPStatusError("500", request=request, response=response)
        mock_client_cls.return_value = mock_client

        clear_inspection_context()
        with pytest.raises(httpx.HTTPStatusError):
            _handle_gateway_call_sync({"model": "gpt-4", "messages": []}, False, [], {}, "openai", self._gw(fail_open=True))

    @patch("httpx.Client")
    def test_http_error_fail_open_false_raises_security(self, mock_client_cls):
        request = httpx.Request("POST", "https://gw.example.com")
        response = httpx.Response(500, request=request)
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = MagicMock(status_code=500)
        mock_client.post.return_value.raise_for_status.side_effect = httpx.HTTPStatusError("500", request=request, response=response)
        mock_client_cls.return_value = mock_client

        clear_inspection_context()
        with pytest.raises(SecurityPolicyError):
            _handle_gateway_call_sync({"model": "gpt-4", "messages": []}, False, [], {}, "openai", self._gw(fail_open=False))

    @patch("httpx.Client")
    def test_azure_url_construction(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": "AZ"}}]}
        mock_resp.raise_for_status = MagicMock()
        mock_resp.status_code = 200
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        clear_inspection_context()
        _handle_gateway_call_sync(
            {"model": "gpt-4", "messages": []}, False, [], {},
            "azure_openai", self._gw(), "2024-01-01", "my-deploy",
        )
        # Verify Azure URL was constructed
        call_args = mock_client.post.call_args
        url = call_args[0][0]
        assert "deployments" in url
        assert "api-version" in url


# ===========================================================================
# StreamingInspectionWrapper
# ===========================================================================

class TestStreamingInspectionWrapper:
    @patch("aidefense.runtime.agentsec.patchers.openai._get_inspector")
    def test_buffers_and_inspects(self, mock_get_inspector):
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = Decision.allow(reasons=[])
        mock_get_inspector.return_value = mock_inspector

        _state.set_state(initialized=True, api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}})
        clear_inspection_context()

        chunk = SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="Hello"))])
        wrapper = StreamingInspectionWrapper(iter([chunk]), [{"role": "user", "content": "Hi"}], {})
        chunks = list(wrapper)
        assert len(chunks) == 1
        assert mock_inspector.inspect_conversation.called

    @patch("aidefense.runtime.agentsec.patchers.openai._get_inspector")
    def test_no_inspection_when_empty_buffer(self, mock_get_inspector):
        mock_inspector = MagicMock()
        mock_get_inspector.return_value = mock_inspector

        _state.set_state(initialized=True, api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}})
        clear_inspection_context()

        chunk = SimpleNamespace(choices=[])
        wrapper = StreamingInspectionWrapper(iter([chunk]), [], {})
        list(wrapper)
        mock_inspector.inspect_conversation.assert_not_called()


# ===========================================================================
# _wrap_chat_completions_create() — sync
# ===========================================================================

class TestWrapChatCompletionsCreate:
    @patch("aidefense.runtime.agentsec.patchers.openai._should_inspect", return_value=False)
    def test_passthrough_when_skip(self, _mock):
        mock_wrapped = MagicMock(return_value="raw")
        result = _wrap_chat_completions_create(mock_wrapped, None, (), {"model": "gpt-4", "messages": []})
        assert result == "raw"

    @patch("aidefense.runtime.agentsec.patchers.openai._get_inspector")
    @patch("aidefense.runtime.agentsec.patchers.openai.resolve_gateway_settings", return_value=None)
    def test_api_mode_pre_post_inspection(self, _gw, mock_get_inspector):
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = Decision.allow(reasons=[])
        mock_get_inspector.return_value = mock_inspector

        _state.set_state(initialized=True, api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}})
        clear_inspection_context()

        mock_wrapped = MagicMock()
        mock_wrapped.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Reply"))])

        result = _wrap_chat_completions_create(mock_wrapped, SimpleNamespace(), (), {"model": "gpt-4", "messages": [{"role": "user", "content": "Hi"}]})
        assert mock_inspector.inspect_conversation.call_count == 2

    @patch("aidefense.runtime.agentsec.patchers.openai._get_inspector")
    @patch("aidefense.runtime.agentsec.patchers.openai.resolve_gateway_settings", return_value=None)
    def test_fail_open_true_calls_wrapped_on_error(self, _gw, mock_get_inspector):
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.side_effect = RuntimeError("down")
        mock_get_inspector.return_value = mock_inspector

        _state.set_state(initialized=True, api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}})
        clear_inspection_context()

        mock_wrapped = MagicMock()
        mock_wrapped.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=""))])
        _wrap_chat_completions_create(mock_wrapped, SimpleNamespace(), (), {"model": "gpt-4", "messages": [{"role": "user", "content": "Hi"}]})
        mock_wrapped.assert_called_once()

    @patch("aidefense.runtime.agentsec.patchers.openai._get_inspector")
    @patch("aidefense.runtime.agentsec.patchers.openai.resolve_gateway_settings", return_value=None)
    def test_fail_open_false_raises_on_error(self, _gw, mock_get_inspector):
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.side_effect = RuntimeError("down")
        mock_get_inspector.return_value = mock_inspector

        _state.set_state(initialized=True, api_mode={"llm_defaults": {"fail_open": False}, "llm": {"mode": "monitor"}})
        clear_inspection_context()

        with pytest.raises(SecurityPolicyError):
            _wrap_chat_completions_create(MagicMock(), SimpleNamespace(), (), {"model": "gpt-4", "messages": [{"role": "user", "content": "Hi"}]})


# ===========================================================================
# _wrap_responses_create()
# ===========================================================================

class TestWrapResponsesCreate:
    @patch("aidefense.runtime.agentsec.patchers.openai._get_inspector")
    @patch("aidefense.runtime.agentsec.patchers.openai.resolve_gateway_settings", return_value=None)
    def test_string_input_inspection(self, _gw, mock_get_inspector):
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = Decision.allow(reasons=[])
        mock_get_inspector.return_value = mock_inspector

        _state.set_state(initialized=True, api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}})
        clear_inspection_context()

        mock_wrapped = MagicMock()
        mock_wrapped.return_value = SimpleNamespace(output_text="Reply")
        _wrap_responses_create(mock_wrapped, None, (), {"input": "Hello"})
        assert mock_inspector.inspect_conversation.call_count >= 1

    @patch("aidefense.runtime.agentsec.patchers.openai._should_inspect", return_value=False)
    def test_passthrough_when_skip(self, _):
        mock_wrapped = MagicMock(return_value="raw")
        result = _wrap_responses_create(mock_wrapped, None, (), {"input": "Hi"})
        assert result == "raw"


# ===========================================================================
# _get_inspector() / patch_openai()
# ===========================================================================

class TestGetInspector:
    @patch("aidefense.runtime.agentsec.inspectors.register_inspector_for_cleanup")
    @patch("aidefense.runtime.agentsec.patchers.openai.LLMInspector")
    def test_creates_on_first_call(self, mock_cls, mock_register):
        from aidefense.runtime.agentsec.patchers.openai import _get_inspector
        import aidefense.runtime.agentsec.patchers.openai as mod
        _state.set_state(initialized=True, api_mode={"llm_defaults": {"fail_open": True}})
        mod._inspector = None
        mock_cls.return_value = MagicMock()
        _get_inspector()
        mock_cls.assert_called_once()

    @patch("aidefense.runtime.agentsec.patchers.openai.LLMInspector")
    def test_returns_cached(self, mock_cls):
        from aidefense.runtime.agentsec.patchers.openai import _get_inspector
        import aidefense.runtime.agentsec.patchers.openai as mod
        sentinel = MagicMock()
        mod._inspector = sentinel
        assert _get_inspector() is sentinel
        mock_cls.assert_not_called()


class TestPatchOpenai:
    def test_returns_false_when_not_installed(self):
        with patch("aidefense.runtime.agentsec.patchers.openai.safe_import", return_value=None):
            assert patch_openai() is False

    def test_returns_true_when_already_patched(self):
        with patch("aidefense.runtime.agentsec.patchers.openai.is_patched", return_value=True):
            assert patch_openai() is True

    def test_successful_patch(self):
        with patch("aidefense.runtime.agentsec.patchers.openai.safe_import", return_value=MagicMock()), \
             patch("aidefense.runtime.agentsec.patchers.openai.is_patched", return_value=False), \
             patch("aidefense.runtime.agentsec.patchers.openai.wrapt") as mock_wrapt, \
             patch("aidefense.runtime.agentsec.patchers.openai.mark_patched"):
            assert patch_openai() is True
            assert mock_wrapt.wrap_function_wrapper.call_count >= 2

    def test_patch_failure_returns_false(self):
        with patch("aidefense.runtime.agentsec.patchers.openai.safe_import", return_value=MagicMock()), \
             patch("aidefense.runtime.agentsec.patchers.openai.is_patched", return_value=False), \
             patch("aidefense.runtime.agentsec.patchers.openai.wrapt") as mock_wrapt:
            mock_wrapt.wrap_function_wrapper.side_effect = Exception("fail")
            assert patch_openai() is False
