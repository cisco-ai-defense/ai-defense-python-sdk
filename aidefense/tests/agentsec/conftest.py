# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

"""Shared pytest fixtures for agentsec tests.

The agentsec test suite requires optional dependencies (wrapt, PyYAML, httpx)
that are not part of the base SDK install.  When any of them are missing the
entire ``aidefense/tests/agentsec/`` tree is excluded from collection so that
CI environments with only base deps are not affected.
"""

import importlib

import pytest
from typing import Generator
from unittest.mock import MagicMock

_REQUIRED_SPECS = ("wrapt", "yaml", "httpx")
_missing = [m for m in _REQUIRED_SPECS if importlib.util.find_spec(m) is None]
if _missing:
    collect_ignore_glob = ["unit/**/*.py", "**/*.py"]


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









