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

from .mcp_scan_base import MCPScan
from .mcp_scan import MCPScanClient
from .resource_connections import ResourceConnectionClient
from .policies import MCPPolicyClient
from .models import (
    # Enums
    TransportType,
    AuthType,
    MCPScanStatus,
    AnalyzerType,
    SeverityLevel,
    CapabilityScanStatus,
    CapabilityType,
    OnboardingStatus,
    ServerType,
    # Auth Config Models
    OAuthConfig,
    ApiKeyConfig,
    AuthConfig,
    # Capability Models
    Argument,
    ToolInputSchema,
    ToolOutputSchema,
    Tool,
    PromptInputSchema,
    Prompt,
    Resource,
    Capability,
    # Threat Models
    ThreatSubTechnique,
    ThreatDetails,
    MCPServerCapabilityThreats,
    # Summary Models
    CapabilitySummary,
    ScanThreatSummary,
    Paging,
    # Server Input Models
    RemoteServerInput,
    StdioServerInput,
    # Scan Request/Response Models
    StartMCPServerScanRequest,
    StartMCPServerScanResponse,
    ErrorInfo,
    GetMCPScanStatusResponse,
    MCPScanResult,
    MCPCapabilityScanResults,
    CapabilityScanResults,
    CapabilityScanResult,
    # Register Server Request/Response Models
    RegisterMCPServerRequest,
    RegisterMCPServerResponse,
    # Delete Server Response Models
    DeleteMCPServerResponse,
    # Capabilities Request/Response Models
    GetMCPServerCapabilitiesRequest,
    GetMCPServerCapabilitiesResponse,
    # Threats Request/Response Models
    GetMCPServerThreatsRequest,
    GetMCPServerThreatsResponse,
    # Scan Summary Request/Response Models
    GetMCPServerScanSummaryRequest,
    GetMCPServerScanSummaryResponse,
    # MCP Server Models
    MCPServer,
    MCPServers,
    # GetMCPServer Request/Response Models
    GetMCPServerRequest,
    GetMCPServerResponse,
    # ListMCPServers Request/Response Models
    ListMCPServersRequest,
    ListMCPServersResponse,
    # UpdateAuthConfig Request/Response Models
    UpdateAuthConfigRequest,
    UpdateAuthConfigResponse,
    # MCP Registry Enums
    RegistryAuthType,
    RegistryStatus,
    # MCP Registry Models
    MCPRegistry,
    MCPRegistries,
    MCPRegistryServerRepository,
    MCPRegistryServerTransport,
    MCPRegistryServerEnvironmentVariable,
    MCPRegistryServerPackage,
    MCPRegistryServerRemote,
    MCPRegistryServerMeta,
    MCPRegistryServer,
    MCPRegistryServerChange,
    MCPRegistryServerDelta,
    MCPServerFromRegistry,
    MCPServersFromRegistry,
    MCPRegistryFilters,
    # MCP Registry Auth Config Models
    RegistryOAuthConfig,
    RegistryApiKeyConfig,
    RegistryBasicAuthConfig,
    RegistryAuthConfig,
    # MCP Registry Request/Response Models
    CreateMCPRegistryRequest,
    CreateMCPRegistryResponse,
    GetMCPRegistryRequest,
    GetMCPRegistryResponse,
    ListMCPRegistriesRequest,
    ListMCPRegistriesResponse,
    ListMCPServersFromRegistryRequest,
    ListMCPServersFromRegistryResponse,
    ListMCPRegistryFiltersRequest,
    ListMCPRegistryFiltersResponse,
    TestMCPRegistryConnectivityRequest,
    TestMCPRegistryConnectivityResponse,
    DeleteMCPRegistryRequest,
    DeleteMCPRegistryResponse,
    ResyncMCPRegistryRequest,
    ResyncMCPRegistryResponse,
    ListMCPRegistryServersDeltaRequest,
    ListMCPRegistryServersDeltaResponse,
    # Bulk Register and Scan Models
    BulkRegisterTarget,
    BulkRegisterSharedAuthConfig,
    BulkRegisterAndScanRequest,
    BulkRegisterAndScanResponse,
    # Resource Connection Enums
    ResourceConnectionStatus,
    ResourceConnectionType,
    ResourceType,
    ResourceConnectionSortBy,
    SortOrder,
    # Resource Connection Models
    Identity,
    ResourceDetails,
    PolicyInfo,
    PoliciesList,
    ResourceInfo,
    ResourcesList,
    ResourceConnection,
    ResourceConnections,
    # Resource Connection Request/Response Models
    CreateResourceConnectionRequest,
    CreateResourceConnectionResponse,
    DeleteResourceConnectionByIDResponse,
    DeleteResourceConnectionsByResourceIdResponse,
    GetResourceConnectionByIDResponse,
    GetResourceConnectionByResourceIDResponse,
    MCPServerFilters,
    ResourceTypeSpecificFilters,
    FilterResourceConnectionsRequest,
    FilterResourceConnectionsResponse,
    FilterResourcesByConnectionIDRequest,
    FilterResourcesByConnectionIDResponse,
    AddOrUpdateResourceConnectionsRequest,
    AddOrUpdateResourceConnectionsResponse,
)

# Re-export policy models from management for convenience
from aidefense.management.models.policy import (
    # Policy Enums
    PolicySortBy,
    RuleStatus,
    Direction,
    Action,
    GuardrailType,
    # Policy Models
    Entity,
    GuardrailRule,
    Guardrail,
    Guardrails,
    Policy,
    Policies,
    # Policy Request/Response Models
    ListPoliciesRequest,
    ListPoliciesResponse,
    UpdatePolicyRequest,
    AddOrUpdatePolicyConnectionsRequest,
)
