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

import aiohttp
import pytest
from unittest.mock import MagicMock

from aidefense.runtime.auth import AsyncAuth


@pytest.mark.asyncio
async def test_async_auth_init_valid():
    """Test initializing AsyncAuth with a valid token."""
    # Valid 64-character token
    token = "0" * 64
    auth = AsyncAuth(token)
    assert auth.token == token


@pytest.mark.asyncio
async def test_async_auth_init_invalid_length():
    """Test initializing AsyncAuth with an invalid token length."""
    # Token with invalid length
    token = "0" * 63  # Too short
    with pytest.raises(ValueError, match="Invalid API key format"):
        AsyncAuth(token)

    token = "0" * 65  # Too long
    with pytest.raises(ValueError, match="Invalid API key format"):
        AsyncAuth(token)


@pytest.mark.asyncio
async def test_async_auth_init_invalid_type():
    """Test initializing AsyncAuth with invalid token types."""
    # None token
    with pytest.raises(ValueError, match="Invalid API key format"):
        AsyncAuth(None)

    # Integer token
    with pytest.raises(ValueError, match="Invalid API key format"):
        AsyncAuth(12345)

    # Empty string token
    with pytest.raises(ValueError, match="Invalid API key format"):
        AsyncAuth("")


@pytest.mark.asyncio
async def test_async_auth_validate():
    """Test the validate method of AsyncAuth."""
    token = "0" * 64
    auth = AsyncAuth(token)

    # Validate should return True for a valid token
    assert auth.validate() is True


@pytest.mark.asyncio
async def test_async_auth_call_sets_header():
    """Test that AsyncAuth.__call__ sets the correct header."""
    token = "0" * 64
    auth = AsyncAuth(token)

    # Create mock request and handler
    mock_request = MagicMock(spec=aiohttp.ClientRequest)
    mock_request.headers = {}

    mock_response = MagicMock(spec=aiohttp.ClientResponse)

    async def mock_handler(request):
        return mock_response

    # Call the auth middleware
    result = await auth(mock_request, mock_handler)

    # Verify the header was set
    assert AsyncAuth.AUTH_HEADER in mock_request.headers
    assert mock_request.headers[AsyncAuth.AUTH_HEADER] == token
    assert result == mock_response


@pytest.mark.asyncio
async def test_async_auth_with_aiohttp_session():
    """Test AsyncAuth integration with aiohttp ClientSession."""
    token = "0" * 64
    auth = AsyncAuth(token)

    # Create a mock request object
    mock_request = MagicMock(spec=aiohttp.ClientRequest)
    mock_request.headers = {}

    # Mock handler that returns a response
    mock_response = MagicMock(spec=aiohttp.ClientResponse)

    async def handler(request):
        # Verify auth header was added
        assert AsyncAuth.AUTH_HEADER in request.headers
        assert request.headers[AsyncAuth.AUTH_HEADER] == token
        return mock_response

    # Apply auth middleware
    response = await auth(mock_request, handler)

    # Verify response was returned
    assert response == mock_response
    # Verify header was set on request
    assert mock_request.headers[AsyncAuth.AUTH_HEADER] == token


@pytest.mark.asyncio
async def test_async_auth_header_value_format():
    """Test that AsyncAuth formats the header value correctly."""
    token = "a" * 64
    auth = AsyncAuth(token)

    mock_request = MagicMock(spec=aiohttp.ClientRequest)
    mock_request.headers = {}

    mock_response = MagicMock(spec=aiohttp.ClientResponse)

    async def mock_handler(request):
        return mock_response

    await auth(mock_request, mock_handler)

    # Verify the header value is exactly the token (no prefix/suffix)
    assert mock_request.headers[AsyncAuth.AUTH_HEADER] == token


@pytest.mark.asyncio
async def test_async_auth_preserves_existing_headers():
    """Test that AsyncAuth preserves existing headers on the request."""
    token = "0" * 64
    auth = AsyncAuth(token)

    # Create request with existing headers
    mock_request = MagicMock(spec=aiohttp.ClientRequest)
    mock_request.headers = {"Content-Type": "application/json", "User-Agent": "test-client"}

    mock_response = MagicMock(spec=aiohttp.ClientResponse)

    async def mock_handler(request):
        return mock_response

    await auth(mock_request, mock_handler)

    # Verify auth header was added
    assert mock_request.headers[AsyncAuth.AUTH_HEADER] == token
    # Verify existing headers were preserved
    assert mock_request.headers["Content-Type"] == "application/json"
    assert mock_request.headers["User-Agent"] == "test-client"
