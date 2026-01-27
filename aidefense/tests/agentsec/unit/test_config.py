"""Tests for configuration and environment variables."""

import os
from unittest.mock import patch

import pytest

from aidefense.runtime.agentsec.config import (
    load_env_config,
    _parse_rules_env,
    _parse_integration_mode_env,
    VALID_INTEGRATION_MODES,
)


class TestParseRulesEnv:
    """Test _parse_rules_env function for LLM rules parsing."""

    def test_parse_rules_comma_separated(self):
        """Test parsing comma-separated rules."""
        result = _parse_rules_env("jailbreak,prompt_injection,pii_detection")
        assert result == ["jailbreak", "prompt_injection", "pii_detection"]

    def test_parse_rules_comma_separated_with_spaces(self):
        """Test parsing comma-separated rules with whitespace."""
        result = _parse_rules_env("  jailbreak , prompt_injection , pii_detection  ")
        assert result == ["jailbreak", "prompt_injection", "pii_detection"]

    def test_parse_rules_json_array(self):
        """Test parsing JSON array format."""
        result = _parse_rules_env('["jailbreak", "prompt_injection"]')
        assert result == ["jailbreak", "prompt_injection"]

    def test_parse_rules_json_array_single_quotes_fallback(self):
        """Test that invalid JSON falls back to comma-separated."""
        # This is invalid JSON (uses single quotes), should fall back to comma-separated
        result = _parse_rules_env("['jailbreak', 'prompt_injection']")
        # Falls back to treating it as comma-separated (which won't work well but handles gracefully)
        assert result is not None

    def test_parse_rules_empty_string(self):
        """Test that empty string returns None."""
        assert _parse_rules_env("") is None
        assert _parse_rules_env("   ") is None

    def test_parse_rules_none(self):
        """Test that None returns None."""
        assert _parse_rules_env(None) is None

    def test_parse_rules_single_rule(self):
        """Test single rule without comma."""
        result = _parse_rules_env("jailbreak")
        assert result == ["jailbreak"]


class TestEnvConfig:
    """Test environment variable loading."""

    def test_load_env_config(self):
        """Test environment variable loading for each AGENTSEC_* var."""
        env_vars = {
            "AGENTSEC_API_MODE_LLM": "on_monitor",
            "AGENTSEC_API_MODE_MCP": "on_enforce",
            "AGENTSEC_API_MODE_FAIL_OPEN_LLM": "true",
            "AGENTSEC_API_MODE_FAIL_OPEN_MCP": "false",
            "AGENTSEC_LLM_RULES": "jailbreak,prompt_injection",
            "AGENTSEC_TENANT_ID": "tenant-123",
            "AGENTSEC_APP_ID": "app-456",
            "AGENTSEC_LOG_LEVEL": "DEBUG",
            "AI_DEFENSE_API_MODE_LLM_API_KEY": "secret-key",
            "AI_DEFENSE_API_MODE_LLM_ENDPOINT": "https://api.example.com",
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            config = load_env_config()
            
            assert config["llm_mode"] == "on_monitor"
            assert config["mcp_mode"] == "on_enforce"
            assert config["llm_fail_open"] is True
            assert config["mcp_fail_open"] is False
            assert config["llm_rules"] == ["jailbreak", "prompt_injection"]
            assert config["tenant_id"] == "tenant-123"
            assert config["application_id"] == "app-456"
            assert config["log_level"] == "DEBUG"
            assert config["api_key"] == "secret-key"
            assert config["api_endpoint"] == "https://api.example.com"

    def test_load_env_config_llm_rules_json(self):
        """Test loading LLM rules in JSON array format."""
        env_vars = {
            "AGENTSEC_LLM_RULES": '["rule1", "rule2", "rule3"]',
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            config = load_env_config()
            assert config["llm_rules"] == ["rule1", "rule2", "rule3"]

    def test_load_env_config_unset_vars(self):
        """Test that unset environment variables return None or defaults."""
        # Clear relevant env vars
        env_to_clear = [
            "AGENTSEC_API_MODE_LLM",
            "AGENTSEC_API_MODE_MCP",
            "AGENTSEC_API_MODE_FAIL_OPEN_LLM",
            "AGENTSEC_API_MODE_FAIL_OPEN_MCP",
            "AGENTSEC_LLM_RULES",
            "AGENTSEC_TENANT_ID", 
            "AGENTSEC_APP_ID",
            "AGENTSEC_LOG_LEVEL",
            "AI_DEFENSE_API_MODE_LLM_API_KEY",
            "AI_DEFENSE_API_MODE_LLM_ENDPOINT",
            "AI_DEFENSE_API_MODE_MCP_API_KEY",
            "AI_DEFENSE_API_MODE_MCP_ENDPOINT",
        ]
        
        with patch.dict(os.environ, {}, clear=False):
            for var in env_to_clear:
                os.environ.pop(var, None)
            
            config = load_env_config()
            
            assert config["llm_mode"] is None
            assert config["mcp_mode"] is None
            # Boolean defaults to True for fail_open
            assert config["llm_fail_open"] is True
            assert config["mcp_fail_open"] is True
            assert config["llm_rules"] is None
            assert config["tenant_id"] is None

    def test_load_env_config_mcp_specific_vars(self):
        """Test MCP-specific API endpoint and key loading."""
        env_vars = {
            "AI_DEFENSE_API_MODE_LLM_API_KEY": "general-key",
            "AI_DEFENSE_API_MODE_LLM_ENDPOINT": "https://general.example.com",
            "AI_DEFENSE_API_MODE_MCP_API_KEY": "mcp-specific-key",
            "AI_DEFENSE_API_MODE_MCP_ENDPOINT": "https://mcp.example.com",
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            config = load_env_config()
            
            # General vars should be as-is
            assert config["api_key"] == "general-key"
            assert config["api_endpoint"] == "https://general.example.com"
            # MCP-specific vars should override
            assert config["mcp_api_key"] == "mcp-specific-key"
            assert config["mcp_api_endpoint"] == "https://mcp.example.com"

    def test_load_env_config_mcp_fallback_to_general(self):
        """Test MCP vars fall back to general vars when not set."""
        env_vars = {
            "AI_DEFENSE_API_MODE_LLM_API_KEY": "general-key",
            "AI_DEFENSE_API_MODE_LLM_ENDPOINT": "https://general.example.com",
        }
        
        # Clear MCP-specific vars
        env_to_clear = ["AI_DEFENSE_API_MODE_MCP_API_KEY", "AI_DEFENSE_API_MODE_MCP_ENDPOINT"]
        
        with patch.dict(os.environ, env_vars, clear=False):
            for var in env_to_clear:
                os.environ.pop(var, None)
            
            config = load_env_config()
            
            # MCP vars should fall back to general
            assert config["mcp_api_key"] == "general-key"
            assert config["mcp_api_endpoint"] == "https://general.example.com"

    def test_load_env_config_mcp_partial_override(self):
        """Test MCP vars can partially override general vars."""
        env_vars = {
            "AI_DEFENSE_API_MODE_LLM_API_KEY": "general-key",
            "AI_DEFENSE_API_MODE_LLM_ENDPOINT": "https://general.example.com",
            "AI_DEFENSE_API_MODE_MCP_ENDPOINT": "https://mcp.example.com",
            # Note: AI_DEFENSE_API_MODE_MCP_API_KEY not set
        }
        
        # Clear MCP API key
        with patch.dict(os.environ, env_vars, clear=False):
            os.environ.pop("AI_DEFENSE_API_MODE_MCP_API_KEY", None)
            
            config = load_env_config()
            
            # MCP endpoint should be specific, key should fall back
            assert config["mcp_api_key"] == "general-key"
            assert config["mcp_api_endpoint"] == "https://mcp.example.com"


class TestIntegrationModeConfig:
    """Test gateway integration mode configuration (Task 1.1)."""

    def test_parse_integration_mode_api(self):
        """Test parsing 'api' integration mode."""
        assert _parse_integration_mode_env("api") == "api"
        assert _parse_integration_mode_env("API") == "api"
        assert _parse_integration_mode_env("Api") == "api"

    def test_parse_integration_mode_gateway(self):
        """Test parsing 'gateway' integration mode."""
        assert _parse_integration_mode_env("gateway") == "gateway"
        assert _parse_integration_mode_env("GATEWAY") == "gateway"
        assert _parse_integration_mode_env("Gateway") == "gateway"

    def test_parse_integration_mode_default(self):
        """Test default integration mode is 'api' when None."""
        assert _parse_integration_mode_env(None) == "api"
        assert _parse_integration_mode_env(None, default="gateway") == "gateway"

    def test_parse_integration_mode_invalid(self):
        """Test invalid integration mode raises ValueError."""
        with pytest.raises(ValueError, match="Invalid integration mode"):
            _parse_integration_mode_env("invalid")
        with pytest.raises(ValueError, match="Invalid integration mode"):
            _parse_integration_mode_env("both")
        with pytest.raises(ValueError, match="api, gateway"):
            _parse_integration_mode_env("proxy")

    def test_load_env_config_integration_modes(self):
        """Test loading LLM and MCP integration modes from env vars."""
        env_vars = {
            "AGENTSEC_LLM_INTEGRATION_MODE": "gateway",
            "AGENTSEC_MCP_INTEGRATION_MODE": "api",
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            config = load_env_config()
            assert config["llm_integration_mode"] == "gateway"
            assert config["mcp_integration_mode"] == "api"

    def test_load_env_config_integration_modes_default(self):
        """Test default integration modes are 'api' when not set."""
        env_to_clear = [
            "AGENTSEC_LLM_INTEGRATION_MODE",
            "AGENTSEC_MCP_INTEGRATION_MODE",
        ]
        
        with patch.dict(os.environ, {}, clear=False):
            for var in env_to_clear:
                os.environ.pop(var, None)
            
            config = load_env_config()
            assert config["llm_integration_mode"] == "api"
            assert config["mcp_integration_mode"] == "api"

    def test_load_env_config_provider_gateway_urls(self):
        """Test loading provider-specific gateway URLs and API keys from env vars."""
        env_vars = {
            "AGENTSEC_OPENAI_GATEWAY_URL": "https://gateway.example.com/openai",
            "AGENTSEC_OPENAI_GATEWAY_API_KEY": "openai-gateway-key",
            "AGENTSEC_VERTEXAI_GATEWAY_URL": "https://gateway.example.com/vertexai",
            "AGENTSEC_VERTEXAI_GATEWAY_API_KEY": "vertexai-gateway-key",
            "AGENTSEC_MCP_GATEWAY_URL": "https://gateway.example.com/mcp",
            "AGENTSEC_MCP_GATEWAY_API_KEY": "mcp-gateway-key",
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            config = load_env_config()
            assert config["provider_gateway_config"]["openai"]["url"] == "https://gateway.example.com/openai"
            assert config["provider_gateway_config"]["openai"]["api_key"] == "openai-gateway-key"
            assert config["provider_gateway_config"]["vertexai"]["url"] == "https://gateway.example.com/vertexai"
            assert config["provider_gateway_config"]["vertexai"]["api_key"] == "vertexai-gateway-key"
            assert config["mcp_gateway_url"] == "https://gateway.example.com/mcp"
            assert config["mcp_gateway_api_key"] == "mcp-gateway-key"

    def test_load_env_config_gateway_urls_unset(self):
        """Test gateway URLs return None when not set."""
        env_to_clear = [
            "AGENTSEC_OPENAI_GATEWAY_URL",
            "AGENTSEC_OPENAI_GATEWAY_API_KEY",
            "AGENTSEC_MCP_GATEWAY_URL",
            "AGENTSEC_MCP_GATEWAY_API_KEY",
        ]
        
        with patch.dict(os.environ, {}, clear=False):
            for var in env_to_clear:
                os.environ.pop(var, None)
            
            config = load_env_config()
            assert config["provider_gateway_config"]["openai"]["url"] is None
            assert config["provider_gateway_config"]["openai"]["api_key"] is None
            assert config["mcp_gateway_url"] is None
            assert config["mcp_gateway_api_key"] is None


class TestGatewayModeConfig:
    """Test gateway mode parsing (off/on only - gateway handles enforcement)."""

    def test_parse_gateway_mode_on(self):
        """Test parsing 'on' gateway mode."""
        from aidefense.runtime.agentsec.config import _parse_gateway_mode_env
        assert _parse_gateway_mode_env("on") == "on"
        assert _parse_gateway_mode_env("ON") == "on"
        assert _parse_gateway_mode_env("On") == "on"

    def test_parse_gateway_mode_off(self):
        """Test parsing 'off' gateway mode."""
        from aidefense.runtime.agentsec.config import _parse_gateway_mode_env
        assert _parse_gateway_mode_env("off") == "off"
        assert _parse_gateway_mode_env("OFF") == "off"

    def test_parse_gateway_mode_default(self):
        """Test default gateway mode is 'on' when not set."""
        from aidefense.runtime.agentsec.config import _parse_gateway_mode_env
        assert _parse_gateway_mode_env(None) == "on"

    def test_parse_gateway_mode_invalid(self):
        """Test invalid gateway mode raises ValueError."""
        from aidefense.runtime.agentsec.config import _parse_gateway_mode_env
        # monitor/enforce are NOT valid for gateway mode
        with pytest.raises(ValueError, match="off, on"):
            _parse_gateway_mode_env("on_monitor")
        with pytest.raises(ValueError, match="off, on"):
            _parse_gateway_mode_env("on_enforce")
        with pytest.raises(ValueError, match="off, on"):
            _parse_gateway_mode_env("invalid")

    def test_load_env_config_gateway_modes(self):
        """Test loading gateway mode settings from env vars."""
        env_vars = {
            "AGENTSEC_GATEWAY_MODE_LLM": "off",
            "AGENTSEC_GATEWAY_MODE_MCP": "on",
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            config = load_env_config()
            assert config["llm_gateway_mode"] == "off"
            assert config["mcp_gateway_mode"] == "on"

    def test_load_env_config_gateway_modes_default(self):
        """Test default gateway modes are 'on' when not set."""
        env_to_clear = [
            "AGENTSEC_GATEWAY_MODE_LLM",
            "AGENTSEC_GATEWAY_MODE_MCP",
        ]
        
        with patch.dict(os.environ, {}, clear=False):
            for var in env_to_clear:
                os.environ.pop(var, None)
            
            config = load_env_config()
            assert config["llm_gateway_mode"] == "on"
            assert config["mcp_gateway_mode"] == "on"

    def test_load_env_config_gateway_fail_open(self):
        """Test loading gateway fail_open settings from env vars."""
        env_vars = {
            "AGENTSEC_GATEWAY_MODE_FAIL_OPEN_LLM": "false",
            "AGENTSEC_GATEWAY_MODE_FAIL_OPEN_MCP": "true",
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            config = load_env_config()
            assert config["llm_gateway_fail_open"] is False
            assert config["mcp_gateway_fail_open"] is True

    def test_load_env_config_gateway_fail_open_default(self):
        """Test default gateway fail_open is True when not set."""
        env_to_clear = [
            "AGENTSEC_GATEWAY_MODE_FAIL_OPEN_LLM",
            "AGENTSEC_GATEWAY_MODE_FAIL_OPEN_MCP",
        ]
        
        with patch.dict(os.environ, {}, clear=False):
            for var in env_to_clear:
                os.environ.pop(var, None)
            
            config = load_env_config()
            assert config["llm_gateway_fail_open"] is True
            assert config["mcp_gateway_fail_open"] is True

    def test_separate_api_and_gateway_settings(self):
        """Test API mode and gateway mode have separate settings."""
        env_vars = {
            # API mode settings
            "AGENTSEC_API_MODE_LLM": "on_enforce",
            "AGENTSEC_API_MODE_MCP": "on_monitor",
            "AGENTSEC_API_MODE_FAIL_OPEN_LLM": "false",
            "AGENTSEC_API_MODE_FAIL_OPEN_MCP": "true",
            # Gateway mode settings (separate!)
            "AGENTSEC_GATEWAY_MODE_LLM": "on",
            "AGENTSEC_GATEWAY_MODE_MCP": "off",
            "AGENTSEC_GATEWAY_MODE_FAIL_OPEN_LLM": "true",
            "AGENTSEC_GATEWAY_MODE_FAIL_OPEN_MCP": "false",
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            config = load_env_config()
            
            # API mode settings
            assert config["llm_mode"] == "on_enforce"
            assert config["mcp_mode"] == "on_monitor"
            assert config["llm_fail_open"] is False
            assert config["mcp_fail_open"] is True
            
            # Gateway mode settings (separate from API mode)
            assert config["llm_gateway_mode"] == "on"
            assert config["mcp_gateway_mode"] == "off"
            assert config["llm_gateway_fail_open"] is True
            assert config["mcp_gateway_fail_open"] is False
