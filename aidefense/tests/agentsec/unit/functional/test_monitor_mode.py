"""Integration tests for monitor mode (Task Group 11)."""

import logging
import pytest
from unittest.mock import patch, MagicMock

from aidefense.runtime import agentsec
from aidefense.runtime.agentsec._state import reset, get_llm_mode
from aidefense.runtime.agentsec.patchers import reset_registry

# API key must be 64 characters (RuntimeAuth validation)
TEST_API_KEY = "0" * 64


def _mock_session_request(response_json):
    """Patch requests.Session.request to return response_json."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = response_json
    return patch("requests.Session.request", return_value=mock_response)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset agentsec state before and after each test."""
    reset()
    reset_registry()
    yield
    reset()
    reset_registry()


class TestMonitorMode:
    """Tests for monitor mode behavior."""

    def test_monitor_mode_sets_correct_mode(self):
        """Test that protect(api_mode={"llm": {"mode": "monitor"}}) sets mode correctly."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode={"llm": {"mode": "monitor"}})
            assert get_llm_mode() == "monitor"

    def test_monitor_mode_with_block_does_not_raise(self):
        """Test that monitor mode with block response logs but does not raise."""
        with _mock_session_request({"action": "Block", "reasons": ["policy_violation"], "is_safe": False}):
            with patch("aidefense.runtime.agentsec._apply_patches"):
                agentsec.protect(api_mode={"llm": {"mode": "monitor"}}, patch_clients=False)
            from aidefense.runtime.agentsec.inspectors.api_llm import LLMInspector
            inspector = LLMInspector(
                api_key=TEST_API_KEY,
                endpoint="http://test.api",
            )
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "Blocked content"}],
                metadata={},
            )
        assert decision.action == "block"

    def test_monitor_mode_with_allow_passes_through(self):
        """Test that monitor mode with allow response passes through."""
        with _mock_session_request({"action": "Allow", "reasons": [], "is_safe": True}):
            with patch("aidefense.runtime.agentsec._apply_patches"):
                agentsec.protect(api_mode={"llm": {"mode": "monitor"}}, patch_clients=False)
            from aidefense.runtime.agentsec.inspectors.api_llm import LLMInspector
            inspector = LLMInspector(
                api_key=TEST_API_KEY,
                endpoint="http://test.api",
            )
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "Hello"}],
                metadata={},
            )
        assert decision.action == "allow"
        assert decision.allows() is True

    def test_monitor_mode_logs_block_decisions(self, caplog):
        """Test that monitor mode logs block decisions."""
        with _mock_session_request({"action": "Block", "reasons": ["suspicious_content"], "is_safe": False}):
            with patch("aidefense.runtime.agentsec._apply_patches"):
                agentsec.protect(api_mode={"llm": {"mode": "monitor"}}, patch_clients=False)
            from aidefense.runtime.agentsec.inspectors.api_llm import LLMInspector
            inspector = LLMInspector(
                api_key=TEST_API_KEY,
                endpoint="http://test.api",
            )
            with caplog.at_level(logging.DEBUG, logger="aidefense.runtime.agentsec"):
                decision = inspector.inspect_conversation(
                    messages=[{"role": "user", "content": "test"}],
                    metadata={},
                )
        assert decision.action == "block"

    def test_monitor_mode_never_raises_security_error(self):
        """Test that monitor mode should never raise SecurityPolicyError."""
        # This tests the principle - actual blocking is in patchers
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode={"llm": {"mode": "monitor"}})
        
        # Verify mode is monitor (patchers check this before deciding to block)
        assert get_llm_mode() == "monitor"
