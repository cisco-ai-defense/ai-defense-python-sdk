"""Tests for VertexAI patcher."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from aidefense.runtime.agentsec.patchers.vertexai import (
    patch_vertexai,
    _wrap_generate_content,
)
from aidefense.runtime.agentsec.exceptions import SecurityPolicyError
from aidefense.runtime.agentsec.decision import Decision
from aidefense.runtime.agentsec import _state
from aidefense.runtime.agentsec._context import clear_inspection_context
from aidefense.runtime.agentsec.patchers import reset_registry


@pytest.fixture(autouse=True)
def reset_state():
    """Reset agentsec state before each test."""
    _state.reset()
    reset_registry()
    clear_inspection_context()
    # Reset global inspector
    import aidefense.runtime.agentsec.patchers.vertexai as vertexai_module
    vertexai_module._inspector = None
    yield
    _state.reset()
    reset_registry()
    clear_inspection_context()
    vertexai_module._inspector = None


class TestVertexAIPatcherInspection:
    """Test inspection integration."""

    @patch("aidefense.runtime.agentsec.patchers.vertexai._get_inspector")
    def test_sync_generate_content_calls_inspector(self, mock_get_inspector):
        """Test that sync generate_content triggers inspection."""
        # Setup
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = Decision.allow(reasons=[])
        mock_get_inspector.return_value = mock_inspector
        
        # Setup state
        _state.set_state(initialized=True, llm_rules=None, api_mode_fail_open_llm=True, api_mode_llm="on_monitor")
        clear_inspection_context()
        
        # Mock wrapped function
        mock_wrapped = MagicMock()
        mock_response = MagicMock()
        mock_response.candidates = []
        mock_wrapped.return_value = mock_response
        
        # Mock instance
        mock_instance = MagicMock()
        mock_instance.model_name = "gemini-pro"
        
        # Call wrapper
        result = _wrap_generate_content(
            mock_wrapped,
            mock_instance,
            ("Hello",),
            {}
        )
        
        # Verify inspector was called
        mock_inspector.inspect_conversation.assert_called()
        # Verify provider metadata
        call_args = mock_inspector.inspect_conversation.call_args
        metadata = call_args[0][1]  # Second positional arg
        assert metadata.get("provider") == "vertexai"

    @patch("aidefense.runtime.agentsec.patchers.vertexai._get_inspector")
    def test_enforce_mode_raises_on_block(self, mock_get_inspector):
        """Test that enforce mode raises SecurityPolicyError on block."""
        # Setup
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = Decision.block(reasons=["policy_violation"])
        mock_get_inspector.return_value = mock_inspector
        
        # Setup state in enforce mode
        _state.set_state(initialized=True, llm_rules=None, api_mode_fail_open_llm=True, api_mode_llm="on_enforce")
        clear_inspection_context()
        
        # Mock wrapped function
        mock_wrapped = MagicMock()
        
        # Mock instance
        mock_instance = MagicMock()
        mock_instance.model_name = "gemini-pro"
        
        # Call wrapper - should raise
        with pytest.raises(SecurityPolicyError):
            _wrap_generate_content(
                mock_wrapped,
                mock_instance,
                ("Hello",),
                {}
            )


class TestVertexAIPatcherAsync:
    """Test async inspection."""

    @pytest.mark.asyncio
    @patch("aidefense.runtime.agentsec.patchers.vertexai._get_inspector")
    async def test_async_generate_content_calls_inspector(self, mock_get_inspector):
        """Test that async generate_content triggers inspection."""
        from aidefense.runtime.agentsec.patchers.vertexai import _wrap_generate_content_async
        
        # Setup
        mock_inspector = MagicMock()
        mock_inspector.ainspect_conversation = AsyncMock(return_value=Decision.allow(reasons=[]))
        mock_get_inspector.return_value = mock_inspector
        
        # Setup state
        _state.set_state(initialized=True, llm_rules=None, api_mode_fail_open_llm=True, api_mode_llm="on_monitor")
        clear_inspection_context()
        
        # Mock wrapped async function
        mock_response = MagicMock()
        mock_response.candidates = []
        mock_wrapped = AsyncMock(return_value=mock_response)
        
        # Mock instance
        mock_instance = MagicMock()
        mock_instance.model_name = "gemini-pro"
        
        # Call wrapper
        result = await _wrap_generate_content_async(
            mock_wrapped,
            mock_instance,
            ("Hello",),
            {}
        )
        
        # Verify async inspector was called
        mock_inspector.ainspect_conversation.assert_called()
        assert mock_wrapped.called


class TestVertexAIPatcherSkipConditions:
    """Test conditions where patching is skipped."""

    def test_skips_when_library_not_installed(self):
        """Test graceful skip when vertexai not installed."""
        with patch("aidefense.runtime.agentsec.patchers.vertexai.safe_import", return_value=None):
            result = patch_vertexai()
            assert result is False

    def test_skips_when_already_patched(self):
        """Test skip when already patched."""
        with patch("aidefense.runtime.agentsec.patchers.vertexai.is_patched", return_value=True):
            result = patch_vertexai()
            assert result is True








