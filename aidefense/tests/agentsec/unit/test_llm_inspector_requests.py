"""Tests for LLMInspector with HTTP mocking (Task Group 7).

LLMInspector uses ChatInspectionClient which uses requests.Session;
we mock requests.Session.request so no real HTTP is made.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from aidefense.runtime.agentsec.inspectors.api_llm import LLMInspector
from aidefense.runtime.agentsec.exceptions import (
    InspectionTimeoutError,
    InspectionNetworkError,
)

# API key must be 64 characters (RuntimeAuth validation)
TEST_API_KEY = "0" * 64


def _mock_session_request(response_json, status_code=200):
    """Patch requests.Session.request to return response_json. Use action 'Allow' or 'Block' (InspectResponse enum)."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = response_json
    return patch("requests.Session.request", return_value=mock_response)


class TestLLMInspectorHTTPX:
    """Tests for LLMInspector with mocked HTTP (requests layer)."""

    def test_successful_api_response_allow(self):
        """Test successful API response returns correct Decision for allow."""
        with _mock_session_request({"action": "Allow", "reasons": [], "is_safe": True}):
            inspector = LLMInspector(
                api_key=TEST_API_KEY,
                endpoint="http://test.api",
            )
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "Hello"}],
                metadata={},
            )
        assert decision.action == "allow"
        assert decision.reasons == []

    def test_successful_api_response_block(self):
        """Test successful API response returns correct Decision for block."""
        with _mock_session_request({
            "action": "Block",
            "reasons": ["pii_detected", "policy_violation"],
            "is_safe": False,
            "explanation": "pii_detected",
        }):
            inspector = LLMInspector(
                api_key=TEST_API_KEY,
                endpoint="http://test.api",
            )
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "My SSN is 123-45-6789"}],
                metadata={},
            )
        assert decision.action == "block"
        assert "pii_detected" in decision.reasons

    def test_successful_api_response_sanitize(self):
        """Test successful API response returns correct Decision for sanitize."""
        # InspectResponse supports Allow/Block; use Block with explanation for content_modified
        with _mock_session_request({
            "action": "Block",
            "reasons": ["content_modified"],
            "is_safe": False,
            "explanation": "content_modified",
        }):
            inspector = LLMInspector(
                api_key=TEST_API_KEY,
                endpoint="http://test.api",
            )
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "My SSN is 123-45-6789"}],
                metadata={},
            )
        assert decision.action == "block"
        assert "content_modified" in decision.reasons

    def test_timeout_handling_fail_open_true(self):
        """Test timeout handling with fail_open=True allows request."""
        import requests
        with patch("requests.Session.request", side_effect=requests.exceptions.Timeout("timed out")):
            inspector = LLMInspector(
                api_key=TEST_API_KEY,
                endpoint="http://test.api",
                timeout_ms=5000,
                fail_open=True,
            )
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "test"}],
                metadata={},
            )
        assert decision.action == "allow"

    def test_timeout_handling_fail_open_false(self):
        """Test timeout handling with fail_open=False raises InspectionTimeoutError."""
        import requests
        with patch("requests.Session.request", side_effect=requests.exceptions.Timeout("timed out")):
            inspector = LLMInspector(
                api_key=TEST_API_KEY,
                endpoint="http://test.api",
                timeout_ms=5000,
                fail_open=False,
            )
            with pytest.raises(InspectionTimeoutError):
                inspector.inspect_conversation(
                    messages=[{"role": "user", "content": "test"}],
                    metadata={},
                )

    def test_retry_logic_on_transient_failure(self):
        """Test retry logic on transient failures."""
        import requests
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise requests.exceptions.ConnectionError("Connection refused")
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"action": "Allow", "reasons": [], "is_safe": True}
            return mock_response

        with patch("requests.Session.request", side_effect=side_effect):
            inspector = LLMInspector(
                api_key=TEST_API_KEY,
                endpoint="http://test.api",
                retry_attempts=2,
                fail_open=False,
            )
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "test"}],
                metadata={},
            )
        assert decision.action == "allow"

    def test_all_decision_types_from_api(self):
        """Test handling all decision types from API responses."""
        # InspectResponse uses Allow/Block; test both
        with _mock_session_request({"action": "Allow", "reasons": [], "is_safe": True}):
            inspector = LLMInspector(
                api_key=TEST_API_KEY,
                endpoint="http://test.api",
            )
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "test"}],
                metadata={},
            )
        assert decision.action == "allow"

        with _mock_session_request({"action": "Block", "reasons": ["logged"], "is_safe": False}):
            decision = inspector.inspect_conversation(
                messages=[{"role": "user", "content": "test2"}],
                metadata={},
            )
        assert decision.action == "block"


class TestLLMInspectorAsyncHTTPX:
    """Async tests for LLMInspector with mocked client."""

    @pytest.mark.asyncio
    async def test_async_inspect_success(self):
        """Test async ainspect_conversation works correctly."""
        from aidefense.runtime.models import InspectResponse, Action
        inspector = LLMInspector(
            api_key=TEST_API_KEY,
            endpoint="http://test.api",
        )
        mock_client = AsyncMock()
        mock_client.inspect_conversation = AsyncMock(
            return_value=InspectResponse(
                action=Action.BLOCK,
                is_safe=False,
                classifications=[],
                explanation="policy_violation",
            )
        )
        with patch.object(inspector, "_get_async_chat_client", return_value=mock_client):
            decision = await inspector.ainspect_conversation(
                messages=[{"role": "user", "content": "test"}],
                metadata={},
            )
        assert decision.action == "block"
        assert "policy_violation" in decision.reasons
