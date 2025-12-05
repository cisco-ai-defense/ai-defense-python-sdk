# Copyright 2025 Cisco Systems, Inc. and its affiliates
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

import pytest
import requests
from unittest.mock import Mock

from aidefense.runtime.auth import RuntimeAuth


def test_runtime_auth_init_valid():
    """Test initializing RuntimeAuth with a valid token."""
    # Valid 64-character token
    token = "0" * 64
    auth = RuntimeAuth(token)
    assert auth.token == token


def test_runtime_auth_init_invalid_length():
    """Test initializing RuntimeAuth with an invalid token length."""
    # Token with invalid length
    token = "0" * 63  # Too short
    with pytest.raises(ValueError, match="Invalid API key format"):
        RuntimeAuth(token)

    token = "0" * 65  # Too long
    with pytest.raises(ValueError, match="Invalid API key format"):
        RuntimeAuth(token)


def test_runtime_auth_init_invalid_type():
    """Test initializing RuntimeAuth with invalid token types."""
    # None token
    with pytest.raises(ValueError, match="Invalid API key format"):
        RuntimeAuth(None)

    # Integer token
    with pytest.raises(ValueError, match="Invalid API key format"):
        RuntimeAuth(12345)

    # Empty string token
    with pytest.raises(ValueError, match="Invalid API key format"):
        RuntimeAuth("")


def test_runtime_auth_call():
    """Test the __call__ method of RuntimeAuth."""
    token = "0" * 64
    auth = RuntimeAuth(token)

    # Create a mock request
    request = Mock()
    request.headers = {}

    # Call the auth object with the request
    result = auth(request)

    # Check that the request was properly modified
    assert result == request
    assert RuntimeAuth.AUTH_HEADER in request.headers
    assert request.headers[RuntimeAuth.AUTH_HEADER] == token


def test_runtime_auth_validate():
    """Test the validate method of RuntimeAuth."""
    token = "0" * 64
    auth = RuntimeAuth(token)

    # Validate should return True for a valid token
    assert auth.validate() is True


def test_runtime_auth_with_requests():
    """Test RuntimeAuth integration with requests library."""
    token = "0" * 64
    auth = RuntimeAuth(token)

    # Create a prepared request
    req = requests.Request("GET", "https://example.com")
    prepared_req = req.prepare()

    # Apply auth
    authenticated_req = auth(prepared_req)

    # Check that auth header was added
    assert RuntimeAuth.AUTH_HEADER in authenticated_req.headers
    assert authenticated_req.headers[RuntimeAuth.AUTH_HEADER] == token
