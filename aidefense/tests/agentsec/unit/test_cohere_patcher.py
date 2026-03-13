"""Unit tests for the Cohere v2 client patcher."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from aidefense.runtime.agentsec.patchers.cohere import (
    patch_cohere,
    _normalize_messages,
    _content_to_string,
    _extract_assistant_content,
    _wrap_chat,
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
    import aidefense.runtime.agentsec.patchers.cohere as cohere_module
    cohere_module._inspector = None
    yield
    _state.reset()
    reset_registry()
    clear_inspection_context()
    cohere_module._inspector = None


class TestCohereNormalization:
    """Test message normalization for Cohere v2 formats."""

    def test_normalize_dict_messages(self):
        """Normalize list of dicts with role/content."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        result = _normalize_messages(messages)
        assert len(result) == 2
        assert result[0]["role"] == "user" and result[0]["content"] == "Hello"
        assert result[1]["role"] == "assistant" and result[1]["content"] == "Hi there"

    def test_normalize_skips_tool_role(self):
        """Tool role messages are skipped."""
        messages = [
            {"role": "user", "content": "Hi"},
            {"role": "tool", "content": "tool result"},
        ]
        result = _normalize_messages(messages)
        assert len(result) == 1
        assert result[0]["role"] == "user"

    def test_normalize_object_messages(self):
        """Normalize message-like objects with role and content attributes."""
        m1 = MagicMock()
        m1.role = "user"
        m1.content = "Hello"
        m2 = MagicMock()
        m2.role = "system"
        m2.content = "You are helpful."
        result = _normalize_messages([m1, m2])
        assert len(result) == 2
        assert result[0]["role"] == "user" and result[0]["content"] == "Hello"
        assert result[1]["role"] == "system" and result[1]["content"] == "You are helpful."

    def test_normalize_empty_or_none(self):
        """Empty or non-list input returns empty list."""
        assert _normalize_messages([]) == []
        assert _normalize_messages(None) == []
        assert _normalize_messages("not a list") == []


class TestContentToString:
    """Test _content_to_string helper."""

    def test_string_passthrough(self):
        assert _content_to_string("hello") == "hello"

    def test_none_empty(self):
        assert _content_to_string(None) == ""
        assert _content_to_string("") == ""

    def test_list_of_dicts_with_text(self):
        assert _content_to_string([{"text": "a"}, {"text": "b"}]) == "a\nb"

    def test_list_with_objects_with_text(self):
        obj = MagicMock()
        obj.text = "obj text"
        assert _content_to_string([obj]) == "obj text"


class TestExtractAssistantContent:
    """Test extraction of assistant text from V2ChatResponse."""

    def test_extract_from_message_content_list(self):
        """Response has message.content as list of items with text."""
        item = MagicMock()
        item.text = "Assistant reply"
        msg = MagicMock()
        msg.content = [item]
        response = MagicMock()
        response.message = msg
        assert _extract_assistant_content(response) == "Assistant reply"

    def test_extract_from_message_content_string(self):
        """Response message.content can be a string."""
        msg = MagicMock()
        msg.content = "Direct string"
        response = MagicMock()
        response.message = msg
        assert _extract_assistant_content(response) == "Direct string"

    def test_extract_empty_when_no_message(self):
        """Response without message attribute returns empty string."""
        response = object()  # no .message
        assert _extract_assistant_content(response) == ""


class TestCoherePatcherInspection:
    """Test that chat wrapper calls inspector and enforces decision."""

    @patch("aidefense.runtime.agentsec.patchers.cohere._get_inspector")
    def test_sync_chat_calls_inspector(self, mock_get_inspector):
        """Sync chat triggers prompt and response inspection."""
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = Decision.allow(reasons=[])
        mock_get_inspector.return_value = mock_inspector

        _state.set_state(
            initialized=True,
            llm_rules=None,
            api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}},
        )
        clear_inspection_context()

        mock_wrapped = MagicMock()
        mock_response = MagicMock()
        mock_response.message = MagicMock()
        mock_response.message.content = [MagicMock(text="Hi")]
        mock_wrapped.return_value = mock_response

        result = _wrap_chat(
            mock_wrapped,
            MagicMock(),
            (),
            {"model": "command-a", "messages": [{"role": "user", "content": "Hello"}]},
        )

        assert mock_inspector.inspect_conversation.call_count >= 1
        assert result == mock_response

    @patch("aidefense.runtime.agentsec.patchers.cohere._get_inspector")
    def test_enforce_mode_raises_on_block(self, mock_get_inspector):
        """Enforce mode raises SecurityPolicyError when decision is block."""
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = Decision.block(reasons=["jailbreak"])
        mock_get_inspector.return_value = mock_inspector

        _state.set_state(
            initialized=True,
            llm_rules=None,
            api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "enforce"}},
        )
        clear_inspection_context()

        mock_wrapped = MagicMock()

        with pytest.raises(SecurityPolicyError):
            _wrap_chat(
                mock_wrapped,
                MagicMock(),
                (),
                {"model": "command-a", "messages": [{"role": "user", "content": "Hello"}]},
            )


class TestCohereGatewayMode:
    """Test gateway mode behavior (parity with OpenAI/Bedrock)."""

    def test_resolve_gateway_returns_none_when_api_mode(self):
        """resolve_gateway_settings returns None when integration mode is not gateway."""
        from aidefense.runtime.agentsec.patchers._base import resolve_gateway_settings
        _state.set_state(initialized=True, llm_integration_mode="api")
        assert resolve_gateway_settings("cohere") is None

    def test_resolve_gateway_raises_when_not_configured(self):
        """resolve_gateway_settings raises when Cohere provider not configured in gateway mode."""
        from aidefense.runtime.agentsec.patchers._base import resolve_gateway_settings
        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            gateway_mode={},
        )
        with pytest.raises(SecurityPolicyError, match="no gateway configuration found for provider"):
            resolve_gateway_settings("cohere")


class TestCoherePatchApply:
    """Test patch_cohere() behavior."""

    def test_returns_false_when_cohere_not_installed(self):
        """When cohere cannot be imported, patch_cohere returns False."""
        with patch("aidefense.runtime.agentsec.patchers.cohere.safe_import", return_value=None):
            assert patch_cohere() is False

    def test_returns_true_when_already_patched(self):
        """When already patched, returns True without re-patching."""
        with patch("aidefense.runtime.agentsec.patchers.cohere.is_patched", return_value=True):
            assert patch_cohere() is True
