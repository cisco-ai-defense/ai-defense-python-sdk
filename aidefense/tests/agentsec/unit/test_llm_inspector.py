"""Tests for LLMInspector with Cisco AI Defense API (Task 3.1).

Enhanced with error handling tests for Task Group 1 (Error Handling spec).
LLMInspector uses ChatInspectionClient; tests mock _get_chat_client.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from aidefense.runtime.agentsec.decision import Decision
from aidefense.runtime.agentsec.exceptions import (
    SecurityPolicyError,
    InspectionTimeoutError,
    InspectionNetworkError,
    AgentsecError,
)
from aidefense.runtime.agentsec.inspectors.api_llm import (
    LLMInspector,
    _messages_to_runtime,
    _metadata_to_runtime,
)
from aidefense.runtime.models import InspectResponse, Action, Classification

# 64-char API key required by RuntimeAuth when client is created
API_KEY_64 = "x" * 64


def _allow_response():
    return InspectResponse(
        classifications=[],
        is_safe=True,
        action=Action.ALLOW,
    )


def _block_response(reasons=None):
    return InspectResponse(
        classifications=[Classification.SECURITY_VIOLATION],
        is_safe=False,
        action=Action.BLOCK,
        explanation=reasons[0] if reasons else "policy violation",
    )


class TestLLMInspector:
    """Test LLMInspector functionality."""

    def test_successful_api_call_returns_decision(self):
        """Test successful API call returns Decision from response."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.return_value = _allow_response()
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "Hello"}],
                metadata={"user": "test"},
            )
        assert decision.action == "allow"

    def test_timeout_handling(self):
        """Test timeout handling with configurable timeout."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            timeout_ms=500,
            fail_open=True,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = httpx.TimeoutException("timeout")
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "Hello"}],
                metadata={},
            )
        assert decision.action == "allow"

    def test_fail_open_true_allows_on_error(self):
        """Test fail_open=True allows on API error."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            fail_open=True,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = Exception("API error")
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "test"}],
                metadata={},
            )
        assert decision.action == "allow"
        assert any("API error" in r or "fail_open" in r for r in decision.reasons)

    def test_fail_open_false_raises_on_error(self):
        """Test fail_open=False raises SecurityPolicyError on API error."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            fail_open=False,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = Exception("API error")
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            with pytest.raises(SecurityPolicyError):
                inspector.inspect_conversation(
                    messages=[{"role": "user", "content": "test"}],
                    metadata={},
                )

    @pytest.mark.asyncio
    async def test_async_inspect_conversation(self):
        """Test async ainspect_conversation() uses AsyncChatInspectionClient."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation = AsyncMock(return_value=_block_response(["policy violation"]))
        with patch.object(inspector, "_get_async_chat_client", new_callable=AsyncMock, return_value=mock_client):
            decision = await inspector.ainspect_conversation(
                messages=[{"role": "user", "content": "test"}],
                metadata={},
            )
        assert decision.action == "block"
        assert any("policy violation" in r or "SECURITY_VIOLATION" in r for r in decision.reasons)

    def test_request_payload_includes_messages_metadata(self):
        """Test message/metadata adapters produce correct runtime structures."""
        messages = [
            {"role": "system", "content": "You are a helper"},
            {"role": "user", "content": "Hello"},
        ]
        metadata = {"user": "test_user", "src_app": "test_app"}
        runtime_messages = _messages_to_runtime(messages)
        runtime_metadata = _metadata_to_runtime(metadata)
        assert len(runtime_messages) == 2
        assert runtime_messages[0].role.value == "system"
        assert runtime_messages[0].content == "You are a helper"
        assert runtime_messages[1].role.value == "user"
        assert runtime_messages[1].content == "Hello"
        assert runtime_metadata is not None
        assert runtime_metadata.user == "test_user"
        assert runtime_metadata.src_app == "test_app"


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
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            fail_open=True,
        )
        
        decision = inspector._handle_error(Exception("Test error"))
        
        assert decision.action == "allow"
        assert any("fail_open" in r.lower() or "api error" in r.lower() for r in decision.reasons)

    def test_handle_error_fail_open_false_raises_security_error(self):
        """Test _handle_error with fail_open=False raises SecurityPolicyError."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
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
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            fail_open=True,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = httpx.TimeoutException("Connection timed out")
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "test"}],
                metadata={},
            )
        assert decision.action == "allow"

    def test_httpx_connect_error_handling(self):
        """Test handling of httpx.ConnectError."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            fail_open=True,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = httpx.ConnectError("Failed to connect")
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "test"}],
                metadata={},
            )
        assert decision.action == "allow"

    def test_httpx_http_status_error_handling(self):
        """Test handling of httpx.HTTPStatusError (non-200 responses)."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            fail_open=True,
        )
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = httpx.HTTPStatusError(
            "Server error",
            request=mock_request,
            response=mock_response,
        )
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "test"}],
                metadata={},
            )
        assert decision.action == "allow"

    def test_malformed_json_response_handling(self):
        """Test handling of malformed JSON responses."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            fail_open=True,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "test"}],
                metadata={},
            )
        assert decision.action == "allow"

    @pytest.mark.asyncio
    async def test_async_httpx_timeout_handling(self):
        """Test async handling of httpx.TimeoutException (AsyncChatInspectionClient path)."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            fail_open=True,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation = AsyncMock(side_effect=httpx.TimeoutException("Async timeout"))
        with patch.object(inspector, "_get_async_chat_client", new_callable=AsyncMock, return_value=mock_client):
            decision = await inspector.ainspect_conversation(
                messages=[{"role": "user", "content": "test"}],
                metadata={},
            )
        assert decision.action == "allow"

    @pytest.mark.asyncio
    async def test_async_fail_open_false_raises(self):
        """Test async fail_open=False raises InspectionNetworkError for network errors."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            fail_open=False,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        with patch.object(inspector, "_get_async_chat_client", new_callable=AsyncMock, return_value=mock_client):
            with pytest.raises(InspectionNetworkError):
                await inspector.ainspect_conversation(
                    messages=[{"role": "user", "content": "test"}],
                    metadata={},
                )









