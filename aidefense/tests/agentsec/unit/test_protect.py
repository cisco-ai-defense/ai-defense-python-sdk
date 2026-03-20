# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for protect() function (Task 5.1)."""

import os
from unittest.mock import patch

import pytest

from aidefense.runtime import agentsec
from aidefense.runtime.agentsec import protect
from aidefense.runtime.agentsec._state import reset
from aidefense.runtime.agentsec.exceptions import ConfigurationError


_ENV_PREFIXES = ("AGENTSEC_", "AI_DEFENSE_")


@pytest.fixture(autouse=True)
def reset_state():
    """Reset agentsec state and clear agentsec/AI Defense env vars before and after each test.
    
    This ensures tests are not affected by environment variables set by
    integration test runs or .env files sourced into the shell.
    Clears both AGENTSEC_* and AI_DEFENSE_* prefixed variables.
    """
    # Save and clear any relevant env vars
    saved_env = {k: v for k, v in os.environ.items() if k.startswith(_ENV_PREFIXES)}
    for k in saved_env:
        del os.environ[k]
    reset()
    yield
    reset()
    # Restore original env vars
    for k in list(os.environ.keys()):
        if k.startswith(_ENV_PREFIXES):
            del os.environ[k]
    os.environ.update(saved_env)


class TestProtect:
    """Test protect() function."""

    def test_protect_default_arguments(self):
        """Test protect() with default arguments succeeds.
        
        With no args, protect() sets initialized=True with no mode configured
        (api_mode_llm and api_mode_mcp are None).
        """
        protect()
        
        from aidefense.runtime.agentsec._state import get_api_mode_llm, get_api_mode_mcp, is_initialized
        assert is_initialized()
        assert get_api_mode_llm() is None
        assert get_api_mode_mcp() is None

    def test_protect_idempotent(self):
        """Test protect() is idempotent (multiple calls don't error)."""
        protect(api_mode={"llm": {"mode": "enforce"}})
        protect(api_mode={"llm": {"mode": "enforce"}})  # Should not raise
        protect(api_mode={"llm": {"mode": "monitor"}})  # Should not change mode (idempotent)
        
        from aidefense.runtime.agentsec._state import get_api_mode_llm
        assert get_api_mode_llm() == "enforce"  # First call wins

    def test_protect_mode_off(self):
        """Test protect() with all modes='off'."""
        protect(api_mode={"llm": {"mode": "off"}, "mcp": {"mode": "off"}})
        
        from aidefense.runtime.agentsec._state import get_api_mode_llm, get_api_mode_mcp, is_initialized
        assert is_initialized()
        assert get_api_mode_llm() == "off"
        assert get_api_mode_mcp() == "off"

    def test_protect_invalid_mode(self):
        """Test protect() with invalid mode raises ConfigurationError."""
        with pytest.raises(ConfigurationError, match="Invalid api_mode.llm.mode"):
            protect(api_mode={"llm": {"mode": "invalid"}})
        
        reset()
        with pytest.raises(ConfigurationError, match="Invalid api_mode.llm.mode"):
            protect(api_mode={"llm": {"mode": "ENFORCE"}})  # Case sensitive
            
        reset()
        with pytest.raises(ConfigurationError, match="Invalid api_mode.mcp.mode"):
            protect(api_mode={"mcp": {"mode": "invalid"}})

    def test_protect_llm_rules_parameter(self):
        """Test protect() accepts rules via api_mode.llm.rules."""
        protect(
            api_mode={"llm": {"rules": ["jailbreak", "prompt_injection"]}},
        )
        
        from aidefense.runtime.agentsec._state import get_llm_rules
        assert get_llm_rules() == ["jailbreak", "prompt_injection"]

    def test_protect_llm_rules_dict_format(self):
        """Test protect() accepts dict-format rules (as from YAML parsing)."""
        protect(
            api_mode={"llm": {"rules": [
                {"rule_name": "PII", "entity_types": ["Email Address"]},
                {"rule_name": "Prompt Injection"},
            ]}},
        )

        from aidefense.runtime.agentsec._state import get_llm_rules
        rules = get_llm_rules()
        assert len(rules) == 2
        assert rules[0]["rule_name"] == "PII"
        assert rules[0]["entity_types"] == ["Email Address"]
        assert rules[1]["rule_name"] == "Prompt Injection"

    def test_protect_fine_grained_modes(self):
        """Test protect() with fine-grained mode control."""
        protect(
            api_mode={"llm": {"mode": "enforce"}, "mcp": {"mode": "monitor"}},
        )
        
        from aidefense.runtime.agentsec._state import get_api_mode_llm, get_api_mode_mcp
        assert get_api_mode_llm() == "enforce"
        assert get_api_mode_mcp() == "monitor"

    def test_protect_gateway_mode_parameters(self):
        """Test protect() with gateway mode configuration parameters."""
        protect(
            llm_integration_mode="gateway",
            gateway_mode={
                "llm_gateways": {
                    "openai-1": {
                        "gateway_url": "https://gateway.example.com/openai",
                        "gateway_api_key": "openai-key-123",
                        "provider": "openai",
                        "default": True,
                    },
                },
                "mcp_gateways": {
                    "https://mcp.example.com/mcp": {"gateway_url": "https://gateway.example.com/mcp", "gateway_api_key": "mcp-key-456"},
                },
            },
            mcp_integration_mode="gateway",
        )
        
        from aidefense.runtime.agentsec._state import (
            get_llm_integration_mode,
            get_mcp_integration_mode,
            get_default_gateway_for_provider,
            get_mcp_gateway_for_url,
        )
        assert get_llm_integration_mode() == "gateway"
        assert get_mcp_integration_mode() == "gateway"
        openai_gateway = get_default_gateway_for_provider("openai")
        assert openai_gateway is not None
        assert openai_gateway["gateway_url"] == "https://gateway.example.com/openai"
        assert openai_gateway["gateway_api_key"] == "openai-key-123"
        mcp_gw = get_mcp_gateway_for_url("https://mcp.example.com/mcp")
        assert mcp_gw is not None
        assert mcp_gw["gateway_url"] == "https://gateway.example.com/mcp"
        assert mcp_gw["gateway_api_key"] == "mcp-key-456"

    def test_protect_invalid_integration_mode(self):
        """Test protect() with invalid integration mode raises ConfigurationError."""
        with pytest.raises(ConfigurationError, match="Invalid llm_integration_mode"):
            protect(llm_integration_mode="invalid")
        
        reset()
        with pytest.raises(ConfigurationError, match="Invalid mcp_integration_mode"):
            protect(mcp_integration_mode="invalid")

    def test_protect_llm_gateway_only(self):
        """Test protect() with LLM in gateway mode, MCP in API mode."""
        protect(
            llm_integration_mode="gateway",
            gateway_mode={
                "llm_gateways": {
                    "openai-1": {
                        "gateway_url": "https://gateway.example.com/openai",
                        "gateway_api_key": "key",
                        "provider": "openai",
                        "default": True,
                    },
                },
            },
            mcp_integration_mode="api",
            api_mode={"mcp": {"mode": "monitor"}},
        )
        
        from aidefense.runtime.agentsec._state import (
            get_llm_integration_mode,
            get_mcp_integration_mode,
            get_api_mode_mcp,
        )
        assert get_llm_integration_mode() == "gateway"
        assert get_mcp_integration_mode() == "api"
        assert get_api_mode_mcp() == "monitor"

    def test_protect_api_mode_parameters(self):
        """Test protect() with API mode configuration parameters."""
        protect(
            api_mode={
                "llm": {
                    "mode": "enforce",
                    "endpoint": "https://api.example.com/api",
                    "api_key": "test-llm-key",
                },
                "mcp": {
                    "mode": "monitor",
                    "endpoint": "https://mcp-api.example.com/api",
                    "api_key": "test-mcp-key",
                },
            },
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
        assert get_api_mode_llm() == "enforce"
        assert get_api_mode_mcp() == "monitor"

    def test_protect_api_mode_mcp_no_llm_fallback(self):
        """Test protect() MCP does NOT fall back to LLM API config."""
        protect(
            api_mode={
                "llm": {
                    "endpoint": "https://api.example.com/api",
                    "api_key": "test-llm-key",
                },
            },
        )
        
        from aidefense.runtime.agentsec._state import (
            get_api_mode_mcp_endpoint,
            get_api_mode_mcp_api_key,
        )
        assert get_api_mode_mcp_endpoint() is None
        assert get_api_mode_mcp_api_key() is None

    def test_protect_api_mode_fail_open(self):
        """Test protect() with fail_open settings for API mode."""
        protect(
            api_mode={
                "llm_defaults": {"fail_open": False},
                "mcp_defaults": {"fail_open": False},
            },
        )
        
        from aidefense.runtime.agentsec._state import (
            get_api_llm_fail_open,
            get_api_mcp_fail_open,
        )
        assert get_api_llm_fail_open() is False
        assert get_api_mcp_fail_open() is False

    def test_protect_gateway_mode_fail_open(self):
        """Test protect() with fail_open settings for gateway mode."""
        protect(
            llm_integration_mode="gateway",
            mcp_integration_mode="gateway",
            gateway_mode={
                "llm_defaults": {"fail_open": False},
                "mcp_defaults": {"fail_open": False},
            },
        )
        
        from aidefense.runtime.agentsec._state import (
            get_gw_llm_fail_open,
            get_gw_mcp_fail_open,
        )
        assert get_gw_llm_fail_open() is False
        assert get_gw_mcp_fail_open() is False

    def test_protect_gateway_mode_on_off(self):
        """Test protect() with gateway mode on/off switches."""
        protect(
            llm_integration_mode="gateway",
            mcp_integration_mode="gateway",
            gateway_mode={
                "llm_mode": "off",
                "mcp_mode": "off",
            },
        )

        from aidefense.runtime.agentsec._state import (
            get_gw_llm_mode,
            get_gw_mcp_mode,
        )
        assert get_gw_llm_mode() == "off"
        assert get_gw_mcp_mode() == "off"

    def test_protect_gateway_mode_default_on(self):
        """Test protect() gateway mode defaults to 'on'."""
        protect(
            llm_integration_mode="gateway",
            gateway_mode={},
        )

        from aidefense.runtime.agentsec._state import get_gw_llm_mode
        assert get_gw_llm_mode() == "on"

    def test_protect_pool_kwargs(self):
        """Test protect() with pool kwargs stores values in state."""
        protect(pool_max_connections=50, pool_max_keepalive=10)

        from aidefense.runtime.agentsec._state import (
            get_pool_max_connections,
            get_pool_max_keepalive,
        )
        assert get_pool_max_connections() == 50
        assert get_pool_max_keepalive() == 10

    def test_protect_pool_defaults_none(self):
        """Test protect() without pool kwargs leaves state as None."""
        protect()

        from aidefense.runtime.agentsec._state import (
            get_pool_max_connections,
            get_pool_max_keepalive,
        )
        assert get_pool_max_connections() is None
        assert get_pool_max_keepalive() is None

    def test_protect_pool_from_yaml(self, tmp_path):
        """Test protect() reads pool settings from YAML when kwargs are None."""
        yaml_file = tmp_path / "agentsec.yaml"
        yaml_file.write_text(
            "pool_max_connections: 200\n"
            "pool_max_keepalive: 30\n"
        )

        protect(config=str(yaml_file))

        from aidefense.runtime.agentsec._state import (
            get_pool_max_connections,
            get_pool_max_keepalive,
        )
        assert get_pool_max_connections() == 200
        assert get_pool_max_keepalive() == 30

    def test_protect_pool_kwargs_override_yaml(self, tmp_path):
        """Test protect() kwargs override YAML pool values."""
        yaml_file = tmp_path / "agentsec.yaml"
        yaml_file.write_text(
            "pool_max_connections: 200\n"
            "pool_max_keepalive: 30\n"
        )

        protect(config=str(yaml_file), pool_max_connections=50, pool_max_keepalive=5)

        from aidefense.runtime.agentsec._state import (
            get_pool_max_connections,
            get_pool_max_keepalive,
        )
        assert get_pool_max_connections() == 50
        assert get_pool_max_keepalive() == 5

    def test_protect_pool_env_var_yaml(self, tmp_path, monkeypatch):
        """Test protect() handles env var substitution for pool YAML values."""
        monkeypatch.setenv("TEST_POOL_CONN", "150")
        monkeypatch.setenv("TEST_POOL_KEEP", "25")
        yaml_file = tmp_path / "agentsec.yaml"
        yaml_file.write_text(
            "pool_max_connections: ${TEST_POOL_CONN}\n"
            "pool_max_keepalive: ${TEST_POOL_KEEP}\n"
        )

        protect(config=str(yaml_file))

        from aidefense.runtime.agentsec._state import (
            get_pool_max_connections,
            get_pool_max_keepalive,
        )
        assert get_pool_max_connections() == 150
        assert get_pool_max_keepalive() == 25

    def test_protect_pool_invalid_max_connections(self):
        """Test protect() with invalid pool_max_connections raises."""
        with pytest.raises(ConfigurationError, match="pool_max_connections"):
            protect(pool_max_connections=0)

    def test_protect_pool_invalid_max_keepalive(self):
        """Test protect() with invalid pool_max_keepalive raises."""
        with pytest.raises(ConfigurationError, match="pool_max_keepalive"):
            protect(pool_max_keepalive=-1)
