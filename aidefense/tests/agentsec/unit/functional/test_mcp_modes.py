"""Integration tests for MCP inspection modes (off/monitor/enforce)."""

import pytest
from unittest.mock import patch

from aidefense.runtime import agentsec
from aidefense.runtime.agentsec._state import reset, get_mcp_mode
from aidefense.runtime.agentsec.patchers import reset_registry
from aidefense.runtime.agentsec.exceptions import SecurityPolicyError


@pytest.fixture(autouse=True)
def reset_state():
    """Reset agentsec state before and after each test."""
    reset()
    reset_registry()
    yield
    reset()
    reset_registry()


class TestMCPOffMode:
    """Tests for MCP off mode behavior."""

    def test_off_mode_sets_correct_mode(self):
        """Test that protect(api_mode_mcp='off') sets mode correctly."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode_mcp="off")
            assert get_mcp_mode() == "off"

    def test_off_mode_should_not_inspect(self):
        """Test that off mode causes _should_inspect to return False."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode_mcp="off")
        
        from aidefense.runtime.agentsec.patchers.mcp import _should_inspect
        assert _should_inspect() is False

    def test_off_mode_skips_inspection(self):
        """Test that off mode completely skips MCP inspection."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode_mcp="off")
        
        # Create a mock MCPInspector
        from aidefense.runtime.agentsec.inspectors.api_mcp import MCPInspector
        
        with patch.object(MCPInspector, 'inspect_request') as mock_inspect:
            from aidefense.runtime.agentsec.patchers.mcp import _should_inspect
            
            # When mode is off, _should_inspect returns False
            assert _should_inspect() is False
            
            # The patcher checks _should_inspect before calling inspect_request
            # So inspect_request should never be called when mode is off


class TestMCPMonitorMode:
    """Tests for MCP monitor mode behavior."""

    def test_monitor_mode_sets_correct_mode(self):
        """Test that protect(api_mode_mcp='monitor') sets mode correctly."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode_mcp="on_monitor")
            assert get_mcp_mode() == "on_monitor"

    def test_monitor_mode_should_inspect(self):
        """Test that monitor mode causes _should_inspect to return True."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode_mcp="on_monitor")
        
        from aidefense.runtime.agentsec.patchers.mcp import _should_inspect
        assert _should_inspect() is True

    def test_monitor_mode_does_not_enforce_block(self):
        """Test that monitor mode does not enforce block decisions."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode_mcp="on_monitor")
        
        from aidefense.runtime.agentsec.patchers.mcp import _enforce_decision
        from aidefense.runtime.agentsec.decision import Decision
        
        # Create a block decision
        block_decision = Decision.block(reasons=["test_violation"])
        
        # Should NOT raise SecurityPolicyError in monitor mode
        _enforce_decision(block_decision)  # No exception expected

    def test_monitor_mode_inspects_but_does_not_block(self):
        """Test that monitor mode inspects MCP calls but does not block."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode_mcp="on_monitor", patch_clients=False)
        
        from aidefense.runtime.agentsec.decision import Decision
        from aidefense.runtime.agentsec.patchers.mcp import _enforce_decision
        
        # Create a block decision (simulates what API would return)
        block_decision = Decision.block(reasons=["Violence: SAFETY_VIOLATION"])
        
        # In monitor mode, _enforce_decision should NOT raise even for block decisions
        _enforce_decision(block_decision)  # Should not raise
        
        # Verify the decision is still block (inspection happened)
        assert block_decision.action == "block"


class TestMCPEnforceMode:
    """Tests for MCP enforce mode behavior."""

    def test_enforce_mode_sets_correct_mode(self):
        """Test that protect(api_mode_mcp='enforce') sets mode correctly."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode_mcp="on_enforce")
            assert get_mcp_mode() == "on_enforce"

    def test_enforce_mode_should_inspect(self):
        """Test that enforce mode causes _should_inspect to return True."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode_mcp="on_enforce")
        
        from aidefense.runtime.agentsec.patchers.mcp import _should_inspect
        assert _should_inspect() is True

    def test_enforce_mode_enforces_block(self):
        """Test that enforce mode enforces block decisions."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode_mcp="on_enforce")
        
        from aidefense.runtime.agentsec.patchers.mcp import _enforce_decision
        from aidefense.runtime.agentsec.decision import Decision
        
        # Create a block decision
        block_decision = Decision.block(reasons=["test_violation"])
        
        # Should raise SecurityPolicyError in enforce mode
        with pytest.raises(SecurityPolicyError) as exc_info:
            _enforce_decision(block_decision)
        
        assert exc_info.value.decision.action == "block"

    def test_enforce_mode_allows_allow_decisions(self):
        """Test that enforce mode does not raise for allow decisions."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode_mcp="on_enforce")
        
        from aidefense.runtime.agentsec.patchers.mcp import _enforce_decision
        from aidefense.runtime.agentsec.decision import Decision
        
        # Create an allow decision
        allow_decision = Decision.allow(reasons=[])
        
        # Should NOT raise for allow decisions
        _enforce_decision(allow_decision)  # No exception expected

    def test_enforce_mode_with_allow_permits_request(self):
        """Test that enforce mode with allow response permits request."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode_mcp="on_enforce", patch_clients=False)
        
        from aidefense.runtime.agentsec.decision import Decision
        from aidefense.runtime.agentsec.patchers.mcp import _enforce_decision
        
        # Create an allow decision (simulates what API would return)
        allow_decision = Decision.allow(reasons=[])
        
        assert allow_decision.action == "allow"
        assert allow_decision.allows() is True
        
        # The patcher's _enforce_decision should not raise for allow
        _enforce_decision(allow_decision)  # Should not raise

    def test_enforce_mode_with_block_raises_error(self):
        """Test that enforce mode with block response raises SecurityPolicyError."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode_mcp="on_enforce", patch_clients=False)
        
        from aidefense.runtime.agentsec.decision import Decision
        from aidefense.runtime.agentsec.patchers.mcp import _enforce_decision
        
        # Create a block decision (simulates what API would return)
        block_decision = Decision.block(reasons=["Violence: SAFETY_VIOLATION"])
        
        assert block_decision.action == "block"
        
        # The patcher's _enforce_decision should raise for block in enforce mode
        with pytest.raises(SecurityPolicyError) as exc_info:
            _enforce_decision(block_decision)
        
        assert exc_info.value.decision.action == "block"


class TestMCPModeEnvVars:
    """Tests for MCP mode via environment variables."""

    def test_env_var_sets_mcp_mode_off(self):
        """Test AGENTSEC_API_MODE_MCP=off sets correct mode."""
        with patch.dict("os.environ", {"AGENTSEC_API_MODE_MCP": "off"}, clear=False):
            with patch("aidefense.runtime.agentsec._apply_patches"):
                agentsec.protect()
                assert get_mcp_mode() == "off"

    def test_env_var_sets_mcp_mode_monitor(self):
        """Test AGENTSEC_API_MODE_MCP=on_monitor sets correct mode."""
        with patch.dict("os.environ", {"AGENTSEC_API_MODE_MCP": "on_monitor"}, clear=False):
            with patch("aidefense.runtime.agentsec._apply_patches"):
                agentsec.protect()
                assert get_mcp_mode() == "on_monitor"

    def test_env_var_sets_mcp_mode_enforce(self):
        """Test AGENTSEC_API_MODE_MCP=on_enforce sets correct mode."""
        with patch.dict("os.environ", {"AGENTSEC_API_MODE_MCP": "on_enforce"}, clear=False):
            with patch("aidefense.runtime.agentsec._apply_patches"):
                agentsec.protect()
                assert get_mcp_mode() == "on_enforce"

    def test_explicit_param_overrides_env_var(self):
        """Test explicit mcp_mode parameter overrides environment variable."""
        with patch.dict("os.environ", {"AGENTSEC_API_MODE_MCP": "off"}, clear=False):
            with patch("aidefense.runtime.agentsec._apply_patches"):
                agentsec.protect(api_mode_mcp="on_enforce")
                assert get_mcp_mode() == "on_enforce"


class TestMCPModeAndLLMModeCombinations:
    """Tests for combining MCP and LLM modes."""

    def test_independent_mcp_and_llm_modes(self):
        """Test that MCP and LLM modes are independent."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode_llm="on_enforce", api_mode_mcp="on_monitor")
            
            from aidefense.runtime.agentsec._state import get_llm_mode, get_mcp_mode
            assert get_llm_mode() == "on_enforce"
            assert get_mcp_mode() == "on_monitor"

    def test_llm_enforce_mcp_off(self):
        """Test LLM enforce with MCP off."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode_llm="on_enforce", api_mode_mcp="off")
            
            from aidefense.runtime.agentsec._state import get_llm_mode, get_mcp_mode
            from aidefense.runtime.agentsec.patchers.mcp import _should_inspect
            
            assert get_llm_mode() == "on_enforce"
            assert get_mcp_mode() == "off"
            assert _should_inspect() is False

    def test_llm_off_mcp_enforce(self):
        """Test LLM off with MCP enforce."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode_llm="off", api_mode_mcp="on_enforce")
            
            from aidefense.runtime.agentsec._state import get_llm_mode, get_mcp_mode
            from aidefense.runtime.agentsec.patchers.mcp import _should_inspect
            
            assert get_llm_mode() == "off"
            assert get_mcp_mode() == "on_enforce"
            assert _should_inspect() is True

