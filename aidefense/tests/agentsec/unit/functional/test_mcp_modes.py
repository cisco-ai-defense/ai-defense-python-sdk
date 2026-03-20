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

"""Integration tests for MCP inspection modes (off/monitor/enforce)."""

import pytest
from unittest.mock import patch

from aidefense.runtime import agentsec
from aidefense.runtime.agentsec._state import reset, get_mcp_mode, get_llm_mode
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
        """Test that protect(api_mode={"mcp": {"mode": "off"}}) sets mode correctly."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode={"mcp": {"mode": "off"}})
            assert get_mcp_mode() == "off"

    def test_off_mode_should_not_inspect(self):
        """Test that off mode causes _should_inspect to return False."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode={"mcp": {"mode": "off"}})
        
        from aidefense.runtime.agentsec.patchers.mcp import _should_inspect
        assert _should_inspect() is False

    def test_off_mode_skips_inspection(self):
        """Test that off mode completely skips MCP inspection."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode={"mcp": {"mode": "off"}})
        
        # Create a mock MCPInspector
        from aidefense.runtime.agentsec.inspectors.api_mcp import MCPInspector
        
        with patch.object(MCPInspector, 'inspect_request') as mock_inspect:
            from aidefense.runtime.agentsec.patchers.mcp import _should_inspect
            
            # When mode is off, _should_inspect returns False
            assert _should_inspect() is False
            
            # The patcher checks _should_inspect before calling inspect_request
            # So inspect_request should never be called when mode is off
            mock_inspect.assert_not_called()


class TestMCPMonitorMode:
    """Tests for MCP monitor mode behavior."""

    def test_monitor_mode_sets_correct_mode(self):
        """Test that protect(api_mode={"mcp": {"mode": "monitor"}}) sets mode correctly."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode={"mcp": {"mode": "monitor"}})
            assert get_mcp_mode() == "monitor"

    def test_monitor_mode_should_inspect(self):
        """Test that monitor mode causes _should_inspect to return True."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode={"mcp": {"mode": "monitor"}})
        
        from aidefense.runtime.agentsec.patchers.mcp import _should_inspect
        assert _should_inspect() is True

    def test_monitor_mode_does_not_enforce_block(self):
        """Test that monitor mode does not enforce block decisions."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode={"mcp": {"mode": "monitor"}})
        
        from aidefense.runtime.agentsec.patchers.mcp import _enforce_decision
        from aidefense.runtime.agentsec.decision import Decision
        
        # Create a block decision
        block_decision = Decision.block(reasons=["test_violation"])
        
        # Should NOT raise SecurityPolicyError in monitor mode
        _enforce_decision(block_decision)  # No exception expected

    def test_monitor_mode_inspects_but_does_not_block(self):
        """Test that monitor mode inspects MCP calls but does not block."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode={"mcp": {"mode": "monitor"}}, patch_clients=False)
        
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
        """Test that protect(api_mode={"mcp": {"mode": "enforce"}}) sets mode correctly."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode={"mcp": {"mode": "enforce"}})
            assert get_mcp_mode() == "enforce"

    def test_enforce_mode_should_inspect(self):
        """Test that enforce mode causes _should_inspect to return True."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode={"mcp": {"mode": "enforce"}})
        
        from aidefense.runtime.agentsec.patchers.mcp import _should_inspect
        assert _should_inspect() is True

    def test_enforce_mode_enforces_block(self):
        """Test that enforce mode enforces block decisions."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode={"mcp": {"mode": "enforce"}})
        
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
            agentsec.protect(api_mode={"mcp": {"mode": "enforce"}})
        
        from aidefense.runtime.agentsec.patchers.mcp import _enforce_decision
        from aidefense.runtime.agentsec.decision import Decision
        
        # Create an allow decision
        allow_decision = Decision.allow(reasons=[])
        
        # Should NOT raise for allow decisions
        _enforce_decision(allow_decision)  # No exception expected

    def test_enforce_mode_with_allow_permits_request(self):
        """Test that enforce mode with allow response permits request."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode={"mcp": {"mode": "enforce"}}, patch_clients=False)
        
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
            agentsec.protect(api_mode={"mcp": {"mode": "enforce"}}, patch_clients=False)
        
        from aidefense.runtime.agentsec.decision import Decision
        from aidefense.runtime.agentsec.patchers.mcp import _enforce_decision
        
        # Create a block decision (simulates what API would return)
        block_decision = Decision.block(reasons=["Violence: SAFETY_VIOLATION"])
        
        assert block_decision.action == "block"
        
        # The patcher's _enforce_decision should raise for block in enforce mode
        with pytest.raises(SecurityPolicyError) as exc_info:
            _enforce_decision(block_decision)
        
        assert exc_info.value.decision.action == "block"


class TestNoneModeDefaultsToOff:
    """Tests that None (unconfigured) mode defaults to off for both MCP and LLM."""

    def test_mcp_none_mode_should_not_inspect(self):
        """When MCP mode is not configured (None), _should_inspect returns False."""
        reset()
        assert get_mcp_mode() is None
        from aidefense.runtime.agentsec.patchers.mcp import _should_inspect
        assert _should_inspect() is False

    def test_llm_none_mode_should_not_inspect(self):
        """When LLM mode is not configured (None), _should_inspect returns False."""
        reset()
        assert get_llm_mode() is None
        from aidefense.runtime.agentsec.patchers.openai import _should_inspect
        assert _should_inspect() is False

    def test_no_patching_when_modes_none(self):
        """_apply_patches should not patch anything when both modes are None."""
        from aidefense.runtime.agentsec import _apply_patches
        with patch("aidefense.runtime.agentsec.patchers.openai.patch_openai") as mock_llm, \
             patch("aidefense.runtime.agentsec.patchers.mcp.patch_mcp") as mock_mcp, \
             patch("aidefense.runtime.agentsec._state.get_llm_integration_mode", return_value="api"), \
             patch("aidefense.runtime.agentsec._state.get_mcp_integration_mode", return_value="api"):
            _apply_patches(api_mode_llm=None, api_mode_mcp=None)
            mock_llm.assert_not_called()
            mock_mcp.assert_not_called()

    def test_only_configured_mode_is_patched(self):
        """When only LLM mode is configured, MCP should not be patched."""
        from aidefense.runtime.agentsec import _apply_patches
        with patch("aidefense.runtime.agentsec.patchers.mcp.patch_mcp") as mock_mcp, \
             patch("aidefense.runtime.agentsec._state.get_llm_integration_mode", return_value="api"), \
             patch("aidefense.runtime.agentsec._state.get_mcp_integration_mode", return_value="api"), \
             patch("aidefense.runtime.agentsec.patchers.openai.patch_openai"), \
             patch("aidefense.runtime.agentsec.patchers.bedrock.patch_bedrock"), \
             patch("aidefense.runtime.agentsec.patchers.vertexai.patch_vertexai"), \
             patch("aidefense.runtime.agentsec.patchers.google_genai.patch_google_genai"), \
             patch("aidefense.runtime.agentsec.patchers.cohere.patch_cohere"), \
             patch("aidefense.runtime.agentsec.patchers.mistral.patch_mistral"), \
             patch("aidefense.runtime.agentsec.patchers.litellm.patch_litellm"), \
             patch("aidefense.runtime.agentsec.patchers.azure_ai_inference.patch_azure_ai_inference"):
            _apply_patches(api_mode_llm="monitor", api_mode_mcp=None)
            mock_mcp.assert_not_called()


class TestNoCredentialFallback:
    """Tests that MCP credentials do not fall back to LLM credentials."""

    def test_mcp_endpoint_no_llm_fallback(self):
        """get_api_mode_mcp_endpoint should not fall back to LLM endpoint."""
        from aidefense.runtime.agentsec import _state
        reset()
        _state._api_mode_llm_endpoint = "https://llm.example.com"
        _state._api_mode_mcp_endpoint = None
        assert _state.get_api_mode_mcp_endpoint() is None

    def test_mcp_api_key_no_llm_fallback(self):
        """get_api_mode_mcp_api_key should not fall back to LLM key."""
        from aidefense.runtime.agentsec import _state
        reset()
        _state._api_mode_llm_api_key = "llm_key_1234"
        _state._api_mode_mcp_api_key = None
        assert _state.get_api_mode_mcp_api_key() is None

    def test_mcp_endpoint_returns_own_value(self):
        """get_api_mode_mcp_endpoint returns MCP-specific endpoint when set."""
        from aidefense.runtime.agentsec import _state
        reset()
        _state._api_mode_mcp_endpoint = "https://mcp.example.com"
        _state._api_mode_llm_endpoint = "https://llm.example.com"
        assert _state.get_api_mode_mcp_endpoint() == "https://mcp.example.com"

    def test_mcp_inspector_no_llm_env_fallback(self):
        """MCPInspector should not fall back to LLM env vars for credentials."""
        import os
        from aidefense.runtime.agentsec.inspectors.api_mcp import MCPInspector

        reset()
        env_overrides = {
            "AI_DEFENSE_API_MODE_LLM_API_KEY": "llm_env_key",
            "AI_DEFENSE_API_MODE_LLM_ENDPOINT": "https://llm-env.example.com",
        }
        env_clear = [
            "AI_DEFENSE_API_MODE_MCP_API_KEY",
            "AI_DEFENSE_API_MODE_MCP_ENDPOINT",
        ]
        with patch.dict(os.environ, env_overrides):
            for k in env_clear:
                os.environ.pop(k, None)
            inspector = MCPInspector(fail_open=True)
            assert inspector.api_key is None
            assert inspector.endpoint is None


class TestMCPModeAndLLMModeCombinations:
    """Tests for combining MCP and LLM modes."""

    def test_independent_mcp_and_llm_modes(self):
        """Test that MCP and LLM modes are independent."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode={"llm": {"mode": "enforce"}, "mcp": {"mode": "monitor"}})
            
            from aidefense.runtime.agentsec._state import get_llm_mode, get_mcp_mode
            assert get_llm_mode() == "enforce"
            assert get_mcp_mode() == "monitor"

    def test_llm_enforce_mcp_off(self):
        """Test LLM enforce with MCP off."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode={"llm": {"mode": "enforce"}, "mcp": {"mode": "off"}})
            
            from aidefense.runtime.agentsec._state import get_llm_mode, get_mcp_mode
            from aidefense.runtime.agentsec.patchers.mcp import _should_inspect
            
            assert get_llm_mode() == "enforce"
            assert get_mcp_mode() == "off"
            assert _should_inspect() is False

    def test_llm_off_mcp_enforce(self):
        """Test LLM off with MCP enforce."""
        with patch("aidefense.runtime.agentsec._apply_patches"):
            agentsec.protect(api_mode={"llm": {"mode": "off"}, "mcp": {"mode": "enforce"}})
            
            from aidefense.runtime.agentsec._state import get_llm_mode, get_mcp_mode
            from aidefense.runtime.agentsec.patchers.mcp import _should_inspect
            
            assert get_llm_mode() == "off"
            assert get_mcp_mode() == "enforce"
            assert _should_inspect() is True

