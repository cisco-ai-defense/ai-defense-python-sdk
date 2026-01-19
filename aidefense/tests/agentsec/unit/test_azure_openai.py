"""Tests for Azure OpenAI coverage verification."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from aidefense.runtime.agentsec.patchers.openai import (
    patch_openai,
    _wrap_chat_completions_create,
)
from aidefense.runtime.agentsec.exceptions import SecurityPolicyError
from aidefense.runtime.agentsec.decision import Decision
from aidefense.runtime.agentsec import _state
from aidefense.runtime.agentsec._context import clear_inspection_context, get_inspection_context
from aidefense.runtime.agentsec.patchers import reset_registry


@pytest.fixture(autouse=True)
def reset_state():
    """Reset agentsec state before each test."""
    _state.reset()
    reset_registry()
    clear_inspection_context()
    # Reset global inspector
    import aidefense.runtime.agentsec.patchers.openai as openai_module
    openai_module._inspector = None
    yield
    _state.reset()
    reset_registry()
    clear_inspection_context()
    openai_module._inspector = None


class TestAzureOpenAICoverage:
    """Verify Azure OpenAI is covered by existing OpenAI patch."""

    @patch("aidefense.runtime.agentsec.patchers.openai._get_inspector")
    def test_azure_openai_uses_same_completions_resource(self, mock_get_inspector):
        """
        Test that AzureOpenAI client inspection works.
        
        The AzureOpenAI client from the openai library uses the same
        Completions resource class as the standard OpenAI client, so
        our patch at openai.resources.chat.completions.Completions.create
        covers both.
        """
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
        mock_response.choices = []
        mock_wrapped.return_value = mock_response
        
        # Mock instance (simulating AzureOpenAI's Completions resource)
        mock_instance = MagicMock()
        # AzureOpenAI-specific attributes
        mock_instance._client = MagicMock()
        mock_instance._client.azure_deployment = "gpt-4-deployment"
        mock_instance._client.api_version = "2024-02-01"
        
        # Call wrapper with typical Azure OpenAI messages
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello from Azure!"},
        ]
        
        result = _wrap_chat_completions_create(
            mock_wrapped,
            mock_instance,
            (),
            {"messages": messages}
        )
        
        # Verify inspector was called
        mock_inspector.inspect_conversation.assert_called()
        assert mock_wrapped.called

    @patch("aidefense.runtime.agentsec.patchers.openai._get_inspector")
    def test_azure_openai_enforce_mode_blocks(self, mock_get_inspector):
        """Test that enforce mode blocks policy violations for Azure OpenAI."""
        # Setup
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = Decision.block(
            reasons=["azure_policy_violation"]
        )
        mock_get_inspector.return_value = mock_inspector
        
        # Setup state in enforce mode
        _state.set_state(initialized=True, llm_rules=None, api_mode_fail_open_llm=True, api_mode_llm="on_enforce")
        clear_inspection_context()
        
        # Mock wrapped function
        mock_wrapped = MagicMock()
        mock_instance = MagicMock()
        
        messages = [{"role": "user", "content": "Test message"}]
        
        # Should raise SecurityPolicyError
        with pytest.raises(SecurityPolicyError) as exc_info:
            _wrap_chat_completions_create(
                mock_wrapped,
                mock_instance,
                (),
                {"messages": messages}
            )
        
        # Verify the decision contains Azure-specific reason
        assert "azure_policy_violation" in exc_info.value.decision.reasons

    @patch("aidefense.runtime.agentsec.patchers.openai._get_inspector")
    def test_azure_openai_streaming_works(self, mock_get_inspector):
        """Test that streaming inspection works for Azure OpenAI."""
        # Setup
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = Decision.allow(reasons=[])
        mock_get_inspector.return_value = mock_inspector
        
        # Setup state
        _state.set_state(initialized=True, llm_rules=None, api_mode_fail_open_llm=True, api_mode_llm="on_monitor")
        clear_inspection_context()
        
        # Mock streaming response
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta = MagicMock()
        chunk1.choices[0].delta.content = "Hello"
        
        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta = MagicMock()
        chunk2.choices[0].delta.content = " world!"
        
        mock_stream = iter([chunk1, chunk2])
        mock_wrapped = MagicMock(return_value=mock_stream)
        mock_instance = MagicMock()
        
        messages = [{"role": "user", "content": "Say hello"}]
        
        result = _wrap_chat_completions_create(
            mock_wrapped,
            mock_instance,
            (),
            {"messages": messages, "stream": True}
        )
        
        # Result should be a streaming wrapper
        assert hasattr(result, "__iter__")
        
        # Iterate through stream
        chunks = list(result)
        assert len(chunks) == 2

    @patch("aidefense.runtime.agentsec.patchers.openai._get_inspector")
    def test_azure_openai_monitor_mode_logs_only(self, mock_get_inspector):
        """Test that monitor mode logs but doesn't block for Azure OpenAI."""
        # Setup
        mock_inspector = MagicMock()
        # Return a block decision
        mock_inspector.inspect_conversation.return_value = Decision.block(
            reasons=["would_block_in_enforce"]
        )
        mock_get_inspector.return_value = mock_inspector
        
        # Setup state in MONITOR mode (not enforce)
        _state.set_state(initialized=True, llm_rules=None, api_mode_fail_open_llm=True, api_mode_llm="on_monitor")
        clear_inspection_context()
        
        # Mock wrapped function
        mock_wrapped = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = []
        mock_wrapped.return_value = mock_response
        
        mock_instance = MagicMock()
        messages = [{"role": "user", "content": "Test"}]
        
        # Should NOT raise in monitor mode, even with block decision
        result = _wrap_chat_completions_create(
            mock_wrapped,
            mock_instance,
            (),
            {"messages": messages}
        )
        
        # Verify the call went through
        assert mock_wrapped.called
        assert result is mock_response








