"""Tests for MCP Gateway Mode Integration.

MCP Gateway mode works by:
1. MCPGatewayInspector provides gateway URL and headers configuration
2. The patcher redirects streamablehttp_client URL to the gateway
3. inspect_request/inspect_response are pass-through (gateway handles inspection)
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import os

from aidefense.runtime.agentsec._state import reset, set_state, get_mcp_integration_mode
from aidefense.runtime.agentsec._context import clear_inspection_context
from aidefense.runtime.agentsec.patchers import reset_registry
from aidefense.runtime.agentsec.inspectors.gateway_mcp import MCPGatewayInspector

# Import the module itself for patching
import aidefense.runtime.agentsec.patchers.mcp as mcp_patcher


@pytest.fixture(autouse=True)
def reset_state():
    """Reset agentsec state before each test."""
    reset()
    reset_registry()
    clear_inspection_context()
    # Clear cached inspectors
    mcp_patcher._api_inspector = None
    mcp_patcher._gateway_inspector = None
    mcp_patcher._gateway_mode_logged = False
    # Clear gateway-related env vars
    for var in ["AGENTSEC_MCP_INTEGRATION_MODE", "AI_DEFENSE_GATEWAY_MODE_MCP_URL", 
                "AI_DEFENSE_GATEWAY_MODE_MCP_API_KEY", "AGENTSEC_GATEWAY_MODE_MCP"]:
        os.environ.pop(var, None)
    yield
    reset()
    reset_registry()
    clear_inspection_context()
    mcp_patcher._api_inspector = None
    mcp_patcher._gateway_inspector = None
    mcp_patcher._gateway_mode_logged = False


class TestMCPGatewayInspector:
    """Test MCPGatewayInspector class."""

    def test_inspector_initialization(self):
        """Test MCPGatewayInspector initialization."""
        inspector = MCPGatewayInspector(
            gateway_url="https://gateway.example.com/mcp",
            api_key="test-key",
            fail_open=True,
        )
        
        assert inspector.gateway_url == "https://gateway.example.com/mcp"
        assert inspector.api_key == "test-key"
        assert inspector.fail_open is True
        assert inspector.is_configured is True

    def test_inspector_not_configured_without_url(self):
        """Test MCPGatewayInspector is not configured without URL."""
        inspector = MCPGatewayInspector()
        assert inspector.is_configured is False
        assert inspector.get_redirect_url() is None

    def test_get_headers_with_api_key(self):
        """Test get_headers returns api-key header."""
        inspector = MCPGatewayInspector(
            gateway_url="https://gateway.example.com/mcp",
            api_key="test-api-key",
        )
        
        headers = inspector.get_headers()
        assert headers == {"api-key": "test-api-key"}

    def test_get_headers_without_api_key(self):
        """Test get_headers returns empty dict without api key."""
        inspector = MCPGatewayInspector(
            gateway_url="https://gateway.example.com/mcp",
        )
        
        headers = inspector.get_headers()
        assert headers == {}

    def test_inspect_request_is_passthrough(self):
        """Test inspect_request returns allow (gateway handles inspection)."""
        inspector = MCPGatewayInspector(
            gateway_url="https://gateway.example.com/mcp",
        )
        
        decision = inspector.inspect_request("test_tool", {"arg": "value"})
        assert decision.action == "allow"
        assert "gateway" in decision.reasons[0].lower()

    def test_inspect_response_is_passthrough(self):
        """Test inspect_response returns allow (gateway handles inspection)."""
        inspector = MCPGatewayInspector(
            gateway_url="https://gateway.example.com/mcp",
        )
        
        decision = inspector.inspect_response("test_tool", {"arg": "value"}, "result")
        assert decision.action == "allow"
        assert "gateway" in decision.reasons[0].lower()

    @pytest.mark.asyncio
    async def test_ainspect_request_is_passthrough(self):
        """Test async inspect_request returns allow."""
        inspector = MCPGatewayInspector(
            gateway_url="https://gateway.example.com/mcp",
        )
        
        decision = await inspector.ainspect_request("test_tool", {"arg": "value"})
        assert decision.action == "allow"

    @pytest.mark.asyncio
    async def test_ainspect_response_is_passthrough(self):
        """Test async inspect_response returns allow."""
        inspector = MCPGatewayInspector(
            gateway_url="https://gateway.example.com/mcp",
        )
        
        decision = await inspector.ainspect_response("test_tool", {"arg": "value"}, "result")
        assert decision.action == "allow"


class TestMCPIntegrationModeDetection:
    """Test MCP integration mode detection."""

    def test_is_gateway_mode_default_api(self):
        """Test default MCP integration mode is 'api'."""
        set_state(
            initialized=True,
            llm_rules=None,
            api_mode_llm="on_monitor",
            api_mode_mcp="on_monitor",
            llm_integration_mode="api",
            mcp_integration_mode="api",
        )
        
        assert mcp_patcher._is_gateway_mode() is False
        assert get_mcp_integration_mode() == "api"

    def test_is_gateway_mode_when_gateway(self):
        """Test MCP integration mode is 'gateway' when configured."""
        set_state(
            initialized=True,
            llm_rules=None,
            api_mode_llm="on_monitor",
            api_mode_mcp="on_monitor",
            llm_integration_mode="api",
            mcp_integration_mode="gateway",
        )
        
        assert mcp_patcher._is_gateway_mode() is True
        assert get_mcp_integration_mode() == "gateway"

    def test_should_use_gateway_requires_url(self):
        """Test gateway mode requires URL to be configured."""
        set_state(
            initialized=True,
            llm_rules=None,
            api_mode_llm="on_monitor",
            api_mode_mcp="on_monitor",
            mcp_integration_mode="gateway",
            gateway_mode_mcp="on",
            gateway_mode_mcp_url=None,
        )
        
        assert mcp_patcher._is_gateway_mode() is True
        assert mcp_patcher._should_use_gateway() is False

    def test_should_use_gateway_requires_mode_on(self):
        """Test gateway mode requires mode to be 'on'."""
        set_state(
            initialized=True,
            llm_rules=None,
            api_mode_llm="on_monitor",
            api_mode_mcp="on_monitor",
            mcp_integration_mode="gateway",
            gateway_mode_mcp="off",
            gateway_mode_mcp_url="https://gateway.example.com/mcp",
        )
        
        assert mcp_patcher._is_gateway_mode() is True
        assert mcp_patcher._should_use_gateway() is False

    def test_should_use_gateway_with_config(self):
        """Test gateway mode works when fully configured."""
        set_state(
            initialized=True,
            llm_rules=None,
            api_mode_llm="on_monitor",
            api_mode_mcp="on_monitor",
            mcp_integration_mode="gateway",
            gateway_mode_mcp="on",
            gateway_mode_mcp_url="https://gateway.example.com/mcp",
            gateway_mode_mcp_api_key="test-key",
        )
        
        assert mcp_patcher._is_gateway_mode() is True
        assert mcp_patcher._should_use_gateway() is True


class TestMCPGatewayURLRedirection:
    """Test MCP gateway URL redirection via streamablehttp_client patching."""

    def test_wrap_streamablehttp_client_redirects_in_gateway_mode(self):
        """Test streamablehttp_client wrapper redirects URL when gateway mode enabled."""
        set_state(
            initialized=True,
            llm_rules=None,
            api_mode_llm="on_monitor",
            api_mode_mcp="on_monitor",
            mcp_integration_mode="gateway",
            gateway_mode_mcp="on",
            gateway_mode_mcp_url="https://gateway.example.com/mcp/server/123",
            gateway_mode_mcp_api_key="test-api-key",
        )
        
        mock_wrapped = MagicMock(return_value="mock_transport")
        
        result = mcp_patcher._wrap_streamablehttp_client(
            mock_wrapped, None,
            ("https://original-server.com/mcp",),
            {}
        )
        
        call_args = mock_wrapped.call_args
        assert call_args[0][0] == "https://gateway.example.com/mcp/server/123"
        
        headers = call_args[1].get('headers', {})
        assert headers.get('api-key') == "test-api-key"

    def test_wrap_streamablehttp_client_passes_through_in_api_mode(self):
        """Test streamablehttp_client wrapper passes through in API mode."""
        set_state(
            initialized=True,
            llm_rules=None,
            api_mode_llm="on_monitor",
            api_mode_mcp="on_monitor",
            mcp_integration_mode="api",
        )
        
        mock_wrapped = MagicMock(return_value="mock_transport")
        original_url = "https://original-server.com/mcp"
        
        result = mcp_patcher._wrap_streamablehttp_client(
            mock_wrapped, None,
            (original_url,),
            {}
        )
        
        call_args = mock_wrapped.call_args
        assert call_args[0][0] == original_url


class TestMCPPatcherModeSelection:
    """Test MCP patcher mode selection."""

    @pytest.mark.asyncio
    async def test_api_mode_uses_api_inspector(self):
        """Test API mode uses MCPInspector."""
        set_state(
            initialized=True,
            llm_rules=None,
            api_mode_llm="on_monitor",
            api_mode_mcp="on_monitor",
            mcp_integration_mode="api",
        )
        
        mock_api_inspector = MagicMock()
        mock_api_inspector.ainspect_request = AsyncMock(return_value=MagicMock(action="allow"))
        mock_api_inspector.ainspect_response = AsyncMock(return_value=MagicMock(action="allow"))
        
        mock_result = {"content": [{"type": "text", "text": "Result"}]}
        wrapped = AsyncMock(return_value=mock_result)
        
        with patch.object(mcp_patcher, "_get_api_inspector", return_value=mock_api_inspector):
            result = await mcp_patcher._wrap_call_tool(
                wrapped, None, 
                ["search_docs", {"query": "test"}], {}
            )
            
            assert mock_api_inspector.ainspect_request.called
            assert mock_api_inspector.ainspect_response.called
            assert wrapped.called

    @pytest.mark.asyncio
    async def test_gateway_mode_uses_gateway_inspector(self):
        """Test gateway mode uses MCPGatewayInspector."""
        set_state(
            initialized=True,
            llm_rules=None,
            api_mode_llm="on_monitor",
            api_mode_mcp="on_monitor",
            mcp_integration_mode="gateway",
            gateway_mode_mcp="on",
            gateway_mode_mcp_url="https://gateway.example.com/mcp",
            gateway_mode_mcp_api_key="test-key",
        )
        
        mock_gateway_inspector = MagicMock()
        mock_gateway_inspector.is_configured = True
        mock_gateway_inspector.ainspect_request = AsyncMock(return_value=MagicMock(action="allow"))
        mock_gateway_inspector.ainspect_response = AsyncMock(return_value=MagicMock(action="allow"))
        
        mock_result = {"content": [{"type": "text", "text": "Gateway result"}]}
        wrapped = AsyncMock(return_value=mock_result)
        
        with patch.object(mcp_patcher, "_get_gateway_inspector", return_value=mock_gateway_inspector):
            result = await mcp_patcher._wrap_call_tool(
                wrapped, None,
                ["search_docs", {"query": "test"}], {}
            )
            
            # Gateway inspector should be called (pass-through)
            assert mock_gateway_inspector.ainspect_request.called
            assert mock_gateway_inspector.ainspect_response.called
            # Wrapped should also be called
            assert wrapped.called
            assert result == mock_result


class TestMCPPromptResourceWrappers:
    """Test MCP get_prompt and read_resource wrapper functions."""

    @pytest.mark.asyncio
    async def test_wrap_get_prompt_api_mode(self):
        """Test _wrap_get_prompt uses API inspector in api mode."""
        set_state(
            initialized=True,
            llm_rules=None,
            api_mode_llm="on_monitor",
            api_mode_mcp="on_monitor",
            mcp_integration_mode="api",
        )
        
        mock_api_inspector = MagicMock()
        mock_api_inspector.ainspect_request = AsyncMock(return_value=MagicMock(action="allow"))
        mock_api_inspector.ainspect_response = AsyncMock(return_value=MagicMock(action="allow"))
        
        mock_result = MagicMock()
        mock_result.messages = [{"role": "user", "content": "prompt template"}]
        wrapped = AsyncMock(return_value=mock_result)
        
        with patch.object(mcp_patcher, "_get_api_inspector", return_value=mock_api_inspector):
            result = await mcp_patcher._wrap_get_prompt(
                wrapped, None,
                ["code_review_prompt", {"language": "python"}], {}
            )
            
            # API inspector should be called with prompts/get method
            mock_api_inspector.ainspect_request.assert_called_once()
            call_args = mock_api_inspector.ainspect_request.call_args
            assert call_args[1].get("method") == "prompts/get" or call_args[0][3] == "prompts/get"
            
            mock_api_inspector.ainspect_response.assert_called_once()
            assert wrapped.called
            assert result == mock_result

    @pytest.mark.asyncio
    async def test_wrap_get_prompt_skips_when_off(self):
        """Test _wrap_get_prompt skips inspection when mode is off."""
        set_state(
            initialized=True,
            llm_rules=None,
            api_mode_llm="on_monitor",
            api_mode_mcp="off",
            mcp_integration_mode="api",
        )
        
        mock_api_inspector = MagicMock()
        mock_api_inspector.ainspect_request = AsyncMock()
        
        mock_result = MagicMock()
        wrapped = AsyncMock(return_value=mock_result)
        
        with patch.object(mcp_patcher, "_get_api_inspector", return_value=mock_api_inspector):
            result = await mcp_patcher._wrap_get_prompt(
                wrapped, None,
                ["code_review_prompt"], {}
            )
            
            # Inspector should NOT be called when mode is off
            mock_api_inspector.ainspect_request.assert_not_called()
            assert wrapped.called
            assert result == mock_result

    @pytest.mark.asyncio
    async def test_wrap_read_resource_api_mode(self):
        """Test _wrap_read_resource uses API inspector in api mode."""
        set_state(
            initialized=True,
            llm_rules=None,
            api_mode_llm="on_monitor",
            api_mode_mcp="on_monitor",
            mcp_integration_mode="api",
        )
        
        mock_api_inspector = MagicMock()
        mock_api_inspector.ainspect_request = AsyncMock(return_value=MagicMock(action="allow"))
        mock_api_inspector.ainspect_response = AsyncMock(return_value=MagicMock(action="allow"))
        
        mock_result = MagicMock()
        mock_result.contents = [{"type": "text", "text": "file content"}]
        wrapped = AsyncMock(return_value=mock_result)
        
        with patch.object(mcp_patcher, "_get_api_inspector", return_value=mock_api_inspector):
            result = await mcp_patcher._wrap_read_resource(
                wrapped, None,
                ["file:///config.yaml"], {}
            )
            
            # API inspector should be called with resources/read method
            mock_api_inspector.ainspect_request.assert_called_once()
            call_args = mock_api_inspector.ainspect_request.call_args
            assert call_args[1].get("method") == "resources/read" or call_args[0][3] == "resources/read"
            
            mock_api_inspector.ainspect_response.assert_called_once()
            assert wrapped.called
            assert result == mock_result

    @pytest.mark.asyncio
    async def test_wrap_read_resource_skips_when_off(self):
        """Test _wrap_read_resource skips inspection when mode is off."""
        set_state(
            initialized=True,
            llm_rules=None,
            api_mode_llm="on_monitor",
            api_mode_mcp="off",
            mcp_integration_mode="api",
        )
        
        mock_api_inspector = MagicMock()
        mock_api_inspector.ainspect_request = AsyncMock()
        
        mock_result = MagicMock()
        wrapped = AsyncMock(return_value=mock_result)
        
        with patch.object(mcp_patcher, "_get_api_inspector", return_value=mock_api_inspector):
            result = await mcp_patcher._wrap_read_resource(
                wrapped, None,
                ["file:///config.yaml"], {}
            )
            
            # Inspector should NOT be called when mode is off
            mock_api_inspector.ainspect_request.assert_not_called()
            assert wrapped.called
            assert result == mock_result

    @pytest.mark.asyncio
    async def test_wrap_get_prompt_gateway_mode(self):
        """Test _wrap_get_prompt in gateway mode."""
        set_state(
            initialized=True,
            llm_rules=None,
            api_mode_llm="on_monitor",
            api_mode_mcp="on_monitor",
            mcp_integration_mode="gateway",
            gateway_mode_mcp="on",
            gateway_mode_mcp_url="https://gateway.example.com/mcp",
            gateway_mode_mcp_api_key="test-key",
        )
        
        mock_gateway_inspector = MagicMock()
        mock_gateway_inspector.is_configured = True
        mock_gateway_inspector.ainspect_request = AsyncMock(return_value=MagicMock(action="allow"))
        mock_gateway_inspector.ainspect_response = AsyncMock(return_value=MagicMock(action="allow"))
        
        mock_result = MagicMock()
        wrapped = AsyncMock(return_value=mock_result)
        
        with patch.object(mcp_patcher, "_get_gateway_inspector", return_value=mock_gateway_inspector):
            result = await mcp_patcher._wrap_get_prompt(
                wrapped, None,
                ["code_review_prompt", {"language": "python"}], {}
            )
            
            assert mock_gateway_inspector.ainspect_request.called
            assert mock_gateway_inspector.ainspect_response.called
            assert wrapped.called
            assert result == mock_result

    @pytest.mark.asyncio
    async def test_wrap_read_resource_gateway_mode(self):
        """Test _wrap_read_resource in gateway mode."""
        set_state(
            initialized=True,
            llm_rules=None,
            api_mode_llm="on_monitor",
            api_mode_mcp="on_monitor",
            mcp_integration_mode="gateway",
            gateway_mode_mcp="on",
            gateway_mode_mcp_url="https://gateway.example.com/mcp",
            gateway_mode_mcp_api_key="test-key",
        )
        
        mock_gateway_inspector = MagicMock()
        mock_gateway_inspector.is_configured = True
        mock_gateway_inspector.ainspect_request = AsyncMock(return_value=MagicMock(action="allow"))
        mock_gateway_inspector.ainspect_response = AsyncMock(return_value=MagicMock(action="allow"))
        
        mock_result = MagicMock()
        wrapped = AsyncMock(return_value=mock_result)
        
        with patch.object(mcp_patcher, "_get_gateway_inspector", return_value=mock_gateway_inspector):
            result = await mcp_patcher._wrap_read_resource(
                wrapped, None,
                ["file:///config.yaml"], {}
            )
            
            assert mock_gateway_inspector.ainspect_request.called
            assert mock_gateway_inspector.ainspect_response.called
            assert wrapped.called
            assert result == mock_result
