"""Tests for GatewayClient (Task 2.1)."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import httpx

from aidefense.runtime.agentsec.inspectors.gateway_llm import GatewayClient
from aidefense.runtime.agentsec.exceptions import SecurityPolicyError


class TestGatewayClientHeaders:
    """Test gateway client header building."""

    def test_build_headers_uses_api_key(self):
        """Test that headers use 'api-key' format (not X-Cisco-AI-Defense-API-Key)."""
        client = GatewayClient(
            gateway_url="https://gateway.example.com/llm",
            api_key="test-api-key-123",
        )
        
        headers = client._build_headers()
        
        assert headers["api-key"] == "test-api-key-123"
        assert "X-Cisco-AI-Defense-API-Key" not in headers
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"

    def test_build_headers_with_extra(self):
        """Test that extra headers are merged correctly."""
        client = GatewayClient(
            gateway_url="https://gateway.example.com/llm",
            api_key="test-key",
        )
        
        headers = client._build_headers({"X-Custom-Header": "custom-value"})
        
        assert headers["api-key"] == "test-key"
        assert headers["X-Custom-Header"] == "custom-value"


class TestGatewayClientSync:
    """Test synchronous gateway calls."""

    def test_call_with_correct_headers(self):
        """Test sync gateway call uses correct api-key header."""
        client = GatewayClient(
            gateway_url="https://gateway.example.com/llm/chat/completions",
            api_key="gateway-api-key",
        )
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "choices": [{"message": {"content": "Hello!"}}],
        }
        mock_response.raise_for_status = MagicMock()
        
        mock_http_client = MagicMock()
        mock_http_client.post.return_value = mock_response
        
        with patch("httpx.Client", return_value=mock_http_client):
            result = client.call({"model": "gpt-4", "messages": [{"role": "user", "content": "Hi"}]})
            
            # Verify the call was made with correct headers
            call_kwargs = mock_http_client.post.call_args
            headers = call_kwargs.kwargs["headers"]
            assert headers["api-key"] == "gateway-api-key"
            assert "X-Cisco-AI-Defense-API-Key" not in headers
            
            # Verify response is returned correctly
            assert result["id"] == "chatcmpl-123"

    def test_call_retries_on_failure(self):
        """Test sync gateway call retries on transient failures."""
        client = GatewayClient(
            gateway_url="https://gateway.example.com/llm",
            api_key="test-key",
            retry_attempts=3,
            fail_open=True,
        )
        
        # First two calls fail, third succeeds
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = MagicMock()
        
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("Connection failed")
            return mock_response
        
        mock_http_client = MagicMock()
        mock_http_client.post.side_effect = side_effect
        
        with patch("httpx.Client", return_value=mock_http_client):
            result = client.call({"test": "data"})
            assert result["success"] is True
            assert call_count == 3


class TestGatewayClientAsync:
    """Test asynchronous gateway calls."""

    @pytest.mark.asyncio
    async def test_acall_with_correct_headers(self):
        """Test async gateway call uses correct api-key header."""
        client = GatewayClient(
            gateway_url="https://gateway.example.com/llm/chat/completions",
            api_key="async-gateway-key",
        )
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "async-123",
            "choices": [{"message": {"content": "Async response"}}],
        }
        mock_response.raise_for_status = MagicMock()
        
        # Mock the async client
        mock_async_client = AsyncMock()
        mock_async_client.post.return_value = mock_response
        mock_async_client.__aenter__.return_value = mock_async_client
        mock_async_client.__aexit__.return_value = None
        
        with patch("httpx.AsyncClient", return_value=mock_async_client):
            result = await client.acall({"model": "gpt-4", "messages": []})
            
            # Verify the call was made with correct headers
            call_kwargs = mock_async_client.post.call_args
            headers = call_kwargs.kwargs["headers"]
            assert headers["api-key"] == "async-gateway-key"
            
            # Verify response
            assert result["id"] == "async-123"


class TestGatewayClientErrorHandling:
    """Test error handling with fail_open settings."""

    def test_error_handling_fail_open_true(self):
        """Test error handling when fail_open=True allows requests through."""
        client = GatewayClient(
            gateway_url="https://gateway.example.com/llm",
            api_key="test-key",
            fail_open=True,
        )
        
        mock_http_client = MagicMock()
        mock_http_client.post.side_effect = httpx.ConnectError("Network error")
        
        with patch("httpx.Client", return_value=mock_http_client):
            result = client.call({"test": "data"})
            
            # Should return error dict, not raise
            assert "error" in result
            assert result["fail_open"] is True

    def test_error_handling_fail_open_false(self):
        """Test error handling when fail_open=False raises SecurityPolicyError."""
        client = GatewayClient(
            gateway_url="https://gateway.example.com/llm",
            api_key="test-key",
            fail_open=False,
        )
        
        mock_http_client = MagicMock()
        mock_http_client.post.side_effect = httpx.ConnectError("Network error")
        
        with patch("httpx.Client", return_value=mock_http_client):
            with pytest.raises(SecurityPolicyError) as exc_info:
                client.call({"test": "data"})
            
            assert "Gateway unavailable" in str(exc_info.value)
            assert exc_info.value.decision.action == "block"

    @pytest.mark.asyncio
    async def test_async_error_handling_fail_open_true(self):
        """Test async error handling when fail_open=True."""
        client = GatewayClient(
            gateway_url="https://gateway.example.com/llm",
            api_key="test-key",
            fail_open=True,
        )
        
        mock_async_client = AsyncMock()
        mock_async_client.post.side_effect = httpx.ConnectError("Async network error")
        mock_async_client.__aenter__.return_value = mock_async_client
        mock_async_client.__aexit__.return_value = None
        
        with patch("httpx.AsyncClient", return_value=mock_async_client):
            result = await client.acall({"test": "data"})
            
            assert "error" in result
            assert result["fail_open"] is True

    @pytest.mark.asyncio
    async def test_async_error_handling_fail_open_false(self):
        """Test async error handling when fail_open=False raises SecurityPolicyError."""
        client = GatewayClient(
            gateway_url="https://gateway.example.com/llm",
            api_key="test-key",
            fail_open=False,
        )
        
        mock_async_client = AsyncMock()
        mock_async_client.post.side_effect = httpx.ConnectError("Async network error")
        mock_async_client.__aenter__.return_value = mock_async_client
        mock_async_client.__aexit__.return_value = None
        
        with patch("httpx.AsyncClient", return_value=mock_async_client):
            with pytest.raises(SecurityPolicyError) as exc_info:
                await client.acall({"test": "data"})
            
            assert "Gateway unavailable" in str(exc_info.value)


class TestGatewayClientConfiguration:
    """Test gateway client configuration."""

    def test_default_timeout(self):
        """Test default timeout is 30 seconds for LLM calls."""
        client = GatewayClient(
            gateway_url="https://gateway.example.com",
            api_key="test",
        )
        
        assert client.timeout_ms == 30000

    def test_custom_timeout(self):
        """Test custom timeout configuration."""
        client = GatewayClient(
            gateway_url="https://gateway.example.com",
            api_key="test",
            timeout_ms=60000,
        )
        
        assert client.timeout_ms == 60000

    def test_retry_attempts_minimum(self):
        """Test retry_attempts has minimum of 1."""
        client = GatewayClient(
            gateway_url="https://gateway.example.com",
            api_key="test",
            retry_attempts=0,
        )
        
        assert client.retry_attempts == 1

    def test_context_manager(self):
        """Test gateway client can be used as context manager."""
        with GatewayClient(
            gateway_url="https://gateway.example.com",
            api_key="test",
        ) as client:
            assert client.gateway_url == "https://gateway.example.com"

    def test_lazy_client_initialization(self):
        """Test HTTP client is not created until first use."""
        client = GatewayClient(
            gateway_url="https://gateway.example.com",
            api_key="test",
        )
        
        # Client should not be created yet
        assert client._sync_client is None
