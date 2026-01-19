"""Tests for LLMInspector with Cisco AI Defense API (Task 3.1).

Enhanced with error handling tests for Task Group 1 (Error Handling spec).
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from aidefense.runtime.agentsec.decision import Decision
from aidefense.runtime.agentsec.exceptions import SecurityPolicyError
from aidefense.runtime.agentsec.inspectors.api_llm import LLMInspector


class TestLLMInspector:
    """Test LLMInspector functionality."""

    def test_successful_api_call_returns_decision(self):
        """Test successful API call returns Decision from response."""
        inspector = LLMInspector(
            api_key="test-key",
            endpoint="http://test.example.com",
        )
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "action": "allow",
            "reasons": [],
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(inspector._sync_client, "post", return_value=mock_response):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "Hello"}],
                metadata={"user": "test"},
            )
        
        assert decision.action == "allow"

    def test_timeout_handling(self):
        """Test timeout handling with configurable timeout."""
        import httpx
        
        inspector = LLMInspector(
            api_key="test-key",
            endpoint="http://test.example.com",
            timeout_ms=500,
            fail_open=True,
        )
        
        with patch.object(
            inspector._sync_client,
            "post",
            side_effect=httpx.TimeoutException("timeout"),
        ):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "Hello"}],
                metadata={},
            )
        
        # fail_open=True should allow
        assert decision.action == "allow"

    def test_fail_open_true_allows_on_error(self):
        """Test fail_open=True allows on API error."""
        inspector = LLMInspector(
            api_key="test-key",
            endpoint="http://test.example.com",
            fail_open=True,
        )
        
        with patch.object(
            inspector._sync_client,
            "post",
            side_effect=Exception("API error"),
        ):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "test"}],
                metadata={},
            )
        
        assert decision.action == "allow"
        assert "API error" in decision.reasons[0] or "fail_open" in decision.reasons[0]

    def test_fail_open_false_raises_on_error(self):
        """Test fail_open=False raises SecurityPolicyError on API error."""
        inspector = LLMInspector(
            api_key="test-key",
            endpoint="http://test.example.com",
            fail_open=False,
        )
        
        with patch.object(
            inspector._sync_client,
            "post",
            side_effect=Exception("API error"),
        ):
            with pytest.raises(SecurityPolicyError):
                inspector.inspect_conversation(
                    messages=[{"role": "user", "content": "test"}],
                    metadata={},
                )

    @pytest.mark.asyncio
    async def test_async_inspect_conversation(self):
        """Test async ainspect_conversation() works correctly."""
        inspector = LLMInspector(
            api_key="test-key",
            endpoint="http://test.example.com",
        )
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "action": "block",
            "reasons": ["policy violation"],
        }
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        
        # ainspect_conversation creates a fresh AsyncClient per request,
        # so we need to patch httpx.AsyncClient itself
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            decision = await inspector.ainspect_conversation(
                messages=[{"role": "user", "content": "test"}],
                metadata={},
            )
        
        assert decision.action == "block"
        assert "policy violation" in decision.reasons

    def test_request_payload_includes_messages_metadata(self):
        """Test request payload includes messages and metadata."""
        inspector = LLMInspector(
            api_key="test-key",
            endpoint="http://test.example.com",
        )
        
        messages = [
            {"role": "system", "content": "You are a helper"},
            {"role": "user", "content": "Hello"},
        ]
        metadata = {"user": "test_user", "src_app": "test_app"}
        
        payload = inspector._build_request_payload(messages, metadata)
        
        assert payload["messages"] == messages
        assert payload["metadata"] == metadata


class TestLLMInspectorNoConfig:
    """Test LLMInspector behavior without API configuration."""

    def test_no_config_allows_by_default(self):
        """Test that missing config allows by default."""
        inspector = LLMInspector()  # No api_key or endpoint
        
        decision = inspector.inspect_conversation(
            messages=[{"role": "user", "content": "test"}],
            metadata={},
        )
        
        assert decision.action == "allow"


class TestLLMInspectorErrorHandling:
    """Test error handling scenarios for LLMInspector (Task Group 1)."""

    def test_handle_error_fail_open_true_returns_allow(self):
        """Test _handle_error with fail_open=True returns allow decision."""
        inspector = LLMInspector(
            api_key="test-key",
            endpoint="http://test.example.com",
            fail_open=True,
        )
        
        decision = inspector._handle_error(Exception("Test error"))
        
        assert decision.action == "allow"
        assert any("fail_open" in r.lower() or "api error" in r.lower() for r in decision.reasons)

    def test_handle_error_fail_open_false_raises_security_error(self):
        """Test _handle_error with fail_open=False raises SecurityPolicyError."""
        inspector = LLMInspector(
            api_key="test-key",
            endpoint="http://test.example.com",
            fail_open=False,
        )
        
        with pytest.raises(SecurityPolicyError) as exc_info:
            inspector._handle_error(Exception("Test error"))
        
        assert exc_info.value.decision.action == "block"
        assert "Test error" in str(exc_info.value)

    def test_httpx_timeout_exception_handling(self):
        """Test handling of httpx.TimeoutException."""
        inspector = LLMInspector(
            api_key="test-key",
            endpoint="http://test.example.com",
            fail_open=True,
        )
        
        with patch.object(
            inspector._sync_client,
            "post",
            side_effect=httpx.TimeoutException("Connection timed out"),
        ):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "test"}],
                metadata={},
            )
        
        assert decision.action == "allow"

    def test_httpx_connect_error_handling(self):
        """Test handling of httpx.ConnectError."""
        inspector = LLMInspector(
            api_key="test-key",
            endpoint="http://test.example.com",
            fail_open=True,
        )
        
        with patch.object(
            inspector._sync_client,
            "post",
            side_effect=httpx.ConnectError("Failed to connect"),
        ):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "test"}],
                metadata={},
            )
        
        assert decision.action == "allow"

    def test_httpx_http_status_error_handling(self):
        """Test handling of httpx.HTTPStatusError (non-200 responses)."""
        inspector = LLMInspector(
            api_key="test-key",
            endpoint="http://test.example.com",
            fail_open=True,
        )
        
        # Create a mock request and response for HTTPStatusError
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        
        with patch.object(
            inspector._sync_client,
            "post",
            side_effect=httpx.HTTPStatusError(
                "Server error",
                request=mock_request,
                response=mock_response,
            ),
        ):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "test"}],
                metadata={},
            )
        
        assert decision.action == "allow"

    def test_malformed_json_response_handling(self):
        """Test handling of malformed JSON responses."""
        inspector = LLMInspector(
            api_key="test-key",
            endpoint="http://test.example.com",
            fail_open=True,
        )
        
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        
        with patch.object(inspector._sync_client, "post", return_value=mock_response):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "test"}],
                metadata={},
            )
        
        assert decision.action == "allow"

    @pytest.mark.asyncio
    async def test_async_httpx_timeout_handling(self):
        """Test async handling of httpx.TimeoutException."""
        inspector = LLMInspector(
            api_key="test-key",
            endpoint="http://test.example.com",
            fail_open=True,
        )
        
        # Create mock async client that raises timeout
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("Async timeout")
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            decision = await inspector.ainspect_conversation(
                messages=[{"role": "user", "content": "test"}],
                metadata={},
            )
        
        assert decision.action == "allow"

    @pytest.mark.asyncio
    async def test_async_fail_open_false_raises(self):
        """Test async fail_open=False raises SecurityPolicyError."""
        inspector = LLMInspector(
            api_key="test-key",
            endpoint="http://test.example.com",
            fail_open=False,
        )
        
        # Create mock async client that raises error
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(SecurityPolicyError):
                await inspector.ainspect_conversation(
                    messages=[{"role": "user", "content": "test"}],
                    metadata={},
                )









