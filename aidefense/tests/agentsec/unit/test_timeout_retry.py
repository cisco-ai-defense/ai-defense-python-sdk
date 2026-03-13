"""Tests for timeout, retry, backoff_factor, and status_codes behavior.

Covers LLMInspector, MCPInspector, and GatewayClient with mocked HTTP
to simulate realistic timeout/retry scenarios.

These tests fill the gap where configuration parsing/wiring was tested
but actual timeout and retry *behavior* was not.
"""

import asyncio
import json
import time
from unittest.mock import MagicMock, patch, AsyncMock, call

import httpx
import pytest
import requests

from aidefense.runtime.agentsec.inspectors.api_llm import LLMInspector
from aidefense.runtime.agentsec.inspectors.api_mcp import MCPInspector
from aidefense.runtime.agentsec.inspectors.gateway_llm import GatewayClient
from aidefense.runtime.agentsec.decision import Decision
from aidefense.runtime.agentsec.exceptions import (
    SecurityPolicyError,
    InspectionTimeoutError,
    InspectionNetworkError,
)
from aidefense.runtime.agentsec import _state
from aidefense.runtime.agentsec.gateway_settings import GatewaySettings
from aidefense.runtime.models import InspectResponse, Action, Classification
from aidefense.runtime.mcp_models import MCPInspectResponse


# 64-char API key required by RuntimeAuth when client is created
API_KEY_64 = "x" * 64


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _allow_response():
    return InspectResponse(
        classifications=[],
        is_safe=True,
        action=Action.ALLOW,
    )


def _block_response():
    return InspectResponse(
        classifications=[Classification.SECURITY_VIOLATION],
        is_safe=False,
        action=Action.BLOCK,
        explanation="policy violation",
    )


def _mcp_allow():
    return MCPInspectResponse(
        result=InspectResponse(
            classifications=[],
            is_safe=True,
            action=Action.ALLOW,
        ),
        id=1,
    )


def _make_http_status_error(status_code: int) -> httpx.HTTPStatusError:
    """Create an httpx.HTTPStatusError with the given status code."""
    mock_request = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = status_code
    return httpx.HTTPStatusError(
        f"Server error {status_code}",
        request=mock_request,
        response=mock_response,
    )


def _make_requests_http_error(status_code: int) -> requests.exceptions.HTTPError:
    """Create a requests.exceptions.HTTPError with the given status code."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    err = requests.exceptions.HTTPError(f"Server error {status_code}")
    err.response = mock_response
    return err


# ===========================================================================
# 1. LLM Inspector — Retry on HTTP Status Codes
# ===========================================================================

class TestLLMInspectorRetryOnStatusCodes:
    """Test that LLMInspector retries on configured HTTP status codes (429, 500, 502, 503, 504)."""

    def test_retry_on_http_500_then_success(self):
        """First call raises HTTP 500, second succeeds → allow."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            retry_total=3,
            retry_backoff=0,  # no delay for tests
            fail_open=False,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = [
            _make_http_status_error(500),
            _allow_response(),
        ]
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "Hello"}],
                metadata={},
            )
        assert decision.action == "allow"
        assert mock_client.inspect_conversation.call_count == 2

    def test_retry_on_http_429_then_success(self):
        """First call raises HTTP 429 (rate limit), second succeeds."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            retry_total=2,
            retry_backoff=0,
            fail_open=False,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = [
            _make_http_status_error(429),
            _allow_response(),
        ]
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "Hello"}],
                metadata={},
            )
        assert decision.action == "allow"
        assert mock_client.inspect_conversation.call_count == 2

    def test_retry_on_http_503_exhausted_then_fail_closed(self):
        """All retries return 503 → raises SecurityPolicyError when fail_open=False."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            retry_total=3,
            retry_backoff=0,
            fail_open=False,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = [
            _make_http_status_error(503),
            _make_http_status_error(503),
            _make_http_status_error(503),
        ]
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            with pytest.raises(SecurityPolicyError):
                inspector.inspect_conversation(
                    messages=[{"role": "user", "content": "Hello"}],
                    metadata={},
                )
        assert mock_client.inspect_conversation.call_count == 3

    def test_retry_on_http_503_exhausted_then_fail_open(self):
        """All retries return 503 → allows when fail_open=True."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            retry_total=2,
            retry_backoff=0,
            fail_open=True,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = [
            _make_http_status_error(503),
            _make_http_status_error(503),
        ]
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "Hello"}],
                metadata={},
            )
        assert decision.action == "allow"
        assert mock_client.inspect_conversation.call_count == 2

    def test_no_retry_on_http_400(self):
        """HTTP 400 (not in retry_status_codes) → no retry, immediate failure."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            retry_total=3,
            retry_backoff=0,
            fail_open=False,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = _make_http_status_error(400)
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            with pytest.raises(SecurityPolicyError):
                inspector.inspect_conversation(
                    messages=[{"role": "user", "content": "Hello"}],
                    metadata={},
                )
        # Should NOT retry — only 1 call
        assert mock_client.inspect_conversation.call_count == 1

    def test_no_retry_on_http_403(self):
        """HTTP 403 (Forbidden, not in retry_status_codes) → no retry."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            retry_total=3,
            retry_backoff=0,
            fail_open=True,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = _make_http_status_error(403)
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "Hello"}],
                metadata={},
            )
        assert decision.action == "allow"
        assert mock_client.inspect_conversation.call_count == 1

    def test_custom_retry_status_codes(self):
        """Custom retry_status_codes=[418] retries on 418 but not 500."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            retry_total=2,
            retry_backoff=0,
            retry_status_codes=[418],
            fail_open=True,
        )
        mock_client = MagicMock()
        # 418 should retry, then succeed
        mock_client.inspect_conversation.side_effect = [
            _make_http_status_error(418),
            _allow_response(),
        ]
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "Hello"}],
                metadata={},
            )
        assert decision.action == "allow"
        assert mock_client.inspect_conversation.call_count == 2

    def test_custom_retry_status_codes_does_not_retry_500(self):
        """When retry_status_codes=[418], HTTP 500 is NOT retried."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            retry_total=3,
            retry_backoff=0,
            retry_status_codes=[418],  # 500 not in list
            fail_open=True,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = _make_http_status_error(500)
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "Hello"}],
                metadata={},
            )
        assert decision.action == "allow"
        assert mock_client.inspect_conversation.call_count == 1


# ===========================================================================
# 2. LLM Inspector — Backoff Factor
# ===========================================================================

class TestLLMInspectorBackoff:
    """Test that LLMInspector applies exponential backoff between retries."""

    def test_backoff_factor_timing(self):
        """Verify time.sleep is called with correct exponential backoff delays."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            retry_total=4,
            retry_backoff=0.5,  # delay = 0.5 * 2^attempt
            fail_open=True,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = [
            httpx.TimeoutException("timeout"),  # attempt 0 → sleep(0.5)
            httpx.TimeoutException("timeout"),  # attempt 1 → sleep(1.0)
            httpx.TimeoutException("timeout"),  # attempt 2 → sleep(2.0)
            _allow_response(),                  # attempt 3 → success
        ]
        with (
            patch.object(inspector, "_get_chat_client", return_value=mock_client),
            patch("time.sleep") as mock_sleep,
        ):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "Hello"}],
                metadata={},
            )
        assert decision.action == "allow"
        assert mock_client.inspect_conversation.call_count == 4
        # Verify backoff delays: 0.5*2^0=0.5, 0.5*2^1=1.0, 0.5*2^2=2.0
        assert mock_sleep.call_count == 3
        delays = [c.args[0] for c in mock_sleep.call_args_list]
        assert delays == pytest.approx([0.5, 1.0, 2.0])

    def test_backoff_factor_zero_no_sleep(self):
        """When retry_backoff=0, no sleep between retries."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            retry_total=3,
            retry_backoff=0,
            fail_open=True,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = [
            httpx.TimeoutException("timeout"),
            httpx.TimeoutException("timeout"),
            _allow_response(),
        ]
        with (
            patch.object(inspector, "_get_chat_client", return_value=mock_client),
            patch("time.sleep") as mock_sleep,
        ):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "Hello"}],
                metadata={},
            )
        assert decision.action == "allow"
        # No sleep calls when backoff=0
        mock_sleep.assert_not_called()

    def test_backoff_capped_at_max(self):
        """Verify backoff is capped at MAX_BACKOFF_DELAY (30s)."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            retry_total=2,
            retry_backoff=20.0,  # 20 * 2^0 = 20, 20 * 2^1 = 40 (capped to 30)
            fail_open=True,
        )
        # Test the _get_backoff_delay method directly
        assert inspector._get_backoff_delay(0) == 20.0
        assert inspector._get_backoff_delay(1) == 30.0  # capped
        assert inspector._get_backoff_delay(5) == 30.0  # still capped


# ===========================================================================
# 3. LLM Inspector — Timeout Exception (fail_open=False)
# ===========================================================================

class TestLLMInspectorTimeoutFailClosed:
    """Test that timeout exceptions raise InspectionTimeoutError when fail_open=False."""

    def test_httpx_timeout_fail_closed_raises_inspection_timeout(self):
        """httpx.TimeoutException with fail_open=False raises InspectionTimeoutError."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            timeout_ms=5000,
            retry_total=1,  # no retry
            fail_open=False,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = httpx.TimeoutException("Connection timed out")
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            with pytest.raises(InspectionTimeoutError) as exc_info:
                inspector.inspect_conversation(
                    messages=[{"role": "user", "content": "Hello"}],
                    metadata={},
                )
        assert exc_info.value.timeout_ms == 5000

    def test_requests_timeout_fail_closed_raises_inspection_timeout(self):
        """requests.exceptions.Timeout with fail_open=False raises InspectionTimeoutError."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            timeout_ms=3000,
            retry_total=1,
            fail_open=False,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = requests.exceptions.Timeout("timed out")
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            with pytest.raises(InspectionTimeoutError) as exc_info:
                inspector.inspect_conversation(
                    messages=[{"role": "user", "content": "Hello"}],
                    metadata={},
                )
        assert exc_info.value.timeout_ms == 3000

    def test_connect_error_fail_closed_raises_network_error(self):
        """httpx.ConnectError with fail_open=False raises InspectionNetworkError."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            retry_total=1,
            fail_open=False,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = httpx.ConnectError("Connection refused")
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            with pytest.raises(InspectionNetworkError):
                inspector.inspect_conversation(
                    messages=[{"role": "user", "content": "Hello"}],
                    metadata={},
                )

    def test_timeout_retried_then_exhausted_raises(self):
        """Timeout retried N times, still fails → raises InspectionTimeoutError."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            timeout_ms=2000,
            retry_total=3,
            retry_backoff=0,
            fail_open=False,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = httpx.TimeoutException("timeout")
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            with pytest.raises(InspectionTimeoutError):
                inspector.inspect_conversation(
                    messages=[{"role": "user", "content": "Hello"}],
                    metadata={},
                )
        # All retry attempts should have been made
        assert mock_client.inspect_conversation.call_count == 3


# ===========================================================================
# 4. LLM Inspector — _should_retry classification
# ===========================================================================

class TestLLMInspectorShouldRetry:
    """Test _should_retry correctly classifies retryable vs non-retryable errors."""

    @pytest.fixture
    def inspector(self):
        return LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            retry_status_codes=[500, 502, 503, 504],
        )

    def test_timeout_exception_is_retryable(self, inspector):
        assert inspector._should_retry(httpx.TimeoutException("timeout")) is True

    def test_connect_error_is_retryable(self, inspector):
        assert inspector._should_retry(httpx.ConnectError("refused")) is True

    def test_network_error_is_retryable(self, inspector):
        assert inspector._should_retry(httpx.NetworkError("broken pipe")) is True

    def test_requests_timeout_is_retryable(self, inspector):
        assert inspector._should_retry(requests.exceptions.Timeout("timeout")) is True

    def test_requests_connection_error_is_retryable(self, inspector):
        assert inspector._should_retry(requests.exceptions.ConnectionError("refused")) is True

    def test_http_500_is_retryable(self, inspector):
        assert inspector._should_retry(_make_http_status_error(500)) is True

    def test_http_502_is_retryable(self, inspector):
        assert inspector._should_retry(_make_http_status_error(502)) is True

    def test_http_503_is_retryable(self, inspector):
        assert inspector._should_retry(_make_http_status_error(503)) is True

    def test_http_504_is_retryable(self, inspector):
        assert inspector._should_retry(_make_http_status_error(504)) is True

    def test_http_400_not_retryable(self, inspector):
        assert inspector._should_retry(_make_http_status_error(400)) is False

    def test_http_401_not_retryable(self, inspector):
        assert inspector._should_retry(_make_http_status_error(401)) is False

    def test_http_403_not_retryable(self, inspector):
        assert inspector._should_retry(_make_http_status_error(403)) is False

    def test_http_404_not_retryable(self, inspector):
        assert inspector._should_retry(_make_http_status_error(404)) is False

    def test_json_decode_error_not_retryable(self, inspector):
        assert inspector._should_retry(json.JSONDecodeError("bad", "", 0)) is False

    def test_generic_exception_not_retryable(self, inspector):
        assert inspector._should_retry(Exception("something")) is False


# ===========================================================================
# 5. LLM Inspector — Async Retry + Backoff
# ===========================================================================

class TestLLMInspectorAsyncRetry:
    """Test async retry and backoff behavior for ainspect_conversation."""

    @pytest.mark.asyncio
    async def test_async_retry_on_http_503_then_success(self):
        """Async: first call 503, second succeeds."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            retry_total=2,
            retry_backoff=0,
            fail_open=False,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation = AsyncMock(side_effect=[
            _make_http_status_error(503),
            _allow_response(),
        ])
        with patch.object(inspector, "_get_async_chat_client", new_callable=AsyncMock, return_value=mock_client):
            decision = await inspector.ainspect_conversation(
                messages=[{"role": "user", "content": "Hello"}],
                metadata={},
            )
        assert decision.action == "allow"
        assert mock_client.inspect_conversation.call_count == 2

    @pytest.mark.asyncio
    async def test_async_backoff_uses_asyncio_sleep(self):
        """Async retries use asyncio.sleep with correct backoff delays."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            retry_total=3,
            retry_backoff=1.0,  # 1.0*2^0=1.0, 1.0*2^1=2.0
            fail_open=True,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation = AsyncMock(side_effect=[
            httpx.TimeoutException("timeout"),
            httpx.TimeoutException("timeout"),
            _allow_response(),
        ])
        with (
            patch.object(inspector, "_get_async_chat_client", new_callable=AsyncMock, return_value=mock_client),
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            decision = await inspector.ainspect_conversation(
                messages=[{"role": "user", "content": "Hello"}],
                metadata={},
            )
        assert decision.action == "allow"
        assert mock_sleep.call_count == 2
        delays = [c.args[0] for c in mock_sleep.call_args_list]
        assert delays == pytest.approx([1.0, 2.0])

    @pytest.mark.asyncio
    async def test_async_timeout_fail_closed_raises(self):
        """Async timeout with fail_open=False raises InspectionTimeoutError."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            timeout_ms=4000,
            retry_total=1,
            fail_open=False,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation = AsyncMock(
            side_effect=httpx.TimeoutException("timed out")
        )
        with patch.object(inspector, "_get_async_chat_client", new_callable=AsyncMock, return_value=mock_client):
            with pytest.raises(InspectionTimeoutError) as exc_info:
                await inspector.ainspect_conversation(
                    messages=[{"role": "user", "content": "Hello"}],
                    metadata={},
                )
        assert exc_info.value.timeout_ms == 4000


# ===========================================================================
# 6. MCP Inspector — Retry on HTTP Status Codes
# ===========================================================================

class TestMCPInspectorRetryOnStatusCodes:
    """Test that MCPInspector retries on configured HTTP status codes."""

    def test_retry_on_http_500_then_success(self):
        """MCP: first call raises 500, second succeeds."""
        inspector = MCPInspector(
            api_key=API_KEY_64,
            endpoint="https://test.example.com",
            retry_total=3,
            retry_backoff=0,
            fail_open=False,
        )
        mock_client = MagicMock()
        mock_client.inspect_tool_call.side_effect = [
            _make_http_status_error(500),
            _mcp_allow(),
        ]
        with patch.object(inspector, "_get_mcp_client", return_value=mock_client):
            decision = inspector.inspect_request(
                tool_name="test_tool",
                arguments={"q": "test"},
                metadata={},
            )
        assert decision.action == "allow"
        assert mock_client.inspect_tool_call.call_count == 2

    def test_retry_on_http_429_then_success(self):
        """MCP: first call raises 429 (rate limit), second succeeds."""
        inspector = MCPInspector(
            api_key=API_KEY_64,
            endpoint="https://test.example.com",
            retry_total=2,
            retry_backoff=0,
            fail_open=False,
        )
        mock_client = MagicMock()
        mock_client.inspect_tool_call.side_effect = [
            _make_http_status_error(429),
            _mcp_allow(),
        ]
        with patch.object(inspector, "_get_mcp_client", return_value=mock_client):
            decision = inspector.inspect_request(
                tool_name="test_tool",
                arguments={},
                metadata={},
            )
        assert decision.action == "allow"
        assert mock_client.inspect_tool_call.call_count == 2

    def test_all_retries_exhausted_fail_closed(self):
        """MCP: all retries return 502 → raises SecurityPolicyError."""
        inspector = MCPInspector(
            api_key=API_KEY_64,
            endpoint="https://test.example.com",
            retry_total=2,
            retry_backoff=0,
            fail_open=False,
        )
        mock_client = MagicMock()
        mock_client.inspect_tool_call.side_effect = [
            _make_http_status_error(502),
            _make_http_status_error(502),
        ]
        with patch.object(inspector, "_get_mcp_client", return_value=mock_client):
            with pytest.raises(SecurityPolicyError):
                inspector.inspect_request(
                    tool_name="test_tool",
                    arguments={},
                    metadata={},
                )
        assert mock_client.inspect_tool_call.call_count == 2

    def test_no_retry_on_http_400(self):
        """MCP: HTTP 400 (client error) → no retry, single call."""
        inspector = MCPInspector(
            api_key=API_KEY_64,
            endpoint="https://test.example.com",
            retry_total=3,
            retry_backoff=0,
            fail_open=True,
        )
        mock_client = MagicMock()
        mock_client.inspect_tool_call.side_effect = _make_http_status_error(400)
        with patch.object(inspector, "_get_mcp_client", return_value=mock_client):
            decision = inspector.inspect_request(
                tool_name="test_tool",
                arguments={},
                metadata={},
            )
        assert decision.action == "allow"
        assert mock_client.inspect_tool_call.call_count == 1


# ===========================================================================
# 7. MCP Inspector — Backoff Factor
# ===========================================================================

class TestMCPInspectorBackoff:
    """Test MCP Inspector exponential backoff behavior."""

    def test_backoff_delays_correct(self):
        """MCP: time.sleep called with correct exponential backoff delays."""
        inspector = MCPInspector(
            api_key=API_KEY_64,
            endpoint="https://test.example.com",
            retry_total=4,
            retry_backoff=0.25,  # 0.25*2^0=0.25, 0.25*2^1=0.5, 0.25*2^2=1.0
            fail_open=True,
        )
        mock_client = MagicMock()
        mock_client.inspect_tool_call.side_effect = [
            httpx.TimeoutException("timeout"),
            httpx.TimeoutException("timeout"),
            httpx.TimeoutException("timeout"),
            _mcp_allow(),
        ]
        with (
            patch.object(inspector, "_get_mcp_client", return_value=mock_client),
            patch("time.sleep") as mock_sleep,
        ):
            decision = inspector.inspect_request(
                tool_name="test_tool",
                arguments={},
                metadata={},
            )
        assert decision.action == "allow"
        assert mock_sleep.call_count == 3
        delays = [c.args[0] for c in mock_sleep.call_args_list]
        assert delays == pytest.approx([0.25, 0.5, 1.0])

    def test_backoff_capped_at_max(self):
        """MCP: backoff is capped at MAX_BACKOFF_DELAY (30s)."""
        inspector = MCPInspector(
            api_key=API_KEY_64,
            endpoint="https://test.example.com",
            retry_total=2,
            retry_backoff=20.0,
        )
        assert inspector._get_backoff_delay(0) == 20.0
        assert inspector._get_backoff_delay(1) == 30.0  # capped
        assert inspector._get_backoff_delay(10) == 30.0  # capped


# ===========================================================================
# 8. MCP Inspector — Timeout
# ===========================================================================

class TestMCPInspectorTimeout:
    """Test MCP Inspector timeout handling."""

    def test_timeout_fail_open_allows(self):
        """MCP: timeout with fail_open=True allows the tool call."""
        inspector = MCPInspector(
            api_key=API_KEY_64,
            endpoint="https://test.example.com",
            timeout_ms=5000,
            retry_total=1,
            fail_open=True,
        )
        mock_client = MagicMock()
        mock_client.inspect_tool_call.side_effect = httpx.TimeoutException("timed out")
        with patch.object(inspector, "_get_mcp_client", return_value=mock_client):
            decision = inspector.inspect_request(
                tool_name="test_tool",
                arguments={},
                metadata={},
            )
        assert decision.action == "allow"
        assert any("fail_open" in r for r in decision.reasons)

    def test_timeout_fail_closed_raises(self):
        """MCP: timeout with fail_open=False raises InspectionTimeoutError."""
        inspector = MCPInspector(
            api_key=API_KEY_64,
            endpoint="https://test.example.com",
            timeout_ms=3000,
            retry_total=1,
            fail_open=False,
        )
        mock_client = MagicMock()
        mock_client.inspect_tool_call.side_effect = httpx.TimeoutException("timed out")
        with patch.object(inspector, "_get_mcp_client", return_value=mock_client):
            with pytest.raises(InspectionTimeoutError) as exc_info:
                inspector.inspect_request(
                    tool_name="test_tool",
                    arguments={},
                    metadata={},
                )
        assert exc_info.value.timeout_ms == 3000

    def test_connect_error_fail_closed_raises_network_error(self):
        """MCP: connect error with fail_open=False raises InspectionNetworkError."""
        inspector = MCPInspector(
            api_key=API_KEY_64,
            endpoint="https://test.example.com",
            retry_total=1,
            fail_open=False,
        )
        mock_client = MagicMock()
        mock_client.inspect_tool_call.side_effect = httpx.ConnectError("refused")
        with patch.object(inspector, "_get_mcp_client", return_value=mock_client):
            with pytest.raises(InspectionNetworkError):
                inspector.inspect_request(
                    tool_name="test_tool",
                    arguments={},
                    metadata={},
                )

    def test_timeout_retried_then_success(self):
        """MCP: timeout on first attempt, success on second."""
        inspector = MCPInspector(
            api_key=API_KEY_64,
            endpoint="https://test.example.com",
            retry_total=2,
            retry_backoff=0,
            fail_open=False,
        )
        mock_client = MagicMock()
        mock_client.inspect_tool_call.side_effect = [
            httpx.TimeoutException("timed out"),
            _mcp_allow(),
        ]
        with patch.object(inspector, "_get_mcp_client", return_value=mock_client):
            decision = inspector.inspect_request(
                tool_name="test_tool",
                arguments={},
                metadata={},
            )
        assert decision.action == "allow"
        assert mock_client.inspect_tool_call.call_count == 2


# ===========================================================================
# 9. MCP Inspector — inspect_response retry
# ===========================================================================

class TestMCPInspectorResponseRetry:
    """Test retry behavior for MCPInspector.inspect_response."""

    def test_inspect_response_retry_on_503(self):
        """MCP inspect_response retries on 503."""
        inspector = MCPInspector(
            api_key=API_KEY_64,
            endpoint="https://test.example.com",
            retry_total=2,
            retry_backoff=0,
            fail_open=False,
        )
        mock_client = MagicMock()
        mock_client.inspect_response.side_effect = [
            _make_http_status_error(503),
            _mcp_allow(),
        ]
        with patch.object(inspector, "_get_mcp_client", return_value=mock_client):
            decision = inspector.inspect_response(
                tool_name="test_tool",
                arguments={},
                result="result data",
                metadata={},
            )
        assert decision.action == "allow"
        assert mock_client.inspect_response.call_count == 2

    def test_inspect_response_timeout_fail_open(self):
        """MCP inspect_response timeout with fail_open=True."""
        inspector = MCPInspector(
            api_key=API_KEY_64,
            endpoint="https://test.example.com",
            timeout_ms=5000,
            retry_total=1,
            fail_open=True,
        )
        mock_client = MagicMock()
        mock_client.inspect_response.side_effect = httpx.TimeoutException("timed out")
        with patch.object(inspector, "_get_mcp_client", return_value=mock_client):
            decision = inspector.inspect_response(
                tool_name="test_tool",
                arguments={},
                result="result",
                metadata={},
            )
        assert decision.action == "allow"


# ===========================================================================
# 10. MCP Inspector — _should_retry classification
# ===========================================================================

class TestMCPInspectorShouldRetry:
    """Test _should_retry for MCPInspector."""

    @pytest.fixture
    def inspector(self):
        return MCPInspector(
            api_key=API_KEY_64,
            endpoint="https://test.example.com",
            retry_status_codes=[500, 502, 503, 504],
        )

    def test_timeout_retryable(self, inspector):
        assert inspector._should_retry(httpx.TimeoutException("t")) is True

    def test_connect_error_retryable(self, inspector):
        assert inspector._should_retry(httpx.ConnectError("c")) is True

    def test_requests_timeout_retryable(self, inspector):
        assert inspector._should_retry(requests.exceptions.Timeout("t")) is True

    def test_http_503_retryable(self, inspector):
        assert inspector._should_retry(_make_http_status_error(503)) is True

    def test_http_400_not_retryable(self, inspector):
        assert inspector._should_retry(_make_http_status_error(400)) is False

    def test_json_error_not_retryable(self, inspector):
        assert inspector._should_retry(json.JSONDecodeError("j", "", 0)) is False

    def test_generic_error_not_retryable(self, inspector):
        assert inspector._should_retry(ValueError("v")) is False


# ===========================================================================
# 11. GatewayClient — Retry on Status Codes
# ===========================================================================

class TestGatewayClientRetryOnStatusCodes:
    """Test GatewayClient retries on configured status codes."""

    def test_retry_on_http_503_then_success(self):
        """Gateway: first call 503, second succeeds."""
        client = GatewayClient(
            gateway_url="https://gw.example.com/v1/chat/completions",
            api_key="test-key",
            timeout_ms=30000,
            retry_attempts=3,
            retry_backoff=0,
        )
        mock_response_ok = MagicMock()
        mock_response_ok.status_code = 200
        mock_response_ok.json.return_value = {"choices": []}
        mock_response_ok.raise_for_status = MagicMock()

        mock_httpx_client = MagicMock()
        mock_httpx_client.post.side_effect = [
            _make_http_status_error(503),
            mock_response_ok,
        ]
        with patch.object(client, "_get_sync_client", return_value=mock_httpx_client):
            result = client.call({"model": "gpt-4", "messages": []})
        assert result == {"choices": []}
        assert mock_httpx_client.post.call_count == 2

    def test_retry_on_http_429_rate_limit(self):
        """Gateway: 429 rate limit retried, then succeeds."""
        client = GatewayClient(
            gateway_url="https://gw.example.com",
            api_key="key",
            retry_attempts=2,
            retry_backoff=0,
        )
        mock_response_ok = MagicMock()
        mock_response_ok.status_code = 200
        mock_response_ok.json.return_value = {"ok": True}
        mock_response_ok.raise_for_status = MagicMock()

        mock_httpx_client = MagicMock()
        mock_httpx_client.post.side_effect = [
            _make_http_status_error(429),
            mock_response_ok,
        ]
        with patch.object(client, "_get_sync_client", return_value=mock_httpx_client):
            result = client.call({"model": "gpt-4", "messages": []})
        assert result == {"ok": True}
        assert mock_httpx_client.post.call_count == 2

    def test_no_retry_on_http_400(self):
        """Gateway: 400 not retried."""
        client = GatewayClient(
            gateway_url="https://gw.example.com",
            api_key="key",
            retry_attempts=3,
            retry_backoff=0,
            fail_open=True,
        )
        mock_httpx_client = MagicMock()
        mock_httpx_client.post.side_effect = _make_http_status_error(400)
        with patch.object(client, "_get_sync_client", return_value=mock_httpx_client):
            result = client.call({"model": "gpt-4", "messages": []})
        # fail_open=True → returns error dict
        assert "error" in result
        assert mock_httpx_client.post.call_count == 1

    def test_all_retries_exhausted_fail_closed(self):
        """Gateway: all retries return 500 → raises SecurityPolicyError."""
        client = GatewayClient(
            gateway_url="https://gw.example.com",
            api_key="key",
            retry_attempts=2,
            retry_backoff=0,
            fail_open=False,
        )
        mock_httpx_client = MagicMock()
        mock_httpx_client.post.side_effect = [
            _make_http_status_error(500),
            _make_http_status_error(500),
        ]
        with patch.object(client, "_get_sync_client", return_value=mock_httpx_client):
            with pytest.raises(SecurityPolicyError):
                client.call({"model": "gpt-4", "messages": []})
        assert mock_httpx_client.post.call_count == 2


# ===========================================================================
# 12. GatewayClient — Backoff
# ===========================================================================

class TestGatewayClientBackoff:
    """Test GatewayClient exponential backoff."""

    def test_backoff_factor_timing(self):
        """Gateway: time.sleep called with correct backoff delays."""
        client = GatewayClient(
            gateway_url="https://gw.example.com",
            api_key="key",
            retry_attempts=4,
            retry_backoff=0.5,
            fail_open=True,
        )
        mock_response_ok = MagicMock()
        mock_response_ok.status_code = 200
        mock_response_ok.json.return_value = {"ok": True}
        mock_response_ok.raise_for_status = MagicMock()

        mock_httpx_client = MagicMock()
        mock_httpx_client.post.side_effect = [
            httpx.TimeoutException("timeout"),
            httpx.TimeoutException("timeout"),
            httpx.TimeoutException("timeout"),
            mock_response_ok,
        ]
        with (
            patch.object(client, "_get_sync_client", return_value=mock_httpx_client),
            patch("time.sleep") as mock_sleep,
        ):
            result = client.call({"model": "gpt-4", "messages": []})
        assert result == {"ok": True}
        assert mock_sleep.call_count == 3
        delays = [c.args[0] for c in mock_sleep.call_args_list]
        assert delays == pytest.approx([0.5, 1.0, 2.0])

    def test_backoff_capped_at_max(self):
        """Gateway: backoff capped at MAX_BACKOFF_DELAY."""
        client = GatewayClient(
            gateway_url="https://gw.example.com",
            api_key="key",
            retry_backoff=20.0,
        )
        assert client._get_backoff_delay(0) == 20.0
        assert client._get_backoff_delay(1) == 30.0  # capped


# ===========================================================================
# 13. GatewayClient — Timeout
# ===========================================================================

class TestGatewayClientTimeout:
    """Test GatewayClient timeout behavior."""

    def test_timeout_fail_open_returns_error_dict(self):
        """Gateway: timeout with fail_open=True returns error dict."""
        client = GatewayClient(
            gateway_url="https://gw.example.com",
            api_key="key",
            timeout_ms=5000,
            retry_attempts=1,
            fail_open=True,
        )
        mock_httpx_client = MagicMock()
        mock_httpx_client.post.side_effect = httpx.TimeoutException("timed out")
        with patch.object(client, "_get_sync_client", return_value=mock_httpx_client):
            result = client.call({"model": "gpt-4", "messages": []})
        assert "error" in result
        assert result.get("fail_open") is True

    def test_timeout_fail_closed_raises(self):
        """Gateway: timeout with fail_open=False raises SecurityPolicyError."""
        client = GatewayClient(
            gateway_url="https://gw.example.com",
            api_key="key",
            timeout_ms=5000,
            retry_attempts=1,
            fail_open=False,
        )
        mock_httpx_client = MagicMock()
        mock_httpx_client.post.side_effect = httpx.TimeoutException("timed out")
        with patch.object(client, "_get_sync_client", return_value=mock_httpx_client):
            with pytest.raises(SecurityPolicyError):
                client.call({"model": "gpt-4", "messages": []})


# ===========================================================================
# 14. State — retry_status_codes Propagation
# ===========================================================================

class TestStateRetryStatusCodesPropagation:
    """Test that retry_status_codes flows correctly through _state to inspectors."""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        _state.reset()
        yield
        _state.reset()

    def test_default_retry_status_codes(self):
        """Default retry_status_codes are [429, 500, 502, 503, 504]."""
        assert _state.get_api_llm_retry_status_codes() == [429, 500, 502, 503, 504]
        assert _state.get_api_mcp_retry_status_codes() == [429, 500, 502, 503, 504]

    def test_custom_retry_status_codes_via_set_state(self):
        """Custom retry_status_codes set via set_state propagate to getters."""
        _state.set_state(
            initialized=True,
            api_mode={
                "llm": {"mode": "monitor"},
                "mcp": {"mode": "monitor"},
                "llm_defaults": {
                    "retry": {"status_codes": [502, 503]},
                },
                "mcp_defaults": {
                    "retry": {"status_codes": [429, 503, 504]},
                },
            },
        )
        assert _state.get_api_llm_retry_status_codes() == [502, 503]
        assert _state.get_api_mcp_retry_status_codes() == [429, 503, 504]

    def test_retry_status_codes_flow_to_llm_inspector(self):
        """retry_status_codes from _state flow into LLMInspector."""
        _state.set_state(
            initialized=True,
            api_mode={
                "llm": {"mode": "monitor"},
                "mcp": {"mode": "monitor"},
                "llm_defaults": {
                    "retry": {"status_codes": [418, 503]},
                },
            },
        )
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
        )
        assert inspector.retry_status_codes == [418, 503]

    def test_retry_status_codes_flow_to_mcp_inspector(self):
        """retry_status_codes from _state flow into MCPInspector."""
        _state.set_state(
            initialized=True,
            api_mode={
                "llm": {"mode": "monitor"},
                "mcp": {"mode": "monitor"},
                "mcp_defaults": {
                    "retry": {"status_codes": [500, 504]},
                },
            },
        )
        inspector = MCPInspector(
            api_key=API_KEY_64,
            endpoint="https://test.example.com",
        )
        assert inspector.retry_status_codes == [500, 504]
        inspector.close()

    def test_explicit_param_overrides_state(self):
        """Explicit retry_status_codes param overrides _state value."""
        _state.set_state(
            initialized=True,
            api_mode={
                "llm": {"mode": "monitor"},
                "mcp": {"mode": "monitor"},
                "llm_defaults": {
                    "retry": {"status_codes": [503]},
                },
            },
        )
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            retry_status_codes=[418, 429],
        )
        assert inspector.retry_status_codes == [418, 429]


# ===========================================================================
# 15. State — retry_status_codes in Gateway Resolution
# ===========================================================================

class TestStateRetryStatusCodesGatewayResolution:
    """Test retry_status_codes in resolve_llm_gateway_settings and resolve_mcp_gateway_settings."""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        _state.reset()
        yield
        _state.reset()

    def test_resolve_llm_gateway_default_status_codes(self):
        """LLM gateway resolution uses default retry_status_codes."""
        _state.set_state(initialized=True, llm_integration_mode="gateway")
        gw = _state.resolve_llm_gateway_settings({
            "gateway_url": "https://gw.example.com",
            "gateway_api_key": "key",
        })
        assert gw.retry_status_codes == [429, 500, 502, 503, 504]

    def test_resolve_llm_gateway_custom_status_codes(self):
        """LLM gateway per-gateway retry.status_codes override defaults."""
        _state.set_state(initialized=True, llm_integration_mode="gateway")
        gw = _state.resolve_llm_gateway_settings({
            "gateway_url": "https://gw.example.com",
            "gateway_api_key": "key",
            "retry": {
                "status_codes": [502, 504],
            },
        })
        assert gw.retry_status_codes == [502, 504]

    def test_resolve_llm_gateway_defaults_from_config(self):
        """LLM gateway defaults from gateway_mode.llm_defaults propagate."""
        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            gateway_mode={
                "llm_defaults": {
                    "retry": {
                        "status_codes": [418, 503],
                    },
                },
            },
        )
        gw = _state.resolve_llm_gateway_settings({
            "gateway_url": "https://gw.example.com",
            "gateway_api_key": "key",
        })
        assert gw.retry_status_codes == [418, 503]

    def test_resolve_mcp_gateway_default_status_codes(self):
        """MCP gateway resolution uses default retry_status_codes."""
        _state.set_state(initialized=True, mcp_integration_mode="gateway")
        gw = _state.resolve_mcp_gateway_settings({
            "gateway_url": "https://mcp-gw.example.com",
        })
        assert gw.retry_status_codes == [429, 500, 502, 503, 504]

    def test_resolve_mcp_gateway_custom_status_codes(self):
        """MCP gateway per-gateway retry.status_codes override defaults."""
        _state.set_state(initialized=True, mcp_integration_mode="gateway")
        gw = _state.resolve_mcp_gateway_settings({
            "gateway_url": "https://mcp-gw.example.com",
            "retry": {
                "status_codes": [429, 502],
            },
        })
        assert gw.retry_status_codes == [429, 502]


# ===========================================================================
# 16. State — retry_total and retry_backoff propagation
# ===========================================================================

class TestStateRetryConfigPropagation:
    """Test retry_total and retry_backoff flow from _state to inspectors."""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        _state.reset()
        yield
        _state.reset()

    def test_retry_total_and_backoff_flow_to_llm_inspector(self):
        """retry_total and retry_backoff from api_mode.llm_defaults flow to LLMInspector."""
        _state.set_state(
            initialized=True,
            api_mode={
                "llm": {"mode": "monitor"},
                "mcp": {"mode": "monitor"},
                "llm_defaults": {
                    "retry": {
                        "total": 5,
                        "backoff_factor": 1.5,
                    },
                },
            },
        )
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
        )
        assert inspector.retry_total == 5
        assert inspector.retry_backoff == 1.5

    def test_retry_total_and_backoff_flow_to_mcp_inspector(self):
        """retry_total and retry_backoff from api_mode.mcp_defaults flow to MCPInspector."""
        _state.set_state(
            initialized=True,
            api_mode={
                "llm": {"mode": "monitor"},
                "mcp": {"mode": "monitor"},
                "mcp_defaults": {
                    "retry": {
                        "total": 4,
                        "backoff_factor": 2.0,
                    },
                },
            },
        )
        inspector = MCPInspector(
            api_key=API_KEY_64,
            endpoint="https://test.example.com",
        )
        assert inspector.retry_total == 4
        assert inspector.retry_backoff == 2.0
        inspector.close()

    def test_timeout_flows_from_state_to_llm_inspector(self):
        """timeout from api_mode.llm_defaults flows to LLMInspector (seconds → ms)."""
        _state.set_state(
            initialized=True,
            api_mode={
                "llm": {"mode": "monitor"},
                "mcp": {"mode": "monitor"},
                "llm_defaults": {
                    "timeout": 10,  # 10 seconds
                },
            },
        )
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
        )
        assert inspector.timeout_ms == 10000  # 10 * 1000

    def test_timeout_flows_from_state_to_mcp_inspector(self):
        """timeout from api_mode.mcp_defaults flows to MCPInspector (seconds → ms)."""
        _state.set_state(
            initialized=True,
            api_mode={
                "llm": {"mode": "monitor"},
                "mcp": {"mode": "monitor"},
                "mcp_defaults": {
                    "timeout": 7,  # 7 seconds
                },
            },
        )
        inspector = MCPInspector(
            api_key=API_KEY_64,
            endpoint="https://test.example.com",
        )
        assert inspector.timeout_ms == 7000  # 7 * 1000
        inspector.close()


# ===========================================================================
# 17. Mixed Retry Scenarios
# ===========================================================================

class TestMixedRetryScenarios:
    """Test complex retry scenarios mixing different error types."""

    def test_llm_timeout_then_500_then_success(self):
        """LLM: timeout → 500 → success (different error types across retries)."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            retry_total=3,
            retry_backoff=0,
            fail_open=False,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = [
            httpx.TimeoutException("timeout"),
            _make_http_status_error(500),
            _allow_response(),
        ]
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "Hello"}],
                metadata={},
            )
        assert decision.action == "allow"
        assert mock_client.inspect_conversation.call_count == 3

    def test_llm_connect_error_then_timeout_then_400_stops(self):
        """LLM: connect error → timeout → 400 (stops, 400 not retryable)."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            retry_total=5,
            retry_backoff=0,
            fail_open=True,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = [
            httpx.ConnectError("refused"),
            httpx.TimeoutException("timeout"),
            _make_http_status_error(400),
        ]
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "Hello"}],
                metadata={},
            )
        # 400 is not retryable, so stops after 3 calls even though retry_total=5
        assert decision.action == "allow"
        assert mock_client.inspect_conversation.call_count == 3

    def test_mcp_request_timeout_then_connect_error_then_success(self):
        """MCP: timeout → connect error → success."""
        inspector = MCPInspector(
            api_key=API_KEY_64,
            endpoint="https://test.example.com",
            retry_total=3,
            retry_backoff=0,
            fail_open=False,
        )
        mock_client = MagicMock()
        mock_client.inspect_tool_call.side_effect = [
            httpx.TimeoutException("timeout"),
            httpx.ConnectError("refused"),
            _mcp_allow(),
        ]
        with patch.object(inspector, "_get_mcp_client", return_value=mock_client):
            decision = inspector.inspect_request(
                tool_name="test_tool",
                arguments={},
                metadata={},
            )
        assert decision.action == "allow"
        assert mock_client.inspect_tool_call.call_count == 3

    def test_json_decode_error_never_retried(self):
        """JSON decode error is never retried regardless of retry_total."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            retry_total=5,
            retry_backoff=0,
            fail_open=True,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = json.JSONDecodeError("bad", "", 0)
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "Hello"}],
                metadata={},
            )
        assert decision.action == "allow"
        # Should only call once — JSON error not retryable
        assert mock_client.inspect_conversation.call_count == 1


# ===========================================================================
# 18. Timeout Truncation — Sub-second values
# ===========================================================================

class TestTimeoutTruncation:
    """Verify sub-second timeout_ms values don't truncate to 0 (AIFW-18900)."""

    def test_sub_second_timeout_ms_clamped_to_1_second(self):
        """timeout_ms=100 should produce at least 1-second config, not 0."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            timeout_ms=100,
            fail_open=False,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = httpx.TimeoutException("timed out")
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            with pytest.raises(InspectionTimeoutError):
                inspector.inspect_conversation(
                    messages=[{"role": "user", "content": "test"}],
                    metadata={},
                )

    def test_timeout_ms_1000_produces_1_second(self):
        """timeout_ms=1000 should produce exactly 1-second timeout."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            timeout_ms=1000,
            fail_open=False,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = httpx.TimeoutException("timed out")
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            with pytest.raises(InspectionTimeoutError) as exc_info:
                inspector.inspect_conversation(
                    messages=[{"role": "user", "content": "test"}],
                    metadata={},
                )
        assert exc_info.value.timeout_ms == 1000


# ===========================================================================
# 19. SDK ApiError Retry
# ===========================================================================

class TestSDKApiErrorRetry:
    """Verify that SDK's own ApiError (from request handler) is retried on
    configured status codes (AIFW-18900)."""

    def test_api_error_500_retried(self):
        """ApiError with status_code=500 should be retried."""
        from aidefense.exceptions import ApiError as SDKApiError

        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            retry_total=2,
            retry_backoff=0,
            fail_open=False,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = [
            SDKApiError("Server error", status_code=500),
            _allow_response(),
        ]
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "test"}],
                metadata={},
            )
        assert decision.action == "allow"
        assert mock_client.inspect_conversation.call_count == 2

    def test_api_error_400_not_retried(self):
        """ApiError with status_code=400 (not in retry codes) should not retry."""
        from aidefense.exceptions import ApiError as SDKApiError

        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            retry_total=3,
            retry_backoff=0,
            fail_open=True,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = SDKApiError("Bad request", status_code=400)
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "test"}],
                metadata={},
            )
        assert decision.action == "allow"
        assert mock_client.inspect_conversation.call_count == 1


# ===========================================================================
# 20. ValueError Timeout Classification
# ===========================================================================

class TestValueErrorTimeoutClassification:
    """Verify that ValueError about timeout is classified as
    InspectionTimeoutError, not generic SecurityPolicyError (AIFW-18900)."""

    def test_value_error_timeout_raises_inspection_timeout(self):
        """ValueError mentioning 'timeout' should become InspectionTimeoutError."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            timeout_ms=5000,
            fail_open=False,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = ValueError(
            "Attempted to set connect timeout to 0, but the timeout cannot be set "
            "to a value less than or equal to 0."
        )
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            with pytest.raises(InspectionTimeoutError):
                inspector.inspect_conversation(
                    messages=[{"role": "user", "content": "test"}],
                    metadata={},
                )

    def test_non_timeout_value_error_raises_security_policy(self):
        """ValueError NOT about timeout should become SecurityPolicyError."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            fail_open=False,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = ValueError("Invalid format")
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            with pytest.raises(SecurityPolicyError):
                inspector.inspect_conversation(
                    messages=[{"role": "user", "content": "test"}],
                    metadata={},
                )


# ===========================================================================
# 21. Malformed Response Handling
# ===========================================================================

class TestMalformedResponseHandling:
    """Verify that malformed JSON responses are handled gracefully."""

    def test_malformed_response_fail_open_allows(self):
        """Malformed JSON with fail_open=True should allow the request."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            fail_open=True,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = json.JSONDecodeError("bad json", "", 0)
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "test"}],
                metadata={},
            )
        assert decision.action == "allow"

    def test_malformed_response_fail_closed_raises(self):
        """Malformed JSON with fail_open=False should raise SecurityPolicyError."""
        inspector = LLMInspector(
            api_key=API_KEY_64,
            endpoint="http://test.example.com",
            fail_open=False,
        )
        mock_client = MagicMock()
        mock_client.inspect_conversation.side_effect = json.JSONDecodeError("bad json", "", 0)
        with patch.object(inspector, "_get_chat_client", return_value=mock_client):
            with pytest.raises(SecurityPolicyError):
                inspector.inspect_conversation(
                    messages=[{"role": "user", "content": "test"}],
                    metadata={},
                )
