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

"""Tests for AsyncRequestHandler request handling."""

import aiohttp
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestAsyncRequestHandlerRequest:
    """Tests for the request() method."""

    @pytest.mark.asyncio
    async def test_request_success_returns_json(self, handler, mock_auth):
        """Test successful request returns JSON response."""
        await handler.ensure_session()

        # Mock the session request
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"success": True, "data": "test"})

        with patch.object(handler._session, "request") as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response

            result = await handler.request(method="GET", url="https://api.example.com/test", auth=mock_auth)

        assert result == {"success": True, "data": "test"}
        mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_includes_headers(self, handler, mock_auth):
        """Test that request includes custom headers."""
        await handler.ensure_session()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={})

        with patch.object(handler._session, "request") as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response

            await handler.request(
                method="POST", url="https://api.example.com/test", auth=mock_auth, headers={"X-Custom-Header": "value"}
            )

        call_kwargs = mock_request.call_args[1]
        assert "headers" in call_kwargs
        assert "X-Custom-Header" in call_kwargs["headers"]

    @pytest.mark.asyncio
    async def test_request_generates_request_id(self, handler, mock_auth):
        """Test that request generates a request ID if not provided."""
        await handler.ensure_session()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={})

        with patch.object(handler._session, "request") as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response

            await handler.request(method="GET", url="https://api.example.com/test", auth=mock_auth)

        call_kwargs = mock_request.call_args[1]
        assert "headers" in call_kwargs
        # Verify a request ID was auto-generated and set in the headers
        assert "x-aidefense-request-id" in call_kwargs["headers"]
        assert len(call_kwargs["headers"]["x-aidefense-request-id"]) > 0

    @pytest.mark.asyncio
    async def test_request_uses_custom_timeout(self, handler, mock_auth):
        """Test that request uses custom timeout when provided."""
        await handler.ensure_session()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={})

        with patch.object(handler._session, "request") as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response

            await handler.request(method="GET", url="https://api.example.com/test", auth=mock_auth, timeout=60)

        call_kwargs = mock_request.call_args[1]
        assert "timeout" in call_kwargs
        assert isinstance(call_kwargs["timeout"], aiohttp.ClientTimeout)

    @pytest.mark.asyncio
    async def test_request_with_query_params(self, handler, mock_auth):
        """Test that request passes query parameters."""
        await handler.ensure_session()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={})

        with patch.object(handler._session, "request") as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response

            await handler.request(
                method="GET",
                url="https://api.example.com/test",
                auth=mock_auth,
                params={
                    "filter": "active",
                    "limit": 10,
                },
            )

        call_kwargs = mock_request.call_args[1]
        assert "params" in call_kwargs
        assert call_kwargs["params"] == {"filter": "active", "limit": 10}

    @pytest.mark.asyncio
    async def test_request_with_json_data(self, handler, mock_auth):
        """Test that request passes JSON body data."""
        await handler.ensure_session()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={})

        json_payload = {"name": "test", "value": 123}

        with patch.object(handler._session, "request") as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response

            await handler.request(
                method="POST", url="https://api.example.com/test", auth=mock_auth, json_data=json_payload
            )

        call_kwargs = mock_request.call_args[1]
        assert "json" in call_kwargs
        assert call_kwargs["json"] == json_payload

    @pytest.mark.asyncio
    async def test_request_with_custom_request_id(self, handler, mock_auth):
        """Test that request uses custom request_id when provided."""
        await handler.ensure_session()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={})

        custom_id = "custom-request-id-12345"

        with patch.object(handler._session, "request") as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response

            await handler.request(
                method="GET", url="https://api.example.com/test", auth=mock_auth, request_id=custom_id
            )

        # Verify the request was made successfully
        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args[1]

        # Verify method and URL are correct
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["url"] == "https://api.example.com/test"

        # Verify the custom request ID was set in the headers
        assert call_kwargs["headers"]["x-aidefense-request-id"] == custom_id

    @pytest.mark.asyncio
    async def test_request_with_different_http_methods(self, handler, mock_auth):
        """Test that request works with various HTTP methods."""
        await handler.ensure_session()

        methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]

        for method in methods:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={})

            with patch.object(handler._session, "request") as mock_request:
                mock_request.return_value.__aenter__.return_value = mock_response

                await handler.request(method=method, url="https://api.example.com/test", auth=mock_auth)

            call_kwargs = mock_request.call_args[1]
            assert call_kwargs["method"] == method

    @pytest.mark.asyncio
    async def test_request_timeout_boolean_edge_case(self, handler, mock_auth):
        """Test that boolean timeout values are rejected (bool is subclass of int)."""
        await handler.ensure_session()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={})

        with patch.object(handler._session, "request") as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response

            # Pass boolean (should not be treated as timeout)
            await handler.request(
                method="GET",
                url="https://api.example.com/test",
                auth=mock_auth,
                timeout=True,  # Boolean should be ignored
            )

        call_kwargs = mock_request.call_args[1]
        # Should use default timeout, not create one from boolean
        assert call_kwargs["timeout"] == handler._timeout

    @pytest.mark.asyncio
    async def test_request_headers_merging(self, handler, mock_auth):
        """Test that custom headers are properly merged with session headers."""
        await handler.ensure_session()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={})

        custom_headers = {"X-Custom": "value", "Authorization": "Bearer custom"}

        with patch.object(handler._session, "request") as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response

            await handler.request(
                method="GET", url="https://api.example.com/test", auth=mock_auth, headers=custom_headers
            )

        call_kwargs = mock_request.call_args[1]
        # Verify custom headers are included in merged headers
        assert "headers" in call_kwargs
        merged_headers = call_kwargs["headers"]
        # Custom headers should be present
        assert merged_headers["X-Custom"] == "value"
        assert merged_headers["Authorization"] == "Bearer custom"
        # Session headers should also be present
        assert "User-Agent" in merged_headers
        assert "Content-Type" in merged_headers
        # Request ID should be added
        assert "x-aidefense-request-id" in merged_headers

    @pytest.mark.asyncio
    async def test_request_handles_client_error(self, handler, mock_auth):
        """Test that ClientError exceptions are properly raised."""
        await handler.ensure_session()

        with patch.object(handler._session, "request") as mock_request:
            # Simulate aiohttp.ClientError
            mock_request.side_effect = aiohttp.ClientConnectorError(
                connection_key=MagicMock(), os_error=OSError("Connection failed")
            )

            with pytest.raises(aiohttp.ClientError):
                await handler.request(method="GET", url="https://api.example.com/test", auth=mock_auth)

    @pytest.mark.asyncio
    async def test_request_handles_generic_exception(self, handler, mock_auth):
        """Test that generic exceptions are properly raised."""
        await handler.ensure_session()

        with patch.object(handler._session, "request") as mock_request:
            # Simulate a generic exception
            mock_request.side_effect = RuntimeError("Unexpected error")

            with pytest.raises(RuntimeError, match="Unexpected error"):
                await handler.request(method="GET", url="https://api.example.com/test", auth=mock_auth)

    @pytest.mark.asyncio
    async def test_integration_full_request_flow(self, async_config, mock_auth):
        """Integration test with minimal mocking for complete request flow."""
        from aidefense.async_request_handler import AsyncRequestHandler

        # Create handler with custom config
        handler = AsyncRequestHandler(async_config)
        await handler.ensure_session()

        # Mock the session request
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"result": "success", "data": [1, 2, 3]})

        with patch.object(handler._session, "request") as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response

            # Make request with all parameters
            result = await handler.request(
                method="POST",
                url="https://api.example.com/endpoint",
                auth=mock_auth,
                request_id="integration-test-id",
                headers={"X-Test": "integration"},
                json_data={"test": "data"},
                timeout=30,
                params={
                    "query": "param",
                },
            )

        # Verify result
        assert result == {"result": "success", "data": [1, 2, 3]}

        # Verify all parameters were passed correctly
        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args[1]

        assert call_kwargs["method"] == "POST"
        assert call_kwargs["url"] == "https://api.example.com/endpoint"
        assert call_kwargs["json"] == {"test": "data"}
        assert call_kwargs["params"] == {"query": "param"}

        # Verify headers include custom headers
        headers = call_kwargs["headers"]
        assert headers["X-Test"] == "integration"

        # Cleanup
        await handler.close()
