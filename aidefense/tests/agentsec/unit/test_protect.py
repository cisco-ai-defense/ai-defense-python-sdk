"""Tests for protect() function (Task 5.1)."""

import os
from unittest.mock import patch

import pytest

from aidefense.runtime import agentsec
from aidefense.runtime.agentsec import protect
from aidefense.runtime.agentsec._state import reset


@pytest.fixture(autouse=True)
def reset_state():
    """Reset agentsec state before and after each test."""
    reset()
    yield
    reset()


class TestProtect:
    """Test protect() function."""

    def test_protect_default_arguments(self):
        """Test protect() with default arguments succeeds.
        
        Default mode is 'monitor' (safer for development).
        Can be overridden via AGENTSEC_API_MODE_LLM/MCP env vars.
        """
        protect()
        
        from aidefense.runtime.agentsec._state import get_api_mode_llm, get_api_mode_mcp, is_initialized
        assert is_initialized()
        assert get_api_mode_llm() == "on_monitor"  # Default is 'monitor' for safety
        assert get_api_mode_mcp() == "on_monitor"

    def test_protect_idempotent(self):
        """Test protect() is idempotent (multiple calls don't error)."""
        protect(api_mode_llm="on_enforce")
        protect(api_mode_llm="on_enforce")  # Should not raise
        protect(api_mode_llm="on_monitor")  # Should not change mode (idempotent)
        
        from aidefense.runtime.agentsec._state import get_api_mode_llm
        assert get_api_mode_llm() == "on_enforce"  # First call wins

    def test_protect_mode_off(self):
        """Test protect() with all modes='off' skips initialization."""
        protect(api_mode_llm="off", api_mode_mcp="off")
        
        from aidefense.runtime.agentsec._state import get_api_mode_llm, get_api_mode_mcp, is_initialized
        assert is_initialized()
        assert get_api_mode_llm() == "off"
        assert get_api_mode_mcp() == "off"

    def test_protect_invalid_mode(self):
        """Test protect() with invalid mode raises ValueError."""
        with pytest.raises(ValueError, match="Invalid api_mode_llm"):
            protect(api_mode_llm="invalid")
        
        with pytest.raises(ValueError, match="Invalid api_mode_llm"):
            protect(api_mode_llm="ENFORCE")  # Case sensitive
            
        with pytest.raises(ValueError, match="Invalid api_mode_mcp"):
            protect(api_mode_mcp="invalid")

    def test_protect_llm_rules_parameter(self):
        """Test protect() accepts api_mode_llm_rules parameter."""
        protect(
            api_mode_llm_rules=["jailbreak", "prompt_injection"],
        )
        
        from aidefense.runtime.agentsec._state import get_llm_rules
        assert get_llm_rules() == ["jailbreak", "prompt_injection"]

    def test_protect_llm_rules_from_env(self):
        """Test protect() loads llm_rules from environment variable."""
        env_vars = {
            "AGENTSEC_LLM_RULES": "rule1,rule2",
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            protect()
        
        from aidefense.runtime.agentsec._state import get_llm_rules
        assert get_llm_rules() == ["rule1", "rule2"]

    def test_protect_fine_grained_modes(self):
        """Test protect() with fine-grained mode control."""
        protect(
            api_mode_llm="on_enforce",
            api_mode_mcp="on_monitor",
        )
        
        from aidefense.runtime.agentsec._state import get_api_mode_llm, get_api_mode_mcp
        assert get_api_mode_llm() == "on_enforce"
        assert get_api_mode_mcp() == "on_monitor"

    def test_protect_gateway_mode_parameters(self):
        """Test protect() with gateway mode configuration parameters."""
        protect(
            llm_integration_mode="gateway",
            providers={
                "openai": {"gateway_url": "https://gateway.example.com/openai", "gateway_api_key": "openai-key-123"},
            },
            mcp_integration_mode="gateway",
            gateway_mode_mcp_url="https://gateway.example.com/mcp",
            gateway_mode_mcp_api_key="mcp-key-456",
        )
        
        from aidefense.runtime.agentsec._state import (
            get_llm_integration_mode,
            get_mcp_integration_mode,
            get_provider_gateway_url,
            get_provider_gateway_api_key,
            get_gateway_mode_mcp_url,
            get_gateway_mode_mcp_api_key,
        )
        assert get_llm_integration_mode() == "gateway"
        assert get_mcp_integration_mode() == "gateway"
        assert get_provider_gateway_url("openai") == "https://gateway.example.com/openai"
        assert get_provider_gateway_api_key("openai") == "openai-key-123"
        assert get_gateway_mode_mcp_url() == "https://gateway.example.com/mcp"
        assert get_gateway_mode_mcp_api_key() == "mcp-key-456"

    def test_protect_invalid_integration_mode(self):
        """Test protect() with invalid integration mode raises ValueError."""
        with pytest.raises(ValueError, match="Invalid llm_integration_mode"):
            protect(llm_integration_mode="invalid")
        
        # Reset for next test
        reset()
        
        with pytest.raises(ValueError, match="Invalid mcp_integration_mode"):
            protect(mcp_integration_mode="invalid")

    def test_protect_llm_gateway_only(self):
        """Test protect() with LLM in gateway mode, MCP in API mode."""
        protect(
            llm_integration_mode="gateway",
            providers={
                "openai": {"gateway_url": "https://gateway.example.com/openai", "gateway_api_key": "key"},
            },
            mcp_integration_mode="api",
            api_mode_mcp="on_monitor",
        )
        
        from aidefense.runtime.agentsec._state import (
            get_llm_integration_mode,
            get_mcp_integration_mode,
            get_api_mode_mcp,
        )
        assert get_llm_integration_mode() == "gateway"
        assert get_mcp_integration_mode() == "api"
        assert get_api_mode_mcp() == "on_monitor"

    def test_protect_api_mode_parameters(self):
        """Test protect() with API mode configuration parameters."""
        protect(
            api_mode_llm="on_enforce",
            api_mode_llm_endpoint="https://api.example.com/api",
            api_mode_llm_api_key="test-llm-key",
            api_mode_mcp="on_monitor",
            api_mode_mcp_endpoint="https://mcp-api.example.com/api",
            api_mode_mcp_api_key="test-mcp-key",
        )
        
        from aidefense.runtime.agentsec._state import (
            get_api_mode_llm_endpoint,
            get_api_mode_llm_api_key,
            get_api_mode_mcp_endpoint,
            get_api_mode_mcp_api_key,
            get_api_mode_llm,
            get_api_mode_mcp,
        )
        assert get_api_mode_llm_endpoint() == "https://api.example.com/api"
        assert get_api_mode_llm_api_key() == "test-llm-key"
        assert get_api_mode_mcp_endpoint() == "https://mcp-api.example.com/api"
        assert get_api_mode_mcp_api_key() == "test-mcp-key"
        assert get_api_mode_llm() == "on_enforce"
        assert get_api_mode_mcp() == "on_monitor"

    def test_protect_api_mode_mcp_fallback(self):
        """Test protect() with MCP falling back to LLM API config."""
        protect(
            api_mode_llm_endpoint="https://api.example.com/api",
            api_mode_llm_api_key="test-llm-key",
            # MCP not specified - should fall back to LLM
        )
        
        from aidefense.runtime.agentsec._state import (
            get_api_mode_mcp_endpoint,
            get_api_mode_mcp_api_key,
        )
        # MCP should fall back to LLM values
        assert get_api_mode_mcp_endpoint() == "https://api.example.com/api"
        assert get_api_mode_mcp_api_key() == "test-llm-key"

    def test_protect_api_mode_fail_open(self):
        """Test protect() with fail_open settings for API mode."""
        protect(
            api_mode_fail_open_llm=False,
            api_mode_fail_open_mcp=False,
        )
        
        from aidefense.runtime.agentsec._state import (
            get_api_mode_fail_open_llm,
            get_api_mode_fail_open_mcp,
        )
        assert get_api_mode_fail_open_llm() is False
        assert get_api_mode_fail_open_mcp() is False

    def test_protect_gateway_mode_fail_open(self):
        """Test protect() with fail_open settings for gateway mode."""
        protect(
            llm_integration_mode="gateway",
            mcp_integration_mode="gateway",
            gateway_mode_fail_open_llm=False,
            gateway_mode_fail_open_mcp=False,
        )
        
        from aidefense.runtime.agentsec._state import (
            get_gateway_mode_fail_open_llm,
            get_gateway_mode_fail_open_mcp,
        )
        assert get_gateway_mode_fail_open_llm() is False
        assert get_gateway_mode_fail_open_mcp() is False

    def test_protect_gateway_mode_control(self):
        """Test protect() with gateway mode on/off control."""
        protect(
            llm_integration_mode="gateway",
            gateway_mode_llm="off",
            gateway_mode_mcp="on",
        )
        
        from aidefense.runtime.agentsec._state import (
            get_gateway_mode_llm,
            get_gateway_mode_mcp,
        )
        assert get_gateway_mode_llm() == "off"
        assert get_gateway_mode_mcp() == "on"
