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

"""Resource connection management client for the AI Defense MCP API."""

from typing import List, Optional

from aidefense.config import Config
from aidefense.management.auth import ManagementAuth
from aidefense.management.base_client import BaseClient
from aidefense.request_handler import HttpMethod
from aidefense.mcpscan.models import (
    ResourceConnection,
    ResourceConnections,
    ResourceType,
    ResourceConnectionType,
    ResourceConnectionStatus,
    ResourceConnectionSortBy,
    SortOrder,
    CreateResourceConnectionRequest,
    CreateResourceConnectionResponse,
    GetResourceConnectionByIDResponse,
    GetResourceConnectionByResourceIDResponse,
    FilterResourceConnectionsRequest,
    FilterResourceConnectionsResponse,
    FilterResourcesByConnectionIDRequest,
    FilterResourcesByConnectionIDResponse,
    AddOrUpdateResourceConnectionsRequest,
)
from aidefense.mcpscan.routes import (
    resource_connections,
    resource_connection_by_id,
    resource_connections_by_resource_id,
    resource_connection_by_resource_id,
    resource_connections_filter,
    resources_by_connection_id,
    add_or_update_resource_connections,
)


class ResourceConnectionClient(BaseClient):
    """
    Client for managing resource connections in the AI Defense MCP API.

    This client provides methods for creating, retrieving, filtering, updating,
    and deleting resource connections. Resource connections link MCP servers
    and other resources to the AI Defense platform for monitoring and protection.

    Typical Usage:
        ```python
        from aidefense.mcpscan import ResourceConnectionClient
        from aidefense.mcpscan.models import (
            CreateResourceConnectionRequest,
            ResourceConnectionType,
            FilterResourceConnectionsRequest,
        )
        from aidefense import Config

        # Initialize the client
        client = ResourceConnectionClient(
            api_key="YOUR_MANAGEMENT_API_KEY",
            config=Config(management_base_url="https://api.security.cisco.com")
        )

        # Create a resource connection
        request = CreateResourceConnectionRequest(
            connection_name="My MCP Connection",
            connection_type=ResourceConnectionType.MCP_GATEWAY,
            resource_ids=["resource-uuid-1", "resource-uuid-2"]
        )
        response = client.create_connection(request)
        print(f"Created connection: {response.connection_id}")

        # Filter connections
        filter_request = FilterResourceConnectionsRequest(
            limit=10,
            connection_type=ResourceConnectionType.MCP_GATEWAY
        )
        connections = client.filter_connections(filter_request)
        for conn in connections.connections.items:
            print(f"  - {conn.connection_name}: {conn.connection_status}")
        ```

    Attributes:
        Inherits all attributes from the base BaseClient class including:
        - auth: Authentication handler
        - config: Configuration object with service settings
    """

    def __init__(
            self,
            api_key: str,
            config: Optional[Config] = None,
            request_handler=None
    ):
        """
        Initialize a ResourceConnectionClient instance.

        Args:
            api_key (str): Your Cisco AI Defense API key for authentication.
            config (Config, optional): SDK-level configuration for endpoints, logging, retries, etc.
                If not provided, a default Config instance is created.
            request_handler: Optional custom request handler for API requests.
        """
        super().__init__(ManagementAuth(api_key), config, request_handler)

    def create_connection(
            self,
            request: CreateResourceConnectionRequest
    ) -> CreateResourceConnectionResponse:
        """
        Create a new resource connection.

        This method creates a new resource connection that links one or more
        resources (such as MCP servers) to the AI Defense platform.

        Args:
            request (CreateResourceConnectionRequest): Request object containing:
                - connection_name: Name for the connection
                - connection_type: Type of connection (e.g., MCP_GATEWAY)
                - resource_ids: List of resource IDs to associate
                - resource_id: Single resource ID (deprecated, use resource_ids)

        Returns:
            CreateResourceConnectionResponse: Response object containing:
                - connection_id: ID of the created connection (UUID)

        Raises:
            ValidationError: If the request parameters are invalid.
            ApiError: If the API returns an error response.
            SDKError: For other SDK-related errors.

        Example:
            ```python
            from aidefense.mcpscan import ResourceConnectionClient
            from aidefense.mcpscan.models import (
                CreateResourceConnectionRequest, ResourceConnectionType
            )

            client = ResourceConnectionClient(api_key="YOUR_API_KEY")

            request = CreateResourceConnectionRequest(
                connection_name="Production MCP Connection",
                connection_type=ResourceConnectionType.MCP_GATEWAY,
                resource_ids=["mcp-server-uuid-1", "mcp-server-uuid-2"]
            )
            response = client.create_connection(request)
            print(f"Created connection ID: {response.connection_id}")
            ```
        """
        res = self.make_request(
            method=HttpMethod.POST,
            path=resource_connections(),
            data=request.to_body_dict(),
        )
        result = CreateResourceConnectionResponse.model_validate(res)
        self.config.logger.debug(f"Created resource connection: {result}")
        return result

    def delete_connection(self, connection_id: str) -> None:
        """
        Delete a resource connection by its ID.

        This method removes a resource connection from the AI Defense platform.
        All associations with resources will be removed.

        Args:
            connection_id (str): The unique identifier of the connection to delete (UUID).

        Returns:
            None

        Raises:
            ValidationError: If the connection_id is invalid.
            ApiError: If the API returns an error response.
            SDKError: For other SDK-related errors.

        Example:
            ```python
            from aidefense.mcpscan import ResourceConnectionClient

            client = ResourceConnectionClient(api_key="YOUR_API_KEY")

            connection_id = "550e8400-e29b-41d4-a716-446655440000"
            client.delete_connection(connection_id)
            print(f"Deleted connection {connection_id}")
            ```
        """
        self.make_request(
            method=HttpMethod.DELETE,
            path=resource_connection_by_id(connection_id),
        )
        self.config.logger.debug(f"Deleted resource connection: {connection_id}")

    def delete_connections_by_resource_id(self, resource_id: str) -> None:
        """
        Delete all resource connections associated with a specific resource.

        This method removes all connections linked to the specified resource ID.

        Args:
            resource_id (str): The unique identifier of the resource (UUID).

        Returns:
            None

        Raises:
            ValidationError: If the resource_id is invalid.
            ApiError: If the API returns an error response.
            SDKError: For other SDK-related errors.

        Example:
            ```python
            from aidefense.mcpscan import ResourceConnectionClient

            client = ResourceConnectionClient(api_key="YOUR_API_KEY")

            resource_id = "550e8400-e29b-41d4-a716-446655440000"
            client.delete_connections_by_resource_id(resource_id)
            print(f"Deleted all connections for resource {resource_id}")
            ```
        """
        self.make_request(
            method=HttpMethod.DELETE,
            path=resource_connections_by_resource_id(resource_id),
        )
        self.config.logger.debug(f"Deleted connections for resource: {resource_id}")

    def get_connection(
            self,
            connection_id: str,
            expanded: bool = False
    ) -> ResourceConnection:
        """
        Get a resource connection by its ID.

        This method retrieves the details of a specific resource connection.

        Args:
            connection_id (str): The unique identifier of the connection (UUID).
            expanded (bool): Whether to include expanded information. Defaults to False.

        Returns:
            ResourceConnection: The resource connection details including:
                - connection_id: Connection identifier
                - connection_name: Connection name
                - connection_status: Current status
                - connection_type: Type of connection
                - resource_details: Associated resource information (if expanded)
                - policies: Associated policies (if expanded)

        Raises:
            ValidationError: If the connection_id is invalid.
            ApiError: If the API returns an error response.
            SDKError: For other SDK-related errors.

        Example:
            ```python
            from aidefense.mcpscan import ResourceConnectionClient

            client = ResourceConnectionClient(api_key="YOUR_API_KEY")

            connection_id = "550e8400-e29b-41d4-a716-446655440000"
            connection = client.get_connection(connection_id, expanded=True)

            print(f"Connection: {connection.connection_name}")
            print(f"Status: {connection.connection_status}")
            if connection.resource_details:
                print(f"Resource: {connection.resource_details.resource_name}")
            ```
        """
        params = {"expanded": expanded} if expanded else None
        res = self.make_request(
            method=HttpMethod.GET,
            path=resource_connection_by_id(connection_id),
            params=params,
        )
        response = GetResourceConnectionByIDResponse.parse_obj(res)
        self.config.logger.debug(f"Retrieved resource connection: {response}")
        return response.connection

    def get_connection_by_resource_id(self, resource_id: str) -> ResourceConnections:
        """
        Get resource connections associated with a specific resource.

        This method retrieves all connections linked to the specified resource ID.

        Args:
            resource_id (str): The unique identifier of the resource (UUID).

        Returns:
            ResourceConnections: Object containing:
                - items: List of ResourceConnection objects
                - paging: Pagination information

        Raises:
            ValidationError: If the resource_id is invalid.
            ApiError: If the API returns an error response.
            SDKError: For other SDK-related errors.

        Example:
            ```python
            from aidefense.mcpscan import ResourceConnectionClient

            client = ResourceConnectionClient(api_key="YOUR_API_KEY")

            resource_id = "550e8400-e29b-41d4-a716-446655440000"
            connections = client.get_connection_by_resource_id(resource_id)

            print(f"Found {len(connections.items)} connections")
            for conn in connections.items:
                print(f"  - {conn.connection_name}: {conn.connection_status}")
            ```
        """
        res = self.make_request(
            method=HttpMethod.GET,
            path=resource_connection_by_resource_id(resource_id),
        )
        response = GetResourceConnectionByResourceIDResponse.parse_obj(res)
        self.config.logger.debug(f"Retrieved connections for resource: {response}")
        return response.connections

    def filter_connections(
            self,
            request: FilterResourceConnectionsRequest
    ) -> FilterResourceConnectionsResponse:
        """
        Filter resource connections based on specified criteria.

        This method retrieves resource connections matching the filter criteria
        with support for pagination and sorting.

        Args:
            request (FilterResourceConnectionsRequest): Request object containing:
                - limit: Maximum number of results to return
                - offset: Number of results to skip
                - resource_ids: Filter by resource IDs
                - policy_ids: Filter by policy IDs
                - connection_type: Filter by connection type
                - connection_status: Filter by connection status
                - policy_applied: Filter by policy assignment status
                - connection_name: Search by connection name
                - sort_by: Field to sort by
                - order: Sort order (asc/desc)

        Returns:
            FilterResourceConnectionsResponse: Response object containing:
                - connections: ResourceConnections with items and paging

        Raises:
            ValidationError: If request parameters are invalid.
            ApiError: If the API returns an error response.
            SDKError: For other SDK-related errors.

        Example:
            ```python
            from aidefense.mcpscan import ResourceConnectionClient
            from aidefense.mcpscan.models import (
                FilterResourceConnectionsRequest,
                ResourceConnectionType,
                ResourceConnectionStatus,
                ResourceConnectionSortBy,
                SortOrder
            )

            client = ResourceConnectionClient(api_key="YOUR_API_KEY")

            # Filter active MCP Gateway connections
            request = FilterResourceConnectionsRequest(
                limit=50,
                connection_type=ResourceConnectionType.MCP_GATEWAY,
                connection_status=ResourceConnectionStatus.ACTIVE,
                sort_by=ResourceConnectionSortBy.CONNECTION_NAME,
                order=SortOrder.ASC
            )
            response = client.filter_connections(request)

            print(f"Found {response.connections.paging.total} total connections")
            for conn in response.connections.items:
                print(f"  - {conn.connection_name}")
            ```
        """
        res = self.make_request(
            method=HttpMethod.POST,
            path=resource_connections_filter(),
            data=request.to_body_dict(),
        )
        result = FilterResourceConnectionsResponse.parse_obj(res)
        self.config.logger.debug(f"Filtered resource connections: {result}")
        return result

    def filter_resources_by_connection_id(
            self,
            request: FilterResourcesByConnectionIDRequest
    ) -> FilterResourcesByConnectionIDResponse:
        """
        Filter resources associated with a specific connection.

        This method retrieves resources linked to a connection with
        support for filtering and pagination.

        Args:
            request (FilterResourcesByConnectionIDRequest): Request object containing:
                - connection_id: Connection ID to filter by
                - resource_type: Type of resources to retrieve
                - limit: Maximum number of results
                - offset: Pagination offset
                - resource_type_specific_filters: Additional type-specific filters

        Returns:
            FilterResourcesByConnectionIDResponse: Response object containing:
                - resources: List of ResourceInfo objects
                - paging: Pagination information

        Raises:
            ValidationError: If request parameters are invalid.
            ApiError: If the API returns an error response.
            SDKError: For other SDK-related errors.

        Example:
            ```python
            from aidefense.mcpscan import ResourceConnectionClient
            from aidefense.mcpscan.models import (
                FilterResourcesByConnectionIDRequest,
                ResourceType,
                MCPServerFilters,
                ResourceTypeSpecificFilters
            )

            client = ResourceConnectionClient(api_key="YOUR_API_KEY")

            # Get MCP servers for a connection
            request = FilterResourcesByConnectionIDRequest(
                connection_id="550e8400-e29b-41d4-a716-446655440000",
                resource_type=ResourceType.MCP_SERVER,
                limit=25,
                resource_type_specific_filters=ResourceTypeSpecificFilters(
                    mcp_server=MCPServerFilters(
                        server_name_substr=["prod-"]
                    )
                )
            )
            response = client.filter_resources_by_connection_id(request)

            print(f"Found {len(response.resources)} resources")
            for resource in response.resources:
                print(f"  - {resource.resource_name}: {resource.resource_url}")
            ```
        """
        # Extract connection_id for the URL
        connection_id = request.connection_id

        # Build the body without connection_id (it's in the URL)
        body = request.to_body_dict()
        body.pop("connection_id", None)

        res = self.make_request(
            method=HttpMethod.POST,
            path=resources_by_connection_id(connection_id),
            data=body,
        )
        result = FilterResourcesByConnectionIDResponse.parse_obj(res)
        self.config.logger.debug(f"Filtered resources by connection: {result}")
        return result

    def add_or_update_connections(
            self,
            request: AddOrUpdateResourceConnectionsRequest
    ) -> None:
        """
        Add or update resource associations for a connection.

        This method allows associating or disassociating resources
        with an existing connection.

        Args:
            request (AddOrUpdateResourceConnectionsRequest): Request object containing:
                - connection_id: Connection ID to update
                - associate_resource_ids: List of resource IDs to associate
                - disassociate_resource_ids: List of resource IDs to disassociate
                - resource_type: Type of resources

        Returns:
            None

        Raises:
            ValidationError: If request parameters are invalid.
            ApiError: If the API returns an error response.
            SDKError: For other SDK-related errors.

        Example:
            ```python
            from aidefense.mcpscan import ResourceConnectionClient
            from aidefense.mcpscan.models import (
                AddOrUpdateResourceConnectionsRequest,
                ResourceType
            )

            client = ResourceConnectionClient(api_key="YOUR_API_KEY")

            # Associate new resources and disassociate old ones
            request = AddOrUpdateResourceConnectionsRequest(
                connection_id="550e8400-e29b-41d4-a716-446655440000",
                associate_resource_ids=["new-resource-uuid-1", "new-resource-uuid-2"],
                disassociate_resource_ids=["old-resource-uuid-1"],
                resource_type=ResourceType.MCP_SERVER
            )
            client.add_or_update_connections(request)
            print("Updated connection associations")
            ```
        """
        # Extract connection_id for the URL
        connection_id = request.connection_id

        # Build the body without connection_id (it's in the URL)
        body = request.to_body_dict()
        body.pop("connection_id", None)

        self.make_request(
            method=HttpMethod.PUT,
            path=add_or_update_resource_connections(connection_id),
            data=body,
        )
        self.config.logger.debug(f"Updated resource connections for: {connection_id}")

