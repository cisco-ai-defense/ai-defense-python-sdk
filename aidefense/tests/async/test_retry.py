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

"""Tests for AsyncRequestHandler retry logic."""

import aiohttp
import pytest
from unittest.mock import MagicMock, patch

from aidefense.async_request_handler import AsyncRequestHandler
from aidefense.exceptions import ApiError, SDKError, ValidationError
from tenacity import RetryCallState


class TestAsyncRequestHandlerRetry:
    """Tests for _should_retry_exception method."""

    @pytest.mark.asyncio
    async def test_should_retry_on_client_error(self, async_config):
        """Test that aiohttp.ClientError triggers retry."""
        handler = AsyncRequestHandler(async_config)

        error = aiohttp.ClientConnectorError(connection_key=MagicMock(), os_error=OSError("Connection failed"))

        result = handler._should_retry_exception(error)
        assert result is True

    @pytest.mark.asyncio
    async def test_should_not_retry_on_client_response_error(self, async_config):
        """Test that aiohttp.ClientResponseError does NOT trigger retry."""
        handler = AsyncRequestHandler(async_config)

        error = aiohttp.ClientResponseError(request_info=MagicMock(), history=(), status=404, message="Not Found")

        result = handler._should_retry_exception(error)
        assert result is False

    @pytest.mark.asyncio
    async def test_should_retry_on_api_error_with_retryable_status(self, async_config):
        """Test that ApiError with status in status_forcelist triggers retry."""
        handler = AsyncRequestHandler(async_config)

        # Default status_forcelist typically includes 500, 502, 503, 504
        error = ApiError("Server error", status_code=503)

        result = handler._should_retry_exception(error)
        assert result is True

    @pytest.mark.asyncio
    async def test_should_not_retry_on_api_error_with_non_retryable_status(self, async_config):
        """Test that ApiError with status NOT in status_forcelist does NOT trigger retry."""
        handler = AsyncRequestHandler(async_config)

        # 404 is typically not in status_forcelist
        error = ApiError("Not found", status_code=404)

        result = handler._should_retry_exception(error)
        assert result is False

    @pytest.mark.asyncio
    async def test_should_not_retry_on_validation_error(self, async_config):
        """Test that ValidationError does NOT trigger retry."""
        handler = AsyncRequestHandler(async_config)

        error = ValidationError("Invalid input", status_code=400)

        result = handler._should_retry_exception(error)
        assert result is False

    @pytest.mark.asyncio
    async def test_should_not_retry_on_sdk_error(self, async_config):
        """Test that SDKError does NOT trigger retry."""
        handler = AsyncRequestHandler(async_config)

        error = SDKError("Authentication failed", status_code=401)

        result = handler._should_retry_exception(error)
        assert result is False

    @pytest.mark.asyncio
    async def test_should_not_retry_on_generic_exception(self, async_config):
        """Test that generic Exception does NOT trigger retry."""
        handler = AsyncRequestHandler(async_config)

        error = ValueError("Some value error")

        result = handler._should_retry_exception(error)
        assert result is False

    @pytest.mark.asyncio
    async def test_should_retry_on_timeout_error(self, async_config):
        """Test that timeout errors trigger retry."""
        handler = AsyncRequestHandler(async_config)

        error = aiohttp.ServerTimeoutError("Timeout")

        result = handler._should_retry_exception(error)
        assert result is True

    @pytest.mark.asyncio
    async def test_should_retry_on_client_os_error(self, async_config):
        """Test that ClientOSError triggers retry."""
        handler = AsyncRequestHandler(async_config)

        error = aiohttp.ClientOSError("Network error")

        result = handler._should_retry_exception(error)
        assert result is True

    @pytest.mark.asyncio
    async def test_log_retry_attempt_logs_info(self, async_config):
        """Test that _log_retry_attempt logs retry information."""
        handler = AsyncRequestHandler(async_config)

        # Create a mock RetryCallState
        retry_state = MagicMock(spec=RetryCallState)
        retry_state.attempt_number = 2
        retry_state.__dict__ = {"attempt_number": 2, "outcome": None}

        with patch.object(handler.config.logger, "info") as mock_logger:
            handler._log_retry_attempt(retry_state)

            # Verify logger.info was called
            mock_logger.assert_called_once()
            call_args = mock_logger.call_args[0][0]
            assert "Retry attempt" in call_args
            assert "2" in call_args
