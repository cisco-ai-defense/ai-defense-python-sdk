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

import logging

import aiohttp
import pytest
from unittest.mock import MagicMock

from aidefense.async_request_handler import AsyncRequestHandler
from aidefense.exceptions import ApiError, SDKError, ValidationError
from tenacity import RetryAction, RetryCallState


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

    @staticmethod
    def _make_retry_state(exception, kwargs=None):
        retry_state = RetryCallState(retry_object=MagicMock(), fn=None, args=(), kwargs=kwargs or {})
        retry_state.attempt_number = 2
        retry_state.set_exception((type(exception), exception, None))
        retry_state.next_action = RetryAction(1.5)
        return retry_state

    @pytest.mark.asyncio
    async def test_log_retry_attempt_logs_metadata_at_warning(self, async_config, caplog):
        """Test that _log_retry_attempt logs retry metadata at WARNING."""
        handler = AsyncRequestHandler(async_config)
        retry_state = self._make_retry_state(ApiError("API error 503: unavailable", status_code=503, request_id="req-123"))

        with caplog.at_level(logging.DEBUG, logger=handler.config.logger.name):
            handler._log_retry_attempt(retry_state)

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.levelno == logging.WARNING
        message = record.getMessage()
        assert "attempt: 2" in message
        assert "error: ApiError" in message
        assert "status_code: 503" in message
        assert "request_id: req-123" in message
        assert "next_wait_seconds: 1.50" in message

    @pytest.mark.asyncio
    async def test_log_retry_attempt_does_not_log_request_payload(self, async_config, caplog):
        """Test that _log_retry_attempt never logs the request body or headers."""
        handler = AsyncRequestHandler(async_config)
        secret_text = "my credit card number is 4111-1111-1111-1111"
        retry_state = self._make_retry_state(
            ApiError("API error 500: internal", status_code=500),
            kwargs={
                "method": "POST",
                "url": "https://example.com/api/v1/inspect/chat",
                "headers": {"X-Cisco-AI-Defense-API-Key": "secret-api-key"},
                "json_data": {"messages": [{"role": "user", "content": secret_text}]},
            },
        )

        with caplog.at_level(logging.DEBUG, logger=handler.config.logger.name):
            handler._log_retry_attempt(retry_state)

        assert secret_text not in caplog.text
        assert "secret-api-key" not in caplog.text
        assert "json_data" not in caplog.text

    @pytest.mark.asyncio
    async def test_log_retry_attempt_handles_network_error(self, async_config, caplog):
        """Test that _log_retry_attempt handles exceptions without status_code or request_id."""
        handler = AsyncRequestHandler(async_config)
        retry_state = self._make_retry_state(aiohttp.ServerTimeoutError("Timeout"))

        with caplog.at_level(logging.DEBUG, logger=handler.config.logger.name):
            handler._log_retry_attempt(retry_state)

        message = caplog.records[0].getMessage()
        assert "error: ServerTimeoutError" in message
        assert "status_code: None" in message
        assert "request_id: None" in message
