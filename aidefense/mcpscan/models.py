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

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Union

from pydantic import Field, model_validator

from aidefense.models.base import AIDefenseModel


# --------------------
# Enums
# --------------------

class TransportType(str, Enum):
    """Transport type for MCP server connection."""
    TRANSPORT_TYPE_UNSPECIFIED = "TRANSPORT_TYPE_UNSPECIFIED"
    SSE = "SSE"
    STREAMABLE = "STREAMABLE"
    STDIO = "STDIO"


class AuthType(str, Enum):
    """Authentication type for MCP server."""
    NO_AUTH = "NO_AUTH"
    API_KEY = "API_KEY"
    OAUTH = "OAUTH"


class MCPScanStatus(str, Enum):
    """Status of an MCP server scan."""
    SCAN_STATUS_UNSPECIFIED = "SCAN_STATUS_UNSPECIFIED"
    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AnalyzerType(str, Enum):
    """Analyzer types available for scanning."""
    UNSPECIFIED = "UNSPECIFIED"
    API = "API"
    YARA = "YARA"
    LLM = "LLM"
    AIGRPC = "AIGRPC"


class SeverityLevel(str, Enum):
    """Severity levels for findings."""
    SEVERITY_UNKNOWN = "SEVERITY_UNKNOWN"
    SAFE = "SAFE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class CapabilityScanStatus(str, Enum):
    """Scan status for a capability."""
    SCAN_STATUS_UNKNOWN = "SCAN_STATUS_UNKNOWN"
    SCAN_COMPLETED = "SCAN_COMPLETED"
    SCAN_FAILED = "SCAN_FAILED"


class CapabilityType(str, Enum):
    """Type of capability exposed by an MCP server."""
    CAPABILITY_KIND_UNSPECIFIED = "CAPABILITY_KIND_UNSPECIFIED"
    TOOL = "TOOL"
    PROMPT = "PROMPT"
    RESOURCE = "RESOURCE"


class OnboardingStatus(str, Enum):
    """Onboarding status of an MCP server."""
    ONBOARDING_STATUS_UNSPECIFIED = "ONBOARDING_STATUS_UNSPECIFIED"
    INPROGRESS = "INPROGRESS"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


class ServerType(str, Enum):
    """Server type for MCP server scanning."""
    SERVER_TYPE_UNSPECIFIED = "UNREGISTERED_SERVER_TYPE_UNSPECIFIED"
    REMOTE = "REMOTE"  # Remote URL-based server (SSE or Streamable HTTP)
    STDIO = "STDIO"    # Stdio-based server spawned from a package/repo (placeholder)


def restore_enum_wrapper(cls, values):
    """Helper to restore enum values from string representations."""
    # Support both Pydantic v1 (__fields__) and v2 (model_fields)
    fields = getattr(cls, 'model_fields', None) or getattr(cls, '__fields__', {})
    for name, field in fields.items():
        value = values.get(name)
        if isinstance(value, str):
            # Get the field type - handle both Pydantic v1 and v2
            field_type = getattr(field, 'annotation', None) or getattr(field, 'type_', None)
            if field_type and hasattr(field_type, '__members__'):
                try:
                    values[name] = field_type(value)
                except ValueError:
                    pass  # leave as-is if invalid
    return values


# --------------------
# Authentication Configuration Models
# --------------------

class OAuthConfig(AIDefenseModel):
    """OAuth configuration for MCP server authentication.

    Args:
        client_id: OAuth client identifier.
        client_secret: OAuth client secret.
        auth_server_url: URL of the OAuth authorization server.
        scope: Optional OAuth scope.
    """
    client_id: str = Field(..., alias="clientId", description="OAuth client identifier")
    client_secret: str = Field(default="", alias="clientSecret", description="OAuth client secret")
    auth_server_url: str = Field(..., alias="authServerUrl", description="OAuth authorization server URL")
    scope: Optional[str] = Field(None, description="OAuth scope")


class ApiKeyConfig(AIDefenseModel):
    """API key configuration for MCP server authentication.

    Args:
        header_name: HTTP header name to use for the API key.
        api_key: The API key value.
    """
    header_name: str = Field(..., alias="headerName", description="HTTP header name for API key")
    api_key: str = Field(..., alias="apiKey", description="API key value")


class AuthConfig(AIDefenseModel):
    """Authentication configuration container for MCP servers.

    Only one of the supported authentication types should be set at a time.

    Args:
        auth_type: Type of authentication (NO_AUTH, API_KEY, OAUTH).
        oauth: OAuth configuration settings.
        api_key: API key configuration settings.
    """
    auth_type: AuthType = Field(..., alias="authType", description="Type of authentication")
    oauth: Optional[OAuthConfig] = Field(None, description="OAuth configuration")
    api_key: Optional[ApiKeyConfig] = Field(None, alias="apiKey", description="API key configuration")

    @model_validator(mode='after')
    def _validate_auth_config(self):
        if self.auth_type == AuthType.OAUTH and self.oauth is None:
            raise ValueError("OAuth configuration is required when auth_type is OAUTH")
        if self.auth_type == AuthType.API_KEY and self.api_key is None:
            raise ValueError("API key configuration is required when auth_type is API_KEY")

        return self


# --------------------
# Capability Models (Tool, Prompt, Resource)
# --------------------

class Argument(AIDefenseModel):
    """Argument definition for tool input/output schemas.

    Args:
        name: Name of the argument parameter.
        description: Description of what this argument is for.
        type: Data type of the argument (e.g., string, number, boolean).
        required: Whether this argument is mandatory.
    """
    name: str = Field(..., description="Argument parameter name")
    description: str = Field(default="", description="Argument description")
    type: str = Field(default="", description="Data type of the argument")
    required: bool = Field(default=False, description="Whether argument is required")


class ToolInputSchema(AIDefenseModel):
    """Tool input schema with arguments.

    Args:
        arguments: List of arguments the tool accepts.
    """
    arguments: List[Argument] = Field(default_factory=list, description="List of input arguments")


class ToolOutputSchema(AIDefenseModel):
    """Tool output schema with arguments.

    Args:
        arguments: List of arguments the tool returns.
    """
    arguments: List[Argument] = Field(default_factory=list, description="List of output arguments")


class Tool(AIDefenseModel):
    """Tool capability exposed by an MCP server.

    Args:
        id: Internal ID of the tool (UUID).
        name: Name of the tool.
        description: Description of the tool.
        title: Optional title of the tool.
        input_schema: Input schema of the tool.
        output_schema: Optional output schema of the tool.
        annotations: Optional annotations map.
    """
    id: str = Field(..., description="Tool identifier (UUID)")
    name: str = Field(..., description="Tool name")
    description: str = Field(default="", description="Tool description")
    title: Optional[str] = Field(None, description="Tool title")
    input_schema: Optional[ToolInputSchema] = Field(None, description="Input schema")
    output_schema: Optional[ToolOutputSchema] = Field(None, description="Output schema")
    annotations: Dict[str, str] = Field(default_factory=dict, description="Annotations")


class PromptInputSchema(AIDefenseModel):
    """Prompt input schema.

    Args:
        name: Name of the prompt template.
        description: Description of what the prompt does.
        required: Whether this argument is mandatory.
    """
    name: str = Field(..., description="Prompt template name")
    description: str = Field(default="", description="Prompt description")
    required: bool = Field(default=False, description="Whether required")


class Prompt(AIDefenseModel):
    """Prompt capability exposed by an MCP server.

    Args:
        id: Internal ID of the prompt (UUID).
        name: Name of the prompt.
        description: Description of the prompt.
        title: Optional title of the prompt.
        input_schema: Schema defining input parameters.
    """
    id: str = Field(..., description="Prompt identifier (UUID)")
    name: str = Field(..., description="Prompt name")
    description: str = Field(default="", description="Prompt description")
    title: Optional[str] = Field(None, description="Prompt title")
    input_schema: List[PromptInputSchema] = Field(default_factory=list, description="Input schema")


class Resource(AIDefenseModel):
    """Resource capability exposed by an MCP server.

    Args:
        id: Internal ID of the resource (UUID).
        name: Name of the resource.
        description: Description of the resource.
        title: Optional title of the resource.
        uri: URI to access the resource.
        mime_type: MIME type of the resource content.
    """
    id: str = Field(..., description="Resource identifier (UUID)")
    name: str = Field(..., description="Resource name")
    description: str = Field(default="", description="Resource description")
    title: Optional[str] = Field(None, description="Resource title")
    uri: str = Field(default="", description="Resource URI")
    mime_type: str = Field(default="", description="MIME type")


class Capability(AIDefenseModel):
    """A capability exposed by an MCP server (tool, prompt, or resource).

    Args:
        capability_type: Type of capability (TOOL, PROMPT, RESOURCE).
        tool: Tool details if capability_type is TOOL.
        prompt: Prompt details if capability_type is PROMPT.
        resource: Resource details if capability_type is RESOURCE.
    """
    capability_type: CapabilityType = Field(..., alias="capabilityType", description="Type of capability")
    tool: Optional[Tool] = Field(None, description="Tool details")
    prompt: Optional[Prompt] = Field(None, description="Prompt details")
    resource: Optional[Resource] = Field(None, description="Resource details")

    @model_validator(mode='before')
    @classmethod
    def __restore_enums(cls, values):
        return restore_enum_wrapper(cls, values)


# --------------------
# Threat Models
# --------------------

class ThreatSubTechnique(AIDefenseModel):
    """Sub-technique details for a threat.

    Args:
        sub_technique_id: Sub-technique ID (e.g., AISubtech-9.1.1).
        sub_technique_name: Sub-technique name (e.g., Code Execution).
        severity: Severity level (HIGH, LOW, MEDIUM).
        description: Description of the technique.
        indicators: List of indicators to display.
        standard_mappings: Standard mappings (e.g., MITRE, OWASP).
    """
    sub_technique_id: str = Field(..., alias="subTechniqueId", description="Sub-technique ID")
    sub_technique_name: str = Field(..., alias="subTechniqueName", description="Sub-technique name")
    severity: str = Field(default="", description="Severity level")
    description: str = Field(default="", description="Description")
    indicators: List[str] = Field(default_factory=list, description="Indicators")
    standard_mappings: List[str] = Field(default_factory=list, description="Standard mappings")


class ThreatDetails(AIDefenseModel):
    """Detailed threat information.

    Args:
        technique_id: Technique ID (e.g., AITech-9.1).
        technique_name: Technique name.
        analyzer_type: Analyzer that generated this result.
        completed_at: When analysis completed.
        sub_techniques: List of sub-techniques.
    """
    technique_id: str = Field(default="", alias="techniqueId", description="Technique ID")
    technique_name: str = Field(default="", alias="techniqueName", description="Technique name")
    analyzer_type: AnalyzerType = Field(default=AnalyzerType.UNSPECIFIED, alias="analyzerType", description="Analyzer type")
    completed_at: Optional[datetime] = Field(None, alias="completedAt", description="Completion timestamp")
    sub_techniques: List[ThreatSubTechnique] = Field(default_factory=list, alias="subTechniques", description="Sub-techniques")

    @model_validator(mode='before')
    @classmethod
    def __restore_enums(cls, values):
        return restore_enum_wrapper(cls, values)


class MCPServerCapabilityThreats(AIDefenseModel):
    """Threats associated with a specific capability.

    Args:
        capability_id: ID of the capability.
        threat: Threat details.
    """
    capability_id: str = Field(..., alias="capabilityId", description="Capability identifier (UUID)")
    threat: Optional[ThreatDetails] = Field(None, description="Threat details")


# --------------------
# Summary Models
# --------------------

class CapabilitySummary(AIDefenseModel):
    """Summary of capabilities for an MCP server scan.

    Args:
        tool_count: Number of tools detected.
        prompt_count: Number of prompts detected.
        resource_count: Number of resources detected.
    """
    tool_count: int = Field(default=0, alias="toolCount", description="Number of tools")
    prompt_count: int = Field(default=0, alias="promptCount", description="Number of prompts")
    resource_count: int = Field(default=0, alias="resourceCount", description="Number of resources")


class ScanThreatSummary(AIDefenseModel):
    """Summary of threats found during an MCP server scan.

    Args:
        critical_count: Number of critical threats found.
        high_count: Number of high severity threats found.
        medium_count: Number of medium severity threats found.
        low_count: Number of low severity threats found.
    """
    critical_count: int = Field(default=0, alias="criticalCount", description="Number of critical threats")
    high_count: int = Field(default=0, alias="highCount", description="Number of high severity threats")
    medium_count: int = Field(default=0, alias="mediumCount", description="Number of medium severity threats")
    low_count: int = Field(default=0, alias="lowCount", description="Number of low severity threats")


# --------------------
# Paging Model
# --------------------

class Paging(AIDefenseModel):
    """Pagination information for list responses.

    Args:
        total: Total number of items.
        limit: Maximum items per page.
        offset: Offset from start.
    """
    total: int = Field(default=0, description="Total number of items")
    limit: int = Field(default=0, description="Maximum items per page")
    offset: int = Field(default=0, description="Offset from start")


# --------------------
# Request/Response Models for RegisterMCPServer
# --------------------

class RegisterMCPServerRequest(AIDefenseModel):
    """Request message for registering an MCP server.

    Args:
        name: Human-readable name for the MCP server (1-128 characters).
        url: URL endpoint of the MCP server (valid URI).
        description: Optional description of the MCP server (max 1024 characters).
        connection_type: Transport type for connecting to the server.
        scan_enabled: Whether to enable scanning for this server.
        auth_config: Optional authentication configuration for the server.
        repository_url: Optional absolute URL of the source code repository (e.g. GitHub URL).
            When provided, must be a valid absolute URI. Required by the API in some environments.
    """
    name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Human-readable name for the MCP server"
    )
    url: str = Field(..., description="URL endpoint of the MCP server")
    description: str = Field(
        default="",
        max_length=1024,
        description="Description of the MCP server"
    )
    connection_type: TransportType = Field(
        ...,
        description="Transport type for server connection"
    )
    scan_enabled: bool = Field(
        default=True,
        description="Whether to enable scanning for this server"
    )
    auth_config: Optional[AuthConfig] = Field(
        None,
        description="Authentication configuration"
    )
    repository_url: Optional[str] = Field(
        None,
        alias="repositoryUrl",
        description="Absolute URL of the source code repository (e.g. https://github.com/org/repo)"
    )


class RegisterMCPServerResponse(AIDefenseModel):
    """Response message for registering an MCP server.

    Args:
        server_id: Unique identifier for the registered server (UUID).
    """
    server_id: str = Field(..., alias="serverId", description="Registered server identifier (UUID)")


class DeleteMCPServerResponse(AIDefenseModel):
    """Response message for deleting an MCP server.

    This is an empty response indicating successful deletion.
    """
    pass


# --------------------
# Request/Response Models for GetMCPServerCapabilities
# --------------------

class GetMCPServerCapabilitiesRequest(AIDefenseModel):
    """Request message for getting MCP server capabilities.

    Args:
        server_id: ID of the MCP server.
        capability_type: Filter by capability type (TOOL, PROMPT, RESOURCE).
        capability_name: Filter by capability name substring.
        limit: Maximum number of results to return.
        offset: Offset for pagination.
    """
    server_id: str = Field(..., description="MCP server identifier (UUID)")
    capability_type: CapabilityType = Field(..., description="Type of capability to retrieve")
    capability_name: str = Field(default="", description="Filter by capability name")
    limit: int = Field(default=25, description="Maximum results to return")
    offset: int = Field(default=0, description="Pagination offset")


class GetMCPServerCapabilitiesResponse(AIDefenseModel):
    """Response message for getting MCP server capabilities.

    Args:
        capabilities: List of capabilities.
        paging: Pagination information.
    """
    capabilities: List[Capability] = Field(default_factory=list, description="List of capabilities")
    paging: Optional[Paging] = Field(None, description="Pagination info")

    @model_validator(mode='before')
    @classmethod
    def unwrap_capabilities(cls, values):
        """Unwrap capabilities from nested structure: {capabilities: {items: [...]}}"""
        caps = values.get("capabilities")
        if isinstance(caps, dict) and "items" in caps:
            values["capabilities"] = caps["items"]
        return values


# --------------------
# Request/Response Models for GetMCPServerThreats
# --------------------

class GetMCPServerThreatsRequest(AIDefenseModel):
    """Request message for getting MCP server threats.

    Args:
        server_id: ID of the MCP server.
        capability_type: Filter by capability type.
        threat_severity: Filter by threat severity levels.
        limit: Maximum number of results to return.
        offset: Offset for pagination.
    """
    server_id: str = Field(..., description="MCP server identifier (UUID)")
    capability_type: Optional[CapabilityType] = Field(None, description="Filter by capability type")
    threat_severity: List[str] = Field(default_factory=list, description="Filter by severity levels")
    limit: int = Field(default=25, description="Maximum results to return")
    offset: int = Field(default=0, description="Pagination offset")


class GetMCPServerThreatsResponse(AIDefenseModel):
    """Response message for getting MCP server threats.

    Args:
        threats: List of capability threats.
        paging: Pagination information.
    """
    threats: List[MCPServerCapabilityThreats] = Field(default_factory=list, description="List of threats")
    paging: Optional[Paging] = Field(None, description="Pagination info")

    @model_validator(mode='before')
    @classmethod
    def unwrap_threats(cls, values):
        """Unwrap threats from nested structure: {threats: {items: [...]}}"""
        threats = values.get("threats")
        if isinstance(threats, dict) and "items" in threats:
            values["threats"] = threats["items"]
        return values


# --------------------
# Request/Response Models for GetMCPServerScanSummary
# --------------------

class GetMCPServerScanSummaryRequest(AIDefenseModel):
    """Request message for getting MCP server scan summary.

    Args:
        server_id: ID of the MCP server.
    """
    server_id: str = Field(..., description="MCP server identifier (UUID)")


class GetMCPServerScanSummaryResponse(AIDefenseModel):
    """Response message for getting MCP server scan summary.

    Args:
        capability_summary: Summary of capabilities.
        scan_threat_summary: Summary of threats.
        completed_at: Timestamp of scan completion.
    """
    capability_summary: Optional[CapabilitySummary] = Field(None, alias="capabilitySummary", description="Capability summary")
    scan_threat_summary: Optional[ScanThreatSummary] = Field(None, alias="scanThreatSummary", description="Threat summary")
    completed_at: Optional[datetime] = Field(None, alias="completedAt", description="Scan completion timestamp")


# --------------------
# Server Input Models for Unregistered MCP Server Scanning
# --------------------

class RemoteServerInput(AIDefenseModel):
    """Input configuration for remote URL-based MCP servers.

    Used when scanning a remote MCP server accessible via URL (SSE or Streamable HTTP).

    Args:
        url: URL endpoint of the MCP server (valid URI).
        connection_type: Transport type for connecting to the server (SSE or STREAMABLE).
    """
    url: str = Field(..., description="URL endpoint of the MCP server")
    connection_type: TransportType = Field(
        ...,
        description="Transport type for server connection (SSE or STREAMABLE)"
    )


class StdioServerInput(AIDefenseModel):
    """Input configuration for stdio-based MCP servers.

    Used when scanning a stdio-based MCP server spawned from packages/repos.
    This is a placeholder - fields will be defined when implementing stdio/repo-based server scanning.
    """
    pass


# --------------------
# Request/Response Models for StartMCPServerScan
# --------------------

class StartMCPServerScanRequest(AIDefenseModel):
    """Request message for starting an MCP server scan without registration.

    This request allows scanning an MCP server without first registering it
    in the system. Useful for one-time scans or testing purposes.

    The request uses a server_type enum to specify whether to scan a remote
    URL-based server or a stdio-based server. Based on the server_type,
    provide either 'remote' or 'stdio' input configuration.

    Args:
        name: Human-readable name for the MCP server (1-128 characters).
        server_type: Type of server to scan (REMOTE or STDIO).
        remote: Configuration for remote URL-based servers (when server_type is REMOTE).
        stdio: Configuration for stdio-based servers (when server_type is STDIO).
        auth_config: Optional authentication configuration for the server.

    Example:
        ```python
        # Scan a remote MCP server
        request = StartMCPServerScanRequest(
            name="My MCP Server",
            server_type=ServerType.REMOTE,
            remote=RemoteServerInput(
                url="https://mcp-server.example.com/sse",
                connection_type=TransportType.SSE
            ),
            auth_config=AuthConfig(auth_type=AuthType.NO_AUTH)
        )
        ```
    """
    name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Human-readable name for the MCP server"
    )
    server_type: ServerType = Field(
        ...,
        description="Type of server to scan (REMOTE or STDIO)"
    )
    remote: Optional[RemoteServerInput] = Field(
        None,
        description="Configuration for remote URL-based servers"
    )
    stdio: Optional[StdioServerInput] = Field(
        None,
        description="Configuration for stdio-based servers (placeholder)"
    )
    auth_config: Optional[AuthConfig] = Field(
        None,
        description="Authentication configuration"
    )

    @model_validator(mode='after')
    def _validate_server_input(self):
        if self.server_type == ServerType.REMOTE and self.remote is None:
            raise ValueError("Remote configuration is required when server_type is REMOTE")
        if self.server_type == ServerType.STDIO and self.stdio is None:
            raise ValueError("Stdio configuration is required when server_type is STDIO")

        return self


class StartMCPServerScanResponse(AIDefenseModel):
    """Response message for starting an MCP server scan.

    Args:
        scan_id: Unique identifier for the scan (UUID string).
    """
    scan_id: str = Field(..., description="Unique scan identifier (UUID)")


# --------------------
# Scan Result Models
# --------------------

class CapabilityScanResult(AIDefenseModel):
    """Scan result for a single capability.

    Args:
        capability_id: Unique identifier for the capability.
        capability_name: Name of the capability.
        capability_description: Description of the capability.
        status: Scan status for this capability.
        is_safe: Whether the capability is considered safe.
        analyzer_type: Analyzer that generated this result.
        severity: Severity level for this analyzer.
        threat_names: List of threat names detected.
        threat_summary: Summary of threats found.
        total_findings: Total number of findings.
        technique_id: Technique ID (e.g., AITech-9.1).
        technique_name: Technique name.
        threats: List of detailed threat information.
    """
    capability_id: str = Field(default="", alias="capabilityId", description="Capability identifier")
    capability_name: str = Field(..., alias="capabilityName", description="Capability name")
    capability_description: str = Field(default="", alias="capabilityDescription", description="Capability description")
    status: CapabilityScanStatus = Field(..., description="Scan status")
    is_safe: bool = Field(..., alias="isSafe", description="Whether capability is safe")
    analyzer_type: AnalyzerType = Field(..., alias="analyzerType", description="Analyzer type")
    severity: str = Field(..., description="Severity level")
    threat_names: List[str] = Field(default_factory=list, alias="threatNames", description="Detected threat names")
    threat_summary: str = Field(default="", alias="threatSummary", description="Threat summary")
    total_findings: int = Field(default=0, alias="totalFindings", description="Total findings count")
    technique_id: str = Field(default="", alias="techniqueId", description="Technique ID")
    technique_name: str = Field(default="", alias="techniqueName", description="Technique name")
    threats: List[ThreatSubTechnique] = Field(default_factory=list, description="Detailed threat information")

    @model_validator(mode='before')
    @classmethod
    def __restore_enums(cls, values):
        return restore_enum_wrapper(cls, values)


class CapabilityScanResults(AIDefenseModel):
    """List of capability scan results.

    Args:
        items: List of individual capability scan results.
    """
    items: List[CapabilityScanResult] = Field(
        default_factory=list,
        description="List of capability scan results"
    )


class MCPCapabilityScanResults(AIDefenseModel):
    """Scan results organized by capability type.

    Args:
        tool_results: Map of capability ID to list of scan results for tools.
    """
    tool_results: Dict[str, CapabilityScanResults] = Field(
        default_factory=dict,
        alias="toolResults",
        description="Map of capability ID to scan results"
    )


class MCPScanResult(AIDefenseModel):
    """Complete scan result for an MCP server.

    Args:
        is_safe: Whether the overall scan result is safe.
        capabilities: Detailed scan results by capability.
    """
    is_safe: bool = Field(..., description="Overall safety status")
    capabilities: Optional[MCPCapabilityScanResults] = Field(
        None,
        description="Capability scan results"
    )


# --------------------
# Request/Response Models for GetMCPScanStatus
# --------------------

class GetMCPScanStatusRequest(AIDefenseModel):
    """Request message for getting MCP scan status.

    Args:
        scan_id: Unique identifier for the scan to query.
    """
    scan_id: str = Field(..., description="Scan identifier (UUID)")


class ErrorInfo(AIDefenseModel):
    """Error information for failed scans.

    Args:
        message: Human-readable summary of what went wrong.
        error_message: Raw error message (may not be exposed to end users).
        remediation_tips: List of remediation steps or tips to resolve the issue.
        occurred_at: Timestamp when the error occurred.
    """
    message: str = Field(..., min_length=1, max_length=32768, description="Human-readable error summary")
    error_message: Optional[str] = Field(None, max_length=32768, description="Raw error message")
    remediation_tips: List[str] = Field(default_factory=list, description="Remediation steps or tips")
    occurred_at: Optional[datetime] = Field(None, description="When the error occurred")


class GetMCPScanStatusResponse(AIDefenseModel):
    """Response message for MCP scan status.

    Contains complete information about the scan including its current status,
    timestamps, and results if the scan has completed.

    Args:
        name: Name of the MCP server being scanned.
        scan_id: Unique identifier for the scan.
        status: Current status of the scan.
        created_at: Timestamp when the scan was created.
        completed_at: Timestamp when the scan completed (if applicable).
        expires_at: Timestamp when the scan results will expire.
        result: Scan results (available when status is COMPLETED).
        error_info: Error information if the scan failed.
    """
    name: str = Field(..., min_length=1, max_length=128, description="MCP server name")
    scan_id: str = Field(..., description="Scan identifier (UUID)")
    status: MCPScanStatus = Field(..., description="Current scan status")
    created_at: datetime = Field(..., description="Scan creation timestamp")
    completed_at: Optional[datetime] = Field(None, description="Scan completion timestamp")
    expires_at: Optional[datetime] = Field(None, description="Result expiration timestamp")
    result: Optional[MCPScanResult] = Field(None, description="Scan results")
    error_info: Optional[ErrorInfo] = Field(None, description="Error information if failed")

    @model_validator(mode='before')
    @classmethod
    def __restore_enums(cls, values):
        return restore_enum_wrapper(cls, values)


# --------------------
# Resource Connection Enums
# --------------------

class ResourceConnectionStatus(str, Enum):
    """Status of a resource connection."""
    UNSPECIFIED = "ConnectionStatusUnspecified"
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    PENDING = "Pending"
    CONNECTED = "Connected"


class ResourceConnectionType(str, Enum):
    """Type of resource connection."""
    UNSPECIFIED = "Unspecified"
    CONNECTION_TYPE_UNSPECIFIED = "ConnectionTypeUnspecified"
    API = "API"
    GATEWAY = "Gateway"
    MCP_GATEWAY = "MCPGateway"


class ResourceType(str, Enum):
    """Type of resource."""
    UNSPECIFIED = "ResourceTypeUnspecified"
    MCP_SERVER = "MCP_SERVER"


class ResourceConnectionSortBy(str, Enum):
    """Sort options for resource connection list operations."""
    UNSPECIFIED = "ConnectionSortBy_Unspecified"
    CONNECTION_NAME = "connection_name"
    STATUS = "status"
    LAST_ACTIVE = "last_active"


class SortOrder(str, Enum):
    """Sort order for list operations."""
    UNSPECIFIED = "SortOrder_Unspecified"
    ASC = "asc"
    DESC = "desc"


# --------------------
# Resource Connection Models
# --------------------

class Identity(AIDefenseModel):
    """Identity information for a resource connection.

    Args:
        identity_id: Unique identifier for the identity.
        identity_name: Name of the identity.
    """
    identity_id: Optional[str] = Field(None, description="Identity identifier")
    identity_name: Optional[str] = Field(None, description="Identity name")


class ResourceDetails(AIDefenseModel):
    """Details about a resource.

    Args:
        resource_id: Unique identifier for the resource.
        resource_name: Name of the resource.
        resource_type: Type of the resource.
        resource_url: URL of the resource.
    """
    resource_id: str = Field(..., description="Resource identifier (UUID)")
    resource_name: str = Field(default="", description="Resource name")
    resource_type: ResourceType = Field(default=ResourceType.UNSPECIFIED, description="Resource type")
    resource_url: str = Field(default="", description="Resource URL")

    @model_validator(mode='before')
    @classmethod
    def __restore_enums(cls, values):
        return restore_enum_wrapper(cls, values)


class PolicyInfo(AIDefenseModel):
    """Policy information associated with a connection.

    Args:
        policy_id: Unique identifier for the policy.
        policy_name: Name of the policy.
    """
    policy_id: str = Field(..., description="Policy identifier (UUID)")
    policy_name: str = Field(default="", description="Policy name")


class PoliciesList(AIDefenseModel):
    """List of policies.

    Args:
        items: List of policy information objects.
    """
    items: List[PolicyInfo] = Field(default_factory=list, description="List of policies")


class ResourceInfo(AIDefenseModel):
    """Resource information.

    Args:
        resource_id: Unique identifier for the resource.
        resource_name: Name of the resource.
        resource_type: Type of the resource.
        resource_url: URL of the resource.
    """
    resource_id: str = Field(..., description="Resource identifier (UUID)")
    resource_name: str = Field(default="", description="Resource name")
    resource_type: ResourceType = Field(default=ResourceType.UNSPECIFIED, description="Resource type")
    resource_url: str = Field(default="", description="Resource URL")

    @model_validator(mode='before')
    @classmethod
    def __restore_enums(cls, values):
        return restore_enum_wrapper(cls, values)


class ResourcesList(AIDefenseModel):
    """List of resources.

    Args:
        items: List of resource information objects.
    """
    items: List[ResourceInfo] = Field(default_factory=list, description="List of resources")


class ResourceConnection(AIDefenseModel):
    """Resource connection details.

    Args:
        connection_id: Unique identifier for the connection.
        connection_name: Name of the connection.
        resource_id: ID of the associated resource.
        connection_status: Status of the connection.
        created_at: Timestamp when the connection was created.
        last_active: Timestamp when the connection was last active.
        updated_at: Timestamp when the connection was last updated.
        identity: Identity information.
        resource_details: Details about the associated resource.
        policies: List of associated policies.
        proxy_url: Proxy URL for the connection.
        connection_type: Type of the connection.
        resources: List of associated resources.
    """
    connection_id: str = Field(..., alias="connectionId", description="Connection identifier (UUID)")
    connection_name: str = Field(default="", alias="connectionName", description="Connection name")
    resource_id: str = Field(default="", alias="resourceId", description="Resource identifier (UUID)")
    connection_status: ResourceConnectionStatus = Field(
        default=ResourceConnectionStatus.UNSPECIFIED,
        alias="connectionStatus",
        description="Connection status"
    )
    created_at: Optional[datetime] = Field(None, alias="createdAt", description="Creation timestamp")
    last_active: Optional[datetime] = Field(None, alias="lastActive", description="Last active timestamp")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt", description="Last update timestamp")
    identity: Optional[Identity] = Field(None, description="Identity information")
    resource_details: Optional[ResourceDetails] = Field(None, alias="resourceDetails", description="Resource details")
    policies: Optional[PoliciesList] = Field(None, description="Associated policies")
    proxy_url: str = Field(default="", alias="proxyUrl", description="Proxy URL")
    connection_type: ResourceConnectionType = Field(
        default=ResourceConnectionType.UNSPECIFIED,
        alias="connectionType",
        description="Connection type"
    )
    resources: Optional[ResourcesList] = Field(None, description="Associated resources")

    @model_validator(mode='before')
    @classmethod
    def __restore_enums(cls, values):
        return restore_enum_wrapper(cls, values)


class ResourceConnections(AIDefenseModel):
    """List of resource connections with pagination.

    Args:
        items: List of resource connections.
        paging: Pagination information.
    """
    items: List[ResourceConnection] = Field(default_factory=list, alias="connections", description="List of connections")
    paging: Optional[Paging] = Field(None, description="Pagination information")


# --------------------
# Resource Connection Request/Response Models
# --------------------

class CreateResourceConnectionRequest(AIDefenseModel):
    """Request to create a new resource connection.

    Args:
        resource_id: ID of the resource to associate (deprecated, use resource_ids).
        connection_name: Name for the connection.
        connection_type: Type of connection.
        resource_ids: List of resource IDs to associate with this connection.
    """
    resource_id: Optional[str] = Field(None, description="Resource identifier (UUID) - deprecated")
    connection_name: str = Field(..., min_length=1, description="Connection name")
    connection_type: ResourceConnectionType = Field(..., description="Connection type")
    resource_ids: List[str] = Field(default_factory=list, description="List of resource IDs")


class CreateResourceConnectionResponse(AIDefenseModel):
    """Response for creating a resource connection.

    Args:
        connection_id: ID of the created connection.
    """
    connection_id: str = Field(..., description="Created connection identifier (UUID)")


class DeleteResourceConnectionByIDResponse(AIDefenseModel):
    """Response for deleting a resource connection by ID.

    This is an empty response indicating successful deletion.
    """
    pass


class DeleteResourceConnectionsByResourceIdResponse(AIDefenseModel):
    """Response for deleting resource connections by resource ID.

    This is an empty response indicating successful deletion.
    """
    pass


class GetResourceConnectionByIDResponse(AIDefenseModel):
    """Response for getting a resource connection by ID.

    Args:
        connection: The resource connection details.
    """
    connection: Optional[ResourceConnection] = Field(None, description="Connection details")


class GetResourceConnectionByResourceIDResponse(AIDefenseModel):
    """Response for getting resource connections by resource ID.

    Args:
        connections: List of resource connections.
    """
    connections: Optional[ResourceConnections] = Field(None, description="Resource connections")


class MCPServerFilters(AIDefenseModel):
    """Filters specific to MCP servers.

    Args:
        server_name_substr: List of server name substrings to filter by.
    """
    server_name_substr: List[str] = Field(default_factory=list, description="Server name substrings")


class ResourceTypeSpecificFilters(AIDefenseModel):
    """Resource type specific filters.

    Args:
        mcp_server: MCP server specific filters.
    """
    mcp_server: Optional[MCPServerFilters] = Field(None, description="MCP server filters")


class FilterResourceConnectionsRequest(AIDefenseModel):
    """Request to filter resource connections.

    Args:
        limit: Maximum number of results to return.
        offset: Number of results to skip.
        resource_ids: Filter by resource IDs.
        policy_ids: Filter by policy IDs.
        connection_type: Filter by connection type.
        connection_status: Filter by connection status.
        policy_applied: Filter by policy assignment status.
        connection_name: Search by connection name.
        sort_by: Field to sort by.
        order: Sort order.
    """
    limit: int = Field(default=25, description="Maximum results to return")
    offset: int = Field(default=0, description="Pagination offset")
    resource_ids: List[str] = Field(default_factory=list, description="Filter by resource IDs")
    policy_ids: List[str] = Field(default_factory=list, description="Filter by policy IDs")
    connection_type: Optional[ResourceConnectionType] = Field(None, description="Filter by connection type")
    connection_status: Optional[ResourceConnectionStatus] = Field(None, description="Filter by connection status")
    policy_applied: Optional[bool] = Field(None, description="Filter by policy assignment")
    connection_name: Optional[str] = Field(None, description="Search by connection name")
    sort_by: Optional[ResourceConnectionSortBy] = Field(None, description="Sort by field")
    order: Optional[SortOrder] = Field(None, description="Sort order")


class FilterResourceConnectionsResponse(AIDefenseModel):
    """Response for filtering resource connections.

    Args:
        connections: Filtered resource connections with pagination.
    """
    connections: Optional[ResourceConnections] = Field(None, description="Filtered connections")


class FilterResourcesByConnectionIDRequest(AIDefenseModel):
    """Request to filter resources by connection ID.

    Args:
        limit: Maximum number of results to return.
        offset: Number of results to skip.
        resource_type: Filter by resource type.
        connection_id: Connection ID to filter by.
        resource_type_specific_filters: Resource type specific filters.
    """
    limit: int = Field(default=25, description="Maximum results to return")
    offset: int = Field(default=0, description="Pagination offset")
    resource_type: ResourceType = Field(..., description="Resource type")
    connection_id: str = Field(..., description="Connection identifier (UUID)")
    resource_type_specific_filters: Optional[ResourceTypeSpecificFilters] = Field(
        None, description="Resource type specific filters"
    )


class FilterResourcesByConnectionIDResponse(AIDefenseModel):
    """Response for filtering resources by connection ID.

    Args:
        resources: List of resources.
        paging: Pagination information.
    """
    resources: List[ResourceInfo] = Field(default_factory=list, description="List of resources")
    paging: Optional[Paging] = Field(None, description="Pagination information")


class AddOrUpdateResourceConnectionsRequest(AIDefenseModel):
    """Request to add or update resource connections.

    Args:
        connection_id: Connection ID to update.
        associate_resource_ids: List of resource IDs to associate.
        disassociate_resource_ids: List of resource IDs to disassociate.
        resource_type: Resource type.
    """
    connection_id: str = Field(..., description="Connection identifier (UUID)")
    associate_resource_ids: List[str] = Field(default_factory=list, description="Resource IDs to associate")
    disassociate_resource_ids: List[str] = Field(default_factory=list, description="Resource IDs to disassociate")
    resource_type: ResourceType = Field(..., description="Resource type")


class AddOrUpdateResourceConnectionsResponse(AIDefenseModel):
    """Response for adding or updating resource connections.

    This is an empty response indicating successful operation.
    """
    pass


# --------------------
# MCP Server Models
# --------------------

class MCPServer(AIDefenseModel):
    """MCP Server details.

    Represents a registered MCP server with all its configuration and status information.

    Args:
        id: Unique identifier for the MCP server (UUID).
        name: Human-readable name for the MCP server.
        url: URL endpoint of the MCP server.
        description: Description of the MCP server.
        connection_type: Transport type for connecting to the server.
        created_at: Timestamp when the server was registered.
        onboarding_status: Current onboarding status of the server.
        scan_enabled: Whether scanning is enabled for this server.
        auth_type: Authentication type used by the server.
        status_info: Error information if the server has issues.
        auth_config: Authentication configuration for the server.
    """
    id: str = Field(..., description="MCP server identifier (UUID)")
    name: str = Field(..., description="MCP server name")
    url: str = Field(..., description="MCP server URL endpoint")
    description: str = Field(default="", description="MCP server description")
    connection_type: TransportType = Field(..., alias="connectionType", description="Transport type for server connection")
    created_at: Optional[datetime] = Field(None, alias="createdAt", description="Registration timestamp")
    onboarding_status: OnboardingStatus = Field(
        default=OnboardingStatus.ONBOARDING_STATUS_UNSPECIFIED,
        alias="onboardingStatus",
        description="Onboarding status"
    )
    scan_enabled: bool = Field(default=True, alias="scanEnabled", description="Whether scanning is enabled")
    scan_periodically: bool = Field(default=False, alias="scanPeriodically", description="Whether periodic scanning is enabled")
    auth_type: AuthType = Field(default=AuthType.NO_AUTH, alias="authType", description="Authentication type")
    status_info: Optional[ErrorInfo] = Field(None, alias="statusInfo", description="Error information if any")
    auth_config: Optional[AuthConfig] = Field(None, alias="authConfig", description="Authentication configuration")

    @model_validator(mode='before')
    @classmethod
    def __restore_enums(cls, values):
        return restore_enum_wrapper(cls, values)


class MCPServers(AIDefenseModel):
    """List of MCP servers with pagination.

    Args:
        items: List of MCP server objects.
        paging: Pagination information.
    """
    items: List[MCPServer] = Field(default_factory=list, description="List of MCP servers")
    paging: Optional[Paging] = Field(None, description="Pagination information")


# --------------------
# GetMCPServer Request/Response Models
# --------------------

class GetMCPServerRequest(AIDefenseModel):
    """Request message for getting an MCP server by ID.

    Args:
        id: Unique identifier of the MCP server to retrieve (UUID).
    """
    id: str = Field(..., description="MCP server identifier (UUID)")


class GetMCPServerResponse(AIDefenseModel):
    """Response message for getting an MCP server.

    Args:
        mcp_server: The requested MCP server details.
    """
    mcp_server: Optional[MCPServer] = Field(None, alias="mcpServer", description="MCP server details")


# --------------------
# ListMCPServers Request/Response Models
# --------------------

class ListMCPServersRequest(AIDefenseModel):
    """Request message for listing MCP servers.

    Args:
        limit: Maximum number of servers to return.
        offset: Offset for pagination.
        server_name_substr: Filter by server name substring match.
        onboarding_status: Filter by onboarding status(es).
        transport_type: Filter by transport type(s).
        severity: Filter by severity level(s).
        creation_date: Filter by creation date.
    """
    limit: int = Field(default=25, description="Maximum results to return")
    offset: int = Field(default=0, description="Pagination offset")
    server_name_substr: Optional[str] = Field(None, description="Filter by server name substring")
    onboarding_status: Optional[List[OnboardingStatus]] = Field(None, description="Filter by onboarding status")
    transport_type: Optional[List[TransportType]] = Field(None, description="Filter by transport type")
    severity: Optional[List[SeverityLevel]] = Field(None, description="Filter by severity level")
    creation_date: Optional[datetime] = Field(None, description="Filter by creation date")


class ListMCPServersResponse(AIDefenseModel):
    """Response message for listing MCP servers.

    Args:
        mcp_servers: List of MCP servers with pagination information.
    """
    mcp_servers: Optional[MCPServers] = Field(None, alias="mcpServers", description="MCP servers list")


# --------------------
# UpdateAuthConfig Request/Response Models
# --------------------

class UpdateAuthConfigRequest(AIDefenseModel):
    """Request message for updating MCP server authentication configuration.

    Args:
        server_id: ID of the MCP server to update (UUID).
        auth_config: New authentication configuration.
    """
    server_id: str = Field(..., description="MCP server identifier (UUID)")
    auth_config: AuthConfig = Field(..., description="New authentication configuration")


class UpdateAuthConfigResponse(AIDefenseModel):
    """Response message for updating MCP server authentication configuration.

    Args:
        server_id: ID of the updated MCP server (UUID).
    """
    server_id: str = Field(..., alias="serverId", description="Updated MCP server identifier (UUID)")


# --------------------
# MCP Registry Enums
# --------------------

class RegistryAuthType(str, Enum):
    """Authentication type for MCP registry."""
    AUTH_TYPE_UNSPECIFIED = "AUTH_TYPE_UNSPECIFIED"
    AUTH_TYPE_NONE = "AUTH_TYPE_NONE"
    AUTH_TYPE_OAUTH2 = "AUTH_TYPE_OAUTH2"
    AUTH_TYPE_API_KEY = "AUTH_TYPE_API_KEY"
    AUTH_TYPE_BASIC = "AUTH_TYPE_BASIC"


class RegistryStatus(str, Enum):
    """Status of an MCP registry."""
    REGISTRY_STATUS_UNSPECIFIED = "REGISTRY_STATUS_UNSPECIFIED"
    REGISTRY_STATUS_CONNECTED = "REGISTRY_STATUS_CONNECTED"
    REGISTRY_STATUS_PENDING = "REGISTRY_STATUS_PENDING"
    REGISTRY_STATUS_FETCHING_DATA = "REGISTRY_STATUS_FETCHING_DATA"
    REGISTRY_STATUS_SERVERS_FETCHED = "REGISTRY_STATUS_SERVERS_FETCHED"


# --------------------
# MCP Registry Models
# --------------------

class MCPRegistry(AIDefenseModel):
    """MCP Registry details.

    Represents a registered MCP registry with its configuration and status.

    Args:
        id: Unique identifier for the MCP registry (UUID).
        name: Human-readable name for the MCP registry.
        url: URL endpoint of the MCP registry.
        auth_type: Authentication type used by the registry.
        status: Current status of the registry.
        created_at: Timestamp when the registry was created.
        updated_at: Timestamp when the registry was last updated.
    """
    id: str = Field(..., description="MCP registry identifier (UUID)")
    name: str = Field(..., description="MCP registry name")
    url: str = Field(..., description="MCP registry URL endpoint")
    auth_type: RegistryAuthType = Field(
        default=RegistryAuthType.AUTH_TYPE_UNSPECIFIED,
        alias="authType",
        description="Authentication type"
    )
    status: RegistryStatus = Field(
        default=RegistryStatus.REGISTRY_STATUS_UNSPECIFIED,
        description="Registry status"
    )
    created_at: Optional[datetime] = Field(None, alias="createdAt", description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt", description="Last update timestamp")

    @model_validator(mode='before')
    @classmethod
    def __restore_enums(cls, values):
        return restore_enum_wrapper(cls, values)


class MCPRegistries(AIDefenseModel):
    """List of MCP registries with pagination.

    Args:
        items: List of MCP registry objects.
        paging: Pagination information.
    """
    items: List[MCPRegistry] = Field(default_factory=list, alias="registries", description="List of MCP registries")
    paging: Optional[Paging] = Field(None, description="Pagination information")


class MCPRegistryServerRepository(AIDefenseModel):
    """Repository information for an MCP server from registry.

    Args:
        url: Repository URL.
        source: Source of the repository.
    """
    url: str = Field(default="", description="Repository URL")
    source: str = Field(default="", description="Repository source")


class MCPRegistryServerTransport(AIDefenseModel):
    """Transport information for an MCP server package.

    Args:
        type: Transport type.
    """
    type: str = Field(default="", description="Transport type")


class MCPRegistryServerEnvironmentVariable(AIDefenseModel):
    """Environment variable for an MCP server package.

    Args:
        name: Name of the environment variable.
        description: Description of the environment variable.
        format: Format of the environment variable value.
        is_secret: Whether the variable contains secret data.
    """
    name: str = Field(..., description="Environment variable name")
    description: str = Field(default="", description="Environment variable description")
    format: str = Field(default="", description="Value format")
    is_secret: bool = Field(default=False, alias="isSecret", description="Whether this is a secret")


class MCPRegistryServerPackage(AIDefenseModel):
    """Package information for an MCP server from registry.

    Args:
        registry_type: Type of package registry.
        identifier: Package identifier.
        transport: Transport configuration.
        environment_variables: List of environment variables.
    """
    registry_type: str = Field(default="", alias="registryType", description="Package registry type")
    identifier: str = Field(default="", description="Package identifier")
    transport: Optional[MCPRegistryServerTransport] = Field(None, description="Transport configuration")
    environment_variables: List[MCPRegistryServerEnvironmentVariable] = Field(
        default_factory=list,
        alias="environmentVariables",
        description="Environment variables"
    )


class MCPRegistryServerRemote(AIDefenseModel):
    """Remote endpoint information for an MCP server.

    Args:
        type: Type of remote endpoint.
        url: URL of the remote endpoint.
    """
    type: str = Field(default="", description="Remote type")
    url: str = Field(default="", description="Remote URL")


class MCPRegistryServerMeta(AIDefenseModel):
    """Metadata for an MCP server from registry.

    Args:
        status: Server status.
        published_at: Publication timestamp.
        updated_at: Last update timestamp.
        is_latest: Whether this is the latest version.
        last_updated_in_registry: Last update in registry timestamp.
        created_at: Creation timestamp.
    """
    status: str = Field(default="", description="Server status")
    published_at: Optional[datetime] = Field(None, alias="publishedAt", description="Publication timestamp")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt", description="Last update timestamp")
    is_latest: bool = Field(default=False, alias="isLatest", description="Whether this is latest version")
    last_updated_in_registry: Optional[datetime] = Field(
        None,
        alias="lastUpdatedInRegistry",
        description="Last registry update timestamp"
    )
    created_at: Optional[datetime] = Field(None, alias="createdAt", description="Creation timestamp")


class MCPRegistryServer(AIDefenseModel):
    """MCP server information from registry.

    Args:
        schema_uri: Schema URI reference.
        name: Server name.
        description: Server description.
        repository: Repository information.
        version: Server version.
        packages: List of packages.
        remotes: List of remote endpoints.
        author: Server author.
        transport_types: List of supported transport types.
        server_schema: Server schema.
        is_latest: Whether this is the latest version.
        last_updated_in_registry: Last update in registry timestamp.
        published_at: Publication timestamp.
        status: Server status.
        created_at: Creation timestamp.
        auth_type: Authentication type.
    """
    schema_uri: str = Field(default="", alias="$schema", description="Schema URI")
    name: str = Field(..., description="Server name")
    description: str = Field(default="", description="Server description")
    repository: Optional[MCPRegistryServerRepository] = Field(None, description="Repository information")
    version: str = Field(default="", description="Server version")
    packages: List[MCPRegistryServerPackage] = Field(default_factory=list, description="Server packages")
    remotes: List[MCPRegistryServerRemote] = Field(default_factory=list, description="Remote endpoints")
    author: str = Field(default="", description="Server author")
    transport_types: List[str] = Field(default_factory=list, alias="transportTypes", description="Transport types")
    server_schema: str = Field(default="", alias="serverSchema", description="Server schema")
    is_latest: bool = Field(default=False, alias="isLatest", description="Whether this is latest version")
    last_updated_in_registry: Optional[datetime] = Field(
        None,
        alias="lastUpdatedInRegistry",
        description="Last registry update timestamp"
    )
    published_at: Optional[datetime] = Field(None, alias="publishedAt", description="Publication timestamp")
    status: str = Field(default="", description="Server status")
    created_at: Optional[datetime] = Field(None, alias="createdAt", description="Creation timestamp")
    auth_type: RegistryAuthType = Field(
        default=RegistryAuthType.AUTH_TYPE_UNSPECIFIED,
        alias="authType",
        description="Authentication type"
    )

    @model_validator(mode='before')
    @classmethod
    def __restore_enums(cls, values):
        return restore_enum_wrapper(cls, values)


class MCPRegistryServerChange(AIDefenseModel):
    """Change information for an MCP server from registry.

    Args:
        field: Changed field name.
        previous: Previous value.
        current: Current value.
    """
    field: str = Field(..., description="Changed field name")
    previous: str = Field(default="", description="Previous value")
    current: str = Field(default="", description="Current value")


class MCPRegistryServerDelta(AIDefenseModel):
    """Delta information showing changes for an MCP server.

    Args:
        has_changes: Whether there are changes.
        changes: List of changes.
        registered_snapshot: Snapshot of the registered server.
    """
    has_changes: bool = Field(default=False, alias="hasChanges", description="Whether there are changes")
    changes: List[MCPRegistryServerChange] = Field(default_factory=list, description="List of changes")
    registered_snapshot: Optional[MCPRegistryServer] = Field(
        None,
        alias="registeredSnapshot",
        description="Registered server snapshot"
    )


class MCPServerFromRegistry(AIDefenseModel):
    """MCP server information retrieved from a registry.

    Args:
        server: Server information.
        meta: Server metadata by version.
        delta: Delta information showing changes.
        server_id: Server ID.
        author: Server author.
        transport_types: Supported transport types.
        server_schema: Server schema.
        is_latest: Whether this is the latest version.
        last_updated_in_registry: Last update in registry timestamp.
        published_at: Publication timestamp.
        status: Server status.
        created_at: Creation timestamp.
        auth_type: Authentication type.
    """
    server: Optional[MCPRegistryServer] = Field(None, description="Server information")
    meta: Dict[str, MCPRegistryServerMeta] = Field(default_factory=dict, alias="_meta", description="Server metadata")
    delta: Optional[MCPRegistryServerDelta] = Field(None, description="Delta information")
    server_id: str = Field(default="", alias="serverId", description="Server identifier")
    author: str = Field(default="", description="Server author")
    transport_types: List[str] = Field(default_factory=list, alias="transportTypes", description="Transport types")
    server_schema: str = Field(default="", alias="serverSchema", description="Server schema")
    is_latest: bool = Field(default=False, alias="isLatest", description="Whether this is latest version")
    last_updated_in_registry: Optional[datetime] = Field(
        None,
        alias="lastUpdatedInRegistry",
        description="Last registry update timestamp"
    )
    published_at: Optional[datetime] = Field(None, alias="publishedAt", description="Publication timestamp")
    status: str = Field(default="", description="Server status")
    created_at: Optional[datetime] = Field(None, alias="createdAt", description="Creation timestamp")
    auth_type: RegistryAuthType = Field(
        default=RegistryAuthType.AUTH_TYPE_UNSPECIFIED,
        alias="authType",
        description="Authentication type"
    )

    @model_validator(mode='before')
    @classmethod
    def __restore_enums(cls, values):
        return restore_enum_wrapper(cls, values)


class MCPServersFromRegistry(AIDefenseModel):
    """List of MCP servers from registry with pagination.

    Args:
        items: List of MCP servers from registry.
        paging: Pagination information.
    """
    items: List[MCPServerFromRegistry] = Field(default_factory=list, description="List of MCP servers")
    paging: Optional[Paging] = Field(None, description="Pagination information")


class MCPRegistryFilters(AIDefenseModel):
    """Available filters for MCP registry servers.

    Args:
        authors: List of available authors.
        source_types: List of available source types.
        versions: List of available versions.
        has_latest: Whether latest versions are available.
    """
    authors: List[str] = Field(default_factory=list, description="Available authors")
    source_types: List[str] = Field(default_factory=list, alias="sourceTypes", description="Available source types")
    versions: List[str] = Field(default_factory=list, description="Available versions")
    has_latest: bool = Field(default=False, alias="hasLatest", description="Whether latest versions available")


# --------------------
# MCP Registry Auth Config Models
# --------------------

class RegistryOAuthConfig(AIDefenseModel):
    """OAuth configuration for MCP registry authentication.

    Args:
        client_id: OAuth client identifier.
        client_secret: OAuth client secret.
        auth_server_url: URL of the OAuth authorization server.
        scope: Optional OAuth scope.
    """
    client_id: str = Field(..., alias="clientId", description="OAuth client identifier")
    client_secret: str = Field(default="", alias="clientSecret", description="OAuth client secret")
    auth_server_url: str = Field(..., alias="authServerUrl", description="OAuth authorization server URL")
    scope: Optional[str] = Field(None, description="OAuth scope")


class RegistryApiKeyConfig(AIDefenseModel):
    """API key configuration for MCP registry authentication.

    Args:
        header_name: HTTP header name to use for the API key.
        api_key: The API key value.
    """
    header_name: str = Field(..., alias="headerName", description="HTTP header name for API key")
    api_key: str = Field(..., alias="apiKey", description="API key value")


class RegistryBasicAuthConfig(AIDefenseModel):
    """Basic authentication configuration for MCP registry.

    Args:
        username: Username for basic auth.
        password: Password for basic auth.
    """
    username: str = Field(..., description="Basic auth username")
    password: str = Field(..., description="Basic auth password")


class RegistryAuthConfig(AIDefenseModel):
    """Authentication configuration container for MCP registries.

    Only one of the supported authentication types should be set at a time.

    Args:
        oauth: OAuth configuration settings.
        api_key: API key configuration settings.
        basic: Basic authentication settings.
    """
    oauth: Optional[RegistryOAuthConfig] = Field(None, description="OAuth configuration")
    api_key: Optional[RegistryApiKeyConfig] = Field(None, alias="apiKey", description="API key configuration")
    basic: Optional[RegistryBasicAuthConfig] = Field(None, description="Basic auth configuration")


# --------------------
# MCP Registry Request/Response Models
# --------------------

class CreateMCPRegistryRequest(AIDefenseModel):
    """Request message for creating an MCP registry.

    Args:
        name: Human-readable name for the MCP registry.
        url: URL endpoint of the MCP registry.
        auth_type: Authentication type for the registry.
        auth_config: Optional authentication configuration.
    """
    name: str = Field(..., min_length=1, description="Human-readable name for the MCP registry")
    url: str = Field(..., description="URL endpoint of the MCP registry")
    auth_type: RegistryAuthType = Field(..., alias="auth_type", description="Authentication type")
    auth_config: Optional[RegistryAuthConfig] = Field(None, alias="auth_config", description="Authentication configuration")


class CreateMCPRegistryResponse(AIDefenseModel):
    """Response message for creating an MCP registry.

    Args:
        id: Unique identifier for the created registry (UUID).
    """
    id: str = Field(..., description="Created registry identifier (UUID)")


class GetMCPRegistryRequest(AIDefenseModel):
    """Request message for getting an MCP registry by ID.

    Args:
        registry_id: Unique identifier of the MCP registry (UUID).
    """
    registry_id: str = Field(..., alias="registry_id", description="MCP registry identifier (UUID)")


class GetMCPRegistryResponse(AIDefenseModel):
    """Response message for getting an MCP registry.

    Args:
        mcp_registry: The requested MCP registry details.
    """
    mcp_registry: Optional[MCPRegistry] = Field(None, alias="mcpRegistry", description="MCP registry details")


class ListMCPRegistriesRequest(AIDefenseModel):
    """Request message for listing MCP registries.

    Args:
        limit: Maximum number of registries to return.
        offset: Offset for pagination.
    """
    limit: int = Field(default=25, description="Maximum results to return")
    offset: int = Field(default=0, description="Pagination offset")


class ListMCPRegistriesResponse(AIDefenseModel):
    """Response message for listing MCP registries.

    Args:
        mcp_registries: List of MCP registries with pagination information.
    """
    mcp_registries: Optional[MCPRegistries] = Field(None, alias="mcpRegistries", description="MCP registries list")


class ListMCPServersFromRegistryRequest(AIDefenseModel):
    """Request message for listing MCP servers from a registry.

    Args:
        registry_id: Unique identifier of the MCP registry (UUID).
        limit: Maximum number of servers to return.
        offset: Offset for pagination.
        query: Search query string.
        authors: Filter by authors.
        source_types: Filter by source types.
        versions: Filter by versions.
    """
    registry_id: str = Field(..., alias="registry_id", description="MCP registry identifier (UUID)")
    limit: int = Field(default=25, description="Maximum results to return")
    offset: int = Field(default=0, description="Pagination offset")
    query: str = Field(default="", description="Search query")
    authors: List[str] = Field(default_factory=list, description="Filter by authors")
    source_types: List[str] = Field(default_factory=list, alias="source_types", description="Filter by source types")
    versions: List[str] = Field(default_factory=list, description="Filter by versions")


class ListMCPServersFromRegistryResponse(AIDefenseModel):
    """Response message for listing MCP servers from a registry.

    Args:
        mcp_servers: List of MCP servers from registry with pagination.
    """
    mcp_servers: Optional[MCPServersFromRegistry] = Field(None, alias="mcpServers", description="MCP servers list")


class ListMCPRegistryFiltersRequest(AIDefenseModel):
    """Request message for listing available filters for a registry.

    Args:
        registry_id: Unique identifier of the MCP registry (UUID).
    """
    registry_id: str = Field(..., alias="registry_id", description="MCP registry identifier (UUID)")


class ListMCPRegistryFiltersResponse(AIDefenseModel):
    """Response message for listing available filters.

    Args:
        filters: Available filter options.
    """
    filters: Optional[MCPRegistryFilters] = Field(None, description="Available filters")


class TestMCPRegistryConnectivityRequest(AIDefenseModel):
    """Request message for testing MCP registry connectivity.

    Args:
        url: URL endpoint of the MCP registry to test.
        auth_config: Optional authentication configuration.
    """
    url: str = Field(..., description="URL endpoint of the MCP registry to test")
    auth_config: Optional[RegistryAuthConfig] = Field(None, alias="auth_config", description="Authentication configuration")


class TestMCPRegistryConnectivityResponse(AIDefenseModel):
    """Response message for testing MCP registry connectivity.

    Args:
        success: Whether the connectivity test succeeded.
        error: Error message if the test failed.
    """
    success: bool = Field(..., description="Whether connectivity test succeeded")
    error: str = Field(default="", description="Error message if failed")


class DeleteMCPRegistryRequest(AIDefenseModel):
    """Request message for deleting an MCP registry.

    Args:
        registry_id: Unique identifier of the MCP registry to delete (UUID).
    """
    registry_id: str = Field(..., alias="registry_id", description="MCP registry identifier (UUID)")


class DeleteMCPRegistryResponse(AIDefenseModel):
    """Response message for deleting an MCP registry.

    This is an empty response indicating successful deletion.
    """
    pass


class ResyncMCPRegistryRequest(AIDefenseModel):
    """Request message for resyncing an MCP registry.

    Args:
        registry_id: Unique identifier of the MCP registry to resync (UUID).
        auth_config: Optional authentication configuration for the resync.
    """
    registry_id: str = Field(..., alias="registry_id", description="MCP registry identifier (UUID)")
    auth_config: Optional[RegistryAuthConfig] = Field(None, alias="auth_config", description="Authentication configuration")


class ResyncMCPRegistryResponse(AIDefenseModel):
    """Response message for resyncing an MCP registry.

    Args:
        status: Status of the resync operation.
        started_at: Timestamp when the resync started.
    """
    status: RegistryStatus = Field(..., description="Resync status")
    started_at: Optional[datetime] = Field(None, alias="startedAt", description="Resync start timestamp")

    @model_validator(mode='before')
    @classmethod
    def __restore_enums(cls, values):
        return restore_enum_wrapper(cls, values)


class ListMCPRegistryServersDeltaRequest(AIDefenseModel):
    """Request message for listing MCP registry servers with delta information.

    Args:
        registry_id: Unique identifier of the MCP registry (UUID).
        limit: Maximum number of servers to return.
        offset: Offset for pagination.
        query: Search query string.
        authors: Filter by authors.
        source_types: Filter by source types.
        versions: Filter by versions.
    """
    registry_id: str = Field(..., alias="registry_id", description="MCP registry identifier (UUID)")
    limit: int = Field(default=25, description="Maximum results to return")
    offset: int = Field(default=0, description="Pagination offset")
    query: str = Field(default="", description="Search query")
    authors: List[str] = Field(default_factory=list, description="Filter by authors")
    source_types: List[str] = Field(default_factory=list, alias="source_types", description="Filter by source types")
    versions: List[str] = Field(default_factory=list, description="Filter by versions")


class ListMCPRegistryServersDeltaResponse(AIDefenseModel):
    """Response message for listing MCP registry servers with delta information.

    Args:
        mcp_servers: List of MCP servers from registry with delta information.
    """
    mcp_servers: Optional[MCPServersFromRegistry] = Field(None, alias="mcpServers", description="MCP servers with delta")


# --------------------
# Bulk Register and Scan Models
# --------------------

class BulkRegisterTarget(AIDefenseModel):
    """Target payload for bulk registration.

    Specifies a staged server to register and optionally override its authentication.

    Args:
        staged_server_id: UUID of the staged server to register.
        use_shared_auth: Whether to use the shared authentication configuration.
        auth_config: Optional per-server authentication configuration override.
    """
    staged_server_id: str = Field(..., alias="stagedServerId", description="Staged server identifier (UUID)")
    use_shared_auth: Optional[bool] = Field(None, alias="useSharedAuth", description="Use shared auth config")
    auth_config: Optional[AuthConfig] = Field(None, alias="authConfig", description="Per-server auth config override")


class BulkRegisterSharedAuthConfig(AIDefenseModel):
    """Shared authentication configuration for bulk registration.

    Args:
        name: Name for the shared auth configuration.
        auth_config: The authentication configuration to share across targets.
    """
    name: str = Field(..., description="Name for the shared auth config")
    auth_config: AuthConfig = Field(..., alias="authConfig", description="Shared authentication configuration")


class BulkRegisterAndScanRequest(AIDefenseModel):
    """Request message for registering staged servers and scanning them via bulk scan.

    This allows bulk registration of servers discovered from a registry and
    immediately initiates a scan of all registered servers.

    Args:
        registry_id: UUID of the registry the staged servers belong to.
        shared_auth: Optional shared authentication configuration for all targets.
        targets: List of target servers to register and scan (1-200 items).

    Example:
        ```python
        from aidefense.mcpscan.models import (
            BulkRegisterAndScanRequest,
            BulkRegisterTarget,
            BulkRegisterSharedAuthConfig,
            AuthConfig,
            AuthType,
        )

        # Register two servers with no auth
        request = BulkRegisterAndScanRequest(
            registry_id="registry-uuid",
            targets=[
                BulkRegisterTarget(staged_server_id="server-uuid-1"),
                BulkRegisterTarget(staged_server_id="server-uuid-2"),
            ]
        )

        # Register servers with shared API key auth
        request = BulkRegisterAndScanRequest(
            registry_id="registry-uuid",
            shared_auth=BulkRegisterSharedAuthConfig(
                name="Shared API Key",
                auth_config=AuthConfig(
                    auth_type=AuthType.API_KEY,
                    api_key=ApiKeyConfig(header_name="X-API-Key", api_key="secret")
                )
            ),
            targets=[
                BulkRegisterTarget(staged_server_id="server-uuid-1", use_shared_auth=True),
                BulkRegisterTarget(staged_server_id="server-uuid-2", use_shared_auth=True),
            ]
        )
        ```
    """
    registry_id: str = Field(..., alias="registry_id", description="MCP registry identifier (UUID)")
    shared_auth: Optional[BulkRegisterSharedAuthConfig] = Field(None, alias="sharedAuth", description="Shared auth config")
    targets: List[BulkRegisterTarget] = Field(..., description="Targets to register and scan (1-200)")


class BulkRegisterAndScanResponse(AIDefenseModel):
    """Response containing the kicked off bulk scan id.

    Args:
        bulk_scan_id: UUID of the initiated bulk scan job.
    """
    bulk_scan_id: str = Field(..., alias="bulkScanId", description="Bulk scan identifier (UUID)")
