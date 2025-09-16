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

    @patch('aidefense.management.applications.ApplicationManagementClient')
    def test_applications_property(self, mock_applications_client):
        """Test the applications property."""
        # Setup mock
        mock_app_client = MagicMock()
        mock_applications_client.return_value = mock_app_client
        
        # Create client
        client = ManagementClient(api_key=TEST_API_KEY)
        
        # Access the property
        applications_client = client.applications
        
        # Verify the client was created
        mock_applications_client.assert_called_once()
        
        # Verify the client is cached
        assert client._applications_client == mock_app_client
        
        # Verify accessing the property again doesn't create a new client
        applications_client_again = client.applications
        assert mock_applications_client.call_count == 1
        assert applications_client_again == mock_app_client

    @patch('aidefense.management.connections.ConnectionManagementClient')
    def test_connections_property(self, mock_connections_client):
        """Test the connections property."""
        # Setup mock
        mock_conn_client = MagicMock()
        mock_connections_client.return_value = mock_conn_client
        
        # Create client
        client = ManagementClient(api_key=TEST_API_KEY)
        
        # Access the property
        connections_client = client.connections
        
        # Verify the client was created
        mock_connections_client.assert_called_once()
        
        # Verify the client is cached
        assert client._connections_client == mock_conn_client
        
        # Verify accessing the property again doesn't create a new client
        connections_client_again = client.connections
        assert mock_connections_client.call_count == 1
        assert connections_client_again == mock_conn_client

    @patch('aidefense.management.policies.PolicyManagementClient')
    def test_policies_property(self, mock_policies_client):
        """Test the policies property."""
        # Setup mock
        mock_policy_client = MagicMock()
        mock_policies_client.return_value = mock_policy_client
        
        # Create client
        client = ManagementClient(api_key=TEST_API_KEY)
        
        # Access the property
        policies_client = client.policies
        
        # Verify the client was created
        mock_policies_client.assert_called_once()
        
        # Verify the client is cached
        assert client._policies_client == mock_policy_client
        
        # Verify accessing the property again doesn't create a new client
        policies_client_again = client.policies
        assert mock_policies_client.call_count == 1
        assert policies_client_again == mock_policy_client

    @patch('aidefense.management.events.EventManagementClient')
    def test_events_property(self, mock_events_client):
        """Test the events property."""
        # Setup mock
        mock_event_client = MagicMock()
        mock_events_client.return_value = mock_event_client
        
        # Create client
        client = ManagementClient(api_key=TEST_API_KEY)
        
        # Access the property
        events_client = client.events
        
        # Verify the client was created
        mock_events_client.assert_called_once()
        
        # Verify the client is cached
        assert client._events_client == mock_event_client
        
        # Verify accessing the property again doesn't create a new client
        events_client_again = client.events
        assert mock_events_client.call_count == 1
        assert events_client_again == mock_event_client

    def test_api_key_validation(self):
        """Test API key validation."""
        # Test with valid API key
        client = ManagementClient(api_key=TEST_API_KEY)
        assert client.api_key == TEST_API_KEY

        # Test with empty API key
        with pytest.raises(ValueError) as excinfo:
            ManagementClient(api_key="")
        assert "API key is required" in str(excinfo.value)
