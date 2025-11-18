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

"""Connection models for the AI Defense Management API."""

from enum import Enum
from typing import List, Optional, Any
from datetime import datetime
from pydantic import Field
from ...models.base import AIDefenseModel

from .common import Paging


class EditConnectionOperationType(str, Enum):
    """Connection API key operation types."""

    GENERATE_API_KEY = "GENERATE_API_KEY"
    REGENERATE_API_KEY = "REGENERATE_API_KEY"
    REVOKE_API_KEY = "REVOKE_API_KEY"


class ConnectionStatus(str, Enum):
    """Connection status enum."""

    Connected = "Connected"
    Disconnected = "Disconnected"
    Pending = "Pending"


class ConnectionType(str, Enum):
    """Connection type enum."""

    API = "API"
    Gateway = "Gateway"
    Unspecified = "Unspecified"


class ConnectionSortBy(str, Enum):
    """Sort options for connection list operations."""

    connection_name = "connection_name"
    status = "status"
    last_active = "last_active"


class ApiKeyRequest(AIDefenseModel):
    """
    API key request model.

    Attributes:
        name (str): Name of the API key.
        expiry (datetime): Expiry timestamp for the API key.
    """

    name: str = Field(..., description="Name of the API key")
    expiry: datetime = Field(..., description="Expiry timestamp for the API key")


class ApiKeyResponse(AIDefenseModel):
    """
    API key response model.

    Attributes:
        key_id (str): ID of the API key created.
        api_key (str): The generated API key (only for connection of type API).
    """

    key_id: str = Field(..., description="ID of the API key created")
    api_key: str = Field(
        ..., description="The generated API key (only for connection of type API)"
    )


class ApiKey(AIDefenseModel):
    """
    API key model.

    Attributes:
        id (str): API key ID.
        name (str): API key name.
        status (str): Status of the API key.
        expiry (datetime): Expiry timestamp.
    """

    id: str = Field(..., description="API key ID")
    name: str = Field(..., description="API key name")
    status: str = Field(..., description="Status of the API key")
    expiry: datetime = Field(..., description="Expiry timestamp")


class ApiKeys(AIDefenseModel):
    """
    List of API keys with pagination.

    Attributes:
        items (List[ApiKey]): List of API keys.
        paging (Paging): Pagination information.
    """

    items: List[ApiKey] = Field(..., description="List of API keys")
    paging: Paging = Field(..., description="Pagination information")


class Endpoint(AIDefenseModel):
    """
    Endpoint model.

    Attributes:
        endpoint_id (str): Endpoint ID.
        model_endpoint_type (str): Type of model endpoint.
        model_endpoint_url (str): URL of the model endpoint.
        model_provider_name (str): Name of the model provider.
    """

    endpoint_id: str = Field(..., description="Endpoint ID")
    model_endpoint_type: Optional[str] = Field(
        None, description="Type of model endpoint"
    )
    model_endpoint_url: Optional[str] = Field(
        None, description="URL of the model endpoint"
    )
    model_provider_name: Optional[str] = Field(
        None, description="Name of the model provider"
    )


class Models(AIDefenseModel):
    """
    Models model.

    Attributes:
        model_name (List[str]): List of model names.
    """

    model_name: List[str] = Field(..., description="List of model names")


class ConnectorDetails(AIDefenseModel):
    """Connector details for hybrid/on-prem connectors."""

    connector_id: Optional[str] = Field(None, description="Connector ID")
    connector_name: Optional[str] = Field(None, description="Connector name")
    connector_version: Optional[str] = Field(None, description="Connector version")


class Connection(AIDefenseModel):
    """
    Connection resource model.

    Attributes:
        connection_id (str): Unique identifier for the connection.
        connection_name (str): Name of the connection.
        application_id (str): ID of the associated application.
        endpoint_id (Optional[str]): ID of the associated endpoint.
        connection_status (ConnectionStatus): Status of the connection.
        created_at (datetime): Timestamp when the connection was created.
        last_active (Optional[datetime]): Timestamp when the connection was last active.
        updated_at (datetime): Timestamp when the connection was last updated.
        updated_by (Optional[str]): User who last updated the connection.
        application (Optional[Any]): Associated application details.
        policies (Optional[Any]): Associated policies.
        endpoint (Optional[Endpoint]): Associated endpoint details.
        models (Optional[Models]): Associated models.
        connector_details (Optional[ConnectorDetails]): Connector information.
    """

    connection_id: str = Field(..., description="Unique identifier for the connection")
    connection_name: str = Field(..., description="Name of the connection")
    application_id: str = Field(..., description="ID of the associated application")
    endpoint_id: Optional[str] = Field(
        None, description="ID of the associated endpoint"
    )
    connection_status: ConnectionStatus = Field(
        ..., description="Status of the connection"
    )
    created_at: datetime = Field(
        ..., description="Timestamp when the connection was created"
    )
    last_active: Optional[datetime] = Field(
        None, description="Timestamp when the connection was last active"
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when the connection was last updated"
    )
    updated_by: Optional[str] = Field(
        None, description="User who last updated the connection"
    )
    application: Optional[Any] = Field(
        None, description="Associated application details"
    )
    policies: Optional[Any] = Field(None, description="Associated policies")
    endpoint: Optional[Endpoint] = Field(
        None, description="Associated endpoint details"
    )
    models: Optional[Models] = Field(None, description="Associated models")
    connector_details: Optional[ConnectorDetails] = Field(
        None, description="Connector information"
    )


class Connections(AIDefenseModel):
    """
    List of connections with pagination.

    Attributes:
        items (List[Connection]): List of connections.
        paging (Paging): Pagination information.
    """

    items: List[Connection] = Field(..., description="List of connections")
    paging: Paging = Field(..., description="Pagination information")


class ListConnectionsRequest(AIDefenseModel):
    """List connections request model."""

    limit: Optional[int] = Field(
        None, description="Number of records to retrieve, default and max value is 100"
    )
    offset: Optional[int] = Field(None, description="Offset for pagination")
    expanded: Optional[bool] = Field(None, description="Whether to expand connections")
    sort_by: Optional[ConnectionSortBy] = Field(
        None, description="Field name to sort the connections returned"
    )
    order: Optional[str] = Field(
        None, description="Sort order of the connections returned"
    )
    connection_type: Optional[ConnectionType] = Field(
        None, description="Filter by connection type"
    )
    connection_status: Optional[ConnectionStatus] = Field(
        None, description="Filter by connection status"
    )
    policy_applied: Optional[bool] = Field(
        None, description="Filter by policy assignment status"
    )
    connection_name: Optional[str] = Field(
        None, description="Search by connection name"
    )


class ListConnectionsResponse(AIDefenseModel):
    """List connections response model."""

    connections: List[Connection] = Field(..., description="List of connections")


class CreateConnectionRequest(AIDefenseModel):
    """Create connection request model."""

    application_id: str = Field(..., description="Application ID")
    connection_name: str = Field(
        ..., description="Connection name", alias="connectionName"
    )
    connection_type: ConnectionType = Field(..., description="Connection type")
    endpoint_id: Optional[str] = Field(
        None, description="Endpoint ID (optional for API flow)"
    )
    connection_guide_id: Optional[str] = Field(
        None, description="Connection guide ID (optional)"
    )
    key: Optional[ApiKeyRequest] = Field(None, description="API key request (optional)")
    connector_id: Optional[str] = Field(
        None,
        description="Connector ID of the onprem data plane deployment",
    )


class CreateConnectionResponse(AIDefenseModel):
    """Create connection response model."""

    connection_id: str = Field(..., description="ID of the created connection")
    key: Optional[ApiKeyResponse] = Field(
        None, description="API key response (if key was requested)"
    )


class GetConnectionByIDRequest(AIDefenseModel):
    """Get connection by ID request model."""

    expanded: Optional[bool] = Field(
        None, description="Whether to return expanded information"
    )


class UpdateConnectionRequest(AIDefenseModel):
    """Update connection request model."""

    key_id: Optional[str] = Field(None, description="Key ID (for revoke op)")
    operation_type: EditConnectionOperationType = Field(
        ..., description="Operation type", alias="op"
    )
    key: Optional[ApiKeyRequest] = Field(
        None, description="API key request for generation"
    )
