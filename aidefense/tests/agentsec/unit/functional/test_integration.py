"""Integration tests for agentsec (Task 6.3)."""

import os
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
        protect(api_mode_llm="on_enforce")
        
        assert is_initialized()
        assert get_llm_mode() == "on_enforce"

    def test_full_init_flow_monitor_mode(self):
        """Test full initialization flow in monitor mode."""
        protect(api_mode_llm="on_monitor")
        
        assert is_initialized()
        assert get_llm_mode() == "on_monitor"


class TestProtectInspectorIntegration:
    """Test protect() → config → inspector integration."""

    def test_inspectors_work_after_protect(self):
        """Test that inspectors work correctly after protect() is called."""
        protect(api_mode_llm="on_enforce")
        
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


class TestEnvVariableOverrides:
    """Test environment variable override scenarios."""

    def test_env_mode_override(self):
        """Test AGENTSEC_MODE environment variable."""
        # Note: Currently env mode doesn't override explicit mode
        # This test documents the current behavior
        with patch.dict(os.environ, {"AGENTSEC_MODE": "on_monitor"}):
            protect(api_mode_llm="on_enforce")
            assert get_llm_mode() == "on_enforce"  # Explicit wins

    def test_env_config_values(self):
        """Test that all env config values are loaded."""
        env_vars = {
            "AI_DEFENSE_API_MODE_LLM_API_KEY": "key-from-env",
            "AI_DEFENSE_API_MODE_LLM_ENDPOINT": "https://api.test.com",
            "AGENTSEC_LLM_RULES": "jailbreak,pii_detection",
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            protect()
            
            from aidefense.runtime.agentsec._state import get_api_mode_llm_api_key, get_api_mode_llm_endpoint, get_llm_rules
            assert get_api_mode_llm_api_key() == "key-from-env"
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
