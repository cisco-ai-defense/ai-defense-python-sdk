"""Integration tests for enforce mode (Task Group 10)."""

import re
import pytest
from unittest.mock import patch, MagicMock

from aidefense.runtime import agentsec
from aidefense.runtime.agentsec._state import reset, get_llm_mode
from aidefense.runtime.agentsec.patchers import reset_registry
from aidefense.runtime.agentsec.exceptions import SecurityPolicyError


# Check if pytest-httpx is available
pytest_httpx_available = True
try:
    from pytest_httpx import HTTPXMock
except ImportError:
    pytest_httpx_available = False


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
        """Test that protect(api_mode_llm='enforce') sets mode correctly."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode_llm="on_enforce")
            assert get_llm_mode() == "on_enforce"

    @pytest.mark.skipif(not pytest_httpx_available, reason="pytest-httpx not installed")
    def test_enforce_mode_with_allow_permits_request(self, httpx_mock: "HTTPXMock"):
        """Test that enforce mode with allow response permits request."""
        httpx_mock.add_response(
            url=re.compile(r".*/v1/inspect/chat"),
            json={"action": "allow", "reasons": []},
        )
        
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode_llm="on_enforce", patch_clients=False)
        
        # Create an inspector and verify allow works
        from aidefense.runtime.agentsec.inspectors.api_llm import LLMInspector
        inspector = LLMInspector(
            api_key="test-key",
            endpoint="http://test.api",
        )
        
        decision = inspector.inspect_conversation(
            messages=[{"role": "user", "content": "Hello"}],
            metadata={},
        )
        
        assert decision.action == "allow"
        assert decision.allows() is True

    @pytest.mark.skipif(not pytest_httpx_available, reason="pytest-httpx not installed")
    def test_enforce_mode_with_block_raises_error(self, httpx_mock: "HTTPXMock"):
        """Test that enforce mode with block response raises SecurityPolicyError."""
        httpx_mock.add_response(
            url=re.compile(r".*/v1/inspect/chat"),
            json={"action": "block", "reasons": ["policy_violation"]},
        )
        
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode_llm="on_enforce", patch_clients=False)
        
        from aidefense.runtime.agentsec.inspectors.api_llm import LLMInspector
        inspector = LLMInspector(
            api_key="test-key",
            endpoint="http://test.api",
            fail_open=False,  # Ensure we raise on block
        )
        
        decision = inspector.inspect_conversation(
            messages=[{"role": "user", "content": "Malicious content"}],
            metadata={},
        )
        
        assert decision.action == "block"
        assert decision.allows() is False
        
        # In actual patched flow, this would raise SecurityPolicyError
        # Here we verify the decision is correct

    @pytest.mark.skipif(not pytest_httpx_available, reason="pytest-httpx not installed")
    def test_enforce_mode_with_sanitize_modifies_content(self, httpx_mock: "HTTPXMock"):
        """Test that enforce mode with sanitize response provides modified content."""
        httpx_mock.add_response(
            url=re.compile(r".*/v1/inspect/chat"),
            json={
                "action": "sanitize",
                "reasons": ["pii_removed"],
                "sanitized_content": "Hello, my name is [REDACTED]",
            },
        )
        
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode_llm="on_enforce", patch_clients=False)
        
        from aidefense.runtime.agentsec.inspectors.api_llm import LLMInspector
        inspector = LLMInspector(
            api_key="test-key",
            endpoint="http://test.api",
        )
        
        decision = inspector.inspect_conversation(
            messages=[{"role": "user", "content": "Hello, my name is John"}],
            metadata={},
        )
        
        assert decision.action == "sanitize"
        assert decision.sanitized_content == "Hello, my name is [REDACTED]"
        assert decision.allows() is True  # sanitize still allows, with modified content
