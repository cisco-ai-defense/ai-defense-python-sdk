"""
Tests for the CrewAI Agent Example.

This module tests:
- Basic example structure and imports
- agentsec protection and patching
- CrewAI agent setup
- MCP tool integration
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
    """Path to the CrewAI agent example file."""
    return os.path.join(os.path.join(os.path.dirname(__file__), "..", ".."), "agent.py")


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
        
        assert "crewai" in content, "Should require crewai"
        assert "python-dotenv" in content, "Should require python-dotenv"
        assert "mcp" in content, "Should require mcp"
    
    def test_env_example_exists(self):
        """Test that shared .env.example exists with required variables."""
        # .env.example is now in examples/ directory
        env_file = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".env.example")
        assert os.path.exists(env_file), "examples/.env.example should exist"
        
        with open(env_file, "r") as f:
            content = f.read()
        
        assert "AGENTSEC_API_MODE_LLM" in content, "Should document AGENTSEC_API_MODE_LLM"
        assert "MCP_SERVER_URL" in content, "Should document MCP_SERVER_URL"
    
    def test_runner_script_exists(self):
        """Test that scripts/run.sh exists."""
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
        
        for i, line in enumerate(lines):
            if "load_dotenv" in line and "import" not in line:
                dotenv_line = i
            if "import agentsec" in line:
                agentsec_line = i
        
        assert dotenv_line is not None, "Should call load_dotenv()"
        assert agentsec_line is not None, "Should import agentsec"
        assert dotenv_line < agentsec_line, "load_dotenv() should be called before agentsec import"
    
    def test_agentsec_imported_before_crewai(self, example_code):
        """Test that agentsec is imported before CrewAI."""
        lines = example_code.split("\n")
        agentsec_line = None
        crewai_line = None
        
        for i, line in enumerate(lines):
            if "import agentsec" in line:
                agentsec_line = i
            if "from crewai import" in line:
                crewai_line = i
        
        assert agentsec_line is not None, "Should import agentsec"
        assert crewai_line is not None, "Should import CrewAI"
        assert agentsec_line < crewai_line, "agentsec should be imported before CrewAI"
    
    def test_protect_called_before_crewai(self, example_code):
        """Test that agentsec.protect() is called before CrewAI import."""
        lines = example_code.split("\n")
        protect_line = None
        crewai_line = None
        
        for i, line in enumerate(lines):
            if "agentsec.protect" in line:
                protect_line = i
            if "from crewai import" in line:
                crewai_line = i
        
        assert protect_line is not None, "Should call agentsec.protect()"
        assert crewai_line is not None, "Should import CrewAI"
        assert protect_line < crewai_line, "agentsec.protect() should be called before CrewAI import"
    
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
    
    def test_agentsec_protect_minimal(self, example_code):
        """Test that agentsec.protect() is used with minimal setup."""
        assert "agentsec.protect()" in example_code, "Should call agentsec.protect()"
    
    def test_mode_from_environment(self, example_code):
        """Test that mode is read from environment variable."""
        assert 'AGENTSEC_API_MODE_LLM' in example_code, "Should read AGENTSEC_API_MODE_LLM from env"
    
    def test_security_policy_error_handled(self, example_code):
        """Test that SecurityPolicyError is imported and handled."""
        assert "SecurityPolicyError" in example_code, "Should import SecurityPolicyError"
        assert "except SecurityPolicyError" in example_code, "Should catch SecurityPolicyError"
    
    def test_get_patched_clients_called(self, example_code):
        """Test that patched clients are logged."""
        assert "get_patched_clients" in example_code, "Should call get_patched_clients()"


# =============================================================================
# Category 4: CrewAI Agent Tests (5 tests)
# =============================================================================

class TestCrewAIAgents:
    """Tests for CrewAI agent implementation."""
    
    def test_crewai_import_present(self, example_code):
        """Test that CrewAI is imported."""
        assert "from crewai import" in example_code, "Should import from crewai"
    
    def test_researcher_agent_defined(self, example_code):
        """Test that Researcher agent is defined."""
        assert "researcher" in example_code.lower(), "Should define researcher agent"
        assert "Technical Researcher" in example_code or "Researcher" in example_code, \
            "Should have researcher role"
    
    def test_writer_agent_defined(self, example_code):
        """Test that Writer agent is defined."""
        assert "writer" in example_code.lower(), "Should define writer agent"
        assert "Technical Writer" in example_code or "Writer" in example_code, \
            "Should have writer role"
    
    def test_crew_created(self, example_code):
        """Test that Crew is created."""
        assert "Crew(" in example_code, "Should create Crew instance"
    
    def test_tasks_created(self, example_code):
        """Test that tasks are created."""
        assert "Task(" in example_code, "Should create Task instances"


# =============================================================================
# Category 5: MCP Integration Tests (4 tests)
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
    
    def test_threading_for_mcp(self, example_code):
        """Test that threading is used for MCP calls."""
        assert "threading" in example_code, "Should use threading for MCP calls"
        assert "Thread" in example_code, "Should use Thread class"
    
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
# Category 7: Syntax and Main Tests (4 tests)
# =============================================================================

class TestSyntaxAndMain:
    """Tests for code syntax and main function."""
    
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
    
    def test_main_function_exists(self, example_code):
        """Test that main() function is defined."""
        assert "def main()" in example_code, "Should define main() function"
    
    def test_main_guard_present(self, example_code):
        """Test that if __name__ == '__main__' guard is present."""
        assert '__name__ == "__main__"' in example_code or "__name__ == '__main__'" in example_code, \
            "Should have main guard"







