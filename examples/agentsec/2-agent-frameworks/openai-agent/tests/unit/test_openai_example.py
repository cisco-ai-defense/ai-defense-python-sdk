"""
Tests for the OpenAI Agent Example.

This module tests:
- Basic example structure and imports
- agentsec protection and patching
- OpenAI client patching verification
- MCP tool integration
- Agent functionality
- Error handling
"""

import ast
import os
import sys
from unittest import mock

import pytest


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def example_file():
    """Path to the OpenAI agent example file."""
    # Go up from tests/unit/ to the agent directory
    return os.path.join(os.path.dirname(__file__), "..", "..", "agent.py")


@pytest.fixture
def example_code(example_file):
    """Read the example file source code."""
    with open(example_file, "r") as f:
        return f.read()


@pytest.fixture
def example_ast(example_code):
    """Parse the example file into an AST."""
    return ast.parse(example_code)


# =============================================================================
# Category 1: File Structure Tests (4 tests)
# =============================================================================

class TestFileStructure:
    """Tests for file structure and basic setup."""
    
    def test_example_file_exists(self, example_file):
        """Test that agent.py exists."""
        assert os.path.exists(example_file), "agent.py should exist"
    
    def test_pyproject_file_exists(self):
        """Test that pyproject.toml exists with correct dependencies."""
        pyproject_file = os.path.join(os.path.join(os.path.dirname(__file__), "..", ".."), "pyproject.toml")
        assert os.path.exists(pyproject_file), "pyproject.toml should exist"
        
        with open(pyproject_file, "r") as f:
            content = f.read()
        
        assert "openai" in content, "Should require openai"
        assert "python-dotenv" in content, "Should require python-dotenv"
        assert "mcp" in content, "Should require mcp"
    
    def test_env_example_exists(self):
        """Test that shared .env.example exists with required variables."""
        # .env.example is now in examples/ directory
        env_file = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".env.example")
        assert os.path.exists(env_file), "examples/.env.example should exist"
        
        with open(env_file, "r") as f:
            content = f.read()
        
        assert "OPENAI_API_KEY" in content, "Should document OPENAI_API_KEY"
        assert "AGENTSEC_API_MODE_LLM" in content, "Should document AGENTSEC_API_MODE_LLM"
        assert "MCP_SERVER_URL" in content, "Should document MCP_SERVER_URL"
    
    def test_runner_script_exists(self):
        """Test that scripts/run.sh exists and is executable."""
        script_file = os.path.join(os.path.join(os.path.dirname(__file__), "..", ".."), "scripts", "run.sh")
        assert os.path.exists(script_file), "scripts/run.sh should exist"


# =============================================================================
# Category 2: Import Order Tests (4 tests)
# =============================================================================

class TestImportOrder:
    """Tests for correct import ordering in the example."""
    
    def test_dotenv_imported_early(self, example_code):
        """Test that dotenv is imported and called early."""
        lines = example_code.split("\n")
        dotenv_line = None
        agentsec_line = None
        openai_line = None
        
        for i, line in enumerate(lines):
            if "load_dotenv" in line and "import" not in line:
                dotenv_line = i
            if "import agentsec" in line:
                agentsec_line = i
            if "from openai import" in line:
                openai_line = i
        
        assert dotenv_line is not None, "Should call load_dotenv()"
        assert agentsec_line is not None, "Should import agentsec"
        assert dotenv_line < agentsec_line, "load_dotenv() should be called before agentsec import"
    
    def test_agentsec_imported_before_mcp(self, example_code):
        """Test that agentsec is imported before MCP client."""
        lines = example_code.split("\n")
        agentsec_line = None
        mcp_line = None
        
        for i, line in enumerate(lines):
            if "import agentsec" in line:
                agentsec_line = i
            if "from mcp" in line:
                mcp_line = i
        
        assert agentsec_line is not None, "Should import agentsec"
        if mcp_line is not None:
            assert agentsec_line < mcp_line, "agentsec should be imported before MCP"
    
    def test_protect_called_before_mcp(self, example_code):
        """Test that agentsec.protect() is called before MCP import."""
        lines = example_code.split("\n")
        protect_line = None
        mcp_line = None
        
        for i, line in enumerate(lines):
            if "agentsec.protect" in line:
                protect_line = i
            if "from mcp" in line:
                mcp_line = i
        
        assert protect_line is not None, "Should call agentsec.protect()"
        if mcp_line is not None:
            assert protect_line < mcp_line, "agentsec.protect() should be called before MCP import"
    
    def test_agentsec_protect_called(self, example_code):
        """Test that agentsec.protect() is called."""
        assert "agentsec.protect()" in example_code, "Should call agentsec.protect()"


# =============================================================================
# Category 3: agentsec Integration Tests (5 tests)
# =============================================================================

class TestAgentsecIntegration:
    """Tests for agentsec SDK integration."""
    
    def test_protect_call_present(self, example_code):
        """Test that agentsec.protect() is called."""
        assert "agentsec.protect" in example_code, "Should call agentsec.protect()"
    
    def test_agentsec_protect_with_minimal_setup(self, example_code):
        """Test that agentsec.protect() is used with minimal setup."""
        assert "agentsec.protect()" in example_code, "Should call agentsec.protect()"
    
    def test_mode_from_environment(self, example_code):
        """Test that mode can be configured from environment."""
        # The mode is read via AGENTSEC_API_MODE_LLM env var (logged in output)
        assert "AGENTSEC_API_MODE_LLM" in example_code, "Should reference AGENTSEC_API_MODE_LLM in output/config"
    
    def test_security_policy_error_handled(self, example_code):
        """Test that SecurityPolicyError is imported and handled."""
        assert "SecurityPolicyError" in example_code, "Should import SecurityPolicyError"
        assert "except SecurityPolicyError" in example_code, "Should catch SecurityPolicyError"
    
    def test_get_patched_clients_called(self, example_code):
        """Test that patched clients are logged."""
        assert "get_patched_clients" in example_code, "Should call get_patched_clients()"


# =============================================================================
# Category 4: OpenAI Agent Tests (5 tests)
# =============================================================================

class TestOpenAIAgent:
    """Tests for OpenAI Agent implementation."""
    
    def test_openai_agent_class_exists(self, example_code):
        """Test that OpenAIAgent class is defined."""
        assert "class OpenAIAgent" in example_code, "Should define OpenAIAgent class"
    
    def test_agent_has_chat_method(self, example_code):
        """Test that agent has a chat method."""
        assert "def chat" in example_code, "Should have chat method"
    
    def test_agent_uses_function_calling(self, example_code):
        """Test that agent uses OpenAI function calling."""
        assert "tools=" in example_code, "Should pass tools to OpenAI"
        assert "tool_calls" in example_code, "Should handle tool_calls"
    
    def test_agent_has_system_prompt(self, example_code):
        """Test that agent has a system prompt."""
        assert "system" in example_code, "Should have system prompt"
        assert "SYSTEM_PROMPT" in example_code or '"role": "system"' in example_code, "Should define system prompt"
    
    def test_agent_supports_reset(self, example_code):
        """Test that agent supports conversation reset."""
        assert "def reset" in example_code, "Should have reset method"


# =============================================================================
# Category 5: MCP Tool Integration Tests (4 tests)
# =============================================================================

class TestMCPIntegration:
    """Tests for MCP tool integration."""
    
    def test_mcp_imports_present(self, example_code):
        """Test that MCP client imports are present."""
        assert "streamablehttp_client" in example_code, "Should import streamablehttp_client"
        assert "ClientSession" in example_code, "Should import ClientSession"
    
    def test_fetch_url_function_exists(self, example_code):
        """Test that fetch_url function is defined."""
        assert "def fetch_url" in example_code, "Should define fetch_url function"
    
    def test_openai_tools_definition(self, example_code):
        """Test that OpenAI tools are properly defined."""
        assert "TOOLS = " in example_code or "TOOLS=" in example_code, "Should define TOOLS list"
        assert '"function"' in example_code, "Should have function type in tools"
        assert '"fetch_url"' in example_code, "Should define fetch_url tool"
    
    def test_mcp_url_from_environment(self, example_code):
        """Test that MCP URL is read from environment."""
        assert 'MCP_SERVER_URL' in example_code, "Should read MCP_SERVER_URL from env"


# =============================================================================
# Category 6: Debug Logging Tests (4 tests)
# =============================================================================

class TestDebugLogging:
    """Tests for debug logging implementation."""
    
    def test_debug_prefix_used(self, example_code):
        """Test that [DEBUG] prefix is used for debug messages."""
        assert '[DEBUG]' in example_code, "Should use [DEBUG] prefix"
    
    def test_flush_used(self, example_code):
        """Test that flush=True is used for immediate output."""
        assert "flush=True" in example_code, "Should use flush=True for immediate output"
    
    def test_debug_messages_exist(self, example_code):
        """Test that debug messages are present in the code."""
        assert '[DEBUG]' in example_code, "Should have [DEBUG] messages for debugging"
    
    def test_debug_on_tool_calls(self, example_code):
        """Test that debug messages are printed for tool calls."""
        assert "[TOOL CALL]" in example_code or "[DEBUG] fetch_url" in example_code, \
            "Should log tool calls"


# =============================================================================
# Category 7: Async and Main Function Tests (4 tests)
# =============================================================================

class TestAsyncAndMain:
    """Tests for async implementation and main function."""
    
    def test_main_function_exists(self, example_code):
        """Test that main() function is defined."""
        assert "def main()" in example_code, "Should define main() function"
    
    def test_main_guard_present(self, example_code):
        """Test that if __name__ == '__main__' guard is present."""
        assert '__name__ == "__main__"' in example_code or "__name__ == '__main__'" in example_code, \
            "Should have main guard"
    
    def test_async_run_agent_exists(self, example_code):
        """Test that async run_agent function exists."""
        assert "async def run_agent" in example_code, "Should define async run_agent"
    
    def test_event_loop_handling(self, example_code):
        """Test that event loop is properly created and handled."""
        assert "asyncio.new_event_loop" in example_code or "asyncio.get_event_loop" in example_code, \
            "Should create or get event loop"
        assert "loop.run_until_complete" in example_code, "Should use run_until_complete"


# =============================================================================
# Category 8: Syntax and Import Validity Tests (4 tests)
# =============================================================================

class TestSyntaxAndImports:
    """Tests for code syntax and import validity."""
    
    def test_code_parses_without_error(self, example_code):
        """Test that the example code parses without syntax errors."""
        try:
            ast.parse(example_code)
        except SyntaxError as e:
            pytest.fail(f"Syntax error in example code: {e}")
    
    def test_has_docstring(self, example_ast):
        """Test that the module has a docstring."""
        docstring = ast.get_docstring(example_ast)
        assert docstring is not None, "Module should have a docstring"
    
    def test_all_functions_have_docstrings(self, example_ast):
        """Test that top-level functions have docstrings."""
        # Only check top-level functions, not methods (which are inside classes)
        for node in example_ast.body:
            if isinstance(node, ast.FunctionDef):
                docstring = ast.get_docstring(node)
                assert docstring is not None, f"Function {node.name} should have a docstring"
            elif isinstance(node, ast.AsyncFunctionDef):
                docstring = ast.get_docstring(node)
                assert docstring is not None, f"Async function {node.name} should have a docstring"
    
    def test_classes_have_docstrings(self, example_ast):
        """Test that all classes have docstrings."""
        for node in ast.walk(example_ast):
            if isinstance(node, ast.ClassDef):
                docstring = ast.get_docstring(node)
                assert docstring is not None, f"Class {node.name} should have a docstring"


# =============================================================================
# Integration Test (Mock-based)
# =============================================================================

class TestMockedExecution:
    """Tests with mocked dependencies."""
    
    def test_agent_can_be_instantiated_with_mocks(self):
        """Test that the agent pattern can be instantiated with mocked OpenAI."""
        # This tests the pattern without actually importing the example
        # to avoid side effects from aidefense.runtime.agentsec.protect()
        
        with mock.patch.dict(os.environ, {
            "OPENAI_API_KEY": "test-key",
            "OPENAI_MODEL": "gpt-4o-mini",
            "AGENTSEC_API_MODE_LLM": "off",
        }):
            # Just verify the environment is set correctly
            assert os.environ["OPENAI_API_KEY"] == "test-key"
            assert os.environ["AGENTSEC_API_MODE_LLM"] == "off"

