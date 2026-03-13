"""Tests for LLM Gateway Mode Integration (Task 3.1)."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import os

from aidefense.runtime import agentsec
from aidefense.runtime.agentsec._state import reset, set_state, get_llm_integration_mode, get_default_gateway_for_provider
from aidefense.runtime.agentsec._context import clear_inspection_context
from aidefense.runtime.agentsec.patchers import reset_registry
from aidefense.runtime.agentsec.patchers._base import resolve_gateway_settings
from aidefense.runtime.agentsec.exceptions import SecurityPolicyError

# Import the module itself for patching
import aidefense.runtime.agentsec.patchers.openai as openai_patcher


@pytest.fixture(autouse=True)
def reset_state():
    """Reset agentsec state before each test."""
    reset()
    reset_registry()
    clear_inspection_context()
    # Clear cached clients
    openai_patcher._inspector = None
    openai_patcher._gateway_client = None
    # Clear gateway-related env vars
    for var in ["AGENTSEC_LLM_INTEGRATION_MODE", "AI_DEFENSE_GATEWAY_MODE_LLM_URL", 
                "AI_DEFENSE_GATEWAY_MODE_LLM_API_KEY"]:
        os.environ.pop(var, None)
    yield
    reset()
    reset_registry()
    clear_inspection_context()
    openai_patcher._inspector = None
    openai_patcher._gateway_client = None


class TestIntegrationModeDetection:
    """Test integration mode detection."""

    def test_is_gateway_mode_default_api(self):
        """Test default integration mode is 'api'."""
        set_state(
            initialized=True,
            llm_rules=None,
            api_mode={"llm": {"mode": "monitor"}, "mcp": {"mode": "monitor"}},
            llm_integration_mode="api",
            mcp_integration_mode="api",
        )
        
        assert get_llm_integration_mode() == "api"
        assert resolve_gateway_settings("openai") is None

    def test_is_gateway_mode_when_gateway(self):
        """Test integration mode is 'gateway' when configured."""
        set_state(
            initialized=True,
            llm_rules=None,
            api_mode={"llm": {"mode": "monitor"}, "mcp": {"mode": "monitor"}},
            llm_integration_mode="gateway",
            mcp_integration_mode="api",
        )
        
        assert get_llm_integration_mode() == "gateway"

    def test_should_use_gateway_requires_config(self):
        """Test gateway mode requires URL and API key to be configured."""
        # Gateway mode but no provider config (no default gateway for openai)
        set_state(
            initialized=True,
            llm_rules=None,
            api_mode={"llm": {"mode": "monitor"}, "mcp": {"mode": "monitor"}},
            llm_integration_mode="gateway",
            mcp_integration_mode="api",
            gateway_mode={"llm_gateways": {}},
        )
        
        assert get_llm_integration_mode() == "gateway"
        # No gateway configured -- must raise instead of silently falling back
        with pytest.raises(SecurityPolicyError, match="no gateway configuration found for provider"):
            resolve_gateway_settings("openai")

    def test_should_use_gateway_with_config(self):
        """Test gateway mode works when fully configured."""
        set_state(
            initialized=True,
            llm_rules=None,
            api_mode={"llm": {"mode": "monitor"}, "mcp": {"mode": "monitor"}},
            llm_integration_mode="gateway",
            mcp_integration_mode="api",
            gateway_mode={"llm_gateways": {"openai-1": {"gateway_url": "https://gateway.example.com/openai", "gateway_api_key": "test-key", "provider": "openai", "default": True}}},
        )
        
        assert get_llm_integration_mode() == "gateway"
        assert resolve_gateway_settings("openai") is not None


class TestProviderGatewayConfig:
    """Test provider-specific gateway configuration."""

    def test_provider_gateway_config_openai(self):
        """Test OpenAI provider gateway config retrieval."""
        set_state(
            initialized=True,
            llm_rules=None,
            api_mode={"llm": {"mode": "monitor"}, "mcp": {"mode": "monitor"}},
            llm_integration_mode="gateway",
            gateway_mode={"llm_gateways": {"openai-1": {"gateway_url": "https://gateway.example.com/openai", "gateway_api_key": "openai-key", "provider": "openai", "default": True}}},
        )
        
        gateway = get_default_gateway_for_provider("openai")
        assert gateway is not None
        assert gateway.get("gateway_url") == "https://gateway.example.com/openai"
        assert gateway.get("gateway_api_key") == "openai-key"

    def test_provider_gateway_config_not_set(self):
        """Test provider gateway config returns None when not set."""
        set_state(
            initialized=True,
            llm_rules=None,
            api_mode={"llm": {"mode": "monitor"}, "mcp": {"mode": "monitor"}},
            llm_integration_mode="gateway",
        )
        
        gateway = get_default_gateway_for_provider("openai")
        assert (gateway or {}).get("gateway_url") is None
        assert (gateway or {}).get("gateway_api_key") is None


class TestDictToOpenAIResponse:
    """Test dictionary to OpenAI response conversion."""

    def test_converts_basic_response(self):
        """Test basic response conversion."""
        response_data = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "gpt-4",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello, how can I help you?",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
            },
        }
        
        response = openai_patcher._dict_to_openai_response(response_data)
        
        assert response.id == "chatcmpl-123"
        assert response.model == "gpt-4"
        assert len(response.choices) == 1
        assert response.choices[0].message.content == "Hello, how can I help you?"
        assert response.choices[0].message.role == "assistant"
        assert response.choices[0].finish_reason == "stop"
        assert response.usage.total_tokens == 30


class TestOpenAIPatcherGatewayMode:
    """Test OpenAI patcher with gateway mode."""

    def test_api_mode_uses_inspector(self):
        """Test API mode uses LLMInspector (not gateway)."""
        set_state(
            initialized=True,
            llm_rules=None,
            api_mode={"llm": {"mode": "monitor"}, "mcp": {"mode": "monitor"}},
            llm_integration_mode="api",
        )
        
        # Mock the inspector
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = MagicMock(action="allow")
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        
        wrapped = MagicMock(return_value=mock_response)
        
        with patch.object(openai_patcher, "_get_inspector", return_value=mock_inspector):
            result = openai_patcher._wrap_chat_completions_create(
                wrapped, None, [], 
                {"model": "gpt-4", "messages": [{"role": "user", "content": "Hi"}]}
            )
            
            # Inspector should have been called
            assert mock_inspector.inspect_conversation.called
            # Original wrapped function should have been called
            assert wrapped.called

    def test_gateway_mode_skips_inspector(self):
        """Test gateway mode skips LLMInspector API calls."""
        set_state(
            initialized=True,
            llm_rules=None,
            api_mode={"llm": {"mode": "monitor"}, "mcp": {"mode": "monitor"}},
            llm_integration_mode="gateway",
            gateway_mode={"llm_gateways": {"openai-1": {"gateway_url": "https://gateway.example.com/openai", "gateway_api_key": "test-key", "provider": "openai", "default": True}}},
        )
        
        # Mock the inspector (should NOT be called)
        mock_inspector = MagicMock()
        
        # Mock httpx Client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "gateway-123",
            "choices": [{"message": {"role": "assistant", "content": "Gateway response"}}],
        }
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        
        wrapped = MagicMock()  # Should NOT be called in gateway mode
        
        with patch.object(openai_patcher, "_get_inspector", return_value=mock_inspector):
            with patch("httpx.Client", return_value=mock_client):
                result = openai_patcher._wrap_chat_completions_create(
                    wrapped, None, [],
                    {"model": "gpt-4", "messages": [{"role": "user", "content": "Hi"}]}
                )
                
                # Inspector should NOT have been called
                assert not mock_inspector.inspect_conversation.called
                # HTTP client should have been called
                assert mock_client.post.called
                # Original wrapped function should NOT be called (gateway handles it)
                assert not wrapped.called

    def test_gateway_mode_raises_when_not_configured(self):
        """Test gateway mode raises SecurityPolicyError when gateway not configured."""
        set_state(
            initialized=True,
            llm_rules=None,
            api_mode={"llm": {"mode": "monitor"}, "mcp": {"mode": "monitor"}},
            llm_integration_mode="gateway",
            gateway_mode={"llm_gateways": {}},  # Not configured - no openai provider
        )
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test"
        
        wrapped = MagicMock(return_value=mock_response)
        
        # Must raise SecurityPolicyError instead of silently falling back to API mode
        with pytest.raises(SecurityPolicyError, match="no gateway configuration found for provider"):
            openai_patcher._wrap_chat_completions_create(
                wrapped, None, [],
                {"model": "gpt-4", "messages": [{"role": "user", "content": "Hi"}]}
            )
        # Original function should never be called
        assert not wrapped.called

    def test_gateway_mode_off_calls_original(self):
        """When gateway llm_mode is 'off', calls go directly to the original."""
        set_state(
            initialized=True,
            llm_integration_mode="gateway",
            gateway_mode={
                "llm_mode": "off",
                "llm_gateways": {
                    "openai-1": {
                        "gateway_url": "https://gateway.example.com/openai",
                        "gateway_api_key": "test-key",
                        "provider": "openai",
                        "default": True,
                    },
                },
            },
        )

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Direct response"

        wrapped = MagicMock(return_value=mock_response)

        result = openai_patcher._wrap_chat_completions_create(
            wrapped, None, [],
            {"model": "gpt-4", "messages": [{"role": "user", "content": "Hi"}]}
        )

        # Original wrapped function SHOULD be called (gateway is off)
        assert wrapped.called
        assert result == mock_response


class TestOpenAIPatcherAsyncGatewayMode:
    """Test async OpenAI patcher with gateway mode."""

    @pytest.mark.asyncio
    async def test_async_gateway_mode_uses_httpx_async_client(self):
        """Test async gateway mode uses async HTTP client."""
        set_state(
            initialized=True,
            llm_rules=None,
            api_mode={"llm": {"mode": "monitor"}, "mcp": {"mode": "monitor"}},
            llm_integration_mode="gateway",
            gateway_mode={"llm_gateways": {"openai-1": {"gateway_url": "https://gateway.example.com/openai", "gateway_api_key": "test-key", "provider": "openai", "default": True}}},
        )
        
        # Mock httpx AsyncClient
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "async-gateway-123",
            "choices": [{"message": {"role": "assistant", "content": "Async gateway response"}}],
        }
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        
        wrapped = AsyncMock()  # Should NOT be called in gateway mode
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await openai_patcher._wrap_chat_completions_create_async(
                wrapped, None, [],
                {"model": "gpt-4", "messages": [{"role": "user", "content": "Hi"}]}
            )
            
            # Async HTTP client should have been called
            assert mock_client.post.called
            # Original wrapped function should NOT be called
            assert not wrapped.called
            # Response should be from gateway
            assert result.id == "async-gateway-123"
