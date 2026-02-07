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

"""Tests for AsyncRequestHandler session management."""

import asyncio
import pytest
import aiohttp

from aidefense.async_request_handler import AsyncRequestHandler


class TestAsyncRequestHandlerSessionManagement:
    """Tests for session lifecycle management."""

    @pytest.mark.asyncio
    async def test_ensure_session_creates_session(self, handler):
        """Test that ensure_session creates a session."""
        assert handler._session is None
        await handler.ensure_session()
        assert handler._session is not None
        assert isinstance(handler._session, aiohttp.ClientSession)

    @pytest.mark.asyncio
    async def test_ensure_session_reuses_existing_session(self, handler):
        """Test that ensure_session reuses existing open session."""
        await handler.ensure_session()
        first_session = handler._session
        await handler.ensure_session()
        second_session = handler._session
        assert first_session is second_session

    @pytest.mark.asyncio
    async def test_ensure_session_recreates_closed_session(self, handler):
        """Test that ensure_session recreates a closed session."""
        await handler.ensure_session()
        first_session = handler._session
        first_session_id = id(first_session)
        await handler._session.close()

        await handler.ensure_session()
        second_session = handler._session
        second_session_id = id(second_session)

        # Verify a new session object was created
        assert second_session_id != first_session_id
        assert second_session is not first_session

    @pytest.mark.asyncio
    async def test_close_cleans_up_resources(self, handler):
        """Test that close() cleans up session and connector."""
        await handler.ensure_session()
        assert handler._session is not None

        await handler.close()
        assert handler._session.closed

    @pytest.mark.asyncio
    async def test_close_when_session_is_none(self, async_config):
        """Test that close() handles None session gracefully."""
        handler = AsyncRequestHandler(async_config)
        assert handler._session is None

        # Should not raise any exception
        await handler.close()

    @pytest.mark.asyncio
    async def test_close_does_not_close_shared_connector(self, async_config):
        """Test that close() does NOT close the connector (it's shared via config)."""
        handler = AsyncRequestHandler(async_config)
        await handler.ensure_session()

        connector = handler._connector
        await handler.close()

        # Verify connector is NOT closed - it's owned by AsyncConfig and may be shared
        # across multiple handlers. Closing it would break other handlers using the same config.
        assert not connector.closed

    @pytest.mark.asyncio
    async def test_ensure_session_concurrent_calls_single_session(self, async_config):
        """Test that concurrent ensure_session calls create only one session."""
        handler = AsyncRequestHandler(async_config)

        # Collect session IDs from concurrent calls
        sessions = []

        async def call_ensure_session():
            await handler.ensure_session()
            return id(handler._session)

        # Run 10 concurrent ensure_session calls
        tasks = [call_ensure_session() for _ in range(10)]
        session_ids = await asyncio.gather(*tasks)

        # All calls should return the same session
        assert len(set(session_ids)) == 1, "Multiple sessions were created during concurrent calls"

        # Cleanup
        await handler.close()

    @pytest.mark.asyncio
    async def test_ensure_session_lock_prevents_race_condition(self, async_config):
        """Test that the lock in ensure_session prevents race conditions."""
        handler = AsyncRequestHandler(async_config)
        creation_count = 0
        original_ensure_session = handler.ensure_session

        async def tracked_ensure_session():
            nonlocal creation_count
            was_none = handler._session is None
            await original_ensure_session()
            if was_none and handler._session is not None:
                creation_count += 1

        handler.ensure_session = tracked_ensure_session

        # Run many concurrent calls
        tasks = [handler.ensure_session() for _ in range(20)]
        await asyncio.gather(*tasks)

        # Session should only be created once
        assert creation_count == 1, f"Session was created {creation_count} times instead of 1"

        # Cleanup
        await handler.close()
