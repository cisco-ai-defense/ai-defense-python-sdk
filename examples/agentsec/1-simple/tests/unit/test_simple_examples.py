#!/usr/bin/env python3
"""
Unit tests for simple examples.

Tests syntax, imports, and correct patterns in each simple example.
"""

import ast
import importlib.util
import os
import sys
from pathlib import Path

import pytest

# Get the simple examples directory
SIMPLE_DIR = Path(__file__).parent.parent.parent
EXAMPLES = [
    "basic_protection",
    "openai_example",
    "streaming_example",
    "mcp_example",
    "simple_strands_bedrock",
    "gateway_mode_example",
    "skip_inspection_example",
]


class TestExamplesSyntax:
    """Test that all examples have valid Python syntax."""

    @pytest.mark.parametrize("example_name", EXAMPLES)
    def test_valid_python_syntax(self, example_name: str):
        """Test that example is syntactically valid Python."""
        example_path = SIMPLE_DIR / f"{example_name}.py"
        assert example_path.exists(), f"{example_name}.py not found"
        
        source = example_path.read_text()
        
        try:
            ast.parse(source)
        except SyntaxError as e:
            pytest.fail(f"Syntax error in {example_name}.py: {e}")

    @pytest.mark.parametrize("example_name", EXAMPLES)
    def test_has_main_function(self, example_name: str):
        """Test that each example has a main() function."""
        example_path = SIMPLE_DIR / f"{example_name}.py"
        source = example_path.read_text()
        
        assert "def main(" in source, f"{example_name}.py should have a main() function"

    @pytest.mark.parametrize("example_name", EXAMPLES)
    def test_has_main_guard(self, example_name: str):
        """Test that each example has if __name__ == '__main__' guard."""
        example_path = SIMPLE_DIR / f"{example_name}.py"
        source = example_path.read_text()
        
        assert 'if __name__ == "__main__"' in source or "if __name__ == '__main__'" in source, \
            f"{example_name}.py should have __main__ guard"


class TestAgentsecIntegration:
    """Test that all examples properly integrate with agentsec."""

    @pytest.mark.parametrize("example_name", EXAMPLES)
    def test_imports_agentsec(self, example_name: str):
        """Test that each example imports agentsec."""
        example_path = SIMPLE_DIR / f"{example_name}.py"
        source = example_path.read_text()
        
        assert "import agentsec" in source, f"{example_name}.py should import agentsec"

    @pytest.mark.parametrize("example_name", EXAMPLES)
    def test_calls_protect(self, example_name: str):
        """Test that each example calls agentsec.protect()."""
        example_path = SIMPLE_DIR / f"{example_name}.py"
        source = example_path.read_text()
        
        assert "agentsec.protect(" in source, f"{example_name}.py should call agentsec.protect()"

    def test_basic_protection_uses_llm_mode(self):
        """Test basic_protection.py uses llm_mode parameter."""
        source = (SIMPLE_DIR / "basic_protection.py").read_text()
        assert "api_mode_llm=" in source

    def test_openai_example_imports_after_protect(self):
        """Test openai_example.py imports OpenAI after protect()."""
        source = (SIMPLE_DIR / "openai_example.py").read_text()
        
        protect_pos = source.find("agentsec.protect(")
        openai_import_pos = source.find("from openai import")
        
        assert protect_pos != -1, "Should call agentsec.protect()"
        assert openai_import_pos != -1, "Should import OpenAI"
        assert protect_pos < openai_import_pos, \
            "agentsec.protect() must be called BEFORE importing OpenAI"

    def test_streaming_example_uses_stream_true(self):
        """Test streaming_example.py demonstrates stream=True."""
        source = (SIMPLE_DIR / "streaming_example.py").read_text()
        assert "stream=True" in source, "Should demonstrate stream=True parameter"

    def test_mcp_example_uses_mcp_mode(self):
        """Test mcp_example.py uses mcp_mode parameter."""
        source = (SIMPLE_DIR / "mcp_example.py").read_text()
        assert "api_mode_mcp=" in source, "Should use api_mode_mcp parameter"

    def test_mcp_example_uses_call_tool(self):
        """Test mcp_example.py demonstrates call_tool."""
        source = (SIMPLE_DIR / "mcp_example.py").read_text()
        assert "call_tool(" in source, "Should demonstrate session.call_tool()"


class TestDocstrings:
    """Test that all examples have proper documentation."""

    @pytest.mark.parametrize("example_name", EXAMPLES)
    def test_has_module_docstring(self, example_name: str):
        """Test that each example has a module docstring."""
        example_path = SIMPLE_DIR / f"{example_name}.py"
        source = example_path.read_text()
        
        # Module docstring should be at the top (after shebang if present)
        tree = ast.parse(source)
        docstring = ast.get_docstring(tree)
        
        assert docstring is not None, f"{example_name}.py should have a module docstring"
        assert len(docstring) > 50, f"{example_name}.py docstring should be descriptive"

    @pytest.mark.parametrize("example_name", EXAMPLES)
    def test_docstring_mentions_usage(self, example_name: str):
        """Test that docstring includes usage instructions."""
        example_path = SIMPLE_DIR / f"{example_name}.py"
        source = example_path.read_text()
        
        tree = ast.parse(source)
        docstring = ast.get_docstring(tree)
        
        assert "Usage:" in docstring or "usage" in docstring.lower(), \
            f"{example_name}.py docstring should include usage instructions"


class TestErrorHandling:
    """Test that examples handle errors gracefully."""

    def test_openai_example_handles_missing_key(self):
        """Test openai_example.py handles missing API key."""
        source = (SIMPLE_DIR / "openai_example.py").read_text()
        
        # Should check for missing key and handle gracefully
        assert "OPENAI_API_KEY" in source
        assert "not set" in source.lower() or "placeholder" in source.lower()

    def test_streaming_example_handles_missing_key(self):
        """Test streaming_example.py handles missing API key."""
        source = (SIMPLE_DIR / "streaming_example.py").read_text()
        
        assert "OPENAI_API_KEY" in source
        assert "not set" in source.lower()

    def test_mcp_example_handles_errors(self):
        """Test mcp_example.py handles errors gracefully."""
        source = (SIMPLE_DIR / "mcp_example.py").read_text()
        
        # The example catches general exceptions and provides helpful error messages
        assert "except Exception" in source, "Should handle exceptions"
        assert "Error:" in source, "Should print error messages"

    def test_mcp_example_handles_connection_error(self):
        """Test mcp_example.py handles connection errors."""
        source = (SIMPLE_DIR / "mcp_example.py").read_text()
        
        assert "except Exception" in source or "Error:" in source, \
            "Should handle connection errors"


class TestGatewayModeExample:
    """Tests specific to gateway_mode_example.py."""

    def test_shows_api_mode_config(self):
        """Test gateway_mode_example.py shows API mode configuration."""
        source = (SIMPLE_DIR / "gateway_mode_example.py").read_text()
        assert "API MODE" in source, "Should explain API mode"
        assert "api_mode_llm" in source, "Should show api_mode_llm parameter"

    def test_shows_gateway_mode_config(self):
        """Test gateway_mode_example.py shows Gateway mode configuration."""
        source = (SIMPLE_DIR / "gateway_mode_example.py").read_text()
        assert "GATEWAY MODE" in source, "Should explain Gateway mode"
        assert "llm_integration_mode" in source, "Should show llm_integration_mode parameter"
        assert "providers" in source, "Should show providers parameter"

    def test_shows_env_vars(self):
        """Test gateway_mode_example.py shows environment variables."""
        source = (SIMPLE_DIR / "gateway_mode_example.py").read_text()
        assert "AI_DEFENSE_API_MODE_LLM_ENDPOINT" in source
        assert "AGENTSEC_OPENAI_GATEWAY_URL" in source
        assert "AGENTSEC_LLM_INTEGRATION_MODE" in source

    def test_has_example_functions(self):
        """Test gateway_mode_example.py has example functions."""
        source = (SIMPLE_DIR / "gateway_mode_example.py").read_text()
        assert "def example_api_mode_programmatic" in source
        assert "def example_openai_gateway_programmatic" in source
        assert "def example_mcp_gateway_programmatic" in source


class TestSkipInspectionExample:
    """Tests specific to skip_inspection_example.py."""

    def test_imports_skip_inspection(self):
        """Test skip_inspection_example.py imports skip_inspection."""
        source = (SIMPLE_DIR / "skip_inspection_example.py").read_text()
        assert "from aidefense.runtime.agentsec import skip_inspection" in source or \
               "skip_inspection" in source, \
            "Should import skip_inspection context manager"

    def test_imports_no_inspection(self):
        """Test skip_inspection_example.py imports no_inspection."""
        source = (SIMPLE_DIR / "skip_inspection_example.py").read_text()
        assert "from aidefense.runtime.agentsec import" in source and "no_inspection" in source, \
            "Should import no_inspection decorator"

    def test_uses_context_manager(self):
        """Test skip_inspection_example.py uses skip_inspection as context manager."""
        source = (SIMPLE_DIR / "skip_inspection_example.py").read_text()
        assert "with skip_inspection(" in source, \
            "Should demonstrate skip_inspection context manager"

    def test_uses_decorator(self):
        """Test skip_inspection_example.py uses @no_inspection decorator."""
        source = (SIMPLE_DIR / "skip_inspection_example.py").read_text()
        assert "@no_inspection" in source, \
            "Should demonstrate @no_inspection decorator"

    def test_shows_granular_control(self):
        """Test skip_inspection_example.py shows granular skip control."""
        source = (SIMPLE_DIR / "skip_inspection_example.py").read_text()
        # The example uses llm= and mcp= parameters for granular control
        assert "llm=True" in source or "mcp=True" in source or \
               "llm=False" in source or "mcp=False" in source, \
            "Should demonstrate granular skip control with llm=/mcp= parameters"

    def test_shows_async_example(self):
        """Test skip_inspection_example.py includes async examples."""
        source = (SIMPLE_DIR / "skip_inspection_example.py").read_text()
        assert "async def" in source or "Async" in source, \
            "Should include async examples"


class TestStrandsBedrock:
    """Tests specific to simple_strands_bedrock.py."""

    def test_imports_strands(self):
        """Test simple_strands_bedrock.py imports strands."""
        source = (SIMPLE_DIR / "simple_strands_bedrock.py").read_text()
        assert "from strands import" in source or "import strands" in source

    def test_uses_bedrock_model(self):
        """Test simple_strands_bedrock.py uses BedrockModel."""
        source = (SIMPLE_DIR / "simple_strands_bedrock.py").read_text()
        assert "BedrockModel" in source

    def test_loads_env_file(self):
        """Test simple_strands_bedrock.py loads .env file."""
        source = (SIMPLE_DIR / "simple_strands_bedrock.py").read_text()
        assert "load_dotenv" in source
        assert ".env" in source

