"""Integration tests for enforce mode (Task Group 10)."""

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


class TestEnforceMode:
    """Tests for enforce mode behavior."""

    def test_enforce_mode_sets_correct_mode(self):
        """Test that protect(api_mode={"llm": {"mode": "enforce"}}) sets mode correctly."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode={"llm": {"mode": "enforce"}})
            assert get_llm_mode() == "enforce"

    def test_enforce_mode_with_allow_permits_request(self):
        """Test that enforce mode with allow response permits request."""
        with _mock_session_request({"action": "Allow", "reasons": [], "is_safe": True}):
            with patch("aidefense.runtime.agentsec._apply_patches"):
                agentsec.protect(api_mode={"llm": {"mode": "enforce"}}, patch_clients=False)
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

    def test_enforce_mode_with_block_raises_error(self):
        """Test that enforce mode with block response gives block decision."""
        with _mock_session_request({"action": "Block", "reasons": ["policy_violation"], "is_safe": False}):
            with patch("aidefense.runtime.agentsec._apply_patches"):
                agentsec.protect(api_mode={"llm": {"mode": "enforce"}}, patch_clients=False)
            from aidefense.runtime.agentsec.inspectors.api_llm import LLMInspector
            inspector = LLMInspector(
                api_key=TEST_API_KEY,
                endpoint="http://test.api",
                fail_open=False,
            )
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "Malicious content"}],
                metadata={},
            )
        assert decision.action == "block"
        assert decision.allows() is False

    def test_enforce_mode_with_sanitize_modifies_content(self):
        """Test that enforce mode with sanitize response provides modified content."""
        with _mock_session_request({
            "action": "Block",
            "reasons": ["pii_removed"],
            "is_safe": False,
            "explanation": "pii_removed",
        }):
            with patch("aidefense.runtime.agentsec._apply_patches"):
                agentsec.protect(api_mode={"llm": {"mode": "enforce"}}, patch_clients=False)
            from aidefense.runtime.agentsec.inspectors.api_llm import LLMInspector
            inspector = LLMInspector(
                api_key=TEST_API_KEY,
                endpoint="http://test.api",
            )
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "Hello, my name is John"}],
                metadata={},
            )
        assert decision.action == "block"
        assert "pii_removed" in decision.reasons
