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

MCP_SERVERS = "mcp/servers"
MCP_SCAN = "scan"


def mcp_scan_start() -> str:
    """Route for starting an MCP server scan without registration."""
    return f"{MCP_SERVERS}/{MCP_SCAN}"


def mcp_scan_status(scan_id: str) -> str:
    """Route for getting the status of an MCP server scan using the scan ID."""
    return f"{MCP_SERVERS}/{MCP_SCAN}/{scan_id}"


def mcp_servers_register() -> str:
    """Route for registering a new MCP server."""
    return MCP_SERVERS


def mcp_server_delete(server_id: str) -> str:
    """Route for deleting an MCP server."""
    return f"{MCP_SERVERS}/{server_id}"


def mcp_server_get(server_id: str) -> str:
    """Route for getting an MCP server by ID."""
    return f"{MCP_SERVERS}/{server_id}"


def mcp_servers_list() -> str:
    """Route for listing MCP servers."""
    return MCP_SERVERS


def mcp_server_update_auth_config(server_id: str) -> str:
    """Route for updating MCP server authentication configuration."""
    return f"{MCP_SERVERS}/{server_id}/auth"


def mcp_server_capabilities(server_id: str) -> str:
    """Route for getting MCP server capabilities."""
    return f"{MCP_SERVERS}/{server_id}/capabilities"


def mcp_server_threats(server_id: str) -> str:
    """Route for getting MCP server threats."""
    return f"{MCP_SERVERS}/{server_id}/threats"


def mcp_server_scan_summary(server_id: str) -> str:
    """Route for getting MCP server scan summary."""
    return f"{MCP_SERVERS}/{server_id}/{MCP_SCAN}/summary"


# --------------------
# Resource Connection Routes
# --------------------

RESOURCE = "resource"
RESOURCE_CONNECTIONS = f"{RESOURCE}/connections"


def resource_connections() -> str:
    """Route for creating resource connections."""
    return RESOURCE_CONNECTIONS


def resource_connection_by_id(connection_id: str) -> str:
    """Route for getting/deleting a resource connection by ID."""
    return f"{RESOURCE_CONNECTIONS}/{connection_id}"


def resource_connection_by_resource_id(resource_id: str) -> str:
    """Route for getting resource connection by resource ID."""
    return f"{RESOURCE}/{resource_id}/connection"


def resource_connections_filter() -> str:
    """Route for filtering resource connections."""
    return f"{RESOURCE_CONNECTIONS}/filter"


def resources_by_connection_id(connection_id: str) -> str:
    """Route for filtering resources by connection ID."""
    return f"{RESOURCE}/connection/{connection_id}/resources"


def add_or_update_resource_connections(connection_id: str) -> str:
    """Route for adding or updating resource connections."""
    return f"{RESOURCE_CONNECTIONS}/{connection_id}"


