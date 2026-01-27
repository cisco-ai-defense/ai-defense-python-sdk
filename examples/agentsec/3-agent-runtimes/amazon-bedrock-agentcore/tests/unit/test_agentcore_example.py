"""
Tests for the AgentCore Runtime Example.

This module tests:
- Basic example structure and imports
- agentsec protection and patching
- AgentCore agent setup
- Deployment configurations
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
def direct_deploy_file():
    """Path to the direct deploy example file."""
    return os.path.join(os.path.dirname(__file__), "..", "..", "direct-deploy", "agentcore_app.py")


@pytest.fixture
def container_deploy_file():
    """Path to the container deploy example file."""
    return os.path.join(os.path.dirname(__file__), "..", "..", "container-deploy", "agentcore_app.py")


@pytest.fixture
def lambda_deploy_file():
    """Path to the lambda deploy example file."""
    return os.path.join(os.path.dirname(__file__), "..", "..", "lambda-deploy", "lambda_handler.py")


@pytest.fixture
def agent_factory_file():
    """Path to the shared agent factory file."""
    return os.path.join(os.path.dirname(__file__), "..", "..", "_shared", "agent_factory.py")


@pytest.fixture
def agent_factory_code(agent_factory_file):
    """Read the agent factory file source code."""
    with open(agent_factory_file, "r") as f:
        return f.read()


@pytest.fixture
def lambda_handler_code(lambda_deploy_file):
    """Read the lambda handler file source code."""
    with open(lambda_deploy_file, "r") as f:
        return f.read()


@pytest.fixture
def test_with_protection_file():
    """Path to the test_with_protection.py file."""
    return os.path.join(os.path.dirname(__file__), "..", "..", "direct-deploy", "test_with_protection.py")


@pytest.fixture
def test_with_protection_code(test_with_protection_file):
    """Read the test_with_protection.py file source code."""
    with open(test_with_protection_file, "r") as f:
        return f.read()


# =============================================================================
# Category 1: File Structure Tests
# =============================================================================

class TestFileStructure:
    """Tests for file structure and basic setup."""
    
    def test_direct_deploy_file_exists(self, direct_deploy_file):
        """Test that direct-deploy/agentcore_app.py exists."""
        assert os.path.exists(direct_deploy_file), "direct-deploy/agentcore_app.py should exist"
    
    def test_container_deploy_file_exists(self, container_deploy_file):
        """Test that container-deploy/agentcore_app.py exists."""
        assert os.path.exists(container_deploy_file), "container-deploy/agentcore_app.py should exist"
    
    def test_lambda_deploy_file_exists(self, lambda_deploy_file):
        """Test that lambda-deploy/lambda_handler.py exists."""
        assert os.path.exists(lambda_deploy_file), "lambda-deploy/lambda_handler.py should exist"
    
    def test_agent_factory_file_exists(self, agent_factory_file):
        """Test that _shared/agent_factory.py exists."""
        assert os.path.exists(agent_factory_file), "_shared/agent_factory.py should exist"
    
    def test_pyproject_file_exists(self):
        """Test that pyproject.toml exists with correct dependencies."""
        pyproject_file = os.path.join(os.path.dirname(__file__), "..", "..", "pyproject.toml")
        assert os.path.exists(pyproject_file), "pyproject.toml should exist"
        
        with open(pyproject_file, "r") as f:
            content = f.read()
        
        assert "agentsec" in content, "Should require agentsec"
        assert "strands-agents" in content, "Should require strands-agents"
    
    def test_shared_env_example_exists(self):
        """Test that shared .env.example exists with required variables."""
        env_file = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".env.example")
        assert os.path.exists(env_file), "examples/.env.example should exist"
        
        with open(env_file, "r") as f:
            content = f.read()
        
        assert "AI_DEFENSE_API_MODE_LLM_ENDPOINT" in content, "Should document AI_DEFENSE_API_MODE_LLM_ENDPOINT"
        assert "AGENTSEC_API_MODE_LLM" in content, "Should document AGENTSEC_API_MODE_LLM"
    
    def test_dockerfile_exists(self):
        """Test that container-deploy/Dockerfile exists."""
        dockerfile = os.path.join(os.path.dirname(__file__), "..", "..", "container-deploy", "Dockerfile")
        assert os.path.exists(dockerfile), "container-deploy/Dockerfile should exist"
    
    def test_deploy_scripts_exist(self):
        """Test that deploy scripts exist for all modes."""
        base = os.path.join(os.path.dirname(__file__), "..", "..")
        
        assert os.path.exists(os.path.join(base, "direct-deploy", "scripts", "deploy.sh")), \
            "direct-deploy/scripts/deploy.sh should exist"
        assert os.path.exists(os.path.join(base, "container-deploy", "scripts", "deploy.sh")), \
            "container-deploy/scripts/deploy.sh should exist"
        assert os.path.exists(os.path.join(base, "lambda-deploy", "scripts", "deploy.sh")), \
            "lambda-deploy/scripts/deploy.sh should exist"
    
    def test_invoke_scripts_exist(self):
        """Test that invoke scripts exist for all modes."""
        base = os.path.join(os.path.dirname(__file__), "..", "..")
        
        assert os.path.exists(os.path.join(base, "direct-deploy", "scripts", "invoke.sh")), \
            "direct-deploy/scripts/invoke.sh should exist"
        assert os.path.exists(os.path.join(base, "container-deploy", "scripts", "invoke.sh")), \
            "container-deploy/scripts/invoke.sh should exist"
        assert os.path.exists(os.path.join(base, "lambda-deploy", "scripts", "invoke.sh")), \
            "lambda-deploy/scripts/invoke.sh should exist"


# =============================================================================
# Category 2: Agent Factory Tests
# =============================================================================

class TestAgentFactory:
    """Tests for the shared agent factory."""
    
    def test_agentsec_imported(self, agent_factory_code):
        """Test that agentsec is imported."""
        assert "import agentsec" in agent_factory_code, "Should import agentsec"
    
    def test_protect_called(self, agent_factory_code):
        """Test that agentsec.protect() is called."""
        assert "agentsec.protect(" in agent_factory_code, "Should call agentsec.protect()"
    
    def test_dotenv_imported(self, agent_factory_code):
        """Test that dotenv is imported for env loading."""
        assert "from dotenv import load_dotenv" in agent_factory_code, "Should import load_dotenv"
    
    def test_llm_integration_mode_configurable(self, agent_factory_code):
        """Test that LLM integration mode is configurable."""
        assert "llm_integration_mode" in agent_factory_code, "Should configure llm_integration_mode"
    
    def test_api_mode_endpoint_configurable(self, agent_factory_code):
        """Test that API mode endpoint is configurable."""
        assert "api_mode_llm_endpoint" in agent_factory_code, "Should configure api_mode_llm_endpoint"
    
    def test_providers_configured(self, agent_factory_code):
        """Test that providers are configured."""
        assert "providers=" in agent_factory_code or "providers={" in agent_factory_code, \
            "Should configure providers"
    
    def test_bedrock_gateway_configurable(self, agent_factory_code):
        """Test that Bedrock gateway is configurable."""
        assert "AGENTSEC_BEDROCK_GATEWAY_URL" in agent_factory_code, \
            "Should configure AGENTSEC_BEDROCK_GATEWAY_URL"
    
    def test_strands_agent_created(self, agent_factory_code):
        """Test that Strands Agent is created."""
        assert "Agent(" in agent_factory_code, "Should create Strands Agent"
    
    def test_bedrock_model_used(self, agent_factory_code):
        """Test that BedrockModel is used."""
        assert "BedrockModel" in agent_factory_code, "Should use BedrockModel"
    
    def test_tools_registered(self, agent_factory_code):
        """Test that tools are registered with the agent."""
        assert "tools=" in agent_factory_code, "Should register tools with agent"


# =============================================================================
# Category 3: Lambda Handler Tests
# =============================================================================

class TestLambdaHandler:
    """Tests for the Lambda handler."""
    
    def test_agentsec_imported(self, lambda_handler_code):
        """Test that agentsec is imported."""
        assert "import agentsec" in lambda_handler_code, "Should import agentsec"
    
    def test_uses_shared_module(self, lambda_handler_code):
        """Test that lambda handler uses _shared module (not duplicate code)."""
        assert "from _shared import get_agent" in lambda_handler_code, \
            "Should import get_agent from _shared"
    
    def test_handler_function_exists(self, lambda_handler_code):
        """Test that handler function is defined."""
        assert "def handler(" in lambda_handler_code, "Should define handler function"
    
    def test_calls_get_agent(self, lambda_handler_code):
        """Test that handler calls get_agent()."""
        assert "get_agent()" in lambda_handler_code, "Should call get_agent()"
    
    def test_shared_has_strands_agent(self):
        """Test that _shared/agent_factory.py uses Strands Agent."""
        agent_factory = os.path.join(os.path.dirname(__file__), "..", "..", "_shared", "agent_factory.py")
        with open(agent_factory, "r") as f:
            content = f.read()
        assert "Agent" in content, "_shared should use Strands Agent"
        assert "BedrockModel" in content, "_shared should use BedrockModel"
    
    def test_shared_has_tools(self):
        """Test that _shared has tools defined."""
        tools_file = os.path.join(os.path.dirname(__file__), "..", "..", "_shared", "tools.py")
        with open(tools_file, "r") as f:
            content = f.read()
        assert "@tool" in content, "_shared/tools.py should define tools with @tool decorator"
    
    def test_result_returned(self, lambda_handler_code):
        """Test that a result is returned."""
        assert 'return' in lambda_handler_code and 'result' in lambda_handler_code, \
            "Should return a result"


# =============================================================================
# Category 4: Direct Deploy Tests
# =============================================================================

class TestDirectDeploy:
    """Tests for direct deploy mode."""
    
    def test_imports_bedrock_agentcore(self, direct_deploy_file):
        """Test that BedrockAgentCoreApp is imported."""
        with open(direct_deploy_file, "r") as f:
            content = f.read()
        assert "BedrockAgentCoreApp" in content, "Should import BedrockAgentCoreApp"
    
    def test_entrypoint_decorator_used(self, direct_deploy_file):
        """Test that @app.entrypoint decorator is used."""
        with open(direct_deploy_file, "r") as f:
            content = f.read()
        assert "@app.entrypoint" in content, "Should use @app.entrypoint decorator"
    
    def test_invoke_function_exists(self, direct_deploy_file):
        """Test that invoke function is defined."""
        with open(direct_deploy_file, "r") as f:
            content = f.read()
        assert "def invoke(" in content, "Should define invoke function"
    
    def test_requirements_file_exists(self):
        """Test that requirements.txt exists."""
        req_file = os.path.join(os.path.dirname(__file__), "..", "..", "direct-deploy", "requirements.txt")
        assert os.path.exists(req_file), "direct-deploy/requirements.txt should exist"


# =============================================================================
# Category 4b: Test With Protection Tests (boto3 SDK Direct)
# =============================================================================

class TestWithProtection:
    """Tests for the test_with_protection.py file that uses boto3 SDK directly."""
    
    def test_file_exists(self, test_with_protection_file):
        """Test that test_with_protection.py exists."""
        assert os.path.exists(test_with_protection_file), "direct-deploy/test_with_protection.py should exist"
    
    def test_uses_boto3_directly(self, test_with_protection_code):
        """Test that it uses boto3 directly (not CLI)."""
        assert "import boto3" in test_with_protection_code, "Should import boto3"
        assert "invoke_agent_runtime(" in test_with_protection_code, "Should call invoke_agent_runtime"
    
    def test_does_not_use_cli(self, test_with_protection_code):
        """Test that it does NOT use the agentcore CLI (uses boto3 SDK only for full response inspection)."""
        assert "invoke_agent_with_cli" not in test_with_protection_code, \
            "Should NOT have invoke_agent_with_cli function (CLI doesn't support response inspection)"
        assert "agentcore invoke" not in test_with_protection_code, \
            "Should NOT call 'agentcore invoke' CLI (CLI doesn't support response inspection)"
    
    def test_has_debug_logging(self, test_with_protection_code):
        """Test that DEBUG logging is enabled for agentsec inspection visibility."""
        assert "import logging" in test_with_protection_code, "Should import logging"
        assert "logging.DEBUG" in test_with_protection_code or "setLevel(logging.DEBUG)" in test_with_protection_code, \
            "Should enable DEBUG level logging"
        assert 'getLogger("agentsec")' in test_with_protection_code or "getLogger('agentsec')" in test_with_protection_code, \
            "Should set agentsec logger to DEBUG"
    
    def test_agentsec_imported(self, test_with_protection_code):
        """Test that agentsec is imported."""
        assert "import agentsec" in test_with_protection_code, "Should import agentsec"
    
    def test_protect_called_before_boto3(self, test_with_protection_code):
        """Test that agentsec.protect() is called before boto3 import."""
        lines = test_with_protection_code.split("\n")
        protect_line = None
        boto3_line = None
        
        for i, line in enumerate(lines):
            if "agentsec.protect(" in line:
                protect_line = i
            if "import boto3" in line and protect_line is None:
                boto3_line = i
        
        assert protect_line is not None, "Should call agentsec.protect()"
        if boto3_line is not None:
            assert protect_line < boto3_line, "agentsec.protect() should be called before boto3 import"
    
    def test_documents_request_response_inspection(self, test_with_protection_code):
        """Test that docstrings mention both request AND response inspection."""
        assert "REQUEST" in test_with_protection_code.upper() and "RESPONSE" in test_with_protection_code.upper(), \
            "Should document that both REQUEST and RESPONSE are inspected"
    
    def test_handles_security_policy_error(self, test_with_protection_code):
        """Test that it handles SecurityPolicyError for blocked requests."""
        assert "SecurityPolicyError" in test_with_protection_code, \
            "Should handle agentsec.SecurityPolicyError for blocked requests"
    
    def test_syntax_valid(self, test_with_protection_code):
        """Test that test_with_protection.py has valid Python syntax."""
        try:
            ast.parse(test_with_protection_code)
        except SyntaxError as e:
            pytest.fail(f"Syntax error in test_with_protection.py: {e}")


# =============================================================================
# Category 5: Container Deploy Tests
# =============================================================================

class TestContainerDeploy:
    """Tests for container deploy mode."""
    
    def test_imports_bedrock_agentcore(self, container_deploy_file):
        """Test that BedrockAgentCoreApp is imported."""
        with open(container_deploy_file, "r") as f:
            content = f.read()
        assert "BedrockAgentCoreApp" in content, "Should import BedrockAgentCoreApp"
    
    def test_entrypoint_decorator_used(self, container_deploy_file):
        """Test that @app.entrypoint decorator is used."""
        with open(container_deploy_file, "r") as f:
            content = f.read()
        assert "@app.entrypoint" in content, "Should use @app.entrypoint decorator"
    
    def test_app_run_exists(self, container_deploy_file):
        """Test that app.run() is called for container mode."""
        with open(container_deploy_file, "r") as f:
            content = f.read()
        assert "app.run(" in content, "Should call app.run() for container mode"
    
    def test_dockerfile_uses_python_311(self):
        """Test that Dockerfile uses Python 3.11."""
        dockerfile = os.path.join(os.path.dirname(__file__), "..", "..", "container-deploy", "Dockerfile")
        with open(dockerfile, "r") as f:
            content = f.read()
        assert "python:3.11" in content, "Dockerfile should use Python 3.11"
    
    def test_dockerfile_copies_agentsec(self):
        """Test that Dockerfile copies agentsec source."""
        dockerfile = os.path.join(os.path.dirname(__file__), "..", "..", "container-deploy", "Dockerfile")
        with open(dockerfile, "r") as f:
            content = f.read()
        assert "COPY agentsec" in content, "Dockerfile should copy agentsec source"


# =============================================================================
# Category 6: Syntax Tests
# =============================================================================

class TestSyntax:
    """Tests for code syntax."""
    
    def test_agent_factory_parses(self, agent_factory_code):
        """Test that agent_factory.py parses without syntax errors."""
        try:
            ast.parse(agent_factory_code)
        except SyntaxError as e:
            pytest.fail(f"Syntax error in agent_factory.py: {e}")
    
    def test_lambda_handler_parses(self, lambda_handler_code):
        """Test that lambda_handler.py parses without syntax errors."""
        try:
            ast.parse(lambda_handler_code)
        except SyntaxError as e:
            pytest.fail(f"Syntax error in lambda_handler.py: {e}")
    
    def test_direct_deploy_parses(self, direct_deploy_file):
        """Test that direct-deploy/agentcore_app.py parses without syntax errors."""
        with open(direct_deploy_file, "r") as f:
            content = f.read()
        try:
            ast.parse(content)
        except SyntaxError as e:
            pytest.fail(f"Syntax error in direct-deploy/agentcore_app.py: {e}")
    
    def test_container_deploy_parses(self, container_deploy_file):
        """Test that container-deploy/agentcore_app.py parses without syntax errors."""
        with open(container_deploy_file, "r") as f:
            content = f.read()
        try:
            ast.parse(content)
        except SyntaxError as e:
            pytest.fail(f"Syntax error in container-deploy/agentcore_app.py: {e}")


# =============================================================================
# Category 7: Tools Tests
# =============================================================================

class TestTools:
    """Tests for the demo tools."""
    
    def test_tools_file_exists(self):
        """Test that _shared/tools.py exists."""
        tools_file = os.path.join(os.path.dirname(__file__), "..", "..", "_shared", "tools.py")
        assert os.path.exists(tools_file), "_shared/tools.py should exist"
    
    def test_add_tool_defined(self):
        """Test that add tool is defined."""
        tools_file = os.path.join(os.path.dirname(__file__), "..", "..", "_shared", "tools.py")
        with open(tools_file, "r") as f:
            content = f.read()
        assert "def add(" in content, "Should define add tool"
    
    def test_check_service_health_tool_defined(self):
        """Test that check_service_health tool is defined."""
        tools_file = os.path.join(os.path.dirname(__file__), "..", "..", "_shared", "tools.py")
        with open(tools_file, "r") as f:
            content = f.read()
        assert "def check_service_health(" in content, "Should define check_service_health tool"
    
    def test_summarize_log_tool_defined(self):
        """Test that summarize_log tool is defined."""
        tools_file = os.path.join(os.path.dirname(__file__), "..", "..", "_shared", "tools.py")
        with open(tools_file, "r") as f:
            content = f.read()
        assert "def summarize_log(" in content, "Should define summarize_log tool"
    
    def test_tools_have_decorators(self):
        """Test that tools have @tool decorators."""
        tools_file = os.path.join(os.path.dirname(__file__), "..", "..", "_shared", "tools.py")
        with open(tools_file, "r") as f:
            content = f.read()
        assert "@tool" in content, "Tools should have @tool decorator"


# =============================================================================
# Category 8: MCP Tools Tests
# =============================================================================

class TestMCPTools:
    """Tests for MCP tool integration."""
    
    def test_mcp_tools_file_exists(self):
        """Test that _shared/mcp_tools.py exists."""
        mcp_tools_file = os.path.join(os.path.dirname(__file__), "..", "..", "_shared", "mcp_tools.py")
        assert os.path.exists(mcp_tools_file), "_shared/mcp_tools.py should exist"
    
    def test_fetch_url_tool_defined(self):
        """Test that fetch_url MCP tool is defined."""
        mcp_tools_file = os.path.join(os.path.dirname(__file__), "..", "..", "_shared", "mcp_tools.py")
        with open(mcp_tools_file, "r") as f:
            content = f.read()
        assert "def fetch_url(" in content, "Should define fetch_url tool"
    
    def test_mcp_tools_have_decorator(self):
        """Test that MCP tools have @tool decorator."""
        mcp_tools_file = os.path.join(os.path.dirname(__file__), "..", "..", "_shared", "mcp_tools.py")
        with open(mcp_tools_file, "r") as f:
            content = f.read()
        assert "@tool" in content, "MCP tools should have @tool decorator"
    
    def test_get_mcp_tools_function_exists(self):
        """Test that get_mcp_tools function exists."""
        mcp_tools_file = os.path.join(os.path.dirname(__file__), "..", "..", "_shared", "mcp_tools.py")
        with open(mcp_tools_file, "r") as f:
            content = f.read()
        assert "def get_mcp_tools(" in content, "Should define get_mcp_tools function"
    
    def test_mcp_tools_uses_mcp_client(self):
        """Test that MCP tools import MCP client."""
        mcp_tools_file = os.path.join(os.path.dirname(__file__), "..", "..", "_shared", "mcp_tools.py")
        with open(mcp_tools_file, "r") as f:
            content = f.read()
        assert "streamablehttp_client" in content, "Should import MCP streamablehttp_client"
        assert "ClientSession" in content, "Should import MCP ClientSession"
    
    def test_mcp_tools_calls_session_call_tool(self):
        """Test that MCP tools use session.call_tool (which agentsec intercepts)."""
        mcp_tools_file = os.path.join(os.path.dirname(__file__), "..", "..", "_shared", "mcp_tools.py")
        with open(mcp_tools_file, "r") as f:
            content = f.read()
        assert "session.call_tool" in content or "await session.call_tool" in content, \
            "Should use session.call_tool which agentsec intercepts"
    
    def test_mcp_tools_reads_mcp_server_url(self):
        """Test that MCP tools read MCP_SERVER_URL from environment."""
        mcp_tools_file = os.path.join(os.path.dirname(__file__), "..", "..", "_shared", "mcp_tools.py")
        with open(mcp_tools_file, "r") as f:
            content = f.read()
        assert "MCP_SERVER_URL" in content, "Should read MCP_SERVER_URL from environment"
    
    def test_mcp_tools_syntax_valid(self):
        """Test that mcp_tools.py has valid Python syntax."""
        mcp_tools_file = os.path.join(os.path.dirname(__file__), "..", "..", "_shared", "mcp_tools.py")
        with open(mcp_tools_file, "r") as f:
            content = f.read()
        try:
            ast.parse(content)
        except SyntaxError as e:
            pytest.fail(f"Syntax error in _shared/mcp_tools.py: {e}")
    
    def test_agent_factory_includes_mcp_tools(self):
        """Test that agent_factory.py imports MCP tools."""
        agent_factory_file = os.path.join(os.path.dirname(__file__), "..", "..", "_shared", "agent_factory.py")
        with open(agent_factory_file, "r") as f:
            content = f.read()
        assert "get_mcp_tools" in content, "agent_factory should import get_mcp_tools"
    
    def test_direct_deploy_uses_shared_module(self):
        """Test that direct-deploy/agentcore_app.py uses _shared module (not duplicate code)."""
        direct_deploy_file = os.path.join(os.path.dirname(__file__), "..", "..", "direct-deploy", "agentcore_app.py")
        with open(direct_deploy_file, "r") as f:
            content = f.read()
        assert "from _shared import get_agent" in content, "direct-deploy should import get_agent from _shared"
        # Should NOT have actual agentsec.protect() call (only in comments is ok)
        # Count lines that start with agentsec.protect (ignoring comments)
        code_lines = [line for line in content.split('\n') if line.strip().startswith('agentsec.protect(')]
        assert len(code_lines) == 0, "direct-deploy should not duplicate agentsec.protect() config"
    
    def test_lambda_handler_uses_shared_module(self):
        """Test that lambda_handler.py uses _shared module (not duplicate code)."""
        lambda_handler_file = os.path.join(os.path.dirname(__file__), "..", "..", "lambda-deploy", "lambda_handler.py")
        with open(lambda_handler_file, "r") as f:
            content = f.read()
        assert "from _shared import get_agent" in content, "lambda_handler should import get_agent from _shared"
        # Should NOT have actual agentsec.protect() call (only in comments is ok)
        # Count lines that start with agentsec.protect (ignoring comments)
        code_lines = [line for line in content.split('\n') if line.strip().startswith('agentsec.protect(')]
        assert len(code_lines) == 0, "lambda_handler should not duplicate agentsec.protect() config"
