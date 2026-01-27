"""Tests for protect() integration (Task 13.1)."""

import pytest
from unittest.mock import patch

from aidefense.runtime import agentsec
from aidefense.runtime.agentsec import protect, get_patched_clients
from aidefense.runtime.agentsec._state import reset


@pytest.fixture(autouse=True)
def reset_state():
    """Reset agentsec state before and after each test."""
    reset()
    # Also reset patch registry
    from aidefense.runtime.agentsec.patchers import reset_registry
    reset_registry()
    yield
    reset()
    reset_registry()


class TestProtectIntegration:
    """Test protect() integration with patching."""

    def test_protect_patches_clients_when_enabled(self):
        """Test protect() patches all clients when patch_clients=True."""
        # Mock the patch functions to track calls
        with patch("aidefense.runtime.agentsec.patchers.patch_openai") as mock_openai, \
             patch("aidefense.runtime.agentsec.patchers.patch_bedrock") as mock_bedrock, \
             patch("aidefense.runtime.agentsec.patchers.patch_vertexai") as mock_vertexai, \
             patch("aidefense.runtime.agentsec.patchers.patch_mcp") as mock_mcp:
            
            protect(api_mode_llm="on_enforce", patch_clients=True)
            
            mock_openai.assert_called_once()
            mock_bedrock.assert_called_once()
            mock_vertexai.assert_called_once()
            mock_mcp.assert_called_once()

    def test_protect_skips_patching_when_disabled(self):
        """Test protect() skips patching when patch_clients=False."""
        with patch("aidefense.runtime.agentsec.patchers.patch_openai") as mock_openai, \
             patch("aidefense.runtime.agentsec.patchers.patch_bedrock") as mock_bedrock:
            
            protect(api_mode_llm="on_enforce", patch_clients=False)
            
            mock_openai.assert_not_called()
            mock_bedrock.assert_not_called()

    def test_get_patched_clients_after_protect(self):
        """Test get_patched_clients() returns correct list after protect()."""
        from aidefense.runtime.agentsec.patchers import mark_patched
        
        protect(api_mode_llm="on_enforce", patch_clients=False)
        
        # Manually mark some as patched
        mark_patched("openai")
        mark_patched("bedrock")
        
        patched = get_patched_clients()
        assert "openai" in patched
        assert "bedrock" in patched


class TestProtectModes:
    """Test protect() with different modes."""

    def test_protect_off_mode_skips_all(self):
        """Test all modes='off' skips patching."""
        with patch("aidefense.runtime.agentsec._apply_patches") as mock_patches:
            
            protect(api_mode_llm="off", api_mode_mcp="off")
            
            mock_patches.assert_not_called()

    def test_protect_monitor_mode_enables_all(self):
        """Test api_mode_llm='monitor' enables patching."""
        with patch("aidefense.runtime.agentsec.patchers.patch_openai"), \
             patch("aidefense.runtime.agentsec.patchers.patch_bedrock"), \
             patch("aidefense.runtime.agentsec.patchers.patch_vertexai"), \
             patch("aidefense.runtime.agentsec.patchers.patch_mcp"):
            
            protect(api_mode_llm="on_monitor")
            
            from aidefense.runtime.agentsec._state import get_llm_mode
            assert get_llm_mode() == "on_monitor"

    def test_protect_enforce_mode_enables_all(self):
        """Test api_mode_llm='enforce' enables patching."""
        with patch("aidefense.runtime.agentsec.patchers.patch_openai"), \
             patch("aidefense.runtime.agentsec.patchers.patch_bedrock"), \
             patch("aidefense.runtime.agentsec.patchers.patch_vertexai"), \
             patch("aidefense.runtime.agentsec.patchers.patch_mcp"):
            
            protect(api_mode_llm="on_enforce")
            
            from aidefense.runtime.agentsec._state import get_llm_mode
            assert get_llm_mode() == "on_enforce"

    def test_protect_fine_grained_modes(self):
        """Test fine-grained mode control."""
        with patch("aidefense.runtime.agentsec.patchers.patch_openai"), \
             patch("aidefense.runtime.agentsec.patchers.patch_bedrock"), \
             patch("aidefense.runtime.agentsec.patchers.patch_vertexai"):
            
            protect(api_mode_llm="on_enforce", api_mode_mcp="on_monitor")
            
            from aidefense.runtime.agentsec._state import get_llm_mode, get_mcp_mode
            assert get_llm_mode() == "on_enforce"
            assert get_mcp_mode() == "on_monitor"
