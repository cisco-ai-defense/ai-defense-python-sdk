"""Tests for LLMInspector using pytest-httpx (Task Group 7)."""

import pytest

from aidefense.runtime.agentsec.inspectors.api_llm import LLMInspector
from aidefense.runtime.agentsec.exceptions import SecurityPolicyError


# Check if pytest-httpx is available
pytest_httpx_available = True
try:
    from pytest_httpx import HTTPXMock
except ImportError:
    pytest_httpx_available = False
    HTTPXMock = None


@pytest.mark.skipif(not pytest_httpx_available, reason="pytest-httpx not installed")
class TestLLMInspectorHTTPX:
    """Tests for LLMInspector using pytest-httpx for HTTP mocking."""

    def test_successful_api_response_allow(self, httpx_mock: "HTTPXMock"):
        """Test successful API response returns correct Decision for allow."""
        httpx_mock.add_response(
            url="http://test.api/v1/inspect/chat",
            json={"action": "allow", "reasons": []},
        )
        
        inspector = LLMInspector(
            api_key="test-key",
            endpoint="http://test.api",
        )
        
        decision = inspector.inspect_conversation(
            messages=[{"role": "user", "content": "Hello"}],
            metadata={},
        )
        
        assert decision.action == "allow"
        assert decision.reasons == []

    def test_successful_api_response_block(self, httpx_mock: "HTTPXMock"):
        """Test successful API response returns correct Decision for block."""
        httpx_mock.add_response(
            url="http://test.api/v1/inspect/chat",
            json={"action": "block", "reasons": ["pii_detected", "policy_violation"]},
        )
        
        inspector = LLMInspector(
            api_key="test-key",
            endpoint="http://test.api",
        )
        
        decision = inspector.inspect_conversation(
            messages=[{"role": "user", "content": "My SSN is 123-45-6789"}],
            metadata={},
        )
        
        assert decision.action == "block"
        assert "pii_detected" in decision.reasons

    def test_successful_api_response_sanitize(self, httpx_mock: "HTTPXMock"):
        """Test successful API response returns correct Decision for sanitize."""
        httpx_mock.add_response(
            url="http://test.api/v1/inspect/chat",
            json={
                "action": "sanitize",
                "reasons": ["content_modified"],
                "sanitized_content": "My SSN is [REDACTED]",
            },
        )
        
        inspector = LLMInspector(
            api_key="test-key",
            endpoint="http://test.api",
        )
        
        decision = inspector.inspect_conversation(
            messages=[{"role": "user", "content": "My SSN is 123-45-6789"}],
            metadata={},
        )
        
        assert decision.action == "sanitize"
        assert decision.sanitized_content == "My SSN is [REDACTED]"

    def test_timeout_handling_fail_open_true(self, httpx_mock: "HTTPXMock"):
        """Test timeout handling with fail_open=True allows request."""
        import httpx
        
        httpx_mock.add_exception(
            httpx.TimeoutException("Connection timed out"),
            url="http://test.api/v1/inspect/chat",
        )
        
        inspector = LLMInspector(
            api_key="test-key",
            endpoint="http://test.api",
            timeout_ms=100,
            fail_open=True,
        )
        
        decision = inspector.inspect_conversation(
            messages=[{"role": "user", "content": "test"}],
            metadata={},
        )
        
        # fail_open=True should allow on timeout
        assert decision.action == "allow"

    def test_timeout_handling_fail_open_false(self, httpx_mock: "HTTPXMock"):
        """Test timeout handling with fail_open=False raises error."""
        import httpx
        
        httpx_mock.add_exception(
            httpx.TimeoutException("Connection timed out"),
            url="http://test.api/v1/inspect/chat",
        )
        
        inspector = LLMInspector(
            api_key="test-key",
            endpoint="http://test.api",
            timeout_ms=100,
            fail_open=False,
        )
        
        with pytest.raises(SecurityPolicyError):
            inspector.inspect_conversation(
                messages=[{"role": "user", "content": "test"}],
                metadata={},
            )

    def test_retry_logic_on_transient_failure(self, httpx_mock: "HTTPXMock"):
        """Test retry logic on transient failures."""
        import httpx
        
        # First call fails, second succeeds
        httpx_mock.add_exception(
            httpx.ConnectError("Connection refused"),
            url="http://test.api/v1/inspect/chat",
        )
        httpx_mock.add_response(
            url="http://test.api/v1/inspect/chat",
            json={"action": "allow", "reasons": []},
        )
        
        inspector = LLMInspector(
            api_key="test-key",
            endpoint="http://test.api",
            retry_attempts=2,
            fail_open=False,
        )
        
        decision = inspector.inspect_conversation(
            messages=[{"role": "user", "content": "test"}],
            metadata={},
        )
        
        # Should succeed on retry
        assert decision.action == "allow"

    def test_all_decision_types_from_api(self, httpx_mock: "HTTPXMock"):
        """Test handling all decision types from API responses."""
        inspector = LLMInspector(
            api_key="test-key",
            endpoint="http://test.api",
        )
        
        # Test allow
        httpx_mock.add_response(
            url="http://test.api/v1/inspect/chat",
            json={"action": "allow", "reasons": []},
        )
        decision = inspector.inspect_conversation(
            messages=[{"role": "user", "content": "test"}],
            metadata={},
        )
        assert decision.action == "allow"
        
        # Test monitor_only
        httpx_mock.add_response(
            url="http://test.api/v1/inspect/chat",
            json={"action": "monitor_only", "reasons": ["logged"]},
        )
        decision = inspector.inspect_conversation(
            messages=[{"role": "user", "content": "test2"}],
            metadata={},
        )
        assert decision.action == "monitor_only"


@pytest.mark.skipif(not pytest_httpx_available, reason="pytest-httpx not installed")
class TestLLMInspectorAsyncHTTPX:
    """Async tests for LLMInspector using pytest-httpx."""

    @pytest.mark.asyncio
    async def test_async_inspect_success(self, httpx_mock: "HTTPXMock"):
        """Test async ainspect_conversation works correctly."""
        httpx_mock.add_response(
            url="http://test.api/v1/inspect/chat",
            json={"action": "block", "reasons": ["policy_violation"]},
        )
        
        inspector = LLMInspector(
            api_key="test-key",
            endpoint="http://test.api",
        )
        
        decision = await inspector.ainspect_conversation(
            messages=[{"role": "user", "content": "test"}],
            metadata={},
        )
        
        assert decision.action == "block"
        assert "policy_violation" in decision.reasons

