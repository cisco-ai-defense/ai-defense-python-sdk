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

"""Shared fixtures for async tests."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock

from aidefense.async_request_handler import AsyncRequestHandler
from aidefense.config import AsyncConfig
from aidefense.runtime.auth import AsyncAuth


@pytest.fixture
def reset_async_config():
    """Reset AsyncConfig singleton before and after each test."""
    AsyncConfig._instances = {}
    yield
    AsyncConfig._instances = {}


@pytest_asyncio.fixture
async def async_config(reset_async_config):
    """Provide a fresh AsyncConfig instance with event loop."""
    config = AsyncConfig(timeout=10)
    yield config
    # Cleanup
    if hasattr(config, "connection_pool") and config.connection_pool:
        await config.connection_pool.close()


@pytest_asyncio.fixture
async def handler(async_config):
    """Provide an AsyncRequestHandler instance."""
    handler = AsyncRequestHandler(async_config)
    yield handler
    # Cleanup
    if handler._session:
        await handler._session.close()


@pytest.fixture
def mock_auth():
    """Provide a mock AsyncAuth instance."""
    auth = AsyncMock(spec=AsyncAuth)
    auth.token = "a" * 64  # Valid 64-char token
    auth.validate.return_value = True
    return auth
