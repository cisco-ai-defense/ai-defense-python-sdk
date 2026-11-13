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

"""Tests for AsyncRequestHandler error handling."""

import logging

import aiohttp
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aidefense.async_request_handler import AsyncRequestHandler
from aidefense.config import AsyncConfig
from aidefense.exceptions import SDKError, ValidationError, ApiError


class TestAsyncRequestHandlerErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_handle_error_401_raises_sdk_error(self, handler, mock_auth):
        """Test that 401 response raises SDKError."""
        await handler.ensure_session()

        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.text = AsyncMock(return_value="Unauthorized")
        mock_response.json = AsyncMock(return_value={"message": "Invalid token"})

        with patch.object(handler._session, "request") as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response

            with pytest.raises(SDKError, match="Authentication error"):
                await handler.request(method="GET", url="https://api.example.com/test", auth=mock_auth)

    @pytest.mark.asyncio
    async def test_handle_error_400_raises_validation_error(self, handler, mock_auth):
        """Test that 400 response raises ValidationError."""
        await handler.ensure_session()

        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value="Bad Request")
        mock_response.json = AsyncMock(return_value={"message": "Invalid params"})

        with patch.object(handler._session, "request") as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response

            with pytest.raises(ValidationError, match="Bad request"):
                await handler.request(method="GET", url="https://api.example.com/test", auth=mock_auth)

    @pytest.mark.asyncio
    async def test_handle_error_500_raises_api_error(self, handler, mock_auth):
        """Test that 500 response raises ApiError."""
        await handler.ensure_session()

        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Server Error")
        mock_response.json = AsyncMock(return_value={"message": "Internal error"})

        with patch.object(handler._session, "request") as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response

            with pytest.raises(ApiError, match="API error 500"):
                await handler.request(method="GET", url="https://api.example.com/test", auth=mock_auth)

    @pytest.mark.asyncio
    async def test_handle_error_non_json_response(self, handler, mock_auth):
        """Test error handling when response is not JSON."""
        await handler.ensure_session()

        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Plain text error")
        mock_response.json = AsyncMock(
            side_effect=aiohttp.ContentTypeError(request_info=MagicMock(), history=MagicMock())
        )

        with patch.object(handler._session, "request") as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response

            with pytest.raises(ApiError, match="Plain text error"):
                await handler.request(method="GET", url="https://api.example.com/test", auth=mock_auth)

    @pytest.mark.asyncio
    async def test_handle_error_403_raises_api_error(self, handler, mock_auth):
        """Test that 403 response raises ApiError."""
        await handler.ensure_session()

        mock_response = AsyncMock()
        mock_response.status = 403
        mock_response.text = AsyncMock(return_value="Forbidden")
        mock_response.json = AsyncMock(return_value={"message": "Access denied"})

        with patch.object(handler._session, "request") as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response

            with pytest.raises(ApiError, match="API error 403"):
                await handler.request(method="GET", url="https://api.example.com/test", auth=mock_auth)

    @pytest.mark.asyncio
    async def test_handle_error_404_raises_api_error(self, handler, mock_auth):
        """Test that 404 response raises ApiError."""
        await handler.ensure_session()

        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.text = AsyncMock(return_value="Not Found")
        mock_response.json = AsyncMock(return_value={"message": "Resource not found"})

        with patch.object(handler._session, "request") as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response

            with pytest.raises(ApiError, match="API error 404"):
                await handler.request(method="GET", url="https://api.example.com/test", auth=mock_auth)

    @pytest.mark.asyncio
    async def test_api_error_includes_request_id(self, handler, mock_auth):
        """Test that ApiError includes request_id when provided."""
        await handler.ensure_session()

        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Server Error")
        mock_response.json = AsyncMock(return_value={"message": "Internal error"})

        custom_request_id = "test-request-id-12345"

        with patch.object(handler._session, "request") as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response

            with pytest.raises(ApiError) as exc_info:
                await handler.request(
                    method="GET", url="https://api.example.com/test", auth=mock_auth, request_id=custom_request_id
                )

            assert exc_info.value.request_id == custom_request_id

    @pytest.mark.asyncio
    async def test_handle_error_empty_response(self, handler, mock_auth):
        """Test error handling when response body is empty."""
        await handler.ensure_session()

        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="")
        mock_response.json = AsyncMock(side_effect=ValueError("No JSON"))

        with patch.object(handler._session, "request") as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response

            with pytest.raises(ApiError, match="Unknown error"):
                await handler.request(method="GET", url="https://api.example.com/test", auth=mock_auth)

    @pytest.mark.asyncio
    async def test_retried_api_error_not_logged_as_unexpected(self, reset_async_config, mock_auth, caplog):
        """Test that retried ApiErrors are not logged as unexpected errors and do not leak the server message."""
        config = AsyncConfig(retry_config={"total": 2, "backoff_factor": 0.01})
        handler = AsyncRequestHandler(config)
        await handler.ensure_session()
        secret = "my SSN is 123-45-6789"

        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Server Error")
        mock_response.json = AsyncMock(return_value={"message": f"Internal error processing: {secret}"})

        try:
            with patch.object(handler._session, "request") as mock_request:
                mock_request.return_value.__aenter__.return_value = mock_response

                with caplog.at_level(logging.WARNING, logger=config.logger.name):
                    with pytest.raises(ApiError, match="API error 500"):
                        await handler.request(method="POST", url="https://api.example.com/test", auth=mock_auth)

            assert mock_request.call_count == 3
            assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []
            assert "Unexpected error" not in caplog.text
            assert secret not in caplog.text
            assert len([r for r in caplog.records if "Retrying request" in r.getMessage()]) == 2
        finally:
            await handler.close()
            await config.close()

    @pytest.mark.asyncio
    async def test_validation_error_not_logged_as_unexpected(self, handler, mock_auth, caplog):
        """Test that SDK validation errors are raised without an unexpected error log."""
        await handler.ensure_session()

        with caplog.at_level(logging.WARNING, logger=handler.config.logger.name):
            with pytest.raises(ValidationError, match="Invalid HTTP method"):
                await handler.request(method="FOO", url="https://api.example.com/test", auth=mock_auth)

        assert "Unexpected error" not in caplog.text

    @pytest.mark.asyncio
    async def test_unexpected_exception_still_logged(self, handler, mock_auth, caplog):
        """Test that non-SDK exceptions are still logged as unexpected errors."""
        await handler.ensure_session()

        with patch.object(handler._session, "request") as mock_request:
            mock_request.side_effect = RuntimeError("boom")

            with caplog.at_level(logging.WARNING, logger=handler.config.logger.name):
                with pytest.raises(RuntimeError, match="boom"):
                    await handler.request(method="GET", url="https://api.example.com/test", auth=mock_auth)

        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) == 1
        assert "Unexpected error in async request: boom" in error_records[0].getMessage()
