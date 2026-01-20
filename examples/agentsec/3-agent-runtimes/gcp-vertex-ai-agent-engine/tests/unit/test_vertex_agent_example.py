"""
Unit tests for GCP Vertex AI Agent Engine example.

These tests verify the structure, configuration, and basic functionality
of the example without making actual API calls.

Test Coverage:
- Example structure (directories, files, scripts)
- Tools module functionality (LangChain @tool decorated)
- Agent factory configuration (LangChain agent)
- FastAPI app endpoints
- Dockerfile structure
- Kubernetes configurations
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

    def test_deploy_directories_exist(self):
        """Test that all deploy directories exist with required files."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        deploy_modes = ["agent-engine-deploy", "cloud-run-deploy", "gke-deploy"]
        
        for deploy_mode in deploy_modes:
            deploy_dir = os.path.join(project_dir, deploy_mode)
            assert os.path.isdir(deploy_dir), f"{deploy_mode} directory should exist"
            assert os.path.isfile(os.path.join(deploy_dir, "app.py")), f"{deploy_mode}/app.py should exist"
            
            scripts_dir = os.path.join(deploy_dir, "scripts")
            assert os.path.isdir(scripts_dir), f"{deploy_mode}/scripts directory should exist"
            assert os.path.isfile(os.path.join(scripts_dir, "deploy.sh")), f"{deploy_mode}/scripts/deploy.sh should exist"
            assert os.path.isfile(os.path.join(scripts_dir, "invoke.sh")), f"{deploy_mode}/scripts/invoke.sh should exist"

    def test_cleanup_scripts_exist_for_cloud_deployments(self):
        """Test that cleanup scripts exist for Cloud Run and GKE."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        for deploy_mode in ["cloud-run-deploy", "gke-deploy"]:
            cleanup_script = os.path.join(project_dir, deploy_mode, "scripts", "cleanup.sh")
            assert os.path.isfile(cleanup_script), f"{deploy_mode}/scripts/cleanup.sh should exist"

    def test_dockerfiles_exist_for_containers(self):
        """Test that Dockerfiles exist for container deployments."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        for deploy_mode in ["cloud-run-deploy", "gke-deploy"]:
            dockerfile = os.path.join(project_dir, deploy_mode, "Dockerfile")
            assert os.path.isfile(dockerfile), f"{deploy_mode}/Dockerfile should exist"

    def test_requirements_files_exist(self):
        """Test that requirements.txt files exist for all deploy modes."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        for deploy_mode in ["agent-engine-deploy", "cloud-run-deploy", "gke-deploy"]:
            requirements = os.path.join(project_dir, deploy_mode, "requirements.txt")
            assert os.path.isfile(requirements), f"{deploy_mode}/requirements.txt should exist"
            
            # Verify agentsec is in requirements
            with open(requirements, "r") as f:
                content = f.read()
            assert "agentsec" in content, f"{deploy_mode}/requirements.txt should include agentsec"

    def test_kubernetes_configs_exist_for_gke(self):
        """Test that Kubernetes configs exist for GKE deployment."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        k8s_dir = os.path.join(project_dir, "gke-deploy", "k8s")
        
        assert os.path.isdir(k8s_dir), "gke-deploy/k8s directory should exist"
        assert os.path.isfile(os.path.join(k8s_dir, "deployment.yaml")), "deployment.yaml should exist"
        assert os.path.isfile(os.path.join(k8s_dir, "service.yaml")), "service.yaml should exist"

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
        assert "google-cloud-aiplatform" in content, "pyproject.toml should include google-cloud-aiplatform"
        assert "fastapi" in content, "pyproject.toml should include fastapi"


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
    """Test the agent factory module structure (LangChain-based agent)."""

    def test_agent_factory_imports_agentsec_first(self):
        """Test that agent_factory.py imports agentsec before AI libraries."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        agent_factory_path = os.path.join(project_dir, "_shared", "agent_factory.py")
        
        with open(agent_factory_path, "r") as f:
            content = f.read()
        
        # Find positions of key imports
        agentsec_pos = content.find("import agentsec")
        protect_pos = content.find("agentsec.protect(")
        langchain_pos = content.find("from langchain_google_vertexai")
        
        assert agentsec_pos != -1, "agentsec import should be present"
        assert protect_pos != -1, "agentsec.protect() should be present"
        assert langchain_pos != -1, "LangChain import should be present"
        
        # Verify order: agentsec.protect() must come before any AI library import
        assert protect_pos < langchain_pos, "agentsec.protect() must be called before importing LangChain"

    def test_agent_factory_uses_langchain(self):
        """Test that agent_factory.py uses LangChain ChatVertexAI."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        agent_factory_path = os.path.join(project_dir, "_shared", "agent_factory.py")
        
        with open(agent_factory_path, "r") as f:
            content = f.read()
        
        assert "from langchain_google_vertexai import ChatVertexAI" in content, "Should use ChatVertexAI from langchain-google-vertexai"
        assert "ChatVertexAI(" in content, "Should instantiate ChatVertexAI"

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

    def test_agent_factory_configures_gateway_mode(self):
        """Test that agent_factory.py has gateway mode configuration."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        agent_factory_path = os.path.join(project_dir, "_shared", "agent_factory.py")
        
        with open(agent_factory_path, "r") as f:
            content = f.read()
        
        assert "llm_integration_mode" in content, "Should configure llm_integration_mode"
        assert "AGENTSEC_LLM_INTEGRATION_MODE" in content, "Should read from AGENTSEC_LLM_INTEGRATION_MODE env var"
        assert "providers" in content, "Should configure providers"

    def test_agent_factory_configures_api_mode(self):
        """Test that agent_factory.py has API mode configuration."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        agent_factory_path = os.path.join(project_dir, "_shared", "agent_factory.py")
        
        with open(agent_factory_path, "r") as f:
            content = f.read()
        
        assert "api_mode_llm" in content, "Should configure api_mode_llm"
        assert "AGENTSEC_API_MODE_LLM" in content, "Should read from AGENTSEC_API_MODE_LLM env var"
        assert "api_mode_llm_endpoint" in content, "Should configure api endpoint"
        assert "api_mode_llm_api_key" in content, "Should configure api key"

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


class TestAppEndpoints:
    """Test the FastAPI app endpoints structure."""

    def test_cloud_run_app_has_required_endpoints(self):
        """Test that cloud-run app.py defines required endpoints."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        app_path = os.path.join(project_dir, "cloud-run-deploy", "app.py")
        
        with open(app_path, "r") as f:
            content = f.read()
        
        assert "@app.get(\"/health\")" in content, "Should have /health endpoint"
        assert "@app.post(\"/invoke\"" in content, "Should have /invoke endpoint"

    def test_gke_app_has_readiness_probe(self):
        """Test that GKE app.py has readiness probe endpoint."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        app_path = os.path.join(project_dir, "gke-deploy", "app.py")
        
        with open(app_path, "r") as f:
            content = f.read()
        
        assert "@app.get(\"/health\")" in content, "Should have /health endpoint"
        assert "@app.get(\"/ready\")" in content, "Should have /ready endpoint for K8s"
        assert "@app.post(\"/invoke\"" in content, "Should have /invoke endpoint"

    def test_agent_engine_app_structure(self):
        """Test that agent-engine app.py has correct structure."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        app_path = os.path.join(project_dir, "agent-engine-deploy", "app.py")
        
        with open(app_path, "r") as f:
            content = f.read()
        
        assert "invoke_agent" in content, "Should use invoke_agent from agent_factory"

    def test_apps_describe_langchain_agent(self):
        """Test that app.py files describe the LangChain agent."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        for deploy_mode in ["cloud-run-deploy", "gke-deploy"]:
            app_path = os.path.join(project_dir, deploy_mode, "app.py")
            
            with open(app_path, "r") as f:
                content = f.read()
            
            assert "LangChain" in content, f"{deploy_mode}/app.py should mention LangChain"


class TestDockerfiles:
    """Test Dockerfile structure and content."""

    def test_cloud_run_dockerfile_has_agentsec(self):
        """Test that Cloud Run Dockerfile includes agentsec."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        dockerfile = os.path.join(project_dir, "cloud-run-deploy", "Dockerfile")
        
        with open(dockerfile, "r") as f:
            content = f.read()
        
        assert "agentsec" in content.lower(), "Dockerfile should reference agentsec"
        assert "COPY" in content, "Dockerfile should copy files"
        assert "8080" in content, "Dockerfile should expose port 8080"

    def test_gke_dockerfile_has_agentsec(self):
        """Test that GKE Dockerfile includes agentsec."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        dockerfile = os.path.join(project_dir, "gke-deploy", "Dockerfile")
        
        with open(dockerfile, "r") as f:
            content = f.read()
        
        assert "agentsec" in content.lower(), "Dockerfile should reference agentsec"
        assert "COPY" in content, "Dockerfile should copy files"
        assert "8080" in content, "Dockerfile should expose port 8080"

    def test_dockerfiles_use_python_311(self):
        """Test that Dockerfiles use Python 3.11."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        for deploy_mode in ["cloud-run-deploy", "gke-deploy"]:
            dockerfile = os.path.join(project_dir, deploy_mode, "Dockerfile")
            
            with open(dockerfile, "r") as f:
                content = f.read()
            
            assert "python:3.11" in content, f"{deploy_mode}/Dockerfile should use Python 3.11"


class TestKubernetesConfigs:
    """Test Kubernetes configuration files."""

    def test_deployment_yaml_structure(self):
        """Test that deployment.yaml has correct structure."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        deployment = os.path.join(project_dir, "gke-deploy", "k8s", "deployment.yaml")
        
        with open(deployment, "r") as f:
            content = f.read()
        
        assert "apiVersion:" in content, "Should have apiVersion"
        assert "kind: Deployment" in content, "Should be a Deployment"
        assert "containerPort:" in content, "Should define container port"

    def test_service_yaml_structure(self):
        """Test that service.yaml has correct structure."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        service = os.path.join(project_dir, "gke-deploy", "k8s", "service.yaml")
        
        with open(service, "r") as f:
            content = f.read()
        
        assert "apiVersion:" in content, "Should have apiVersion"
        assert "kind: Service" in content, "Should be a Service"
        assert "LoadBalancer" in content, "Should use LoadBalancer type"


class TestDeployScripts:
    """Test deploy script structure and content."""

    def test_deploy_scripts_are_executable_format(self):
        """Test that deploy scripts have correct shebang."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        for deploy_mode in ["agent-engine-deploy", "cloud-run-deploy", "gke-deploy"]:
            deploy_script = os.path.join(project_dir, deploy_mode, "scripts", "deploy.sh")
            
            with open(deploy_script, "r") as f:
                first_line = f.readline()
            
            assert first_line.startswith("#!/"), f"{deploy_mode}/deploy.sh should have shebang"

    def test_cloud_run_deploy_has_gcloud_commands(self):
        """Test that Cloud Run deploy script uses gcloud."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        deploy_script = os.path.join(project_dir, "cloud-run-deploy", "scripts", "deploy.sh")
        
        with open(deploy_script, "r") as f:
            content = f.read()
        
        assert "gcloud" in content, "Should use gcloud CLI"
        assert "docker" in content, "Should use docker"
        assert "GOOGLE_CLOUD_PROJECT" in content, "Should reference GOOGLE_CLOUD_PROJECT"

    def test_gke_deploy_has_kubectl_commands(self):
        """Test that GKE deploy script uses kubectl."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        deploy_script = os.path.join(project_dir, "gke-deploy", "scripts", "deploy.sh")
        
        with open(deploy_script, "r") as f:
            content = f.read()
        
        assert "kubectl" in content, "Should use kubectl"
        assert "gcloud" in content, "Should use gcloud for cluster credentials"
        assert "docker" in content, "Should use docker"


class TestIntegrationTestScript:
    """Test the integration test script structure."""

    def test_integration_script_supports_all_modes(self):
        """Test that integration test script supports all deploy and integration modes."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        test_script = os.path.join(project_dir, "tests", "integration", "test-all-modes.sh")
        
        with open(test_script, "r") as f:
            content = f.read()
        
        # Deploy modes
        assert "agent-engine" in content, "Should support agent-engine mode"
        assert "cloud-run" in content, "Should support cloud-run mode"
        assert "gke" in content, "Should support gke mode"
        
        # Integration modes
        assert "--api" in content, "Should support --api flag"
        assert "--gateway" in content, "Should support --gateway flag"

    def test_integration_script_has_cleanup_option(self):
        """Test that integration test script has cleanup option."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        test_script = os.path.join(project_dir, "tests", "integration", "test-all-modes.sh")
        
        with open(test_script, "r") as f:
            content = f.read()
        
        assert "--cleanup" in content, "Should support --cleanup flag"

    def test_integration_script_has_quick_mode(self):
        """Test that integration test script has quick mode."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        test_script = os.path.join(project_dir, "tests", "integration", "test-all-modes.sh")
        
        with open(test_script, "r") as f:
            content = f.read()
        
        assert "--quick" in content, "Should support --quick flag"

    def test_integration_script_has_mcp_options(self):
        """Test that integration test script has MCP test options."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        test_script = os.path.join(project_dir, "tests", "integration", "test-all-modes.sh")
        
        with open(test_script, "r") as f:
            content = f.read()
        
        assert "--mcp-only" in content, "Should support --mcp-only flag"
        assert "--no-mcp" in content, "Should support --no-mcp flag"

    def test_integration_script_uses_tool_prompts(self):
        """Test that integration test script uses prompts that trigger tools."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        test_script = os.path.join(project_dir, "tests", "integration", "test-all-modes.sh")
        
        with open(test_script, "r") as f:
            content = f.read()
        
        # Check for prompts that trigger the check_service_health tool
        assert "Check the health" in content or "check_service_health" in content, \
            "Should use prompts that trigger tool execution"


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
        """Test that agent_factory.py includes MCP configuration."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        agent_factory_file = os.path.join(project_dir, "_shared", "agent_factory.py")
        with open(agent_factory_file, "r") as f:
            content = f.read()
        assert "mcp_integration_mode" in content, "agent_factory should configure mcp_integration_mode"
        assert "api_mode_mcp" in content, "agent_factory should configure api_mode_mcp"
    
    def test_init_exports_mcp_tools(self):
        """Test that __init__.py exports MCP tools."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        init_file = os.path.join(project_dir, "_shared", "__init__.py")
        with open(init_file, "r") as f:
            content = f.read()
        assert "fetch_url" in content, "__init__.py should export fetch_url"
        assert "get_mcp_tools" in content, "__init__.py should export get_mcp_tools"
    
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
        assert "langchain-google-vertexai" in content, "pyproject.toml should include langchain-google-vertexai"
    
    def test_mcp_integration_test_exists(self):
        """Test that MCP integration test script exists."""
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        test_script = os.path.join(project_dir, "tests", "integration", "test_mcp_protection.py")
        assert os.path.isfile(test_script), "tests/integration/test_mcp_protection.py should exist"
