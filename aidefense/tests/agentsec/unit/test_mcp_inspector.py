"""Tests for MCPInspector with real API integration."""

import os
from unittest.mock import patch, MagicMock
import pytest
import httpx

from aidefense.runtime.agentsec.inspectors.api_mcp import MCPInspector
from aidefense.runtime.agentsec.decision import Decision
from aidefense.runtime.agentsec.exceptions import SecurityPolicyError


class TestMCPInspectorConstructor:
    """Test MCPInspector constructor and initialization (Task Group 2)."""

    def test_constructor_with_explicit_params(self):
        """Test constructor with explicit api_key and endpoint params."""
        inspector = MCPInspector(
            api_key="explicit-key",
            endpoint="https://explicit.example.com",
            timeout_ms=2000,
            retry_attempts=3,
            fail_open=False,
        )
        
        assert inspector.api_key == "explicit-key"
        assert inspector.endpoint == "https://explicit.example.com"
        assert inspector.timeout_ms == 2000
        assert inspector.retry_attempts == 3
        assert inspector.fail_open is False
        inspector.close()

    def test_constructor_env_var_fallback_mcp_specific(self):
        """Test constructor falls back to MCP-specific env vars."""
        env_vars = {
            "AI_DEFENSE_API_MODE_MCP_API_KEY": "mcp-key",
            "AI_DEFENSE_API_MODE_MCP_ENDPOINT": "https://mcp.example.com",
            "AI_DEFENSE_API_MODE_LLM_API_KEY": "general-key",
            "AI_DEFENSE_API_MODE_LLM_ENDPOINT": "https://general.example.com",
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            inspector = MCPInspector()
            
            # Should use MCP-specific vars
            assert inspector.api_key == "mcp-key"
            assert inspector.endpoint == "https://mcp.example.com"
            inspector.close()

    def test_constructor_env_var_fallback_general(self):
        """Test constructor falls back to general env vars when MCP not set."""
        env_vars = {
            "AI_DEFENSE_API_MODE_LLM_API_KEY": "general-key",
            "AI_DEFENSE_API_MODE_LLM_ENDPOINT": "https://general.example.com",
        }
        
        # Clear MCP-specific vars
        with patch.dict(os.environ, env_vars, clear=False):
            os.environ.pop("AI_DEFENSE_API_MODE_MCP_API_KEY", None)
            os.environ.pop("AI_DEFENSE_API_MODE_MCP_ENDPOINT", None)
            
            inspector = MCPInspector()
            
            # Should fall back to general vars
            assert inspector.api_key == "general-key"
            assert inspector.endpoint == "https://general.example.com"
            inspector.close()

    def test_constructor_defaults(self):
        """Test constructor default values."""
        # Clear all env vars
        with patch.dict(os.environ, {}, clear=False):
            for var in ["AI_DEFENSE_API_MODE_MCP_API_KEY", "AI_DEFENSE_API_MODE_MCP_ENDPOINT",
                       "AI_DEFENSE_API_MODE_LLM_API_KEY", "AI_DEFENSE_API_MODE_LLM_ENDPOINT"]:
                os.environ.pop(var, None)
            
            inspector = MCPInspector()
            
            assert inspector.api_key is None
            assert inspector.endpoint is None
            assert inspector.timeout_ms == 1000
            assert inspector.retry_attempts == 1
            assert inspector.fail_open is True
            assert inspector._request_id_counter == 0
            inspector.close()

    def test_http_client_created(self):
        """Test that HTTP client is created correctly."""
        inspector = MCPInspector(api_key="test", endpoint="https://test.com")
        
        assert inspector._sync_client is not None
        assert isinstance(inspector._sync_client, httpx.Client)
        inspector.close()


class TestMCPInspectorRequestBuilding:
    """Test JSON-RPC message building methods."""

    def test_build_request_message(self):
        """Test building JSON-RPC 2.0 request message."""
        inspector = MCPInspector()
        
        message = inspector._build_request_message(
            tool_name="search_docs",
            arguments={"query": "test", "max_results": 5},
        )
        
        assert message["jsonrpc"] == "2.0"
        assert message["method"] == "tools/call"
        assert message["params"]["name"] == "search_docs"
        assert message["params"]["arguments"] == {"query": "test", "max_results": 5}
        assert message["id"] == 1
        inspector.close()

    def test_build_request_message_increments_id(self):
        """Test that request IDs increment."""
        inspector = MCPInspector()
        
        msg1 = inspector._build_request_message("tool1", {})
        msg2 = inspector._build_request_message("tool2", {})
        msg3 = inspector._build_request_message("tool3", {})
        
        assert msg1["id"] == 1
        assert msg2["id"] == 2
        assert msg3["id"] == 3
        inspector.close()

    def test_build_request_message_prompts_get(self):
        """Test building JSON-RPC 2.0 request message for prompts/get."""
        inspector = MCPInspector()
        
        message = inspector._build_request_message(
            tool_name="code_review_prompt",
            arguments={"language": "python", "style": "detailed"},
            method="prompts/get",
        )
        
        assert message["jsonrpc"] == "2.0"
        assert message["method"] == "prompts/get"
        assert message["params"]["name"] == "code_review_prompt"
        assert message["params"]["arguments"] == {"language": "python", "style": "detailed"}
        inspector.close()

    def test_build_request_message_resources_read(self):
        """Test building JSON-RPC 2.0 request message for resources/read."""
        inspector = MCPInspector()
        
        message = inspector._build_request_message(
            tool_name="file:///path/to/config.yaml",
            arguments={},
            method="resources/read",
        )
        
        assert message["jsonrpc"] == "2.0"
        assert message["method"] == "resources/read"
        assert message["params"]["uri"] == "file:///path/to/config.yaml"
        # resources/read doesn't include arguments, only uri
        assert "arguments" not in message["params"]
        inspector.close()

    def test_build_response_message_string_result(self):
        """Test building response message with string result."""
        inspector = MCPInspector()
        
        message = inspector._build_response_message("Hello, world!")
        
        assert message["jsonrpc"] == "2.0"
        assert message["result"]["content"][0]["type"] == "text"
        assert message["result"]["content"][0]["text"] == "Hello, world!"
        inspector.close()

    def test_build_response_message_dict_result(self):
        """Test building response message with dict result."""
        inspector = MCPInspector()
        
        result = {"status": "success", "data": [1, 2, 3]}
        message = inspector._build_response_message(result)
        
        assert message["result"]["content"][0]["text"] == '{"status": "success", "data": [1, 2, 3]}'
        inspector.close()

    def test_build_response_message_list_result(self):
        """Test building response message with list result."""
        inspector = MCPInspector()
        
        message = inspector._build_response_message([1, 2, 3])
        
        assert message["result"]["content"][0]["text"] == "[1, 2, 3]"
        inspector.close()


class TestMCPInspectorResponseParsing:
    """Test API response parsing."""

    def test_parse_allow_response(self):
        """Test parsing Allow response."""
        inspector = MCPInspector()
        
        response = {
            "jsonrpc": "2.0",
            "result": {
                "is_safe": True,
                "action": "Allow",
                "severity": "NONE_SEVERITY",
                "rules": [],
                "classifications": [],
            },
            "id": 1,
        }
        
        decision = inspector._parse_mcp_response(response)
        
        assert decision.action == "allow"
        inspector.close()

    def test_parse_block_response_by_action(self):
        """Test parsing Block response based on action field."""
        inspector = MCPInspector()
        
        response = {
            "jsonrpc": "2.0",
            "result": {
                "is_safe": False,
                "action": "Block",
                "severity": "HIGH",
                "rules": [
                    {
                        "rule_name": "Code Detection",
                        "classification": "SECURITY_VIOLATION",
                    }
                ],
                "classifications": ["SECURITY_VIOLATION"],
            },
            "id": 1,
        }
        
        decision = inspector._parse_mcp_response(response)
        
        assert decision.action == "block"
        assert "Code Detection: SECURITY_VIOLATION" in decision.reasons
        inspector.close()

    def test_parse_block_response_by_is_safe(self):
        """Test parsing block response based on is_safe=false."""
        inspector = MCPInspector()
        
        response = {
            "jsonrpc": "2.0",
            "result": {
                "is_safe": False,
                "action": "Allow",  # Even if action says Allow
                "severity": "MEDIUM",
                "rules": [],
                "explanation": "Potentially unsafe content",
            },
            "id": 1,
        }
        
        decision = inspector._parse_mcp_response(response)
        
        # Should block because is_safe is False
        assert decision.action == "block"
        assert "Potentially unsafe content" in decision.reasons
        inspector.close()

    def test_parse_response_with_attack_technique(self):
        """Test parsing response with attack technique."""
        inspector = MCPInspector()
        
        response = {
            "jsonrpc": "2.0",
            "result": {
                "is_safe": False,
                "action": "Block",
                "severity": "HIGH",
                "attack_technique": "SQL_INJECTION",
                "rules": [],
            },
            "id": 1,
        }
        
        decision = inspector._parse_mcp_response(response)
        
        assert decision.action == "block"
        assert any("SQL_INJECTION" in r for r in decision.reasons)
        inspector.close()


class TestMCPInspectorInspectRequest:
    """Test inspect_request method (Task Group 3)."""

    def test_inspect_request_no_api_configured(self):
        """Test inspect_request allows when no API configured."""
        with patch.dict(os.environ, {}, clear=False):
            for var in ["AI_DEFENSE_API_MODE_MCP_API_KEY", "AI_DEFENSE_API_MODE_MCP_ENDPOINT",
                       "AI_DEFENSE_API_MODE_LLM_API_KEY", "AI_DEFENSE_API_MODE_LLM_ENDPOINT"]:
                os.environ.pop(var, None)
            
            inspector = MCPInspector()
            
            decision = inspector.inspect_request(
                tool_name="test_tool",
                arguments={"arg": "value"},
                metadata={},
            )
            
            assert decision.action == "allow"
            inspector.close()

    def test_inspect_request_allow(self):
        """Test inspect_request returns allow for safe request."""
        inspector = MCPInspector(
            api_key="test-key",
            endpoint="https://test.example.com",
        )
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "result": {
                "is_safe": True,
                "action": "Allow",
                "severity": "NONE_SEVERITY",
                "rules": [],
            },
            "id": 1,
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(inspector._sync_client, 'post', return_value=mock_response):
            decision = inspector.inspect_request(
                tool_name="search_docs",
                arguments={"query": "safe query"},
                metadata={},
            )
            
            assert decision.action == "allow"
        
        inspector.close()

    def test_inspect_request_block(self):
        """Test inspect_request returns block for unsafe request."""
        inspector = MCPInspector(
            api_key="test-key",
            endpoint="https://test.example.com",
        )
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "result": {
                "is_safe": False,
                "action": "Block",
                "severity": "HIGH",
                "rules": [{"rule_name": "Violence", "classification": "SAFETY_VIOLATION"}],
            },
            "id": 1,
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(inspector._sync_client, 'post', return_value=mock_response):
            decision = inspector.inspect_request(
                tool_name="search_docs",
                arguments={"query": "how to make a bomb"},
                metadata={},
            )
            
            assert decision.action == "block"
        
        inspector.close()

    def test_inspect_request_api_error_fail_open_true(self):
        """Test inspect_request allows on API error when fail_open=True."""
        inspector = MCPInspector(
            api_key="test-key",
            endpoint="https://test.example.com",
            fail_open=True,
        )
        
        with patch.object(inspector._sync_client, 'post', side_effect=httpx.ConnectError("Connection failed")):
            decision = inspector.inspect_request(
                tool_name="test_tool",
                arguments={},
                metadata={},
            )
            
            assert decision.action == "allow"
            assert "fail_open=True" in decision.reasons[0]
        
        inspector.close()

    def test_inspect_request_api_error_fail_open_false(self):
        """Test inspect_request raises SecurityPolicyError when fail_open=False."""
        inspector = MCPInspector(
            api_key="test-key",
            endpoint="https://test.example.com",
            fail_open=False,
        )
        
        with patch.object(inspector._sync_client, 'post', side_effect=httpx.ConnectError("Connection failed")):
            with pytest.raises(SecurityPolicyError) as exc_info:
                inspector.inspect_request(
                    tool_name="test_tool",
                    arguments={},
                    metadata={},
                )
            
            assert exc_info.value.decision.action == "block"
        
        inspector.close()

    def test_inspect_request_prompts_get(self):
        """Test inspect_request with prompts/get method."""
        inspector = MCPInspector(
            api_key="test-key",
            endpoint="https://test.example.com",
        )
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "result": {
                "is_safe": True,
                "action": "Allow",
                "severity": "NONE_SEVERITY",
                "rules": [],
            },
            "id": 1,
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(inspector._sync_client, 'post', return_value=mock_response) as mock_post:
            decision = inspector.inspect_request(
                tool_name="code_review_prompt",
                arguments={"language": "python"},
                metadata={},
                method="prompts/get",
            )
            
            assert decision.action == "allow"
            # Verify the request was built with prompts/get method
            call_args = mock_post.call_args
            request_body = call_args.kwargs.get('json') or call_args[1].get('json')
            assert request_body["method"] == "prompts/get"
        
        inspector.close()

    def test_inspect_request_resources_read(self):
        """Test inspect_request with resources/read method."""
        inspector = MCPInspector(
            api_key="test-key",
            endpoint="https://test.example.com",
        )
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "result": {
                "is_safe": True,
                "action": "Allow",
                "severity": "NONE_SEVERITY",
                "rules": [],
            },
            "id": 1,
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(inspector._sync_client, 'post', return_value=mock_response) as mock_post:
            decision = inspector.inspect_request(
                tool_name="file:///config.yaml",
                arguments={},
                metadata={},
                method="resources/read",
            )
            
            assert decision.action == "allow"
            # Verify the request was built with resources/read method
            call_args = mock_post.call_args
            request_body = call_args.kwargs.get('json') or call_args[1].get('json')
            assert request_body["method"] == "resources/read"
            assert request_body["params"]["uri"] == "file:///config.yaml"
        
        inspector.close()


class TestMCPInspectorInspectResponse:
    """Test inspect_response method (Task Group 4)."""

    def test_inspect_response_no_api_configured(self):
        """Test inspect_response allows when no API configured."""
        with patch.dict(os.environ, {}, clear=False):
            for var in ["AI_DEFENSE_API_MODE_MCP_API_KEY", "AI_DEFENSE_API_MODE_MCP_ENDPOINT",
                       "AI_DEFENSE_API_MODE_LLM_API_KEY", "AI_DEFENSE_API_MODE_LLM_ENDPOINT"]:
                os.environ.pop(var, None)
            
            inspector = MCPInspector()
            
            decision = inspector.inspect_response(
                tool_name="test_tool",
                arguments={},
                result="Some result",
                metadata={},
            )
            
            assert decision.action == "allow"
            inspector.close()

    def test_inspect_response_allow(self):
        """Test inspect_response returns allow for safe response."""
        inspector = MCPInspector(
            api_key="test-key",
            endpoint="https://test.example.com",
        )
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "result": {
                "is_safe": True,
                "action": "Allow",
                "severity": "NONE_SEVERITY",
                "rules": [],
            },
            "id": 1,
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(inspector._sync_client, 'post', return_value=mock_response):
            decision = inspector.inspect_response(
                tool_name="search_docs",
                arguments={},
                result="Safe search results",
                metadata={},
            )
            
            assert decision.action == "allow"
        
        inspector.close()

    def test_inspect_response_block_pii(self):
        """Test inspect_response blocks response with PII."""
        inspector = MCPInspector(
            api_key="test-key",
            endpoint="https://test.example.com",
        )
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "result": {
                "is_safe": False,
                "action": "Block",
                "severity": "HIGH",
                "rules": [{"rule_name": "PII", "classification": "PRIVACY_VIOLATION"}],
                "classifications": ["PRIVACY_VIOLATION"],
            },
            "id": 1,
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(inspector._sync_client, 'post', return_value=mock_response):
            decision = inspector.inspect_response(
                tool_name="get_user",
                arguments={},
                result="SSN: 123-45-6789",
                metadata={},
            )
            
            assert decision.action == "block"
            assert "PII: PRIVACY_VIOLATION" in decision.reasons
        
        inspector.close()


class TestMCPInspectorAsync:
    """Test async methods (Task Group 5)."""

    @pytest.mark.asyncio
    async def test_ainspect_request_no_api_configured(self):
        """Test ainspect_request allows when no API configured."""
        with patch.dict(os.environ, {}, clear=False):
            for var in ["AI_DEFENSE_API_MODE_MCP_API_KEY", "AI_DEFENSE_API_MODE_MCP_ENDPOINT",
                       "AI_DEFENSE_API_MODE_LLM_API_KEY", "AI_DEFENSE_API_MODE_LLM_ENDPOINT"]:
                os.environ.pop(var, None)
            
            inspector = MCPInspector()
            
            decision = await inspector.ainspect_request(
                tool_name="test_tool",
                arguments={},
                metadata={},
            )
            
            assert decision.action == "allow"
            inspector.close()

    @pytest.mark.asyncio
    async def test_ainspect_response_no_api_configured(self):
        """Test ainspect_response allows when no API configured."""
        with patch.dict(os.environ, {}, clear=False):
            for var in ["AI_DEFENSE_API_MODE_MCP_API_KEY", "AI_DEFENSE_API_MODE_MCP_ENDPOINT",
                       "AI_DEFENSE_API_MODE_LLM_API_KEY", "AI_DEFENSE_API_MODE_LLM_ENDPOINT"]:
                os.environ.pop(var, None)
            
            inspector = MCPInspector()
            
            decision = await inspector.ainspect_response(
                tool_name="test_tool",
                arguments={},
                result="Some result",
                metadata={},
            )
            
            assert decision.action == "allow"
            inspector.close()

    @pytest.mark.asyncio
    async def test_ainspect_request_error_handling(self):
        """Test ainspect_request error handling with fail_open=True."""
        inspector = MCPInspector(
            api_key="test-key",
            endpoint="https://test.example.com",
            fail_open=True,
        )
        
        # Mock httpx.AsyncClient to raise an exception
        async def mock_post(*args, **kwargs):
            raise httpx.ConnectError("Connection failed")
        
        with patch('aidefense.runtime.agentsec.inspectors.api_mcp.httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.post = mock_post
            
            async def aenter_mock(*args):
                return mock_client
            
            async def aexit_mock(*args):
                return None
            
            mock_client_class.return_value.__aenter__ = aenter_mock
            mock_client_class.return_value.__aexit__ = aexit_mock
            
            decision = await inspector.ainspect_request(
                tool_name="test_tool",
                arguments={},
                metadata={},
            )
            
            assert decision.action == "allow"
            assert "fail_open=True" in decision.reasons[0]
        
        inspector.close()

    @pytest.mark.asyncio
    async def test_ainspect_request_prompts_get(self):
        """Test ainspect_request with prompts/get method."""
        inspector = MCPInspector(
            api_key="test-key",
            endpoint="https://test.example.com",
        )
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "result": {
                "is_safe": True,
                "action": "Allow",
                "severity": "NONE_SEVERITY",
                "rules": [],
            },
            "id": 1,
        }
        mock_response.raise_for_status = MagicMock()
        
        async def mock_post(*args, **kwargs):
            return mock_response
        
        with patch('aidefense.runtime.agentsec.inspectors.api_mcp.httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.post = mock_post
            
            async def aenter_mock(*args):
                return mock_client
            
            async def aexit_mock(*args):
                return None
            
            mock_client_class.return_value.__aenter__ = aenter_mock
            mock_client_class.return_value.__aexit__ = aexit_mock
            
            decision = await inspector.ainspect_request(
                tool_name="code_review_prompt",
                arguments={"language": "python"},
                metadata={},
                method="prompts/get",
            )
            
            assert decision.action == "allow"
        
        inspector.close()

    @pytest.mark.asyncio
    async def test_ainspect_request_resources_read(self):
        """Test ainspect_request with resources/read method."""
        inspector = MCPInspector(
            api_key="test-key",
            endpoint="https://test.example.com",
        )
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "result": {
                "is_safe": True,
                "action": "Allow",
                "severity": "NONE_SEVERITY",
                "rules": [],
            },
            "id": 1,
        }
        mock_response.raise_for_status = MagicMock()
        
        async def mock_post(*args, **kwargs):
            return mock_response
        
        with patch('aidefense.runtime.agentsec.inspectors.api_mcp.httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.post = mock_post
            
            async def aenter_mock(*args):
                return mock_client
            
            async def aexit_mock(*args):
                return None
            
            mock_client_class.return_value.__aenter__ = aenter_mock
            mock_client_class.return_value.__aexit__ = aexit_mock
            
            decision = await inspector.ainspect_request(
                tool_name="file:///config.yaml",
                arguments={},
                metadata={},
                method="resources/read",
            )
            
            assert decision.action == "allow"
        
        inspector.close()
