"""
Tests for the Google ADK Agent Example.

This module tests:
- Basic example structure and imports
- agentsec protection and patching
- Google ADK agent setup (LlmAgent, Runner)
- MCP tool integration via McpToolset
- Error handling (SecurityPolicyError)
"""

import ast
import os

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

EXAMPLE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""Path to the google-adk-agent example directory."""


@pytest.fixture(scope="module")
def example_file():
    """Path to the example agent.py file."""
    return os.path.join(EXAMPLE_DIR, "agent.py")


@pytest.fixture(scope="module")
def example_code(example_file):
    """Read the example file source code."""
    with open(example_file) as f:
        return f.read()


@pytest.fixture(scope="module")
def example_ast(example_code):
    """Parse the example file into an AST."""
    return ast.parse(example_code)


# ---------------------------------------------------------------------------
# File structure
# ---------------------------------------------------------------------------

class TestFileStructure:
    """Tests for file structure and basic setup."""

    def test_agent_py_exists(self):
        """Test that agent.py exists."""
        assert os.path.exists(os.path.join(EXAMPLE_DIR, "agent.py")), \
            "agent.py should exist"

    def test_pyproject_toml_exists(self):
        """Test that pyproject.toml exists with correct dependencies."""
        pyproject_file = os.path.join(EXAMPLE_DIR, "pyproject.toml")
        assert os.path.exists(pyproject_file), "pyproject.toml should exist"

        with open(pyproject_file) as f:
            content = f.read()

        assert "google-adk" in content, "Should require google-adk"
        assert "google-genai" in content, "Should require google-genai"
        assert "python-dotenv" in content, "Should require python-dotenv"
        assert "mcp" in content, "Should require mcp"

    def test_run_script_exists(self):
        """Test that scripts/run.sh exists."""
        script_file = os.path.join(EXAMPLE_DIR, "scripts", "run.sh")
        assert os.path.exists(script_file), "scripts/run.sh should exist"


# ---------------------------------------------------------------------------
# Import ordering
# ---------------------------------------------------------------------------

class TestImportOrder:
    """Tests for correct import ordering in the example."""

    def test_dotenv_before_agentsec(self, example_code):
        """Test that dotenv is imported and called early."""
        lines = example_code.splitlines()

        dotenv_line = next(
            (i for i, l in enumerate(lines) if "load_dotenv" in l and "import" in l), None
        )
        agentsec_line = next(
            (i for i, l in enumerate(lines) if "from aidefense.runtime import agentsec" in l),
            None,
        )
        assert dotenv_line is not None, "Should call load_dotenv()"
        assert agentsec_line is not None, "Should import agentsec"
        assert dotenv_line < agentsec_line, \
            "load_dotenv() should be called before agentsec import"

    def test_agentsec_before_adk(self, example_code):
        """Test that agentsec is imported before ADK."""
        lines = example_code.splitlines()

        agentsec_line = next(
            (i for i, l in enumerate(lines) if "from aidefense.runtime import agentsec" in l),
            None,
        )
        adk_line = next(
            (i for i, l in enumerate(lines)
             if "from google.adk" in l or "from google.genai" in l),
            None,
        )
        assert agentsec_line is not None, "Should import agentsec"
        assert adk_line is not None, "Should import google.adk"
        assert agentsec_line < adk_line, \
            "agentsec should be imported before Google ADK"

    def test_protect_before_adk(self, example_code):
        """Test that agentsec.protect() is called before ADK import."""
        lines = example_code.splitlines()

        protect_line = next(
            (i for i, l in enumerate(lines) if "agentsec.protect" in l), None
        )
        adk_line = next(
            (i for i, l in enumerate(lines)
             if "from google.adk" in l or "from google.genai" in l),
            None,
        )
        assert protect_line is not None, "Should call agentsec.protect()"
        assert adk_line is not None, "Should import Google ADK"
        assert protect_line < adk_line, \
            "agentsec.protect() should be called before ADK import"


# ---------------------------------------------------------------------------
# agentsec integration
# ---------------------------------------------------------------------------

class TestAgentsecIntegration:
    """Tests for agentsec SDK integration."""

    def test_protect_is_called(self, example_code):
        """Test that agentsec.protect() is called."""
        assert "agentsec.protect(" in example_code, \
            "Should call agentsec.protect()"

    def test_mode_from_env(self, example_code):
        """Test that mode is read from environment variable."""
        assert "AGENTSEC_API_MODE_LLM" in example_code, \
            "Should read AGENTSEC_API_MODE_LLM from env"

    def test_security_policy_error_handled(self, example_code):
        """Test that SecurityPolicyError is imported and handled."""
        assert "SecurityPolicyError" in example_code, \
            "Should import SecurityPolicyError"
        assert "except SecurityPolicyError" in example_code, \
            "Should catch SecurityPolicyError"

    def test_patched_clients_logged(self, example_code):
        """Test that patched clients are logged."""
        assert "get_patched_clients" in example_code, \
            "Should call get_patched_clients()"


# ---------------------------------------------------------------------------
# ADK agent setup
# ---------------------------------------------------------------------------

class TestADKAgent:
    """Tests for Google ADK agent implementation."""

    def test_llm_agent_used(self, example_code):
        """Test that LlmAgent is imported and used."""
        assert "from google.adk.agents import LlmAgent" in example_code or \
               "from google.adk.agents.llm_agent import LlmAgent" in example_code, \
            "Should import LlmAgent from google.adk"
        assert "LlmAgent(" in example_code, "Should instantiate LlmAgent"

    def test_runner_used(self, example_code):
        """Test that Runner is imported and used."""
        assert "from google.adk.runners import Runner" in example_code, \
            "Should import Runner"
        assert "Runner(" in example_code, "Should instantiate Runner"

    def test_session_service_used(self, example_code):
        """Test that InMemorySessionService is used."""
        assert "InMemorySessionService" in example_code, \
            "Should use InMemorySessionService"

    def test_gemini_model_specified(self, example_code):
        """Test that a Gemini model is specified."""
        assert "gemini" in example_code.lower(), \
            "Should specify a Gemini model"

    def test_run_async_used(self, example_code):
        """Test that runner.run_async is used for agent execution."""
        assert "run_async" in example_code, \
            "Should use run_async() for agent execution"

    def test_content_created(self, example_code):
        """Test that google.genai types.Content is used for user input."""
        assert "types.Content(" in example_code, \
            "Should create Content for user message"


# ---------------------------------------------------------------------------
# MCP integration
# ---------------------------------------------------------------------------

class TestMCPIntegration:
    """Tests for MCP tool integration."""

    def test_mcp_toolset_imported(self, example_code):
        """Test that McpToolset is imported."""
        assert "McpToolset" in example_code, \
            "Should import McpToolset"

    def test_streamable_http_params(self, example_code):
        """Test that StreamableHTTPConnectionParams is used."""
        assert "StreamableHTTPConnectionParams" in example_code, \
            "Should import StreamableHTTPConnectionParams"

    def test_mcp_url_from_env(self, example_code):
        """Test that MCP URL is read from environment."""
        assert "MCP_SERVER_URL" in example_code, \
            "Should read MCP_SERVER_URL from env"

    def test_mcp_toolset_cleanup(self, example_code):
        """Test that MCP toolset is properly closed."""
        assert "toolset.close()" in example_code or "mcp_toolset.close()" in example_code, \
            "Should close MCP toolset on exit"


# ---------------------------------------------------------------------------
# Debug logging
# ---------------------------------------------------------------------------

class TestDebugLogging:
    """Tests for debug logging implementation."""

    def test_logger_debug_used(self, example_code):
        """Test that logger.debug is used for debug messages."""
        assert "logger.debug" in example_code, \
            "Should use logger.debug for debug messages"

    def test_flush_true_used(self, example_code):
        """Test that flush=True is used for immediate output."""
        assert "flush=True" in example_code, \
            "Should use flush=True for immediate output"

    def test_logging_configured(self, example_code):
        """Test that logging is properly configured."""
        assert "logging.basicConfig" in example_code or \
               "logging.getLogger" in example_code, \
            "Should configure logging"


# ---------------------------------------------------------------------------
# Syntax and main
# ---------------------------------------------------------------------------

class TestSyntaxAndMain:
    """Tests for code syntax and main function."""

    def test_syntax_valid(self, example_code):
        """Test that the example code parses without syntax errors."""
        try:
            ast.parse(example_code)
        except SyntaxError as e:
            pytest.fail(f"Syntax error in example code: {e}")

    def test_has_docstring(self, example_ast):
        """Test that the module has a docstring."""
        docstring = ast.get_docstring(example_ast)
        assert docstring, "Module should have a docstring"

    def test_main_function_defined(self, example_code):
        """Test that main() function is defined."""
        assert "async def main()" in example_code or "def main()" in example_code, \
            "Should define main() function"

    def test_main_guard(self, example_code):
        """Test that if __name__ == '__main__' guard is present."""
        assert '__name__ == "__main__"' in example_code or \
               "__name__ == '__main__'" in example_code, \
            "Should have main guard"
