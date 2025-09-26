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
from unittest.mock import MagicMock, patch

from aidefense.management.management_client import ManagementClient
from aidefense.management.applications import ApplicationManagementClient
from aidefense.management.connections import ConnectionManagementClient
from aidefense.management.policies import PolicyManagementClient
from aidefense.management.events import EventManagementClient


# Create a valid format dummy API key for testing
TEST_API_KEY = "0123456789" * 6 + "0123"  # 64 characters


class TestManagementClient:
    """Tests for the ManagementClient."""

    def test_api_key_validation(self):
        """Test API key validation."""
        # Test with valid API key
        client = ManagementClient(api_key=TEST_API_KEY)
        assert client.api_key == TEST_API_KEY

        # Test with empty API key
        with pytest.raises(ValueError) as excinfo:
            ManagementClient(api_key="")
        assert "API key is required" in str(excinfo.value)
