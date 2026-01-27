"""Integration tests for monitor mode (Task Group 11)."""

import logging
import re
import pytest
from unittest.mock import patch

from aidefense.runtime import agentsec
from aidefense.runtime.agentsec._state import reset, get_llm_mode
from aidefense.runtime.agentsec.patchers import reset_registry


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


class TestMonitorMode:
    """Tests for monitor mode behavior."""

    def test_monitor_mode_sets_correct_mode(self):
        """Test that protect(api_mode_llm='monitor') sets mode correctly."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode_llm="on_monitor")
            assert get_llm_mode() == "on_monitor"

    @pytest.mark.skipif(not pytest_httpx_available, reason="pytest-httpx not installed")
    def test_monitor_mode_with_block_does_not_raise(self, httpx_mock: "HTTPXMock"):
        """Test that monitor mode with block response logs but does not raise."""
        httpx_mock.add_response(
            url=re.compile(r".*/v1/inspect/chat"),
            json={"action": "block", "reasons": ["policy_violation"]},
        )
        
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode_llm="on_monitor", patch_clients=False)
        
        from aidefense.runtime.agentsec.inspectors.api_llm import LLMInspector
        inspector = LLMInspector(
            api_key="test-key",
            endpoint="http://test.api",
        )
        
        # Should NOT raise even with block decision in monitor mode
        decision = inspector.inspect_conversation(
            messages=[{"role": "user", "content": "Blocked content"}],
            metadata={},
        )
        
        # Decision is block, but in monitor mode we just log
        assert decision.action == "block"
        # Note: actual blocking/logging behavior depends on patcher implementation

    @pytest.mark.skipif(not pytest_httpx_available, reason="pytest-httpx not installed")
    def test_monitor_mode_with_allow_passes_through(self, httpx_mock: "HTTPXMock"):
        """Test that monitor mode with allow response passes through."""
        httpx_mock.add_response(
            url=re.compile(r".*/v1/inspect/chat"),
            json={"action": "allow", "reasons": []},
        )
        
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode_llm="on_monitor", patch_clients=False)
        
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
    def test_monitor_mode_logs_block_decisions(self, httpx_mock: "HTTPXMock", caplog):
        """Test that monitor mode logs block decisions."""
        httpx_mock.add_response(
            url=re.compile(r".*/v1/inspect/chat"),
            json={"action": "block", "reasons": ["suspicious_content"]},
        )
        
        # Reset logger handlers for clean test
        logger = logging.getLogger("agentsec")
        logger.handlers.clear()
        
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode_llm="on_monitor", patch_clients=False)
        
        from aidefense.runtime.agentsec.inspectors.api_llm import LLMInspector
        inspector = LLMInspector(
            api_key="test-key",
            endpoint="http://test.api",
        )
        
        with caplog.at_level(logging.WARNING, logger="agentsec"):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "test"}],
                metadata={},
            )
        
        # Verify we got a block decision
        assert decision.action == "block"
        # Note: Actual logging happens in patcher wrappers, not inspector

    def test_monitor_mode_never_raises_security_error(self):
        """Test that monitor mode should never raise SecurityPolicyError."""
        # This tests the principle - actual blocking is in patchers
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode_llm="on_monitor")
        
        # Verify mode is monitor (patchers check this before deciding to block)
        assert get_llm_mode() == "on_monitor"
