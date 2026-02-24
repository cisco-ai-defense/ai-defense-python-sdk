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

"""Tests for AsyncRequestHandler initialization."""

import aiohttp
import pytest

from aidefense.async_request_handler import AsyncRequestHandler
from aidefense.config import AsyncConfig


class TestAsyncRequestHandlerInit:
    """Tests for AsyncRequestHandler initialization."""

    @pytest.mark.asyncio
    async def test_init_creates_handler(self, async_config):
        """Test that handler initializes with config."""
        handler = AsyncRequestHandler(async_config)
        assert handler.config is async_config
        assert handler._session is None
        assert handler._timeout is not None
        assert handler._connector is not None

    @pytest.mark.asyncio
    async def test_init_applies_retry_decorator(self, async_config):
        """Test that retry decorator is applied during init."""
        handler = AsyncRequestHandler(async_config)
        # The request method should be wrapped by tenacity
        assert hasattr(handler.request, "retry")

    @pytest.mark.asyncio
    async def test_get_request_id(self, async_config):
        """Test that get_request_id generates valid request IDs."""
        handler = AsyncRequestHandler(async_config)
        request_id = handler.get_request_id()

        # Verify it's a string and has reasonable length
        assert isinstance(request_id, str)
        assert len(request_id) > 10

        # Verify each call generates a unique ID
        request_id2 = handler.get_request_id()
        assert request_id != request_id2

    @pytest.mark.asyncio
    async def test_connector_configuration(self, async_config):
        """Test that TCPConnector is properly configured."""
        handler = AsyncRequestHandler(async_config)
        assert handler._connector is not None
        assert isinstance(handler._connector, aiohttp.TCPConnector)

    @pytest.mark.asyncio
    async def test_custom_connector(self, reset_async_config):
        """Test handler with custom TCPConnector."""
        custom_connector = aiohttp.TCPConnector(limit=50, limit_per_host=20)
        config = AsyncConfig(connection_pool=custom_connector)
        handler = AsyncRequestHandler(config)

        # Verify custom connector is used
        assert handler._connector is custom_connector
