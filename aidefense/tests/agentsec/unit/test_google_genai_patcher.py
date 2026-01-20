"""
Unit tests for the google-genai SDK patcher.

Tests the patching of the google-genai library (from google import genai)
for AI Defense inspection of LLM calls.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
import sys


class TestGoogleGenAINormalization:
    """Test message normalization for google-genai SDK formats."""
    
    def test_normalize_string_contents(self):
        """Test normalizing a simple string input."""
        from aidefense.runtime.agentsec.patchers.google_genai import _normalize_genai_contents
        
        result = _normalize_genai_contents("Hello, how are you?")
        
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello, how are you?"
    
    def test_normalize_none_contents(self):
        """Test normalizing None input."""
        from aidefense.runtime.agentsec.patchers.google_genai import _normalize_genai_contents
        
        result = _normalize_genai_contents(None)
        
        assert result == []
    
    def test_normalize_dict_contents(self):
        """Test normalizing dict format contents."""
        from aidefense.runtime.agentsec.patchers.google_genai import _normalize_genai_contents
        
        contents = [
            {"role": "user", "parts": [{"text": "Hello"}]},
            {"role": "model", "parts": [{"text": "Hi there!"}]},
        ]
        
        result = _normalize_genai_contents(contents)
        
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello"
        assert result[1]["role"] == "assistant"  # model -> assistant
        assert result[1]["content"] == "Hi there!"
    
    def test_normalize_content_objects(self):
        """Test normalizing Content objects with role and parts attributes."""
        from aidefense.runtime.agentsec.patchers.google_genai import _normalize_genai_contents
        
        # Create mock Content objects
        part1 = MagicMock()
        part1.text = "What is AI?"
        
        content1 = MagicMock()
        content1.role = "user"
        content1.parts = [part1]
        
        part2 = MagicMock()
        part2.text = "AI stands for Artificial Intelligence."
        
        content2 = MagicMock()
        content2.role = "model"
        content2.parts = [part2]
        
        result = _normalize_genai_contents([content1, content2])
        
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "What is AI?"
        assert result[1]["role"] == "assistant"
        assert result[1]["content"] == "AI stands for Artificial Intelligence."


class TestGoogleGenAIResponseExtraction:
    """Test response text extraction from google-genai responses."""
    
    def test_extract_response_with_text_property(self):
        """Test extracting from response with text property."""
        from aidefense.runtime.agentsec.patchers.google_genai import _extract_genai_response
        
        response = MagicMock()
        response.text = "Hello, I'm an AI assistant."
        
        result = _extract_genai_response(response)
        
        assert result == "Hello, I'm an AI assistant."
    
    def test_extract_response_with_candidates(self):
        """Test extracting from response with candidates structure."""
        from aidefense.runtime.agentsec.patchers.google_genai import _extract_genai_response
        
        # Create mock response with candidates
        part = MagicMock()
        part.text = "Response from candidates"
        
        content = MagicMock()
        content.parts = [part]
        
        candidate = MagicMock()
        candidate.content = content
        
        response = MagicMock()
        response.text = None  # text property returns None
        response.candidates = [candidate]
        
        result = _extract_genai_response(response)
        
        assert result == "Response from candidates"
    
    def test_extract_response_none(self):
        """Test extracting from None response."""
        from aidefense.runtime.agentsec.patchers.google_genai import _extract_genai_response
        
        result = _extract_genai_response(None)
        
        assert result == ""
    
    def test_extract_response_empty_candidates(self):
        """Test extracting from response with empty candidates."""
        from aidefense.runtime.agentsec.patchers.google_genai import _extract_genai_response
        
        response = MagicMock()
        response.text = None
        response.candidates = []
        
        result = _extract_genai_response(response)
        
        assert result == ""


class TestModelNameExtraction:
    """Test model name extraction from various inputs."""
    
    def test_extract_string_model(self):
        """Test extracting model name from string."""
        from aidefense.runtime.agentsec.patchers.google_genai import _extract_model_name
        
        result = _extract_model_name("gemini-2.0-flash")
        
        assert result == "gemini-2.0-flash"
    
    def test_extract_none_model(self):
        """Test extracting model name from None."""
        from aidefense.runtime.agentsec.patchers.google_genai import _extract_model_name
        
        result = _extract_model_name(None)
        
        assert result == "unknown"
    
    def test_extract_model_with_name_attribute(self):
        """Test extracting model name from object with name attribute."""
        from aidefense.runtime.agentsec.patchers.google_genai import _extract_model_name
        
        model = MagicMock()
        model.name = "gemini-1.5-pro"
        
        result = _extract_model_name(model)
        
        assert result == "gemini-1.5-pro"


class TestResponseWrapper:
    """Test the response wrapper classes."""
    
    def test_response_wrapper_text_property(self):
        """Test response wrapper text property."""
        from aidefense.runtime.agentsec.patchers.google_genai import _GoogleGenAIResponseWrapper
        
        response_data = {
            "candidates": [{
                "content": {
                    "role": "model",
                    "parts": [{"text": "Hello!"}]
                },
                "finishReason": "STOP"
            }]
        }
        
        wrapper = _GoogleGenAIResponseWrapper(response_data)
        
        assert wrapper.text == "Hello!"
    
    def test_response_wrapper_candidates(self):
        """Test response wrapper candidates property."""
        from aidefense.runtime.agentsec.patchers.google_genai import _GoogleGenAIResponseWrapper
        
        response_data = {
            "candidates": [{
                "content": {
                    "role": "model",
                    "parts": [{"text": "Response 1"}]
                }
            }, {
                "content": {
                    "role": "model",
                    "parts": [{"text": "Response 2"}]
                }
            }]
        }
        
        wrapper = _GoogleGenAIResponseWrapper(response_data)
        
        assert len(wrapper.candidates) == 2
        assert wrapper.candidates[0].content.parts[0].text == "Response 1"
        assert wrapper.candidates[1].content.parts[0].text == "Response 2"
    
    def test_response_wrapper_to_dict(self):
        """Test response wrapper to_dict method."""
        from aidefense.runtime.agentsec.patchers.google_genai import _GoogleGenAIResponseWrapper
        
        response_data = {"candidates": [], "test": "value"}
        wrapper = _GoogleGenAIResponseWrapper(response_data)
        
        assert wrapper.to_dict() == response_data


class TestPatcherInfrastructure:
    """Test the patcher infrastructure functions."""
    
    def test_should_inspect_off_mode(self):
        """Test _should_inspect returns False when mode is off."""
        from aidefense.runtime.agentsec.patchers.google_genai import _should_inspect
        from aidefense.runtime.agentsec import _state
        from aidefense.runtime.agentsec.patchers import reset_registry
        
        # Reset state
        reset_registry()
        _state._initialized = False
        
        # Initialize with off mode
        _state.set_state(
            initialized=True,
            api_mode_llm="off",
            api_mode_mcp="off",
            llm_integration_mode="api",
            mcp_integration_mode="api",
        )
        
        result = _should_inspect()
        
        assert result is False
        
        # Cleanup
        _state._initialized = False
        reset_registry()
    
    def test_should_inspect_monitor_mode(self):
        """Test _should_inspect returns True when mode is on_monitor."""
        from aidefense.runtime.agentsec.patchers.google_genai import _should_inspect
        from aidefense.runtime.agentsec import _state
        from aidefense.runtime.agentsec.patchers import reset_registry
        
        # Reset state
        reset_registry()
        _state._initialized = False
        
        # Initialize with monitor mode
        _state.set_state(
            initialized=True,
            api_mode_llm="on_monitor",
            api_mode_mcp="on_monitor",
            llm_integration_mode="api",
            mcp_integration_mode="api",
        )
        
        result = _should_inspect()
        
        assert result is True
        
        # Cleanup
        _state._initialized = False
        reset_registry()


class TestPatchFunction:
    """Test the main patch_google_genai function."""
    
    def test_patch_returns_false_when_module_not_installed(self):
        """Test that patch_google_genai returns False when google-genai is not installed."""
        from aidefense.runtime.agentsec.patchers.google_genai import patch_google_genai
        from aidefense.runtime.agentsec.patchers import reset_registry
        
        reset_registry()
        
        # If google-genai is not installed, should return False
        # The function uses safe_import which returns None if not installed
        with patch('aidefense.runtime.agentsec.patchers.google_genai.safe_import', return_value=None):
            result = patch_google_genai()
        
        assert result is False
        
        reset_registry()
    
    def test_patch_is_idempotent(self):
        """Test that patching twice doesn't fail."""
        from aidefense.runtime.agentsec.patchers.google_genai import patch_google_genai
        from aidefense.runtime.agentsec.patchers import reset_registry, mark_patched, is_patched
        
        reset_registry()
        
        # Mark as already patched
        mark_patched("google_genai")
        
        # Should return True immediately without trying to patch again
        result = patch_google_genai()
        
        assert result is True
        assert is_patched("google_genai")
        
        reset_registry()


class TestStreamingWrapper:
    """Test the streaming response wrappers."""
    
    def test_streaming_wrapper_collects_text(self):
        """Test that streaming wrapper collects text from chunks."""
        from aidefense.runtime.agentsec.patchers.google_genai import GoogleGenAIStreamingWrapper
        
        # Create mock chunks
        chunk1 = MagicMock()
        chunk1.text = "Hello"
        
        chunk2 = MagicMock()
        chunk2.text = " World"
        
        chunks = iter([chunk1, chunk2])
        
        wrapper = GoogleGenAIStreamingWrapper(
            original_iterator=chunks,
            normalized_messages=[{"role": "user", "content": "Hi"}],
            metadata={"provider": "google_genai"}
        )
        
        collected = []
        for chunk in wrapper:
            collected.append(chunk)
        
        # Should have collected both chunks
        assert len(collected) == 2
        # Text should have been collected
        assert wrapper._collected_text == ["Hello", " World"]
    
    def test_async_streaming_wrapper_exists(self):
        """Test that async streaming wrapper class exists."""
        from aidefense.runtime.agentsec.patchers.google_genai import AsyncGoogleGenAIStreamingWrapper
        
        # Just verify the class exists and can be instantiated
        wrapper = AsyncGoogleGenAIStreamingWrapper(
            original_iterator=MagicMock(),
            normalized_messages=[],
            metadata={}
        )
        
        assert wrapper is not None
        assert hasattr(wrapper, '__aiter__')
        assert hasattr(wrapper, '__anext__')


class TestIntegrationWithAgentsec:
    """Test integration with the main agentsec module."""
    
    def test_google_genai_in_patchers_all(self):
        """Test that patch_google_genai is exported from patchers."""
        from aidefense.runtime.agentsec.patchers import patch_google_genai, __all__
        
        assert "patch_google_genai" in __all__
        assert callable(patch_google_genai)
    
    def test_google_genai_provider_in_protect(self):
        """Test that google_genai is a valid provider in protect()."""
        from aidefense.runtime import agentsec
        from aidefense.runtime.agentsec import _state
        from aidefense.runtime.agentsec.patchers import reset_registry
        
        # Reset
        _state._initialized = False
        reset_registry()
        
        # Should not raise when configuring google_genai provider
        agentsec.protect(
            api_mode_llm="off",
            api_mode_mcp="off",
            providers={
                "google_genai": {
                    "gateway_url": "https://test-gateway.example.com",
                    "gateway_api_key": "test-key",
                }
            },
            auto_dotenv=False,
        )
        
        # Verify state was set
        assert _state.is_initialized()
        
        # Cleanup
        _state._initialized = False
        reset_registry()
