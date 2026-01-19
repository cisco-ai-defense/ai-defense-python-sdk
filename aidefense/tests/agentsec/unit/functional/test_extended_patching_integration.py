"""Integration tests for extended client autopatching."""

import pytest
from unittest.mock import patch, MagicMock

from aidefense.runtime.agentsec import protect, get_patched_clients, _state
from aidefense.runtime.agentsec.patchers import reset_registry


@pytest.fixture(autouse=True)
def reset_state():
    """Reset agentsec state before each test."""
    _state.reset()
    reset_registry()
    yield
    _state.reset()
    reset_registry()


class TestVertexAIIntegration:
    """Test VertexAI integration with protect()."""

    @patch("aidefense.runtime.agentsec.patchers.vertexai.safe_import")
    @patch("aidefense.runtime.agentsec.patchers.vertexai.wrapt")
    def test_vertexai_patched_when_library_installed(self, mock_wrapt, mock_safe_import):
        """Test that vertexai appears in patched clients when library is installed."""
        # Mock the library as installed
        mock_module = MagicMock()
        mock_safe_import.return_value = mock_module
        
        # Mock other libraries as not installed to simplify
        with patch("aidefense.runtime.agentsec.patchers.openai.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.bedrock.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.mcp.safe_import", return_value=None):
            
            protect(api_mode_llm="on_monitor")
            
            patched = get_patched_clients()
            assert "vertexai" in patched

    @patch("aidefense.runtime.agentsec.patchers.vertexai.safe_import", return_value=None)
    def test_vertexai_not_patched_when_library_missing(self, mock_safe_import):
        """Test that vertexai is not in patched clients when library not installed."""
        with patch("aidefense.runtime.agentsec.patchers.openai.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.bedrock.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.mcp.safe_import", return_value=None):
            
            protect(api_mode_llm="on_monitor")
            
            patched = get_patched_clients()
            assert "vertexai" not in patched


class TestBedrockIntegration:
    """Test Bedrock integration with protect()."""

    @patch("aidefense.runtime.agentsec.patchers.bedrock.safe_import")
    @patch("aidefense.runtime.agentsec.patchers.bedrock.wrapt")
    def test_bedrock_patched_when_library_installed(self, mock_wrapt, mock_safe_import):
        """Test that bedrock appears in patched clients when library is installed."""
        # Mock the library as installed
        mock_module = MagicMock()
        mock_safe_import.return_value = mock_module
        
        # Mock other libraries as not installed to simplify
        with patch("aidefense.runtime.agentsec.patchers.openai.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.vertexai.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.mcp.safe_import", return_value=None):
            
            protect(api_mode_llm="on_monitor")
            
            patched = get_patched_clients()
            assert "bedrock" in patched

    @patch("aidefense.runtime.agentsec.patchers.bedrock.safe_import", return_value=None)
    def test_bedrock_not_patched_when_library_missing(self, mock_safe_import):
        """Test that bedrock is not in patched clients when library not installed."""
        with patch("aidefense.runtime.agentsec.patchers.openai.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.vertexai.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.mcp.safe_import", return_value=None):
            
            protect(api_mode_llm="on_monitor")
            
            patched = get_patched_clients()
            assert "bedrock" not in patched
