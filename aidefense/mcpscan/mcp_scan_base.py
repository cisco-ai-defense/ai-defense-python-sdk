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

from typing import List, Optional

from aidefense.config import Config
from aidefense.management.auth import ManagementAuth
from aidefense.management.base_client import BaseClient
from aidefense.request_handler import HttpMethod
from aidefense.mcpscan.models import (
    StartMCPServerScanRequest,
    StartMCPServerScanResponse,
    GetMCPScanStatusResponse,
    RegisterMCPServerRequest,
    RegisterMCPServerResponse,
    GetMCPServerCapabilitiesResponse,
    GetMCPServerThreatsResponse,
    GetMCPServerScanSummaryResponse,
    CapabilityType,
    GetMCPServerResponse,
    ListMCPServersResponse,
    UpdateAuthConfigRequest,
    UpdateAuthConfigResponse,
    OnboardingStatus,
    SeverityLevel,
    TransportType,
)
from aidefense.mcpscan.routes import (
    mcp_scan_start,
    mcp_scan_status,
    mcp_servers_register,
    mcp_server_delete,
    mcp_server_capabilities,
    mcp_server_threats,
    mcp_server_scan_summary,
    mcp_server_get,
    mcp_servers_list,
    mcp_server_update_auth_config,
)


class MCPScan(BaseClient):
    """
    Client for scanning MCP (Model Context Protocol) servers with Cisco AI Defense.

    The MCPScan class provides methods to scan MCP servers for security threats and
    vulnerabilities without requiring prior registration. It communicates with the
    AI Defense MCP scanning API endpoints to detect potential security issues in
    MCP server configurations and capabilities.

    Typical usage:
        ```python
        from aidefense.mcpscan import MCPScan
        from aidefense.mcpscan.models import (
            StartMCPServerScanRequest, TransportType, MCPScanStatus,
            ServerType, RemoteServerInput
        )

        client = MCPScan(api_key="YOUR_MANAGEMENT_API_KEY")

        # Start a scan
        request = StartMCPServerScanRequest(
            name="My MCP Server",
            server_type=ServerType.REMOTE,
            remote=RemoteServerInput(
                url="https://mcp-server.example.com/sse",
                connection_type=TransportType.SSE
            )
        )
        response = client.start_scan(request)
        print(f"Scan started with ID: {response.scan_id}")

        # Check scan status
        status = client.get_scan_status(response.scan_id)
        if status.status == MCPScanStatus.COMPLETED:
            print("Scan completed successfully")
        ```

    Args:
        api_key (str): Your Cisco AI Defense API key for authentication.
        config (Config, optional): SDK configuration for endpoints, logging, retries, etc.
            If not provided, a default Config is used.

    Attributes:
        auth (ManagementAuth): Authentication handler for API requests.
        config (Config): SDK configuration instance.
        api_key (str): The API key used for authentication.
    """

    def __init__(
            self, api_key: str, config: Optional[Config] = None, request_handler=None):
        """
        Initialize an MCPScan client instance.

        Args:
            api_key (str): Your Cisco AI Defense API key for authentication.
            config (Config, optional): SDK-level configuration for endpoints, logging, retries, etc.
                If not provided, a default Config instance is created.
            request_handler: Optional custom request handler for API requests.
        """
        super().__init__(ManagementAuth(api_key), config, request_handler)

    def start_scan(self, request: StartMCPServerScanRequest) -> StartMCPServerScanResponse:
        """
        Start a security scan on an MCP server without prior registration.

        This method initiates an asynchronous security scan of the specified MCP server.
        The scan analyzes the server's capabilities (tools, prompts, resources) for
        potential security threats and vulnerabilities.

        Args:
            request (StartMCPServerScanRequest): Request object containing MCP server details
                including name, URL, connection type, and optional authentication config.

        Returns:
            StartMCPServerScanResponse: Response object containing:
                - scan_id: Unique identifier for tracking the scan
                - status: Initial status of the scan (typically QUEUED or IN_PROGRESS)
                - created_at: Timestamp when the scan was created

        Raises:
            ValidationError: If the request parameters are invalid.
            ApiError: If the API returns an error response.
            SDKError: For other SDK-related errors.

        Example:
            ```python
            from aidefense.mcpscan import MCPScan
            from aidefense.mcpscan.models import (
                StartMCPServerScanRequest, TransportType, AuthConfig, 
                AuthType, ApiKeyConfig, ServerType, RemoteServerInput
            )

            client = MCPScan(api_key="YOUR_MANAGEMENT_API_KEY")

            # Scan an MCP server with API key authentication
            request = StartMCPServerScanRequest(
                name="Production MCP Server",
                server_type=ServerType.REMOTE,
                remote=RemoteServerInput(
                    url="https://mcp-server.example.com/sse",
                    connection_type=TransportType.SSE
                ),
                auth_config=AuthConfig(
                    auth_type=AuthType.API_KEY,
                    api_key=ApiKeyConfig(
                        header_name="X-API-Key",
                        api_key="server_api_key_here"
                    )
                )
            )
            response = client.start_scan(request)
            print(f"Scan ID: {response.scan_id}")
            ```
        """
        res = self.make_request(
            method=HttpMethod.POST,
            path=mcp_scan_start(),
            data=request.to_body_dict(),
        )
        result = StartMCPServerScanResponse.model_validate(res)
        self.config.logger.debug(f"Raw API response: {result}")
        return result

    def get_scan_status(self, scan_id: str) -> GetMCPScanStatusResponse:
        """
        Get the current status and results of an MCP server scan.

        This method retrieves the current status of a previously initiated scan.
        If the scan has completed, the response will include the full scan results
        with threat analysis for each capability.

        Args:
            scan_id (str): The unique identifier of the scan to query (UUID string).

        Returns:
            GetMCPScanStatusResponse: Response object containing:
                - scan_id: The scan identifier
                - status: Current scan status (QUEUED, IN_PROGRESS, COMPLETED, FAILED, etc.)
                - created_at: When the scan was created
                - completed_at: When the scan completed (if applicable)
                - expires_at: When the scan results will expire
                - result: Detailed scan results (when status is COMPLETED)
                - error_message: Error details (when status is FAILED)

        Raises:
            ValidationError: If the scan_id is invalid.
            ApiError: If the API returns an error response.
            SDKError: For other SDK-related errors.

        Example:
            ```python
            from aidefense.mcpscan import MCPScan
            from aidefense.mcpscan.models import MCPScanStatus

            client = MCPScan(api_key="YOUR_MANAGEMENT_API_KEY")

            # Get scan status
            scan_id = "550e8400-e29b-41d4-a716-446655440000"
            status = client.get_scan_status(scan_id)

            print(f"Scan Status: {status.status}")

            if status.status == MCPScanStatus.COMPLETED:
                print(f"Completed at: {status.completed_at}")
                if status.result:
                    print(f"Is Safe: {status.result.is_safe}")
                    if status.result.capabilities:
                        for cap_id, results in status.result.capabilities.tool_results.items():
                            print(f"Capability {cap_id}:")
                            for item in results.items:
                                print(f"  - {item.capability_name}: {item.severity}")
            elif status.status == MCPScanStatus.FAILED:
                print(f"Error: {status.error_message}")
            ```
        """
        res = self.make_request(
            method=HttpMethod.GET,
            path=mcp_scan_status(scan_id),
        )
        result = GetMCPScanStatusResponse.model_validate(res)
        self.config.logger.debug(f"Raw API response: {result}")
        return result

    def register_server(self, request: RegisterMCPServerRequest) -> RegisterMCPServerResponse:
        """
        Register a new MCP server with Cisco AI Defense.

        This method registers an MCP server for ongoing security monitoring. Once registered,
        the server can be scanned on-demand or periodically based on configured settings.

        Args:
            request (RegisterMCPServerRequest): Request object containing MCP server details
                including name, URL, connection type, scan settings, and optional authentication config.

        Returns:
            RegisterMCPServerResponse: Response object containing:
                - server_id: Unique identifier for the registered server (UUID)

        Raises:
            ValidationError: If the request parameters are invalid.
            ApiError: If the API returns an error response.
            SDKError: For other SDK-related errors.

        Example:
            ```python
            from aidefense.mcpscan import MCPScan
            from aidefense.mcpscan.models import (
                RegisterMCPServerRequest, TransportType, AuthConfig,
                AuthType, ApiKeyConfig
            )

            client = MCPScan(api_key="YOUR_MANAGEMENT_API_KEY")

            # Register an MCP server with API key authentication
            request = RegisterMCPServerRequest(
                name="Production MCP Server",
                url="https://mcp-server.example.com/sse",
                description="Main production MCP server",
                connection_type=TransportType.SSE,
                scan_enabled=True,
                auth_config=AuthConfig(
                    auth_type=AuthType.API_KEY,
                    api_key=ApiKeyConfig(
                        header_name="X-API-Key",
                        api_key="server_api_key_here"
                    )
                )
            )
            response = client.register_server(request)
            print(f"Registered server ID: {response.server_id}")
            ```
        """
        res = self.make_request(
            method=HttpMethod.POST,
            path=mcp_servers_register(),
            data=request.to_body_dict(),
        )
        result = RegisterMCPServerResponse.parse_obj(res)
        self.config.logger.debug(f"Registered MCP server: {result}")
        return result

    def delete_server(self, server_id: str) -> None:
        """
        Delete a registered MCP server.

        This method removes a previously registered MCP server from Cisco AI Defense.
        All associated scan results and configurations will be deleted.

        Args:
            server_id (str): The unique identifier of the server to delete (UUID string).

        Returns:
            None

        Raises:
            ValidationError: If the server_id is invalid.
            ApiError: If the API returns an error response (e.g., server not found).
            SDKError: For other SDK-related errors.

        Example:
            ```python
            from aidefense.mcpscan import MCPScan

            client = MCPScan(api_key="YOUR_MANAGEMENT_API_KEY")

            # Delete an MCP server
            server_id = "550e8400-e29b-41d4-a716-446655440000"
            client.delete_server(server_id)
            print(f"Server {server_id} deleted successfully")
            ```
        """
        self.make_request(
            method=HttpMethod.DELETE,
            path=mcp_server_delete(server_id),
        )
        self.config.logger.debug(f"Deleted MCP server: {server_id}")

    def get_server_capabilities(
            self,
            server_id: str,
            capability_type: CapabilityType,
            capability_name: str = "",
            limit: int = 25,
            offset: int = 0,
    ) -> GetMCPServerCapabilitiesResponse:
        """
        Get capabilities of a registered MCP server.

        This method retrieves the capabilities (tools, prompts, or resources) exposed
        by a registered MCP server. Capabilities are discovered during the server
        onboarding or scanning process.

        Args:
            server_id (str): The unique identifier of the MCP server (UUID string).
            capability_type (CapabilityType): Type of capabilities to retrieve
                (TOOL, PROMPT, or RESOURCE).
            capability_name (str): Optional filter by capability name substring.
            limit (int): Maximum number of results to return (default: 25).
            offset (int): Offset for pagination (default: 0).

        Returns:
            GetMCPServerCapabilitiesResponse: Response object containing:
                - capabilities: List of Capability objects matching the filter
                - paging: Pagination information (total, limit, offset)

        Raises:
            ValidationError: If parameters are invalid.
            ApiError: If the API returns an error response.
            SDKError: For other SDK-related errors.

        Example:
            ```python
            from aidefense.mcpscan import MCPScan
            from aidefense.mcpscan.models import CapabilityType

            client = MCPScan(api_key="YOUR_MANAGEMENT_API_KEY")

            # Get all tools for an MCP server
            server_id = "550e8400-e29b-41d4-a716-446655440000"
            response = client.get_server_capabilities(
                server_id=server_id,
                capability_type=CapabilityType.TOOL,
                limit=50
            )

            print(f"Found {len(response.capabilities)} tools")
            for cap in response.capabilities:
                if cap.tool:
                    print(f"  - {cap.tool.name}: {cap.tool.description}")

            # Get resources with a specific name pattern
            response = client.get_server_capabilities(
                server_id=server_id,
                capability_type=CapabilityType.RESOURCE,
                capability_name="config"
            )
            for cap in response.capabilities:
                if cap.resource:
                    print(f"  - {cap.resource.name}: {cap.resource.uri}")
            ```
        """
        params = {
            "capability_type": capability_type.value,
            "limit": limit,
            "offset": offset,
        }
        if capability_name:
            params["capability_name"] = capability_name

        res = self.make_request(
            method=HttpMethod.GET,
            path=mcp_server_capabilities(server_id),
            params=params,
        )
        result = GetMCPServerCapabilitiesResponse.parse_obj(res)
        self.config.logger.debug(f"Retrieved capabilities for server {server_id}: {result}")
        return result

    def get_server_threats(
            self,
            server_id: str,
            capability_type: Optional[CapabilityType] = None,
            threat_severity: Optional[List[str]] = None,
            limit: int = 25,
            offset: int = 0,
    ) -> GetMCPServerThreatsResponse:
        """
        Get threats detected for a registered MCP server.

        This method retrieves the security threats detected across capabilities
        of a registered MCP server. Results can be filtered by capability type
        and threat severity.

        Args:
            server_id (str): The unique identifier of the MCP server (UUID string).
            capability_type (CapabilityType, optional): Filter by capability type.
            threat_severity (List[str], optional): Filter by severity levels
                (e.g., ["HIGH", "CRITICAL"]).
            limit (int): Maximum number of results to return (default: 25).
            offset (int): Offset for pagination (default: 0).

        Returns:
            GetMCPServerThreatsResponse: Response object containing:
                - threats: List of MCPServerCapabilityThreats objects
                - paging: Pagination information

        Raises:
            ValidationError: If parameters are invalid.
            ApiError: If the API returns an error response.
            SDKError: For other SDK-related errors.

        Example:
            ```python
            from aidefense.mcpscan import MCPScan
            from aidefense.mcpscan.models import CapabilityType

            client = MCPScan(api_key="YOUR_MANAGEMENT_API_KEY")

            # Get all threats for an MCP server
            server_id = "550e8400-e29b-41d4-a716-446655440000"
            response = client.get_server_threats(server_id=server_id)

            print(f"Found {len(response.threats)} threats")
            for threat_item in response.threats:
                if threat_item.threat:
                    print(f"  Capability {threat_item.capability_id}:")
                    print(f"    - {threat_item.threat.technique_name}")
                    for sub in threat_item.threat.sub_techniques:
                        print(f"      - {sub.sub_technique_name}: {sub.severity}")

            # Get only high and critical threats for tools
            response = client.get_server_threats(
                server_id=server_id,
                capability_type=CapabilityType.TOOL,
                threat_severity=["HIGH", "CRITICAL"]
            )
            ```
        """
        params = {
            "limit": limit,
            "offset": offset,
        }
        if capability_type:
            params["capability_type"] = capability_type.value
        if threat_severity:
            params["threat_severity"] = threat_severity

        res = self.make_request(
            method=HttpMethod.GET,
            path=mcp_server_threats(server_id),
            params=params,
        )
        result = GetMCPServerThreatsResponse.parse_obj(res)
        self.config.logger.debug(f"Retrieved threats for server {server_id}: {result}")
        return result

    def get_server_scan_summary(self, server_id: str) -> GetMCPServerScanSummaryResponse:
        """
        Get scan summary for a registered MCP server.

        This method retrieves a summary of the most recent scan for a registered
        MCP server, including capability counts and threat statistics.

        Args:
            server_id (str): The unique identifier of the MCP server (UUID string).

        Returns:
            GetMCPServerScanSummaryResponse: Response object containing:
                - capability_summary: Counts of tools, prompts, and resources
                - scan_threat_summary: Counts of threats by severity level
                - completed_at: Timestamp of the most recent scan

        Raises:
            ValidationError: If the server_id is invalid.
            ApiError: If the API returns an error response.
            SDKError: For other SDK-related errors.

        Example:
            ```python
            from aidefense.mcpscan import MCPScan

            client = MCPScan(api_key="YOUR_MANAGEMENT_API_KEY")

            # Get scan summary
            server_id = "550e8400-e29b-41d4-a716-446655440000"
            summary = client.get_server_scan_summary(server_id)

            print(f"Last scan: {summary.completed_at}")

            if summary.capability_summary:
                print(f"Capabilities found:")
                print(f"  - Tools: {summary.capability_summary.tool_count}")
                print(f"  - Prompts: {summary.capability_summary.prompt_count}")
                print(f"  - Resources: {summary.capability_summary.resource_count}")

            if summary.scan_threat_summary:
                print(f"Threats found:")
                print(f"  - Critical: {summary.scan_threat_summary.critical_count}")
                print(f"  - High: {summary.scan_threat_summary.high_count}")
                print(f"  - Medium: {summary.scan_threat_summary.medium_count}")
                print(f"  - Low: {summary.scan_threat_summary.low_count}")
            ```
        """
        res = self.make_request(
            method=HttpMethod.GET,
            path=mcp_server_scan_summary(server_id),
        )
        result = GetMCPServerScanSummaryResponse.parse_obj(res)
        self.config.logger.debug(f"Retrieved scan summary for server {server_id}: {result}")
        return result

    def get_server(self, server_id: str) -> GetMCPServerResponse:
        """
        Get details of a registered MCP server by ID.

        This method retrieves the full details of a previously registered MCP server,
        including its configuration, status, and authentication settings.

        Args:
            server_id (str): The unique identifier of the MCP server (UUID string).

        Returns:
            GetMCPServerResponse: Response object containing:
                - mcp_server: MCPServer object with full server details including
                  name, URL, connection type, onboarding status, auth config, etc.

        Raises:
            ValidationError: If the server_id is invalid.
            ApiError: If the API returns an error response (e.g., server not found).
            SDKError: For other SDK-related errors.

        Example:
            ```python
            from aidefense.mcpscan import MCPScan

            client = MCPScan(api_key="YOUR_MANAGEMENT_API_KEY")

            # Get MCP server details
            server_id = "550e8400-e29b-41d4-a716-446655440000"
            response = client.get_server(server_id)

            if response.mcp_server:
                server = response.mcp_server
                print(f"Server Name: {server.name}")
                print(f"URL: {server.url}")
                print(f"Connection Type: {server.connection_type}")
                print(f"Onboarding Status: {server.onboarding_status}")
                print(f"Scan Enabled: {server.scan_enabled}")
                print(f"Auth Type: {server.auth_type}")
                print(f"Created At: {server.created_at}")

                if server.status_info:
                    print(f"Status Error: {server.status_info.message}")
            ```
        """
        res = self.make_request(
            method=HttpMethod.GET,
            path=mcp_server_get(server_id),
        )
        result = GetMCPServerResponse.parse_obj(res)
        self.config.logger.debug(f"Retrieved MCP server {server_id}: {result}")
        return result

    def list_servers(
            self,
            limit: int = 25,
            offset: int = 0,
            server_name_substr: Optional[str] = None,
            onboarding_status: Optional[List[OnboardingStatus]] = None,
            transport_type: Optional[List[TransportType]] = None,
            severity: Optional[List[SeverityLevel]] = None,
    ) -> ListMCPServersResponse:
        """
        List registered MCP servers with optional filtering.

        This method retrieves a list of MCP servers registered with Cisco AI Defense.
        Results can be filtered by various criteria and paginated.

        Args:
            limit (int): Maximum number of servers to return (default: 25).
            offset (int): Offset for pagination (default: 0).
            server_name_substr (str, optional): Filter by server name substring match.
            onboarding_status (List[OnboardingStatus], optional): Filter by onboarding
                status(es). Use OnboardingStatus enum values.
            transport_type (List[TransportType], optional): Filter by transport type(s).
                Use TransportType enum values.
            severity (List[SeverityLevel], optional): Filter by severity level(s).
                Use SeverityLevel enum values.

        Returns:
            ListMCPServersResponse: Response object containing:
                - mcp_servers: MCPServers object with:
                  - items: List of MCPServer objects
                  - paging: Pagination information (total, limit, offset)

        Raises:
            ValidationError: If parameters are invalid.
            ApiError: If the API returns an error response.
            SDKError: For other SDK-related errors.

        Example:
            ```python
            from aidefense.mcpscan import MCPScan
            from aidefense.mcpscan.models import OnboardingStatus, TransportType

            client = MCPScan(api_key="YOUR_MANAGEMENT_API_KEY")

            # List all MCP servers
            response = client.list_servers(limit=50)

            if response.mcp_servers:
                print(f"Total servers: {response.mcp_servers.paging.total}")
                for server in response.mcp_servers.items:
                    print(f"  - {server.name}: {server.url}")
                    print(f"    Status: {server.onboarding_status}")

            # Filter by onboarding status
            response = client.list_servers(
                onboarding_status=[OnboardingStatus.COMPLETED],
                transport_type=[TransportType.SSE]
            )

            # Search by name
            response = client.list_servers(
                server_name_substr="production",
                limit=10
            )
            ```
        """
        params = {
            "limit": limit,
            "offset": offset,
        }
        if server_name_substr:
            params["server_name_substr"] = server_name_substr
        if onboarding_status:
            params["onboarding_status"] = [status.value for status in onboarding_status]
        if transport_type:
            params["transport_type"] = [t.value for t in transport_type]
        if severity:
            params["severity"] = [s.value for s in severity]

        res = self.make_request(
            method=HttpMethod.GET,
            path=mcp_servers_list(),
            params=params,
        )
        result = ListMCPServersResponse.parse_obj(res)
        self.config.logger.debug(f"Listed MCP servers: {result}")
        return result

    def update_auth_config(
            self,
            request: UpdateAuthConfigRequest
    ) -> UpdateAuthConfigResponse:
        """
        Update authentication configuration for a registered MCP server.

        This method updates the authentication settings for a previously registered
        MCP server. Use this to change authentication type, update API keys, or
        modify OAuth settings.

        Args:
            request (UpdateAuthConfigRequest): Request object containing:
                - server_id: ID of the MCP server to update (UUID)
                - auth_config: New authentication configuration

        Returns:
            UpdateAuthConfigResponse: Response object containing:
                - server_id: ID of the updated MCP server

        Raises:
            ValidationError: If the request parameters are invalid.
            ApiError: If the API returns an error response (e.g., server not found).
            SDKError: For other SDK-related errors.

        Example:
            ```python
            from aidefense.mcpscan import MCPScan
            from aidefense.mcpscan.models import (
                UpdateAuthConfigRequest, AuthConfig, AuthType, ApiKeyConfig
            )

            client = MCPScan(api_key="YOUR_MANAGEMENT_API_KEY")

            # Update to API key authentication
            request = UpdateAuthConfigRequest(
                server_id="550e8400-e29b-41d4-a716-446655440000",
                auth_config=AuthConfig(
                    auth_type=AuthType.API_KEY,
                    api_key=ApiKeyConfig(
                        header_name="X-API-Key",
                        api_key="new_api_key_here"
                    )
                )
            )
            response = client.update_auth_config(request)
            print(f"Updated auth config for server: {response.server_id}")

            # Update to no authentication
            request = UpdateAuthConfigRequest(
                server_id="550e8400-e29b-41d4-a716-446655440000",
                auth_config=AuthConfig(auth_type=AuthType.NO_AUTH)
            )
            response = client.update_auth_config(request)
            ```
        """
        res = self.make_request(
            method=HttpMethod.PUT,
            path=mcp_server_update_auth_config(request.server_id),
            data=request.to_body_dict(),
        )
        result = UpdateAuthConfigResponse.parse_obj(res)
        self.config.logger.debug(f"Updated auth config for server {request.server_id}: {result}")
        return result

