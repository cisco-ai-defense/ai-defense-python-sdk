"""Shared fixtures for integration tests."""

import re
import pytest
from typing import Generator


@pytest.fixture
def reset_agentsec_state() -> Generator[None, None, None]:
    """Reset agentsec state for test isolation."""
    from aidefense.runtime.agentsec._state import reset
    from aidefense.runtime.agentsec.patchers import reset_registry
    
    reset()
    reset_registry()
    yield
    reset()
    reset_registry()


# Check if pytest-httpx is available
pytest_httpx_available = True
try:
    from pytest_httpx import HTTPXMock
except ImportError:
    pytest_httpx_available = False


if pytest_httpx_available:
    @pytest.fixture
    def mock_ai_defense_allow(httpx_mock: HTTPXMock) -> HTTPXMock:
        """Mock AI Defense API returning allow action."""
        httpx_mock.add_response(
            url=re.compile(r".*/v1/inspect/chat"),
            json={"action": "allow", "reasons": []},
        )
        return httpx_mock

    @pytest.fixture
    def mock_ai_defense_block(httpx_mock: HTTPXMock) -> HTTPXMock:
        """Mock AI Defense API returning block action."""
        httpx_mock.add_response(
            url=re.compile(r".*/v1/inspect/chat"),
            json={"action": "block", "reasons": ["policy_violation", "pii_detected"]},
        )
        return httpx_mock

    @pytest.fixture
    def mock_ai_defense_sanitize(httpx_mock: HTTPXMock) -> HTTPXMock:
        """Mock AI Defense API returning sanitize action."""
        httpx_mock.add_response(
            url=re.compile(r".*/v1/inspect/chat"),
            json={
                "action": "sanitize",
                "reasons": ["content_modified"],
                "sanitized_content": "Sanitized content here",
            },
        )
        return httpx_mock

    @pytest.fixture
    def mock_ai_defense_monitor(httpx_mock: HTTPXMock) -> HTTPXMock:
        """Mock AI Defense API returning monitor_only action."""
        httpx_mock.add_response(
            url=re.compile(r".*/v1/inspect/chat"),
            json={"action": "monitor_only", "reasons": ["logged_for_review"]},
        )
        return httpx_mock

