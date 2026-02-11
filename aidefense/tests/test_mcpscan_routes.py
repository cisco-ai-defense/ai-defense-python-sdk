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

import pytest

from aidefense.mcpscan.routes import (
    # MCP Server routes
    mcp_scan_start,
    mcp_scan_status,
    mcp_servers_register,
    mcp_server_delete,
    mcp_server_get,
    mcp_servers_list,
    mcp_server_update_auth_config,
    mcp_server_capabilities,
    mcp_server_threats,
    mcp_server_scan_summary,
    # Resource Connection routes
    resource_connections,
    resource_connection_by_id,
    resource_connection_by_resource_id,
    resource_connections_filter,
    resources_by_connection_id,
    add_or_update_resource_connections,
)


class TestMCPServerRoutes:
    """Tests for MCP server route functions."""

    def test_mcp_scan_start(self):
        """Test the MCP scan start route."""
        assert mcp_scan_start() == "mcp/servers/scan"

    def test_mcp_scan_status(self):
        """Test the MCP scan status route."""
        scan_id = "scan-123-456"
        assert mcp_scan_status(scan_id) == f"mcp/servers/scan/{scan_id}"

    def test_mcp_servers_register(self):
        """Test the MCP servers register route."""
        assert mcp_servers_register() == "mcp/servers"

    def test_mcp_server_delete(self):
        """Test the MCP server delete route."""
        server_id = "server-123"
        assert mcp_server_delete(server_id) == f"mcp/servers/{server_id}"

    def test_mcp_server_get(self):
        """Test the MCP server get route."""
        server_id = "server-456"
        assert mcp_server_get(server_id) == f"mcp/servers/{server_id}"

    def test_mcp_servers_list(self):
        """Test the MCP servers list route."""
        assert mcp_servers_list() == "mcp/servers"

    def test_mcp_server_update_auth_config(self):
        """Test the MCP server update auth config route."""
        server_id = "server-789"
        assert mcp_server_update_auth_config(server_id) == f"mcp/servers/{server_id}/auth"

    def test_mcp_server_capabilities(self):
        """Test the MCP server capabilities route."""
        server_id = "server-cap"
        assert mcp_server_capabilities(server_id) == f"mcp/servers/{server_id}/capabilities"

    def test_mcp_server_threats(self):
        """Test the MCP server threats route."""
        server_id = "server-threat"
        assert mcp_server_threats(server_id) == f"mcp/servers/{server_id}/threats"

    def test_mcp_server_scan_summary(self):
        """Test the MCP server scan summary route."""
        server_id = "server-summary"
        assert mcp_server_scan_summary(server_id) == f"mcp/servers/{server_id}/scan/summary"


class TestResourceConnectionRoutes:
    """Tests for resource connection route functions."""

    def test_resource_connections(self):
        """Test the resource connections route."""
        assert resource_connections() == "resource/connections"

    def test_resource_connection_by_id(self):
        """Test the resource connection by ID route."""
        connection_id = "conn-123"
        assert resource_connection_by_id(connection_id) == f"resource/connections/{connection_id}"

    def test_resource_connection_by_resource_id(self):
        """Test the resource connection by resource ID route."""
        resource_id = "res-789"
        assert resource_connection_by_resource_id(resource_id) == f"resource/{resource_id}/connection"

    def test_resource_connections_filter(self):
        """Test the resource connections filter route."""
        assert resource_connections_filter() == "resource/connections/filter"

    def test_resources_by_connection_id(self):
        """Test the resources by connection ID route."""
        connection_id = "conn-res"
        assert resources_by_connection_id(connection_id) == f"resource/connection/{connection_id}/resources"

    def test_add_or_update_resource_connections(self):
        """Test the add or update resource connections route."""
        connection_id = "conn-update"
        assert add_or_update_resource_connections(connection_id) == f"resource/connections/{connection_id}"
