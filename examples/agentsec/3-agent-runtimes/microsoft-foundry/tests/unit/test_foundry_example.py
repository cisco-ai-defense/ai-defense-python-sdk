"""
Unit tests for Microsoft Azure AI Foundry example.

These tests verify the structure, configuration, and basic functionality
of the example without making actual API calls.

Test Coverage:
- Example structure (directories, files, scripts)
- Tools module functionality (LangChain @tool decorated)
- Agent factory configuration (LangChain agent with AzureChatOpenAI)
- Flask app endpoints
- Dockerfile structure
- Azure Functions configuration
- agentsec integration patterns
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest


class TestExampleStructure:
    """Test that the example has the correct structure."""

    def test_shared_module_exists(self):
        """Test that _shared module directory exists with required files."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        shared_dir = os.path.join(project_dir, "_shared")
        
        assert os.path.isdir(shared_dir), "_shared directory should exist"
        assert os.path.isfile(os.path.join(shared_dir, "__init__.py")), "_shared/__init__.py should exist"
        assert os.path.isfile(os.path.join(shared_dir, "agent_factory.py")), "_shared/agent_factory.py should exist"
        assert os.path.isfile(os.path.join(shared_dir, "tools.py")), "_shared/tools.py should exist"
        assert os.path.isfile(os.path.join(shared_dir, "mcp_tools.py")), "_shared/mcp_tools.py should exist"

    def test_deploy_directories_exist(self):
        """Test that all deploy directories exist with required files."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        deploy_modes = ["foundry-agent-app", "azure-functions", "foundry-container"]
        
        for deploy_mode in deploy_modes:
            deploy_dir = os.path.join(project_dir, deploy_mode)
            assert os.path.isdir(deploy_dir), f"{deploy_mode} directory should exist"
            
            scripts_dir = os.path.join(deploy_dir, "scripts")
            assert os.path.isdir(scripts_dir), f"{deploy_mode}/scripts directory should exist"
            assert os.path.isfile(os.path.join(scripts_dir, "deploy.sh")), f"{deploy_mode}/scripts/deploy.sh should exist"
            assert os.path.isfile(os.path.join(scripts_dir, "invoke.sh")), f"{deploy_mode}/scripts/invoke.sh should exist"

    def test_app_files_exist(self):
        """Test that app files exist for each deployment mode."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        # Check main.py for Azure ML managed endpoint deployments
        for deploy_mode in ["foundry-agent-app", "foundry-container"]:
            main_file = os.path.join(project_dir, deploy_mode, "main.py")
            assert os.path.isfile(main_file), f"{deploy_mode}/main.py should exist"
        
        # Check Azure Functions app
        function_app = os.path.join(project_dir, "azure-functions", "function_app.py")
        assert os.path.isfile(function_app), "azure-functions/function_app.py should exist"

    def test_dockerfile_exists_for_container(self):
        """Test that Dockerfile exists for container deployment."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        dockerfile = os.path.join(project_dir, "foundry-container", "Dockerfile")
        assert os.path.isfile(dockerfile), "foundry-container/Dockerfile should exist"

    def test_host_json_exists_for_azure_functions(self):
        """Test that host.json exists for Azure Functions."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        host_json = os.path.join(project_dir, "azure-functions", "host.json")
        assert os.path.isfile(host_json), "azure-functions/host.json should exist"

    def test_requirements_files_exist(self):
        """Test that requirements.txt files exist for all deploy modes."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        for deploy_mode in ["foundry-agent-app", "azure-functions", "foundry-container"]:
            requirements = os.path.join(project_dir, deploy_mode, "requirements.txt")
            assert os.path.isfile(requirements), f"{deploy_mode}/requirements.txt should exist"

    def test_integration_tests_exist(self):
        """Test that integration test script exists."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        test_script = os.path.join(project_dir, "tests", "integration", "test-all-modes.sh")
        
        assert os.path.isfile(test_script), "tests/integration/test-all-modes.sh should exist"

    def test_pyproject_toml_exists(self):
        """Test that pyproject.toml exists with correct dependencies."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        pyproject = os.path.join(project_dir, "pyproject.toml")
        
        assert os.path.isfile(pyproject), "pyproject.toml should exist"
        
        with open(pyproject, "r") as f:
            content = f.read()
        
        assert "agentsec" in content, "pyproject.toml should reference agentsec"
        assert "langchain-openai" in content, "pyproject.toml should include langchain-openai"
        assert "flask" in content, "pyproject.toml should include flask"


class TestToolsModule:
    """Test the tools module functionality with LangChain @tool decorators."""

    def test_tools_use_langchain_decorator(self):
        """Test that tools use LangChain @tool decorator."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        tools_file = os.path.join(project_dir, "_shared", "tools.py")
        
        with open(tools_file, "r") as f:
            content = f.read()
        
        assert "from langchain_core.tools import tool" in content, "Should import langchain_core.tools.tool"
        assert "@tool" in content, "Should use @tool decorator"

    def test_check_service_health_is_tool(self):
        """Test that check_service_health is a LangChain tool."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        tools_file = os.path.join(project_dir, "_shared", "tools.py")
        
        with open(tools_file, "r") as f:
            content = f.read()
        
        # Check for @tool decorator before function definition
        assert "@tool\ndef check_service_health" in content, "check_service_health should be decorated with @tool"

    def test_get_recent_logs_is_tool(self):
        """Test that get_recent_logs is a LangChain tool."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        tools_file = os.path.join(project_dir, "_shared", "tools.py")
        
        with open(tools_file, "r") as f:
            content = f.read()
        
        assert "@tool\ndef get_recent_logs" in content, "get_recent_logs should be decorated with @tool"

    def test_calculate_capacity_is_tool(self):
        """Test that calculate_capacity is a LangChain tool."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        tools_file = os.path.join(project_dir, "_shared", "tools.py")
        
        with open(tools_file, "r") as f:
            content = f.read()
        
        assert "@tool\ndef calculate_capacity" in content, "calculate_capacity should be decorated with @tool"

    def test_tools_list_exports_all_tools(self):
        """Test that TOOLS list exports all tool functions."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        tools_file = os.path.join(project_dir, "_shared", "tools.py")
        
        with open(tools_file, "r") as f:
            content = f.read()
        
        assert "TOOLS = [" in content, "TOOLS list should be defined"
        assert "check_service_health" in content, "TOOLS should include check_service_health"
        assert "get_recent_logs" in content, "TOOLS should include get_recent_logs"
        assert "calculate_capacity" in content, "TOOLS should include calculate_capacity"


class TestAgentFactoryStructure:
    """Test the agent factory module structure (LangChain-based agent with Azure OpenAI)."""

    def test_agent_factory_imports_agentsec_first(self):
        """Test that agent_factory.py imports agentsec (via aidefense) before AI libraries."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        agent_factory_path = os.path.join(project_dir, "_shared", "agent_factory.py")
        
        with open(agent_factory_path, "r") as f:
            content = f.read()
        
        # Find positions of key imports (using aidefense.runtime import agentsec)
        aidefense_pos = content.find("from aidefense.runtime import agentsec")
        protect_pos = content.find("agentsec.protect(")
        langchain_pos = content.find("from langchain_openai")
        
        assert aidefense_pos != -1, "aidefense.runtime import should be present"
        assert protect_pos != -1, "agentsec.protect() call should be present"
        assert langchain_pos != -1, "LangChain import should be present"
        
        # Verify order: protect() must come before any AI library import
        assert protect_pos < langchain_pos, "agentsec.protect() must be called before importing LangChain"

    def test_agent_factory_uses_azure_chat_openai(self):
        """Test that agent_factory.py uses AzureChatOpenAI."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        agent_factory_path = os.path.join(project_dir, "_shared", "agent_factory.py")
        
        with open(agent_factory_path, "r") as f:
            content = f.read()
        
        assert "from langchain_openai import AzureChatOpenAI" in content, "Should use AzureChatOpenAI from langchain-openai"
        assert "AzureChatOpenAI(" in content, "Should instantiate AzureChatOpenAI"

    def test_agent_factory_binds_tools(self):
        """Test that agent_factory.py binds tools to LLM."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        agent_factory_path = os.path.join(project_dir, "_shared", "agent_factory.py")
        
        with open(agent_factory_path, "r") as f:
            content = f.read()
        
        assert ".bind_tools(" in content, "Should bind tools to LLM using bind_tools()"

    def test_agent_factory_has_agent_loop(self):
        """Test that agent_factory.py implements an agent loop."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        agent_factory_path = os.path.join(project_dir, "_shared", "agent_factory.py")
        
        with open(agent_factory_path, "r") as f:
            content = f.read()
        
        assert "def _run_agent_loop" in content, "Should define agent loop function"
        assert "tool_calls" in content, "Should check for tool_calls"
        assert "ToolMessage" in content, "Should use ToolMessage for tool results"

    def test_agent_factory_uses_yaml_config(self):
        """Test that agent_factory.py uses agentsec.yaml config file."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        agent_factory_path = os.path.join(project_dir, "_shared", "agent_factory.py")
        
        with open(agent_factory_path, "r") as f:
            content = f.read()
        
        assert "agentsec.yaml" in content, "Should reference agentsec.yaml config file"
        assert "config=" in content, "Should pass config= parameter to agentsec.protect()"

    def test_agent_factory_has_invoke_function(self):
        """Test that agent_factory.py exports invoke_agent function."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        agent_factory_path = os.path.join(project_dir, "_shared", "agent_factory.py")
        
        with open(agent_factory_path, "r") as f:
            content = f.read()
        
        assert "def invoke_agent" in content, "Should define invoke_agent function"

    def test_agent_factory_imports_tools(self):
        """Test that agent_factory.py imports both local and MCP tools."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        agent_factory_path = os.path.join(project_dir, "_shared", "agent_factory.py")
        
        with open(agent_factory_path, "r") as f:
            content = f.read()
        
        assert "from .tools import TOOLS" in content, "Should import TOOLS from tools module"
        assert "from .mcp_tools import get_mcp_tools" in content, "Should import get_mcp_tools from mcp_tools module"

    def test_agent_factory_uses_azure_openai_env_vars(self):
        """Test that agent_factory.py reads Azure OpenAI configuration from env vars."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        agent_factory_path = os.path.join(project_dir, "_shared", "agent_factory.py")
        
        with open(agent_factory_path, "r") as f:
            content = f.read()
        
        assert "AZURE_OPENAI_ENDPOINT" in content, "Should read AZURE_OPENAI_ENDPOINT"
        assert "AZURE_OPENAI_API_KEY" in content, "Should read AZURE_OPENAI_API_KEY"


class TestAppEndpoints:
    """Test the Flask app endpoints structure."""

    def test_foundry_agent_app_has_required_endpoints(self):
        """Test that foundry-agent-app has required Azure ML interface (init/run)."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        # For Azure ML managed endpoints, we use main.py with init()/run() pattern
        main_path = os.path.join(project_dir, "foundry-agent-app", "main.py")
        
        with open(main_path, "r") as f:
            content = f.read()
        
        assert "def init():" in content, "Should have init() function for Azure ML"
        assert "def run(" in content, "Should have run() function for Azure ML"
        assert "invoke_agent" in content, "Should use invoke_agent from agent_factory"

    def test_foundry_container_app_has_required_interface(self):
        """Test that foundry-container has required Azure ML interface (init/run)."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        main_path = os.path.join(project_dir, "foundry-container", "main.py")
        
        with open(main_path, "r") as f:
            content = f.read()
        
        assert "def init():" in content, "Should have init() function for Azure ML"
        assert "def run(" in content, "Should have run() function for Azure ML"
        assert "invoke_agent" in content, "Should use invoke_agent from agent_factory"

    def test_azure_functions_has_required_routes(self):
        """Test that azure-functions has required routes."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        app_path = os.path.join(project_dir, "azure-functions", "function_app.py")
        
        with open(app_path, "r") as f:
            content = f.read()
        
        assert 'route="invoke"' in content or "route=invoke" in content, "Should have invoke route"
        assert 'route="health"' in content or "route=health" in content, "Should have health route"

    def test_main_files_import_agent_factory(self):
        """Test that main.py files import from agent_factory."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        for deploy_mode in ["foundry-agent-app", "foundry-container"]:
            main_path = os.path.join(project_dir, deploy_mode, "main.py")
            
            with open(main_path, "r") as f:
                content = f.read()
            
            assert "invoke_agent" in content, f"{deploy_mode}/main.py should use invoke_agent"

    def test_azure_functions_imports_agent_factory(self):
        """Test that Azure Functions imports from agent_factory."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        app_path = os.path.join(project_dir, "azure-functions", "function_app.py")
        
        with open(app_path, "r") as f:
            content = f.read()
        
        assert "invoke_agent" in content, "function_app.py should use invoke_agent"


class TestDockerfile:
    """Test Dockerfile structure and content."""

    def test_dockerfile_has_agentsec(self):
        """Test that Dockerfile includes agentsec."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        dockerfile = os.path.join(project_dir, "foundry-container", "Dockerfile")
        
        with open(dockerfile, "r") as f:
            content = f.read()
        
        assert "agentsec" in content.lower(), "Dockerfile should reference agentsec"
        assert "COPY" in content, "Dockerfile should copy files"
        # Azure ML managed endpoints use port 5001 externally (31311 internally)
        assert "5001" in content, "Dockerfile should expose port 5001 for Azure ML"

    def test_dockerfile_uses_python_310(self):
        """Test that Dockerfile uses Python 3.10."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        dockerfile = os.path.join(project_dir, "foundry-container", "Dockerfile")
        
        with open(dockerfile, "r") as f:
            content = f.read()
        
        # Python 3.10 is used for broader compatibility with Azure ML
        assert "python:3.10" in content, "Dockerfile should use Python 3.10"

    def test_dockerfile_has_main_py_for_azure_ml(self):
        """Test that Dockerfile copies main.py for Azure ML inference server."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        dockerfile = os.path.join(project_dir, "foundry-container", "Dockerfile")
        
        with open(dockerfile, "r") as f:
            content = f.read()
        
        # Azure ML managed endpoints require main.py with init()/run() at /var/azureml-app
        assert "main.py" in content, "Dockerfile should copy main.py"
        assert "/var/azureml-app" in content, "Dockerfile should use /var/azureml-app for Azure ML"


class TestAzureFunctionsConfig:
    """Test Azure Functions configuration."""

    def test_host_json_structure(self):
        """Test that host.json has correct structure."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        host_json = os.path.join(project_dir, "azure-functions", "host.json")
        
        with open(host_json, "r") as f:
            content = f.read()
        
        assert '"version"' in content, "host.json should have version"
        assert '"extensionBundle"' in content, "host.json should have extensionBundle"

    def test_function_app_uses_v2_model(self):
        """Test that function_app.py uses Azure Functions v2 programming model."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        app_path = os.path.join(project_dir, "azure-functions", "function_app.py")
        
        with open(app_path, "r") as f:
            content = f.read()
        
        assert "import azure.functions as func" in content, "Should import azure.functions"
        assert "FunctionApp" in content, "Should use FunctionApp (v2 model)"
        assert "@app.route" in content, "Should use @app.route decorator (v2 model)"


class TestDeployScripts:
    """Test deploy script structure and content."""

    def test_deploy_scripts_are_executable_format(self):
        """Test that deploy scripts have correct shebang."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        for deploy_mode in ["foundry-agent-app", "azure-functions", "foundry-container"]:
            deploy_script = os.path.join(project_dir, deploy_mode, "scripts", "deploy.sh")
            
            with open(deploy_script, "r") as f:
                first_line = f.readline()
            
            assert first_line.startswith("#!/"), f"{deploy_mode}/deploy.sh should have shebang"

    def test_foundry_agent_app_deploy_has_az_commands(self):
        """Test that foundry-agent-app deploy script uses Azure CLI."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        deploy_script = os.path.join(project_dir, "foundry-agent-app", "scripts", "deploy.sh")
        
        with open(deploy_script, "r") as f:
            content = f.read()
        
        assert "az" in content, "Should use az CLI"
        assert "AZURE_SUBSCRIPTION_ID" in content, "Should reference AZURE_SUBSCRIPTION_ID"

    def test_azure_functions_deploy_has_func_commands(self):
        """Test that azure-functions deploy script uses Azure Functions Core Tools."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        deploy_script = os.path.join(project_dir, "azure-functions", "scripts", "deploy.sh")
        
        with open(deploy_script, "r") as f:
            content = f.read()
        
        assert "func" in content, "Should use func CLI"
        assert "AZURE_FUNCTION_APP_NAME" in content, "Should reference AZURE_FUNCTION_APP_NAME"

    def test_foundry_container_deploy_has_acr_commands(self):
        """Test that foundry-container deploy script uses ACR."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        deploy_script = os.path.join(project_dir, "foundry-container", "scripts", "deploy.sh")
        
        with open(deploy_script, "r") as f:
            content = f.read()
        
        assert "az acr" in content, "Should use az acr for container registry"
        assert "AZURE_ACR_NAME" in content, "Should reference AZURE_ACR_NAME"


class TestIntegrationTestScript:
    """Test the integration test script structure."""

    def test_integration_script_supports_all_modes(self):
        """Test that integration test script supports all deploy and integration modes."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        test_script = os.path.join(project_dir, "tests", "integration", "test-all-modes.sh")
        
        with open(test_script, "r") as f:
            content = f.read()
        
        # Deploy modes
        assert "agent-app" in content, "Should support agent-app mode"
        assert "azure-functions" in content, "Should support azure-functions mode"
        assert "container" in content, "Should support container mode"
        
        # Integration modes
        assert "--api" in content, "Should support --api flag"
        assert "--gateway" in content, "Should support --gateway flag"

    def test_integration_script_has_mcp_options(self):
        """Test that integration test script has MCP test options."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        test_script = os.path.join(project_dir, "tests", "integration", "test-all-modes.sh")
        
        with open(test_script, "r") as f:
            content = f.read()
        
        assert "--mcp-only" in content, "Should support --mcp-only flag"
        assert "--no-mcp" in content, "Should support --no-mcp flag"


class TestMCPTools:
    """Tests for MCP tool integration with LangChain."""
    
    def test_mcp_tools_file_exists(self):
        """Test that _shared/mcp_tools.py exists."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        mcp_tools_file = os.path.join(project_dir, "_shared", "mcp_tools.py")
        assert os.path.isfile(mcp_tools_file), "_shared/mcp_tools.py should exist"
    
    def test_mcp_tools_use_langchain_decorator(self):
        """Test that MCP tools use LangChain @tool decorator."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        mcp_tools_file = os.path.join(project_dir, "_shared", "mcp_tools.py")
        
        with open(mcp_tools_file, "r") as f:
            content = f.read()
        
        assert "from langchain_core.tools import tool" in content, "Should import langchain_core.tools.tool"
        assert "@tool" in content, "Should use @tool decorator"
    
    def test_fetch_url_is_langchain_tool(self):
        """Test that fetch_url is a LangChain tool."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        mcp_tools_file = os.path.join(project_dir, "_shared", "mcp_tools.py")
        
        with open(mcp_tools_file, "r") as f:
            content = f.read()
        
        assert "@tool\ndef fetch_url(" in content, "fetch_url should be decorated with @tool"
    
    def test_get_mcp_tools_function_exists(self):
        """Test that get_mcp_tools function exists."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        mcp_tools_file = os.path.join(project_dir, "_shared", "mcp_tools.py")
        with open(mcp_tools_file, "r") as f:
            content = f.read()
        assert "def get_mcp_tools(" in content, "Should define get_mcp_tools function"
    
    def test_mcp_tools_uses_mcp_client(self):
        """Test that MCP tools import MCP client."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        mcp_tools_file = os.path.join(project_dir, "_shared", "mcp_tools.py")
        with open(mcp_tools_file, "r") as f:
            content = f.read()
        assert "streamablehttp_client" in content, "Should import MCP streamablehttp_client"
        assert "ClientSession" in content, "Should import MCP ClientSession"
    
    def test_mcp_tools_calls_session_call_tool(self):
        """Test that MCP tools use session.call_tool (which agentsec intercepts)."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        mcp_tools_file = os.path.join(project_dir, "_shared", "mcp_tools.py")
        with open(mcp_tools_file, "r") as f:
            content = f.read()
        assert "session.call_tool" in content or "await session.call_tool" in content, \
            "Should use session.call_tool which agentsec intercepts"
    
    def test_mcp_tools_reads_mcp_server_url(self):
        """Test that MCP tools read MCP_SERVER_URL from environment."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        mcp_tools_file = os.path.join(project_dir, "_shared", "mcp_tools.py")
        with open(mcp_tools_file, "r") as f:
            content = f.read()
        assert "MCP_SERVER_URL" in content, "Should read MCP_SERVER_URL from environment"
    
    def test_agent_factory_has_mcp_config(self):
        """Test that agent_factory.py includes MCP tool support."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        agent_factory_file = os.path.join(project_dir, "_shared", "agent_factory.py")
        with open(agent_factory_file, "r") as f:
            content = f.read()
        assert "mcp_tools" in content, "agent_factory should reference mcp_tools"
        assert "agentsec.yaml" in content, "agent_factory should use agentsec.yaml for MCP config"
    
    def test_pyproject_has_mcp_dependency(self):
        """Test that pyproject.toml includes mcp dependency."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        pyproject_file = os.path.join(project_dir, "pyproject.toml")
        with open(pyproject_file, "r") as f:
            content = f.read()
        assert "mcp" in content, "pyproject.toml should include mcp dependency"
    
    def test_pyproject_has_langchain_dependency(self):
        """Test that pyproject.toml includes LangChain dependencies."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        pyproject_file = os.path.join(project_dir, "pyproject.toml")
        with open(pyproject_file, "r") as f:
            content = f.read()
        assert "langchain" in content, "pyproject.toml should include langchain dependency"
        assert "langchain-openai" in content, "pyproject.toml should include langchain-openai"
    
    def test_mcp_integration_test_exists(self):
        """Test that MCP integration test script exists."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        test_script = os.path.join(project_dir, "tests", "integration", "test_mcp_protection.py")
        assert os.path.isfile(test_script), "tests/integration/test_mcp_protection.py should exist"
