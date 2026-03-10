"""Tests for patcher error handling.

Tests that LLM patchers handle inspector errors gracefully, respect fail_open
settings, and that _state.reset() properly clears cached inspector singletons.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from aidefense.runtime.agentsec.decision import Decision
from aidefense.runtime.agentsec.exceptions import SecurityPolicyError


class TestOpenAIPatcherErrorHandling:
    """Test error handling in OpenAI patcher."""

    def test_inspector_error_with_fail_open_true_allows_call(self):
        """Test that inspector errors with fail_open=True allow the LLM call."""
        from aidefense.runtime.agentsec.patchers.openai import (
            _wrap_chat_completions_create,
            _get_inspector,
        )
        
        # Mock the inspector to raise an error
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.side_effect = Exception("API error")
        mock_inspector.fail_open = True
        
        # Mock the wrapped function
        mock_wrapped = MagicMock(return_value=MagicMock())
        
        # Mock context and state
        with patch("aidefense.runtime.agentsec.patchers.openai._get_inspector", return_value=mock_inspector):
            with patch("aidefense.runtime.agentsec.patchers.openai._should_inspect", return_value=True):
                with patch("aidefense.runtime.agentsec.patchers.openai.get_inspection_context") as mock_ctx:
                    mock_ctx.return_value.metadata = {}
                    with patch("aidefense.runtime.agentsec.patchers.openai._state") as mock_state:
                        mock_state.get_llm_mode.return_value = "monitor"
                        mock_state.get_api_llm_fail_open.return_value = True
                        
                        # Should not raise, should allow the call
                        result = _wrap_chat_completions_create(
                            mock_wrapped,
                            None,
                            [],
                            {"messages": [{"role": "user", "content": "test"}]},
                        )
        
        # The wrapped function should have been called
        mock_wrapped.assert_called_once()

    def test_streaming_wrapper_raises_on_inspection_error_fail_open_false(self):
        """Test StreamingInspectionWrapper raises SecurityPolicyError when fail_open=False."""
        from aidefense.runtime.agentsec.patchers.openai import StreamingInspectionWrapper

        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta.content = "Hello"

        def mock_stream():
            yield mock_chunk
            yield mock_chunk

        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.side_effect = Exception("API error")
        mock_inspector.fail_open = False

        with patch("aidefense.runtime.agentsec.patchers.openai._get_inspector", return_value=mock_inspector):
            with patch("aidefense.runtime.agentsec.patchers.openai._should_inspect", return_value=True):
                with patch("aidefense.runtime.agentsec.patchers.openai._state") as mock_state:
                    mock_state.get_api_llm_fail_open.return_value = False
                    wrapper = StreamingInspectionWrapper(
                        mock_stream(),
                        [{"role": "user", "content": "test"}],
                        {},
                    )

                    with pytest.raises(SecurityPolicyError):
                        list(wrapper)

    def test_streaming_wrapper_allows_on_inspection_error_fail_open_true(self):
        """Test StreamingInspectionWrapper allows through when fail_open=True."""
        from aidefense.runtime.agentsec.patchers.openai import StreamingInspectionWrapper

        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta.content = "Hello"

        def mock_stream():
            yield mock_chunk
            yield mock_chunk

        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.side_effect = Exception("API error")
        mock_inspector.fail_open = True

        with patch("aidefense.runtime.agentsec.patchers.openai._get_inspector", return_value=mock_inspector):
            with patch("aidefense.runtime.agentsec.patchers.openai._should_inspect", return_value=True):
                with patch("aidefense.runtime.agentsec.patchers.openai._state") as mock_state:
                    mock_state.get_api_llm_fail_open.return_value = True
                    wrapper = StreamingInspectionWrapper(
                        mock_stream(),
                        [{"role": "user", "content": "test"}],
                        {},
                    )

                    chunks = list(wrapper)
                    assert len(chunks) == 2


class TestInspectorResetOnReprotect:
    """AIFW-18900: Verify _state.reset() clears cached patcher inspectors."""

    def test_reset_clears_all_patcher_inspectors(self):
        """Each patcher's _inspector should be None after reset_all_patcher_inspectors()."""
        from aidefense.runtime.agentsec.patchers import (
            openai, bedrock, cohere, mistral, vertexai,
            google_genai, azure_ai_inference, litellm, mcp,
            reset_all_patcher_inspectors,
        )

        # Seed every patcher's singleton with a sentinel object
        sentinel = object()
        openai._inspector = sentinel
        bedrock._inspector = sentinel
        cohere._inspector = sentinel
        mistral._inspector = sentinel
        vertexai._inspector = sentinel
        google_genai._inspector = sentinel
        azure_ai_inference._inspector = sentinel
        litellm._inspector = sentinel
        mcp._api_inspector = sentinel
        mcp._gateway_pass_through_inspector = sentinel

        reset_all_patcher_inspectors()

        assert openai._inspector is None
        assert bedrock._inspector is None
        assert cohere._inspector is None
        assert mistral._inspector is None
        assert vertexai._inspector is None
        assert google_genai._inspector is None
        assert azure_ai_inference._inspector is None
        assert litellm._inspector is None
        assert mcp._api_inspector is None
        assert mcp._gateway_pass_through_inspector is None

    def test_state_reset_clears_patcher_inspectors(self):
        """_state.reset() should call reset_all_patcher_inspectors internally."""
        from aidefense.runtime.agentsec import _state
        from aidefense.runtime.agentsec.patchers import openai as openai_patcher

        # Seed OpenAI patcher with a sentinel
        sentinel = object()
        openai_patcher._inspector = sentinel
        assert openai_patcher._inspector is sentinel

        _state.reset()

        assert openai_patcher._inspector is None

    def test_get_inspector_picks_up_new_fail_open_after_reset(self):
        """After reset, _get_inspector() should create a new inspector with
        the current _state fail_open value, not the old cached one."""
        from aidefense.runtime.agentsec import _state
        from aidefense.runtime.agentsec.patchers import openai as openai_patcher
        from aidefense.runtime.agentsec.inspectors import LLMInspector

        # Simulate first protect() with fail_open=True
        _state.reset()
        with patch.object(_state, "get_api_llm_fail_open", return_value=True), \
             patch.object(_state, "get_llm_rules", return_value=None), \
             patch.object(_state, "is_initialized", return_value=True):
            inspector1 = openai_patcher._get_inspector()
            assert inspector1.fail_open is True

        # Simulate re-protect() with fail_open=False
        _state.reset()
        assert openai_patcher._inspector is None  # reset cleared it
        with patch.object(_state, "get_api_llm_fail_open", return_value=False), \
             patch.object(_state, "get_llm_rules", return_value=None), \
             patch.object(_state, "is_initialized", return_value=True):
            inspector2 = openai_patcher._get_inspector()
            assert inspector2.fail_open is False
            assert inspector2 is not inspector1


class TestApiKeyValueErrorClassification:
    """AIFW-18905: ValueError('Invalid API key format') should raise
    ConfigurationError, not SecurityPolicyError, when fail_open=False."""

    def test_llm_handle_error_api_key_raises_configuration_error(self):
        from aidefense.runtime.agentsec.inspectors.api_llm import LLMInspector
        from aidefense.runtime.agentsec.exceptions import ConfigurationError

        inspector = LLMInspector.__new__(LLMInspector)
        inspector.fail_open = False
        inspector.timeout_ms = None

        with pytest.raises(ConfigurationError, match="Invalid API key"):
            inspector._handle_error(ValueError("Invalid API key format"))

    def test_llm_handle_error_api_key_fail_open_allows(self):
        from aidefense.runtime.agentsec.inspectors.api_llm import LLMInspector

        inspector = LLMInspector.__new__(LLMInspector)
        inspector.fail_open = True
        inspector.timeout_ms = None

        decision = inspector._handle_error(ValueError("Invalid API key format"))
        assert decision.action == "allow"

    def test_mcp_handle_error_api_key_raises_configuration_error(self):
        from aidefense.runtime.agentsec.inspectors.api_mcp import MCPInspector
        from aidefense.runtime.agentsec.exceptions import ConfigurationError

        inspector = MCPInspector.__new__(MCPInspector)
        inspector.fail_open = False
        inspector.timeout_ms = None

        with pytest.raises(ConfigurationError, match="Invalid API key"):
            inspector._handle_error(ValueError("Invalid API key format"), tool_name="test_tool")

    def test_mcp_handle_error_api_key_fail_open_allows(self):
        from aidefense.runtime.agentsec.inspectors.api_mcp import MCPInspector

        inspector = MCPInspector.__new__(MCPInspector)
        inspector.fail_open = True
        inspector.timeout_ms = None

        decision = inspector._handle_error(ValueError("Invalid API key format"), tool_name="test_tool")
        assert decision.action == "allow"


