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
            
            protect(api_mode={"llm": {"mode": "monitor"}})
            
            patched = get_patched_clients()
            assert "vertexai" in patched

    @patch("aidefense.runtime.agentsec.patchers.vertexai.safe_import", return_value=None)
    def test_vertexai_not_patched_when_library_missing(self, mock_safe_import):
        """Test that vertexai is not in patched clients when library not installed."""
        with patch("aidefense.runtime.agentsec.patchers.openai.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.bedrock.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.mcp.safe_import", return_value=None):
            
            protect(api_mode={"llm": {"mode": "monitor"}})
            
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
            
            protect(api_mode={"llm": {"mode": "monitor"}})
            
            patched = get_patched_clients()
            assert "bedrock" in patched

    @patch("aidefense.runtime.agentsec.patchers.bedrock.safe_import", return_value=None)
    def test_bedrock_not_patched_when_library_missing(self, mock_safe_import):
        """Test that bedrock is not in patched clients when library not installed."""
        with patch("aidefense.runtime.agentsec.patchers.openai.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.vertexai.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.mcp.safe_import", return_value=None):
            
            protect(api_mode={"llm": {"mode": "monitor"}})
            
            patched = get_patched_clients()
            assert "bedrock" not in patched


class TestCohereIntegration:
    """Test Cohere integration with protect()."""

    @patch("aidefense.runtime.agentsec.patchers.cohere.safe_import")
    @patch("aidefense.runtime.agentsec.patchers.cohere.wrapt")
    def test_cohere_patched_when_library_installed(self, mock_wrapt, mock_safe_import):
        """Test that cohere appears in patched clients when library is installed."""
        mock_module = MagicMock()
        mock_safe_import.return_value = mock_module

        with patch("aidefense.runtime.agentsec.patchers.openai.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.bedrock.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.vertexai.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.mcp.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.google_genai.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.mistral.safe_import", return_value=None):

            protect(api_mode={"llm": {"mode": "monitor"}})

            patched = get_patched_clients()
            assert "cohere" in patched

    @patch("aidefense.runtime.agentsec.patchers.cohere.safe_import", return_value=None)
    def test_cohere_not_patched_when_library_missing(self, mock_safe_import):
        """Test that cohere is not in patched clients when library not installed."""
        with patch("aidefense.runtime.agentsec.patchers.openai.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.bedrock.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.vertexai.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.mcp.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.google_genai.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.mistral.safe_import", return_value=None):

            protect(api_mode={"llm": {"mode": "monitor"}})

            patched = get_patched_clients()
            assert "cohere" not in patched


class TestMistralIntegration:
    """Test Mistral integration with protect()."""

    @patch("aidefense.runtime.agentsec.patchers.mistral.safe_import")
    @patch("aidefense.runtime.agentsec.patchers.mistral.wrapt")
    def test_mistral_patched_when_library_installed(self, mock_wrapt, mock_safe_import):
        """Test that mistral appears in patched clients when library is installed."""
        mock_module = MagicMock()
        mock_safe_import.return_value = mock_module

        with patch("aidefense.runtime.agentsec.patchers.openai.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.bedrock.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.vertexai.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.mcp.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.google_genai.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.cohere.safe_import", return_value=None):

            protect(api_mode={"llm": {"mode": "monitor"}})

            patched = get_patched_clients()
            assert "mistral" in patched

    @patch("aidefense.runtime.agentsec.patchers.mistral.safe_import", return_value=None)
    def test_mistral_not_patched_when_library_missing(self, mock_safe_import):
        """Test that mistral is not in patched clients when library not installed."""
        with patch("aidefense.runtime.agentsec.patchers.openai.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.bedrock.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.vertexai.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.mcp.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.google_genai.safe_import", return_value=None), \
             patch("aidefense.runtime.agentsec.patchers.cohere.safe_import", return_value=None):

            protect(api_mode={"llm": {"mode": "monitor"}})

            patched = get_patched_clients()
            assert "mistral" not in patched
