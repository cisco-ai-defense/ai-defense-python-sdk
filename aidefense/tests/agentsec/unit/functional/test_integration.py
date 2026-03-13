"""Integration tests for agentsec (Task 6.3)."""

from unittest.mock import patch

import pytest

from aidefense.runtime import agentsec
from aidefense.runtime.agentsec import Decision, SecurityPolicyError, protect
from aidefense.runtime.agentsec._state import get_llm_mode, get_mcp_mode, is_initialized, reset
from aidefense.runtime.agentsec.inspectors import LLMInspector, MCPInspector


@pytest.fixture(autouse=True)
def reset_state():
    """Reset agentsec state before and after each test."""
    reset()
    yield
    reset()


class TestFullInitialization:
    """Test full initialization flow."""

    def test_full_init_flow_enforce_mode(self):
        """Test full initialization flow with all components in enforce mode."""
        protect(api_mode={"llm": {"mode": "enforce"}})
        
        assert is_initialized()
        assert get_llm_mode() == "enforce"

    def test_full_init_flow_monitor_mode(self):
        """Test full initialization flow in monitor mode."""
        protect(api_mode={"llm": {"mode": "monitor"}})
        
        assert is_initialized()
        assert get_llm_mode() == "monitor"


class TestProtectInspectorIntegration:
    """Test protect() → config → inspector integration."""

    def test_inspectors_work_after_protect(self):
        """Test that inspectors work correctly after protect() is called."""
        protect(api_mode={"llm": {"mode": "enforce"}})
        
        # All inspectors should return allow (stubs)
        llm = LLMInspector()
        mcp = MCPInspector()
        
        assert llm.inspect_conversation([], {}).action == "allow"
        assert mcp.inspect_request("tool", {}, {}).action == "allow"

    def test_decision_to_exception_flow(self):
        """Test that block decisions can be converted to exceptions."""
        decision = Decision.block(reasons=["test violation"])
        error = SecurityPolicyError(decision)
        
        assert error.decision.action == "block"
        assert "test violation" in str(error)


class TestProgrammaticConfig:
    """Test programmatic config via protect() api_mode."""

    def test_explicit_mode_wins(self):
        """Test that explicit api_mode sets mode correctly."""
        protect(api_mode={"llm": {"mode": "enforce"}})
        assert get_llm_mode() == "enforce"

    def test_programmatic_config_values(self):
        """Test that api_mode endpoint, api_key, and rules are stored correctly."""
        protect(api_mode={
            "llm": {
                "endpoint": "https://api.test.com",
                "api_key": "key-from-config",
                "rules": ["jailbreak", "pii_detection"],
            },
        })
        
        from aidefense.runtime.agentsec._state import get_api_mode_llm_api_key, get_api_mode_llm_endpoint, get_llm_rules
        assert get_api_mode_llm_api_key() == "key-from-config"
        assert get_api_mode_llm_endpoint() == "https://api.test.com"
        assert get_llm_rules() == ["jailbreak", "pii_detection"]


class TestComponentIntegration:
    """Test component integration."""

    def test_llm_inspector_decision_types(self):
        """Test LLMInspector returns correct decision types."""
        inspector = LLMInspector()
        decision = inspector.inspect_conversation([{"role": "user", "content": "test"}], {})
        
        assert decision.action in ["allow", "block", "sanitize", "monitor_only"]
        assert isinstance(decision.reasons, list)

    def test_mcp_inspector_decision_types(self):
        """Test MCPInspector returns correct decision types."""
        inspector = MCPInspector()
        decision = inspector.inspect_request("tool", {"arg": "value"}, {})
        
        assert decision.action in ["allow", "block", "sanitize", "monitor_only"]
        assert isinstance(decision.reasons, list)

    def test_security_policy_error_attributes(self):
        """Test SecurityPolicyError has correct attributes."""
        decision = Decision.block(reasons=["violation"])
        error = SecurityPolicyError(decision)
        
        assert hasattr(error, "decision")
        assert error.decision.action == "block"
        assert "violation" in error.decision.reasons
