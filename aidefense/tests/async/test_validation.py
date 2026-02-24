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

"""Tests for AsyncRequestHandler input validation."""

import pytest
from unittest.mock import AsyncMock

from aidefense.exceptions import ValidationError
from aidefense.runtime.auth import AsyncAuth


class TestAsyncRequestHandlerValidation:
    """Tests for input validation."""

    @pytest.mark.asyncio
    async def test_validate_method_rejects_invalid_method(self, handler):
        """Test that _validate_method raises for invalid HTTP methods."""
        await handler.ensure_session()
        with pytest.raises(ValidationError, match="Invalid HTTP method"):
            await handler.request(method="INVALID", url="https://api.example.com", auth=AsyncMock(spec=AsyncAuth))

    @pytest.mark.asyncio
    async def test_validate_url_rejects_invalid_url(self, handler):
        """Test that _validate_url raises for invalid URLs."""
        await handler.ensure_session()
        with pytest.raises(ValidationError, match="Invalid URL"):
            await handler.request(method="GET", url="not-a-url", auth=AsyncMock(spec=AsyncAuth))

    @pytest.mark.asyncio
    async def test_request_without_session_raises_error(self, handler):
        """Test that request without initialized session raises RuntimeError."""
        with pytest.raises(RuntimeError, match="Session not initialized"):
            await handler.request(method="GET", url="https://api.example.com", auth=AsyncMock(spec=AsyncAuth))
