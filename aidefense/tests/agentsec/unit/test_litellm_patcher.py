"""Unit tests for the LiteLLM patcher.

Covers patch_litellm(), _detect_provider(), _should_inspect(), _extract_response_text(),
_wrap_completion() (API + gateway mode), and _handle_patcher_error()-equivalent paths.
"""

import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from aidefense.runtime.agentsec.patchers.litellm import (
    patch_litellm,
    _detect_provider,
    _should_inspect,
    _enforce_decision,
    _extract_response_text,
    _wrap_completion,
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
    import aidefense.runtime.agentsec.patchers.litellm as litellm_module
    litellm_module._inspector = None
    yield
    _state.reset()
    reset_registry()
    clear_inspection_context()
    litellm_module._inspector = None


# ===========================================================================
# patch_litellm()
# ===========================================================================

class TestPatchLitellm:
    """Test patch_litellm() behavior."""

    def test_returns_false_when_litellm_not_installed(self):
        with patch("aidefense.runtime.agentsec.patchers.litellm.safe_import", return_value=None):
            assert patch_litellm() is False

    def test_returns_true_when_already_patched(self):
        with patch("aidefense.runtime.agentsec.patchers.litellm.is_patched", return_value=True):
            assert patch_litellm() is True

    def test_successful_patch(self):
        """When litellm is importable, patch_litellm patches and returns True."""
        mock_litellm = MagicMock()
        with patch("aidefense.runtime.agentsec.patchers.litellm.safe_import", return_value=mock_litellm), \
             patch("aidefense.runtime.agentsec.patchers.litellm.is_patched", return_value=False), \
             patch("aidefense.runtime.agentsec.patchers.litellm.wrapt") as mock_wrapt, \
             patch("aidefense.runtime.agentsec.patchers.litellm.mark_patched"):
            assert patch_litellm() is True
            # Should have patched completion and attempted acompletion
            assert mock_wrapt.wrap_function_wrapper.call_count >= 1


# ===========================================================================
# _detect_provider()
# ===========================================================================

class TestDetectProvider:
    """Test LiteLLM model string to provider mapping."""

    def test_vertexai(self):
        assert _detect_provider("vertex_ai/gemini-2.5-flash") == "vertexai"

    def test_vertexai_beta(self):
        assert _detect_provider("vertex_ai_beta/gemini-pro") == "vertexai"

    def test_azure_openai(self):
        assert _detect_provider("azure/gpt-4") == "azure_openai"

    def test_bedrock(self):
        assert _detect_provider("bedrock/anthropic.claude-3") == "bedrock"

    def test_bedrock_anthropic_prefix(self):
        assert _detect_provider("anthropic.claude-3-haiku") == "bedrock"

    def test_google_genai_gemini(self):
        assert _detect_provider("gemini/pro") == "google_genai"

    def test_google_genai_google(self):
        assert _detect_provider("google/gemini-pro") == "google_genai"

    def test_openai_default(self):
        assert _detect_provider("gpt-4") == "openai"

    def test_empty_returns_unknown(self):
        assert _detect_provider("") == "unknown"

    def test_none_returns_unknown(self):
        assert _detect_provider(None) == "unknown"


# ===========================================================================
# _should_inspect()
# ===========================================================================

class TestShouldInspect:
    """Test _should_inspect() skip conditions."""

    def test_returns_false_when_skip_active(self):
        with patch("aidefense.runtime.agentsec._context.is_llm_skip_active", return_value=True):
            assert _should_inspect() is False

    def test_returns_false_when_mode_off(self):
        _state.set_state(
            initialized=True,
            api_mode={"llm": {"mode": "off"}},
        )
        assert _should_inspect() is False

    def test_returns_false_when_context_done(self):
        from aidefense.runtime.agentsec._context import set_inspection_context
        _state.set_state(
            initialized=True,
            api_mode={"llm": {"mode": "monitor"}},
        )
        set_inspection_context(done=True)
        assert _should_inspect() is False

    def test_returns_true_when_active(self):
        _state.set_state(
            initialized=True,
            api_mode={"llm": {"mode": "monitor"}},
        )
        clear_inspection_context()
        assert _should_inspect() is True

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
# _enforce_decision()
# ===========================================================================

class TestEnforceDecision:
    """Test _enforce_decision() behavior."""

    def test_enforce_block_raises(self):
        _state.set_state(
            initialized=True,
            api_mode={"llm": {"mode": "enforce"}},
        )
        with pytest.raises(SecurityPolicyError):
            _enforce_decision(Decision.block(reasons=["bad"]))

    def test_monitor_block_does_not_raise(self):
        _state.set_state(
            initialized=True,
            api_mode={"llm": {"mode": "monitor"}},
        )
        _enforce_decision(Decision.block(reasons=["bad"]))  # no error

    def test_enforce_allow_does_not_raise(self):
        _state.set_state(
            initialized=True,
            api_mode={"llm": {"mode": "enforce"}},
        )
        _enforce_decision(Decision.allow(reasons=["ok"]))  # no error


# ===========================================================================
# _extract_response_text()
# ===========================================================================

class TestExtractResponseText:
    """Test extraction of text from LiteLLM ModelResponse."""

    def test_valid_response_object(self):
        msg = SimpleNamespace(content="Hello world")
        choice = SimpleNamespace(message=msg)
        response = SimpleNamespace(choices=[choice])
        assert _extract_response_text(response) == "Hello world"

    def test_empty_choices(self):
        response = SimpleNamespace(choices=[])
        assert _extract_response_text(response) == ""

    def test_dict_response(self):
        response = {"choices": [{"message": {"content": "dict reply"}}]}
        assert _extract_response_text(response) == "dict reply"

    def test_missing_content_returns_empty(self):
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=None))])
        assert _extract_response_text(response) == ""

    def test_no_choices_attr_returns_empty(self):
        assert _extract_response_text(object()) == ""


# ===========================================================================
# _wrap_completion() — API mode
# ===========================================================================

class TestWrapCompletionApiMode:
    """Test _wrap_completion in API mode (no gateway)."""

    @patch("aidefense.runtime.agentsec.patchers.litellm._get_inspector")
    @patch("aidefense.runtime.agentsec.patchers.litellm.resolve_gateway_settings", return_value=None)
    def test_pre_and_post_inspection_called(self, _mock_gw, mock_get_inspector):
        """Both pre-call and post-call inspection should be invoked."""
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = Decision.allow(reasons=[])
        mock_get_inspector.return_value = mock_inspector

        _state.set_state(
            initialized=True,
            api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}},
        )
        clear_inspection_context()

        mock_wrapped = MagicMock()
        mock_response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Hi there"))]
        )
        mock_wrapped.return_value = mock_response

        result = _wrap_completion(
            mock_wrapped, None, (),
            {"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}]},
        )

        assert result == mock_response
        # Pre-call + post-call = at least 2 calls
        assert mock_inspector.inspect_conversation.call_count == 2
        mock_wrapped.assert_called_once()

    @patch("aidefense.runtime.agentsec.patchers.litellm._get_inspector")
    @patch("aidefense.runtime.agentsec.patchers.litellm.resolve_gateway_settings", return_value=None)
    def test_enforce_block_raises_on_pre_call(self, _mock_gw, mock_get_inspector):
        """Enforce mode blocks before calling the original function."""
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = Decision.block(reasons=["jailbreak"])
        mock_get_inspector.return_value = mock_inspector

        _state.set_state(
            initialized=True,
            api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "enforce"}},
        )
        clear_inspection_context()

        mock_wrapped = MagicMock()

        with pytest.raises(SecurityPolicyError):
            _wrap_completion(
                mock_wrapped, None, (),
                {"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}]},
            )
        # Original should NOT have been called
        mock_wrapped.assert_not_called()

    @patch("aidefense.runtime.agentsec.patchers.litellm._should_inspect", return_value=False)
    def test_passthrough_when_should_inspect_false(self, _mock_inspect):
        """When _should_inspect returns False, call original directly."""
        mock_wrapped = MagicMock(return_value="raw_response")
        result = _wrap_completion(
            mock_wrapped, None, (),
            {"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}]},
        )
        assert result == "raw_response"
        mock_wrapped.assert_called_once()

    @patch("aidefense.runtime.agentsec.patchers.litellm._get_inspector")
    @patch("aidefense.runtime.agentsec.patchers.litellm.resolve_gateway_settings", return_value=None)
    def test_no_post_inspection_when_no_assistant_content(self, _mock_gw, mock_get_inspector):
        """Post-call inspection is skipped when response has no content."""
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = Decision.allow(reasons=[])
        mock_get_inspector.return_value = mock_inspector

        _state.set_state(
            initialized=True,
            api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}},
        )
        clear_inspection_context()

        mock_wrapped = MagicMock()
        # Response with empty content
        mock_wrapped.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=""))])

        _wrap_completion(
            mock_wrapped, None, (),
            {"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}]},
        )

        # Only pre-call inspection (no post-call since content is empty)
        assert mock_inspector.inspect_conversation.call_count == 1


# ===========================================================================
# _wrap_completion() — Gateway mode
# ===========================================================================

class TestWrapCompletionGatewayMode:
    """Test _wrap_completion in gateway mode."""

    @patch("aidefense.runtime.agentsec.patchers.litellm.resolve_gateway_settings")
    def test_non_vertexai_overrides_api_base(self, mock_resolve_gw):
        """For non-vertexai providers, gateway mode sets api_base and api_key."""
        gw_settings = SimpleNamespace(
            url="https://gateway.example.com", api_key="gw-key",
            fail_open=True, timeout=30,
        )
        mock_resolve_gw.return_value = gw_settings

        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            api_mode={"llm": {"mode": "monitor"}},
        )
        clear_inspection_context()

        mock_wrapped = MagicMock()
        mock_wrapped.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="GW reply"))])

        kwargs = {"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}]}
        result = _wrap_completion(mock_wrapped, None, (), kwargs)

        # api_base and api_key should have been injected
        assert kwargs["api_base"] == "https://gateway.example.com"
        assert kwargs["api_key"] == "gw-key"
        mock_wrapped.assert_called_once()

    @patch("aidefense.runtime.agentsec.patchers.litellm._litellm_vertexai_gateway_call")
    @patch("aidefense.runtime.agentsec.patchers.litellm.resolve_gateway_settings")
    def test_vertexai_direct_http_call(self, mock_resolve_gw, mock_vertexai_call):
        """For vertexai provider, gateway mode makes a direct HTTP call."""
        gw_settings = SimpleNamespace(
            url="https://gateway.example.com", api_key="gw-key",
            auth_mode="api_key", fail_open=True, timeout=30,
        )
        mock_resolve_gw.return_value = gw_settings
        mock_vertexai_call.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="VTX reply"))]
        )

        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            api_mode={"llm": {"mode": "monitor"}},
        )
        clear_inspection_context()

        mock_wrapped = MagicMock()
        result = _wrap_completion(
            mock_wrapped, None, (),
            {"model": "vertex_ai/gemini-2.5-flash", "messages": [{"role": "user", "content": "Hello"}]},
        )

        mock_vertexai_call.assert_called_once()
        # Original wrapped function should NOT have been called
        mock_wrapped.assert_not_called()

    @patch("aidefense.runtime.agentsec.patchers.litellm.resolve_gateway_settings")
    def test_gateway_error_fail_open_true_reraises(self, mock_resolve_gw):
        """Gateway error with fail_open=True re-raises the original error."""
        gw_settings = SimpleNamespace(
            url="https://gateway.example.com", api_key="gw-key",
            fail_open=True, timeout=30,
        )
        mock_resolve_gw.return_value = gw_settings

        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            api_mode={"llm": {"mode": "monitor"}},
        )
        clear_inspection_context()

        mock_wrapped = MagicMock(side_effect=ConnectionError("network down"))

        with pytest.raises(ConnectionError, match="network down"):
            _wrap_completion(
                mock_wrapped, None, (),
                {"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}]},
            )

    @patch("aidefense.runtime.agentsec.patchers.litellm.resolve_gateway_settings")
    def test_gateway_error_fail_open_false_raises_security_error(self, mock_resolve_gw):
        """Gateway error with fail_open=False raises SecurityPolicyError."""
        gw_settings = SimpleNamespace(
            url="https://gateway.example.com", api_key="gw-key",
            fail_open=False, timeout=30,
        )
        mock_resolve_gw.return_value = gw_settings

        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            api_mode={"llm": {"mode": "monitor"}},
        )
        clear_inspection_context()

        mock_wrapped = MagicMock(side_effect=ConnectionError("network down"))

        with pytest.raises(SecurityPolicyError):
            _wrap_completion(
                mock_wrapped, None, (),
                {"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}]},
            )

    @patch("aidefense.runtime.agentsec.patchers.litellm._litellm_vertexai_gateway_call")
    @patch("aidefense.runtime.agentsec.patchers.litellm.resolve_gateway_settings")
    def test_vertexai_gateway_error_fail_open_false(self, mock_resolve_gw, mock_vtx_call):
        """Vertex AI gateway error with fail_open=False raises SecurityPolicyError."""
        gw_settings = SimpleNamespace(
            url="https://gateway.example.com", api_key="gw-key",
            auth_mode="api_key", fail_open=False, timeout=30,
        )
        mock_resolve_gw.return_value = gw_settings
        mock_vtx_call.side_effect = ConnectionError("vtx down")

        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            api_mode={"llm": {"mode": "monitor"}},
        )
        clear_inspection_context()

        with pytest.raises(SecurityPolicyError):
            _wrap_completion(
                MagicMock(), None, (),
                {"model": "vertex_ai/gemini-pro", "messages": [{"role": "user", "content": "Hello"}]},
            )

    @patch("aidefense.runtime.agentsec.patchers.litellm._litellm_vertexai_gateway_call")
    @patch("aidefense.runtime.agentsec.patchers.litellm.resolve_gateway_settings")
    def test_vertexai_gateway_error_fail_open_true_reraises(self, mock_resolve_gw, mock_vtx_call):
        """Vertex AI gateway error with fail_open=True re-raises the original error."""
        gw_settings = SimpleNamespace(
            url="https://gateway.example.com", api_key="gw-key",
            auth_mode="api_key", fail_open=True, timeout=30,
        )
        mock_resolve_gw.return_value = gw_settings
        mock_vtx_call.side_effect = ConnectionError("vtx down")

        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            api_mode={"llm": {"mode": "monitor"}},
        )
        clear_inspection_context()

        with pytest.raises(ConnectionError, match="vtx down"):
            _wrap_completion(
                MagicMock(), None, (),
                {"model": "vertex_ai/gemini-pro", "messages": [{"role": "user", "content": "Hello"}]},
            )

    @patch("aidefense.runtime.agentsec.patchers.litellm._litellm_vertexai_gateway_call")
    @patch("aidefense.runtime.agentsec.patchers.litellm.resolve_gateway_settings")
    def test_vertexai_security_policy_error_reraises(self, mock_resolve_gw, mock_vtx_call):
        """Vertex AI SecurityPolicyError is re-raised directly."""
        gw_settings = SimpleNamespace(
            url="https://gateway.example.com", api_key="gw-key",
            auth_mode="api_key", fail_open=True, timeout=30,
        )
        mock_resolve_gw.return_value = gw_settings
        mock_vtx_call.side_effect = SecurityPolicyError(
            Decision.block(reasons=["policy"]), "policy violation"
        )

        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            api_mode={"llm": {"mode": "monitor"}},
        )
        clear_inspection_context()

        with pytest.raises(SecurityPolicyError):
            _wrap_completion(
                MagicMock(), None, (),
                {"model": "vertex_ai/gemini-pro", "messages": [{"role": "user", "content": "Hello"}]},
            )


# ===========================================================================
# _get_inspector()
# ===========================================================================

class TestGetInspector:
    """Test the inspector singleton initialization."""

    @patch("aidefense.runtime.agentsec.inspectors.register_inspector_for_cleanup")
    @patch("aidefense.runtime.agentsec.patchers.litellm.LLMInspector")
    def test_creates_inspector_on_first_call(self, mock_inspector_cls, mock_register):
        from aidefense.runtime.agentsec.patchers.litellm import _get_inspector
        import aidefense.runtime.agentsec.patchers.litellm as litellm_module

        _state.set_state(
            initialized=True,
            api_mode={"llm_defaults": {"fail_open": True}},
        )
        litellm_module._inspector = None
        mock_inspector_cls.return_value = MagicMock()

        inspector = _get_inspector()

        mock_inspector_cls.assert_called_once()
        mock_register.assert_called_once()
        assert inspector is mock_inspector_cls.return_value

    @patch("aidefense.runtime.agentsec.patchers.litellm.LLMInspector")
    def test_returns_same_instance_on_second_call(self, mock_inspector_cls):
        from aidefense.runtime.agentsec.patchers.litellm import _get_inspector
        import aidefense.runtime.agentsec.patchers.litellm as litellm_module

        _state.set_state(
            initialized=True,
            api_mode={"llm_defaults": {"fail_open": True}},
        )
        sentinel = MagicMock()
        litellm_module._inspector = sentinel

        inspector = _get_inspector()
        assert inspector is sentinel
        mock_inspector_cls.assert_not_called()


# ===========================================================================
# _wrap_completion() — model/messages from args (not kwargs)
# ===========================================================================

class TestWrapCompletionArgsParsing:
    """Test _wrap_completion extracts model/messages from positional args."""

    @patch("aidefense.runtime.agentsec.patchers.litellm._get_inspector")
    @patch("aidefense.runtime.agentsec.patchers.litellm.resolve_gateway_settings", return_value=None)
    def test_model_from_positional_args(self, _mock_gw, mock_get_inspector):
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = Decision.allow(reasons=[])
        mock_get_inspector.return_value = mock_inspector

        _state.set_state(
            initialized=True,
            api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}},
        )
        clear_inspection_context()

        mock_wrapped = MagicMock()
        mock_wrapped.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=""))])

        # Pass model as first positional arg, messages as second
        _wrap_completion(
            mock_wrapped, None,
            ("gpt-4", [{"role": "user", "content": "Positional"}]),
            {},
        )
        mock_wrapped.assert_called_once()
