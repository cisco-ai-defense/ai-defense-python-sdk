"""Unit tests for the Azure AI Inference patcher.

Covers patch_azure_ai_inference(), _normalize_messages(), _extract_assistant_content(),
_wrap_complete() (API + gateway mode), and streaming wrappers.
"""

import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, AsyncMock

from aidefense.runtime.agentsec.patchers.azure_ai_inference import (
    patch_azure_ai_inference,
    _normalize_messages,
    _extract_assistant_content,
    _should_inspect,
    _enforce_decision,
    _wrap_complete,
    _wrap_complete_async,
    _handle_patcher_error,
    _extract_model_from_instance,
    _messages_to_dicts,
    _dict_to_azure_response,
    _AzureResponseWrapper,
    _StreamingInspectionWrapper,
)
from aidefense.runtime.agentsec.exceptions import SecurityPolicyError
from aidefense.runtime.agentsec.decision import Decision
from aidefense.runtime.agentsec import _state
from aidefense.runtime.agentsec._context import clear_inspection_context
from aidefense.runtime.agentsec.patchers import reset_registry


@pytest.fixture(autouse=True)
def reset_state():
    """Reset agentsec state and patch registry before each test."""
    _state.reset()
    reset_registry()
    clear_inspection_context()
    import aidefense.runtime.agentsec.patchers.azure_ai_inference as mod
    mod._inspector = None
    yield
    _state.reset()
    reset_registry()
    clear_inspection_context()
    mod._inspector = None


# ===========================================================================
# patch_azure_ai_inference()
# ===========================================================================

class TestPatchAzureAiInference:
    """Test patch_azure_ai_inference() behavior."""

    def test_returns_false_when_not_installed(self):
        with patch("aidefense.runtime.agentsec.patchers.azure_ai_inference.safe_import", return_value=None):
            assert patch_azure_ai_inference() is False

    def test_returns_true_when_already_patched(self):
        with patch("aidefense.runtime.agentsec.patchers.azure_ai_inference.is_patched", return_value=True):
            assert patch_azure_ai_inference() is True

    def test_successful_patch(self):
        mock_mod = MagicMock()
        with patch("aidefense.runtime.agentsec.patchers.azure_ai_inference.safe_import", return_value=mock_mod), \
             patch("aidefense.runtime.agentsec.patchers.azure_ai_inference.is_patched", return_value=False), \
             patch("wrapt.wrap_function_wrapper") as mock_wrapt:
            result = patch_azure_ai_inference()
            assert result is True
            assert mock_wrapt.call_count >= 1


# ===========================================================================
# _normalize_messages()
# ===========================================================================

class TestNormalizeMessages:
    """Test message normalization."""

    def test_empty_list(self):
        assert _normalize_messages([]) == []

    def test_none_input(self):
        assert _normalize_messages(None) == []

    def test_basic_dict_messages(self):
        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        result = _normalize_messages(msgs)
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "hello"
        assert result[1]["role"] == "assistant"
        assert result[1]["content"] == "hi there"

    def test_skips_tool_messages(self):
        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "tool", "content": "tool result"},
            {"role": "assistant", "content": "done"},
        ]
        result = _normalize_messages(msgs)
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"

    def test_handles_tool_calls_in_assistant(self):
        msgs = [
            {"role": "assistant", "content": "Let me check", "tool_calls": [
                {"function": {"name": "fetch_url"}}
            ]},
        ]
        result = _normalize_messages(msgs)
        assert len(result) == 1
        assert "fetch_url" in result[0]["content"]

    def test_handles_object_messages(self):
        msg = SimpleNamespace(role="user", content="hello")
        result = _normalize_messages([msg])
        assert len(result) == 1
        assert result[0]["content"] == "hello"

    def test_handles_list_content(self):
        msgs = [
            {"role": "user", "content": [{"type": "text", "text": "hello"}, {"type": "text", "text": "world"}]},
        ]
        result = _normalize_messages(msgs)
        assert len(result) == 1
        assert result[0]["content"] == "hello\nworld"

    def test_skips_empty_content(self):
        msgs = [
            {"role": "user", "content": ""},
        ]
        result = _normalize_messages(msgs)
        assert len(result) == 0


# ===========================================================================
# _extract_assistant_content()
# ===========================================================================

class TestExtractAssistantContent:
    """Test response content extraction."""

    def test_extract_from_object(self):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Hello!"))]
        )
        assert _extract_assistant_content(response) == "Hello!"

    def test_extract_from_dict(self):
        response = {
            "choices": [{"message": {"content": "Hello!"}}]
        }
        assert _extract_assistant_content(response) == "Hello!"

    def test_empty_choices(self):
        response = SimpleNamespace(choices=[])
        assert _extract_assistant_content(response) == ""

    def test_no_content(self):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=None))]
        )
        assert _extract_assistant_content(response) == ""

    def test_error_handling(self):
        assert _extract_assistant_content(None) == ""


# ===========================================================================
# _should_inspect()
# ===========================================================================

class TestShouldInspect:
    """Test inspection gate logic."""

    def test_returns_true_when_api_mode_active(self):
        _state.set_state(
            initialized=True,
            api_mode={"llm": {"mode": "monitor"}},
        )
        clear_inspection_context()
        assert _should_inspect() is True

    def test_returns_false_when_mode_off(self):
        _state.set_state(
            initialized=True,
            api_mode={"llm": {"mode": "off"}},
        )
        clear_inspection_context()
        assert _should_inspect() is False

    def test_returns_true_when_gateway_on(self):
        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            gateway_mode={"llm_mode": "on"},
        )
        clear_inspection_context()
        assert _should_inspect() is True

    def test_returns_false_when_gateway_off(self):
        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            gateway_mode={"llm_mode": "off"},
        )
        clear_inspection_context()
        assert _should_inspect() is False


# ===========================================================================
# _enforce_decision()
# ===========================================================================

class TestEnforceDecision:
    def test_allow_passes(self):
        _state.set_state(initialized=True, api_mode={"llm": {"mode": "enforce"}})
        _enforce_decision(Decision.allow())

    def test_block_in_enforce_raises(self):
        _state.set_state(initialized=True, api_mode={"llm": {"mode": "enforce"}})
        with pytest.raises(SecurityPolicyError):
            _enforce_decision(Decision.block(reasons=["test"]))

    def test_block_in_monitor_passes(self):
        _state.set_state(initialized=True, api_mode={"llm": {"mode": "monitor"}})
        _enforce_decision(Decision.block(reasons=["test"]))


# ===========================================================================
# _messages_to_dicts()
# ===========================================================================

class TestMessagesToDicts:
    def test_dict_messages(self):
        msgs = [{"role": "user", "content": "hi"}]
        result = _messages_to_dicts(msgs)
        assert result == [{"role": "user", "content": "hi"}]

    def test_object_with_as_dict(self):
        msg = MagicMock()
        msg.as_dict.return_value = {"role": "user", "content": "hi"}
        result = _messages_to_dicts([msg])
        assert result[0] == {"role": "user", "content": "hi"}

    def test_empty_list(self):
        assert _messages_to_dicts([]) == []

    def test_none_input(self):
        assert _messages_to_dicts(None) == []


# ===========================================================================
# _AzureResponseWrapper
# ===========================================================================

class TestAzureResponseWrapper:
    def test_choices(self):
        wrapper = _AzureResponseWrapper({
            "choices": [{"message": {"content": "hello", "role": "assistant"}, "finish_reason": "stop", "index": 0}],
            "id": "test-id",
            "model": "gpt-4o",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        })
        assert len(wrapper.choices) == 1
        assert wrapper.choices[0].message.content == "hello"
        assert wrapper.choices[0].message.role == "assistant"
        assert wrapper.choices[0].finish_reason == "stop"
        assert wrapper.id == "test-id"
        assert wrapper.model == "gpt-4o"
        assert wrapper.usage.prompt_tokens == 10
        assert wrapper.usage.total_tokens == 15


# ===========================================================================
# _wrap_complete() - API mode
# ===========================================================================

class TestWrapCompleteApiMode:
    """Test the sync wrapper in API mode."""

    def _setup_api_mode(self):
        _state.set_state(
            initialized=True,
            api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}},
        )
        clear_inspection_context()

    def test_calls_original_and_inspects(self):
        self._setup_api_mode()
        mock_response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="response text"))]
        )
        wrapped = MagicMock(return_value=mock_response)
        instance = MagicMock()

        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = Decision.allow()

        with patch("aidefense.runtime.agentsec.patchers.azure_ai_inference._get_inspector", return_value=mock_inspector):
            result = _wrap_complete(
                wrapped, instance, (),
                {"messages": [{"role": "user", "content": "hello"}], "model": "gpt-4o"},
            )

        wrapped.assert_called_once()
        assert mock_inspector.inspect_conversation.call_count >= 1
        assert result is mock_response

    def test_skips_when_mode_off(self):
        _state.set_state(
            initialized=True,
            api_mode={"llm": {"mode": "off"}},
        )
        clear_inspection_context()

        wrapped = MagicMock(return_value="original")
        instance = MagicMock()

        result = _wrap_complete(wrapped, instance, (), {"messages": [], "model": "gpt-4o"})
        wrapped.assert_called_once()
        assert result == "original"

    def test_enforce_block_raises(self):
        _state.set_state(
            initialized=True,
            api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "enforce"}},
        )
        clear_inspection_context()

        wrapped = MagicMock()
        instance = MagicMock()

        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = Decision.block(reasons=["blocked"])

        with patch("aidefense.runtime.agentsec.patchers.azure_ai_inference._get_inspector", return_value=mock_inspector):
            with pytest.raises(SecurityPolicyError):
                _wrap_complete(
                    wrapped, instance, (),
                    {"messages": [{"role": "user", "content": "test"}], "model": "gpt-4o"},
                )


# ===========================================================================
# _wrap_complete() - Gateway mode
# ===========================================================================

class TestWrapCompleteGatewayMode:
    """Test the sync wrapper in gateway mode."""

    def _setup_gateway_mode(self):
        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            gateway_mode={"llm_mode": "on"},
            api_mode={"llm": {"mode": "enforce"}},
        )
        clear_inspection_context()

    def test_routes_to_gateway(self):
        self._setup_gateway_mode()

        wrapped = MagicMock()
        instance = MagicMock()

        mock_gw_settings = SimpleNamespace(
            url="https://gw.example.com",
            api_key="test-key",
            timeout=30,
            fail_open=True,
            gateway_model="gpt-4o",
        )

        with patch("aidefense.runtime.agentsec.patchers.azure_ai_inference.resolve_gateway_settings", return_value=mock_gw_settings), \
             patch("aidefense.runtime.agentsec.patchers.azure_ai_inference._handle_gateway_call_sync") as mock_gw:
            mock_gw.return_value = _AzureResponseWrapper({"choices": [{"message": {"content": "gw response"}}]})
            result = _wrap_complete(
                wrapped, instance, (),
                {"messages": [{"role": "user", "content": "hello"}], "model": "gpt-4o"},
            )

        wrapped.assert_not_called()
        mock_gw.assert_called_once()
        assert result.choices[0].message.content == "gw response"


# ===========================================================================
# _handle_patcher_error()
# ===========================================================================

class TestHandlePatcherError:
    def test_fail_open_returns_allow(self):
        _state.set_state(
            initialized=True,
            api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}},
        )
        result = _handle_patcher_error(ValueError("test"), "test_op")
        assert result.action == "allow"

    def test_fail_closed_raises(self):
        _state.set_state(
            initialized=True,
            api_mode={"llm_defaults": {"fail_open": False}, "llm": {"mode": "monitor"}},
        )
        with pytest.raises(SecurityPolicyError):
            _handle_patcher_error(ValueError("test"), "test_op")


# ===========================================================================
# Streaming wrapper
# ===========================================================================

class TestStreamingInspectionWrapper:
    def test_passes_through_chunks(self):
        _state.set_state(
            initialized=True,
            api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}},
        )
        clear_inspection_context()

        chunks = [
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="hello"))]),
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=" world"))]),
        ]

        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = Decision.allow()

        with patch("aidefense.runtime.agentsec.patchers.azure_ai_inference._get_inspector", return_value=mock_inspector):
            wrapper = _StreamingInspectionWrapper(
                iter(chunks),
                [{"role": "user", "content": "test"}],
                {},
            )
            result = list(wrapper)

        assert len(result) == 2
