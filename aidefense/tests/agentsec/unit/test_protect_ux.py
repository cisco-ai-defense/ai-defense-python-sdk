"""Tests for agentsec protect() UX features.

Covers:
  - Informational log when LLM clients are already in sys.modules
  - on_violation callback and WARNING log in monitor mode
  - get_patched_clients() docstring clarity (via import)
  - Unknown config key validation with fuzzy-match suggestions
  - Enriched SecurityPolicyError message (severity, classifications, explanation)
  - get_inspection_context / InspectionContext in public API
  - enabled toggle (parameter, env var, YAML)
"""

import logging
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from aidefense.runtime.agentsec import _state
from aidefense.runtime.agentsec.decision import Decision
from aidefense.runtime.agentsec.exceptions import SecurityPolicyError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset():
    """Reset global state before each test."""
    _state.reset()
    from aidefense.runtime.agentsec.patchers import reset_registry
    reset_registry()


# =========================================================================
# SecurityPolicyError enriched message
# =========================================================================

class TestSecurityPolicyErrorMessage:

    def test_message_with_reasons_only(self):
        decision = Decision.block(reasons=["PII detected"])
        err = SecurityPolicyError(decision)
        assert "PII detected" in str(err)

    def test_message_with_severity_and_classifications(self):
        decision = Decision.block(
            reasons=["Prompt injection"],
            severity="high",
            classifications=["prompt_injection"],
        )
        err = SecurityPolicyError(decision)
        msg = str(err)
        assert "Prompt injection" in msg
        assert "severity=high" in msg
        assert "prompt_injection" in msg

    def test_message_with_explanation(self):
        decision = Decision.block(
            reasons=["Blocked"],
            explanation="Content violates safety policy",
        )
        err = SecurityPolicyError(decision)
        assert "Content violates safety policy" in str(err)

    def test_message_fallback_when_no_reasons(self):
        decision = Decision.block(reasons=[])
        err = SecurityPolicyError(decision)
        assert "request blocked" in str(err)

    def test_message_with_all_fields(self):
        decision = Decision.block(
            reasons=["Malware signature found"],
            severity="critical",
            classifications=["malware"],
            explanation="Binary pattern matched known malware",
        )
        err = SecurityPolicyError(decision)
        msg = str(err)
        assert "Malware signature found" in msg
        assert "severity=critical" in msg
        assert "malware" in msg
        assert "Binary pattern matched known malware" in msg

    def test_string_constructor_unchanged(self):
        err = SecurityPolicyError("plain message")
        assert str(err) == "plain message"
        assert err.decision is None


# =========================================================================
# get_inspection_context / InspectionContext in public API
# =========================================================================

class TestPublicAPIExports:

    def setup_method(self):
        from aidefense.runtime.agentsec._context import clear_inspection_context
        clear_inspection_context()

    def test_get_inspection_context_importable(self):
        from aidefense.runtime.agentsec import get_inspection_context
        ctx = get_inspection_context()
        assert ctx.decision is None
        assert ctx.done is False

    def test_inspection_context_importable(self):
        from aidefense.runtime.agentsec import InspectionContext
        assert InspectionContext is not None

    def test_in_all(self):
        from aidefense.runtime import agentsec
        assert "get_inspection_context" in agentsec.__all__
        assert "InspectionContext" in agentsec.__all__


# =========================================================================
# enabled toggle (parameter, env var, YAML)
# =========================================================================

class TestEnabledToggle:

    def setup_method(self):
        _reset()

    def test_protect_enabled_false_skips_init(self):
        from aidefense.runtime.agentsec import protect
        protect(enabled=False)
        assert not _state.is_initialized()

    def test_protect_env_var_disabled(self):
        from aidefense.runtime.agentsec import protect
        with patch.dict(os.environ, {"AGENTSEC_DISABLED": "true"}):
            protect()
        assert not _state.is_initialized()

    def test_protect_env_var_disabled_1(self):
        from aidefense.runtime.agentsec import protect
        with patch.dict(os.environ, {"AGENTSEC_DISABLED": "1"}):
            protect()
        assert not _state.is_initialized()

    def test_protect_env_var_disabled_yes(self):
        from aidefense.runtime.agentsec import protect
        with patch.dict(os.environ, {"AGENTSEC_DISABLED": "yes"}):
            protect()
        assert not _state.is_initialized()

    def test_protect_env_var_not_disabled(self):
        from aidefense.runtime.agentsec import protect
        with patch.dict(os.environ, {"AGENTSEC_DISABLED": "false"}):
            protect(
                api_mode={"llm": {"mode": "monitor", "endpoint": "http://x", "api_key": "k"}},
            )
        assert _state.is_initialized()

    def test_protect_enabled_true_overrides_env_var(self):
        from aidefense.runtime.agentsec import protect
        with patch.dict(os.environ, {"AGENTSEC_DISABLED": "true"}):
            protect(
                enabled=True,
                api_mode={"llm": {"mode": "monitor", "endpoint": "http://x", "api_key": "k"}},
            )
        assert _state.is_initialized()


# =========================================================================
# on_violation callback and WARNING log in monitor mode
# =========================================================================

class TestOnViolationCallback:

    def setup_method(self):
        _reset()

    def test_on_violation_stored_in_state(self):
        from aidefense.runtime.agentsec import protect
        cb = MagicMock()
        protect(
            api_mode={"llm": {"mode": "monitor", "endpoint": "http://x", "api_key": "k"}},
            on_violation=cb,
        )
        assert _state.get_on_violation() is cb

    def test_monitor_mode_block_calls_callback(self):
        _state.set_state(initialized=True, api_mode={"llm": {"mode": "monitor"}})
        cb = MagicMock()
        _state.set_on_violation(cb)

        from aidefense.runtime.agentsec.patchers.openai import _enforce_decision
        decision = Decision.block(reasons=["test violation"])
        _enforce_decision(decision)

        cb.assert_called_once_with(decision)

    def test_monitor_mode_block_logs_warning(self):
        _state.set_state(initialized=True, api_mode={"llm": {"mode": "monitor"}})

        from aidefense.runtime.agentsec.patchers.openai import _enforce_decision
        decision = Decision.block(reasons=["test violation"], severity="high")

        with patch("aidefense.runtime.agentsec.patchers.openai.logger") as mock_logger:
            _enforce_decision(decision)
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert "Block decision in monitor mode" in call_args[0][0]

    def test_enforce_mode_still_raises(self):
        _state.set_state(initialized=True, api_mode={"llm": {"mode": "enforce"}})

        from aidefense.runtime.agentsec.patchers.openai import _enforce_decision
        decision = Decision.block(reasons=["test"])

        with pytest.raises(SecurityPolicyError):
            _enforce_decision(decision)

    def test_callback_exception_is_swallowed(self):
        _state.set_state(initialized=True, api_mode={"llm": {"mode": "monitor"}})
        cb = MagicMock(side_effect=RuntimeError("callback boom"))
        _state.set_on_violation(cb)

        from aidefense.runtime.agentsec.patchers.openai import _enforce_decision
        decision = Decision.block(reasons=["test"])
        _enforce_decision(decision)
        cb.assert_called_once()

    def test_on_violation_cleared_on_reset(self):
        _state.set_on_violation(lambda d: None)
        assert _state.get_on_violation() is not None
        _state.reset()
        assert _state.get_on_violation() is None

    def test_mcp_monitor_mode_block_calls_callback(self):
        _state.set_state(initialized=True, api_mode={"mcp": {"mode": "monitor"}})
        cb = MagicMock()
        _state.set_on_violation(cb)

        from aidefense.runtime.agentsec.patchers.mcp import _enforce_decision
        decision = Decision.block(reasons=["mcp violation"])
        _enforce_decision(decision)
        cb.assert_called_once_with(decision)


# =========================================================================
# Unknown config key validation with fuzzy-match suggestions
# =========================================================================

class TestConfigKeyValidation:

    def setup_method(self):
        _reset()

    def test_unknown_key_warns(self):
        from aidefense.runtime.agentsec import protect

        with patch("aidefense.runtime.agentsec.logger") as mock_logger:
            protect(
                api_mode={
                    "llm": {
                        "mode": "monitor",
                        "endpoint": "http://x",
                        "api_key": "k",
                        "mdoe": "enforce",
                    },
                },
            )
        warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
        assert any("mdoe" in c for c in warning_calls)

    def test_unknown_key_suggests_close_match(self):
        _reset()
        from aidefense.runtime.agentsec import protect

        with patch("aidefense.runtime.agentsec.logger") as mock_logger:
            protect(
                api_mode={
                    "llm": {
                        "mode": "monitor",
                        "endpoint": "http://x",
                        "api_key": "k",
                        "endpont": "http://y",
                    },
                },
            )
        warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
        assert any("Did you mean 'endpoint'" in c for c in warning_calls)

    def test_known_keys_no_warning(self):
        _reset()
        from aidefense.runtime.agentsec import protect

        with patch("aidefense.runtime.agentsec.logger") as mock_logger:
            protect(
                api_mode={
                    "llm": {
                        "mode": "monitor",
                        "endpoint": "http://x",
                        "api_key": "k",
                    },
                },
            )
        warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
        assert not any("Unknown key" in c for c in warning_calls)


# =========================================================================
# Informational log when LLM clients already in sys.modules
# =========================================================================

class TestPreImportedClientsLog:

    def setup_method(self):
        _reset()

    def test_logs_when_openai_already_imported(self):
        from aidefense.runtime.agentsec import protect

        with patch.dict(sys.modules, {"openai": MagicMock()}):
            with patch("aidefense.runtime.agentsec.logger") as mock_logger:
                protect(
                    api_mode={
                        "llm": {"mode": "monitor", "endpoint": "http://x", "api_key": "k"},
                    },
                )
        info_calls = [str(c) for c in mock_logger.info.call_args_list]
        assert any("already imported" in c for c in info_calls)

    def test_no_log_when_no_llm_clients_imported(self):
        _reset()
        from aidefense.runtime.agentsec import protect

        saved = {}
        for name in ("openai", "anthropic", "cohere", "mistralai", "google.generativeai", "boto3"):
            if name in sys.modules:
                saved[name] = sys.modules.pop(name)

        try:
            with patch("aidefense.runtime.agentsec.logger") as mock_logger:
                protect(
                    api_mode={
                        "llm": {"mode": "monitor", "endpoint": "http://x", "api_key": "k"},
                    },
                )
            info_calls = [str(c) for c in mock_logger.info.call_args_list]
            assert not any("already imported" in c for c in info_calls)
        finally:
            sys.modules.update(saved)
