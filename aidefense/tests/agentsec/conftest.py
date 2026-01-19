"""Shared pytest fixtures for agentsec tests."""

import pytest
from typing import Generator
from unittest.mock import MagicMock


@pytest.fixture
def reset_state() -> Generator[None, None, None]:
    """Reset agentsec state before and after each test."""
    from aidefense.runtime.agentsec._state import reset
    reset()
    yield
    reset()


@pytest.fixture
def reset_patch_registry() -> Generator[None, None, None]:
    """Reset the patch registry before and after each test."""
    from aidefense.runtime.agentsec.patchers import reset_registry
    reset_registry()
    yield
    reset_registry()


@pytest.fixture
def reset_all(reset_state: None, reset_patch_registry: None) -> None:
    """Reset both state and patch registry."""
    pass


@pytest.fixture
def mock_ai_defense_allow() -> dict:
    """Mock AI Defense API response for allow action."""
    return {
        "action": "allow",
        "reasons": [],
    }


@pytest.fixture
def mock_ai_defense_block() -> dict:
    """Mock AI Defense API response for block action."""
    return {
        "action": "block",
        "reasons": ["policy_violation", "pii_detected"],
    }


@pytest.fixture
def mock_ai_defense_sanitize() -> dict:
    """Mock AI Defense API response for sanitize action."""
    return {
        "action": "sanitize",
        "reasons": ["content_modified"],
        "sanitized_content": "This is sanitized content",
    }


@pytest.fixture
def mock_ai_defense_monitor() -> dict:
    """Mock AI Defense API response for monitor_only action."""
    return {
        "action": "monitor_only",
        "reasons": ["logged_for_review"],
    }


@pytest.fixture
def sample_messages() -> list:
    """Sample conversation messages for testing."""
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]


@pytest.fixture
def sample_metadata() -> dict:
    """Sample metadata for testing."""
    return {
        "user_id": "test-user-123",
        "session_id": "session-456",
        "application": "test-app",
    }













