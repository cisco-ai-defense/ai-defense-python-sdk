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
from aidefense.runtime.agentsec.exceptions import SecurityPolicyError
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
    mcp_patcher._gateway_pass_through_inspector = None
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
    mcp_patcher._gateway_pass_through_inspector = None
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
        """Test get_headers returns api-key header when auth_mode is api_key."""
        inspector = MCPGatewayInspector(
            gateway_url="https://gateway.example.com/mcp",
            api_key="test-api-key",
            auth_mode="api_key",
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

    def test_get_headers_auth_mode_none_returns_empty(self):
        """Test get_headers with explicit auth_mode='none' returns empty dict, even with api_key."""
        inspector = MCPGatewayInspector(
            gateway_url="https://gateway.example.com/mcp",
            api_key="some-key",
            auth_mode="none",
        )

        headers = inspector.get_headers()
        assert headers == {}

    def test_get_headers_auth_mode_oauth2_returns_empty(self):
        """Test get_headers with auth_mode='oauth2_client_credentials' returns empty dict.

        OAuth2 token injection is handled by the MCP patcher, not the inspector.
        """
        inspector = MCPGatewayInspector(
            gateway_url="https://gateway.example.com/mcp",
            auth_mode="oauth2_client_credentials",
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

    def test_should_use_gateway_default_api(self):
        """Test _should_use_gateway is False when integration mode is 'api'."""
        set_state(
            initialized=True,
            mcp_integration_mode="api",
            api_mode={"mcp": {"mode": "monitor"}},
        )
        assert get_mcp_integration_mode() == "api"
        assert mcp_patcher._should_use_gateway() is False

    def test_should_use_gateway_when_gateway_mode(self):
        """Test _should_use_gateway is True when integration mode is 'gateway' (and not skipped)."""
        set_state(
            initialized=True,
            mcp_integration_mode="gateway",
            gateway_mode={"mcp_gateways": {"https://mcp.example.com/mcp": {"gateway_url": "https://gateway.example.com/mcp"}}},
            api_mode={"mcp": {"mode": "monitor"}},
        )
        assert get_mcp_integration_mode() == "gateway"
        assert mcp_patcher._should_use_gateway() is True


class TestMCPGatewayURLRedirection:
    """Test MCP gateway URL redirection via streamablehttp_client patching."""

    def test_wrap_streamablehttp_client_redirects_with_per_url_gateway(self):
        """Test streamablehttp_client redirects when gateway configured for that URL."""
        set_state(
            initialized=True,
            mcp_integration_mode="gateway",
            gateway_mode={
                "mcp_gateways": {
                    "https://original-server.com/mcp": {
                        "gateway_url": "https://gateway.example.com/mcp/server/123",
                        "api_key": "test-api-key",
                    }
                }
            },
            api_mode={"mcp": {"mode": "monitor"}},
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

    def test_wrap_streamablehttp_client_raises_for_unconfigured_url(self):
        """Test streamablehttp_client raises SecurityPolicyError when no gateway is configured for the URL."""
        set_state(
            initialized=True,
            mcp_integration_mode="gateway",
            gateway_mode={
                "mcp_gateways": {
                    "https://configured-server.com/mcp": {
                        "gateway_url": "https://gateway.example.com/mcp",
                        "api_key": "configured-key",
                    }
                }
            },
            api_mode={"mcp": {"mode": "monitor"}},
        )
        mock_wrapped = MagicMock(return_value="mock_transport")
        original_url = "https://other-server.com/mcp"
        # Must raise instead of silently connecting directly without inspection
        with pytest.raises(SecurityPolicyError, match="no gateway configuration.*found for URL"):
            mcp_patcher._wrap_streamablehttp_client(
                mock_wrapped, None,
                (original_url,),
                {}
            )

    def test_wrap_streamablehttp_client_passes_through_in_api_mode(self):
        """Test streamablehttp_client passes through in API mode."""
        set_state(
            initialized=True,
            mcp_integration_mode="api",
            api_mode={"mcp": {"mode": "monitor"}},
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

    def test_wrap_streamablehttp_client_passes_through_when_gateway_off(self):
        """Test streamablehttp_client passes through when gateway mcp_mode is 'off'."""
        set_state(
            initialized=True,
            mcp_integration_mode="gateway",
            gateway_mode={
                "mcp_mode": "off",
                "mcp_gateways": {
                    "https://original-server.com/mcp": {
                        "gateway_url": "https://gateway.example.com/mcp",
                        "api_key": "test-key",
                    },
                },
            },
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

    def test_wrap_streamablehttp_client_auth_mode_none_no_headers(self):
        """Test auth_mode='none' injects no auth headers."""
        set_state(
            initialized=True,
            mcp_integration_mode="gateway",
            gateway_mode={
                "mcp_gateways": {
                    "https://no-auth-server.com/mcp": {
                        "gateway_url": "https://gateway.example.com/mcp/noauth",
                        "auth_mode": "none",
                    }
                }
            },
            api_mode={"mcp": {"mode": "monitor"}},
        )
        mock_wrapped = MagicMock(return_value="mock_transport")
        result = mcp_patcher._wrap_streamablehttp_client(
            mock_wrapped, None,
            ("https://no-auth-server.com/mcp",),
            {}
        )
        call_args = mock_wrapped.call_args
        assert call_args[0][0] == "https://gateway.example.com/mcp/noauth"
        headers = call_args[1].get('headers', {})
        assert 'api-key' not in headers
        assert 'Authorization' not in headers

    def test_wrap_streamablehttp_client_auth_mode_api_key(self):
        """Test auth_mode='api_key' injects api-key header."""
        set_state(
            initialized=True,
            mcp_integration_mode="gateway",
            gateway_mode={
                "mcp_gateways": {
                    "https://apikey-server.com/mcp": {
                        "gateway_url": "https://gateway.example.com/mcp/apikey",
                        "auth_mode": "api_key",
                        "api_key": "my-api-key",
                    }
                }
            },
            api_mode={"mcp": {"mode": "monitor"}},
        )
        mock_wrapped = MagicMock(return_value="mock_transport")
        result = mcp_patcher._wrap_streamablehttp_client(
            mock_wrapped, None,
            ("https://apikey-server.com/mcp",),
            {}
        )
        call_args = mock_wrapped.call_args
        assert call_args[0][0] == "https://gateway.example.com/mcp/apikey"
        headers = call_args[1].get('headers', {})
        assert headers.get('api-key') == "my-api-key"

    def test_wrap_streamablehttp_client_auth_mode_oauth2(self):
        """Test auth_mode='oauth2_client_credentials' injects Authorization Bearer header."""
        set_state(
            initialized=True,
            mcp_integration_mode="gateway",
            gateway_mode={
                "mcp_gateways": {
                    "https://oauth-server.com/mcp": {
                        "gateway_url": "https://gateway.example.com/mcp/oauth",
                        "auth_mode": "oauth2_client_credentials",
                        "oauth2_token_url": "https://auth.example.com/token",
                        "oauth2_client_id": "test-client-id",
                        "oauth2_client_secret": "test-client-secret",
                        "oauth2_scopes": "read",
                    }
                }
            },
            api_mode={"mcp": {"mode": "monitor"}},
        )
        mock_wrapped = MagicMock(return_value="mock_transport")
        with patch("aidefense.runtime.agentsec._oauth2.get_oauth2_token", return_value="mock-oauth-token") as mock_get_token:
            result = mcp_patcher._wrap_streamablehttp_client(
                mock_wrapped, None,
                ("https://oauth-server.com/mcp",),
                {}
            )
        call_args = mock_wrapped.call_args
        assert call_args[0][0] == "https://gateway.example.com/mcp/oauth"
        headers = call_args[1].get('headers', {})
        assert headers.get('Authorization') == "Bearer mock-oauth-token"
        assert 'api-key' not in headers
        mock_get_token.assert_called_once_with(
            token_url="https://auth.example.com/token",
            client_id="test-client-id",
            client_secret="test-client-secret",
            scopes="read",
        )

    def test_wrap_streamablehttp_client_backward_compat_no_auth_mode(self):
        """Test backward compat: api_key present without explicit auth_mode injects api-key header."""
        set_state(
            initialized=True,
            mcp_integration_mode="gateway",
            gateway_mode={
                "mcp_gateways": {
                    "https://legacy-server.com/mcp": {
                        "gateway_url": "https://gateway.example.com/mcp/legacy",
                        "api_key": "legacy-key",
                        # no auth_mode field — should be inferred as "api_key"
                    }
                }
            },
            api_mode={"mcp": {"mode": "monitor"}},
        )
        mock_wrapped = MagicMock(return_value="mock_transport")
        result = mcp_patcher._wrap_streamablehttp_client(
            mock_wrapped, None,
            ("https://legacy-server.com/mcp",),
            {}
        )
        call_args = mock_wrapped.call_args
        assert call_args[0][0] == "https://gateway.example.com/mcp/legacy"
        headers = call_args[1].get('headers', {})
        assert headers.get('api-key') == "legacy-key"

    def test_wrap_streamablehttp_client_oauth2_token_error_propagates(self):
        """Test that OAuth2 token fetch errors propagate through the patcher."""
        from aidefense.runtime.agentsec.exceptions import InspectionNetworkError

        set_state(
            initialized=True,
            mcp_integration_mode="gateway",
            gateway_mode={
                "mcp_gateways": {
                    "https://oauth-error-server.com/mcp": {
                        "gateway_url": "https://gateway.example.com/mcp/oauth-err",
                        "auth_mode": "oauth2_client_credentials",
                        "oauth2_token_url": "https://auth.example.com/token",
                        "oauth2_client_id": "cid",
                        "oauth2_client_secret": "csecret",
                    }
                }
            },
            api_mode={"mcp": {"mode": "monitor"}},
        )
        mock_wrapped = MagicMock(return_value="mock_transport")
        with patch(
            "aidefense.runtime.agentsec._oauth2.get_oauth2_token",
            side_effect=InspectionNetworkError("OAuth2 token request failed with status 401: Unauthorized"),
        ):
            with pytest.raises(InspectionNetworkError, match="401"):
                mcp_patcher._wrap_streamablehttp_client(
                    mock_wrapped, None,
                    ("https://oauth-error-server.com/mcp",),
                    {}
                )
        # Verify the wrapped function was never called (auth failed before reaching it)
        mock_wrapped.assert_not_called()


class TestMCPPatcherModeSelection:
    """Test MCP patcher mode selection."""

    @pytest.mark.asyncio
    async def test_api_mode_uses_api_inspector(self):
        """Test API mode uses MCPInspector."""
        set_state(
            initialized=True,
            mcp_integration_mode="api",
            api_mode={"mcp": {"mode": "monitor"}},
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
        """Test gateway mode uses MCPGatewayInspector (pass-through)."""
        set_state(
            initialized=True,
            mcp_integration_mode="gateway",
            gateway_mode={"mcp_gateways": {"https://mcp.example.com/mcp": {"gateway_url": "https://gateway.example.com/mcp"}}},
            api_mode={"mcp": {"mode": "monitor"}},
        )
        mock_gateway_inspector = MagicMock()
        mock_gateway_inspector.ainspect_request = AsyncMock(return_value=MagicMock(action="allow"))
        mock_gateway_inspector.ainspect_response = AsyncMock(return_value=MagicMock(action="allow"))
        mock_result = {"content": [{"type": "text", "text": "Gateway result"}]}
        wrapped = AsyncMock(return_value=mock_result)
        with patch.object(mcp_patcher, "_get_gateway_pass_through_inspector", return_value=mock_gateway_inspector):
            result = await mcp_patcher._wrap_call_tool(
                wrapped, None,
                ["search_docs", {"query": "test"}], {}
            )
            assert mock_gateway_inspector.ainspect_request.called
            assert mock_gateway_inspector.ainspect_response.called
            assert wrapped.called
            assert result == mock_result


class TestMCPPromptResourceWrappers:
    """Test MCP get_prompt and read_resource wrapper functions."""

    @pytest.mark.asyncio
    async def test_wrap_get_prompt_api_mode(self):
        """Test _wrap_get_prompt uses API inspector in api mode."""
        set_state(
            initialized=True,
            mcp_integration_mode="api",
            api_mode={"mcp": {"mode": "monitor"}},
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
            mcp_integration_mode="api",
            api_mode={"mcp": {"mode": "off"}},
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
            mcp_integration_mode="api",
            api_mode={"mcp": {"mode": "monitor"}},
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
            mcp_integration_mode="api",
            api_mode={"mcp": {"mode": "off"}},
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
            mcp_integration_mode="gateway",
            gateway_mode={"mcp_gateways": {"https://mcp.example.com/mcp": {"gateway_url": "https://gateway.example.com/mcp"}}},
            api_mode={"mcp": {"mode": "monitor"}},
        )
        mock_gateway_inspector = MagicMock()
        mock_gateway_inspector.ainspect_request = AsyncMock(return_value=MagicMock(action="allow"))
        mock_gateway_inspector.ainspect_response = AsyncMock(return_value=MagicMock(action="allow"))
        mock_result = MagicMock()
        wrapped = AsyncMock(return_value=mock_result)
        with patch.object(mcp_patcher, "_get_gateway_pass_through_inspector", return_value=mock_gateway_inspector):
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
            mcp_integration_mode="gateway",
            gateway_mode={"mcp_gateways": {"https://mcp.example.com/mcp": {"gateway_url": "https://gateway.example.com/mcp"}}},
            api_mode={"mcp": {"mode": "monitor"}},
        )
        mock_gateway_inspector = MagicMock()
        mock_gateway_inspector.ainspect_request = AsyncMock(return_value=MagicMock(action="allow"))
        mock_gateway_inspector.ainspect_response = AsyncMock(return_value=MagicMock(action="allow"))
        mock_result = MagicMock()
        wrapped = AsyncMock(return_value=mock_result)
        with patch.object(mcp_patcher, "_get_gateway_pass_through_inspector", return_value=mock_gateway_inspector):
            result = await mcp_patcher._wrap_read_resource(
                wrapped, None,
                ["file:///config.yaml"], {}
            )
            
            assert mock_gateway_inspector.ainspect_request.called
            assert mock_gateway_inspector.ainspect_response.called
            assert wrapped.called
            assert result == mock_result


class TestMCP405ReconnectPatch:
    """Test MCP handle_get_stream 405 reconnection patch."""

    def test_patch_mcp_handle_get_stream_405_replaces_method(self):
        """Test that _patch_mcp_handle_get_stream_405 replaces handle_get_stream when MCP is available."""
        pytest.importorskip("mcp")
        from mcp.client import streamable_http as _sh

        orig_handle_get_stream = _sh.StreamableHTTPTransport.handle_get_stream

        # Apply patch
        mcp_patcher._patch_mcp_handle_get_stream_405()

        # Verify method was replaced
        assert _sh.StreamableHTTPTransport.handle_get_stream is not orig_handle_get_stream
        assert callable(_sh.StreamableHTTPTransport.handle_get_stream)

    def test_patch_mcp_handle_get_stream_405_idempotent(self):
        """Test that _patch_mcp_handle_get_stream_405 can be called multiple times without error."""
        pytest.importorskip("mcp")
        # First call replaces the method; second call replaces with same patched version
        mcp_patcher._patch_mcp_handle_get_stream_405()
        mcp_patcher._patch_mcp_handle_get_stream_405()
        from mcp.client import streamable_http as _sh
        assert callable(_sh.StreamableHTTPTransport.handle_get_stream)
