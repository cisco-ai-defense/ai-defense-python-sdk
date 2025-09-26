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

"""Application models for the AI Defense Management API."""

from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import Field
from ...models.base import AIDefenseModel

from .common import Paging
from .connection import ConnectionType, Connections


class ApplicationSortBy(str, Enum):
    """Application sort by enum."""

    application_name = "application_name"
    description = "description"
    connection_type = "connection_type"


class Application(AIDefenseModel):
    """Application model."""

    application_id: str = Field(description="Application ID")
    application_name: str = Field(description="Application name")
    description: str = Field(description="Description")
    updated_at: Optional[datetime] = Field(None, description="Last updated timestamp")
    connection_type: ConnectionType = Field(description="Connection type")
    created_at: Optional[datetime] = Field(None, description="Created timestamp")
    updated_by: Optional[str] = Field(None, description="Updated by")
    connections: Optional[Connections] = Field(
        None, description="Connections associated with this application"
    )


class Applications(AIDefenseModel):
    """Applications model."""

    items: List[Application] = Field(
        default_factory=list, description="List of applications"
    )
    paging: Paging = Field(default=None, description="Pagination information")


class CreateApplicationRequest(AIDefenseModel):
    """Create application request model."""

    application_name: str = Field(description="Application name")
    description: str = Field(description="Description")
    connection_type: ConnectionType = Field(description="Connection type")


class CreateApplicationResponse(AIDefenseModel):
    """Create application response model."""

    application_id: str = Field(description="Application ID")


class ListApplicationsRequest(AIDefenseModel):
    """List applications request model."""

    limit: Optional[int] = Field(
        None, description="Number of records to retrieve, default and max value is 100"
    )
    offset: Optional[int] = Field(None, description="Offset for pagination")
    expanded: Optional[bool] = Field(None, description="Whether to expand connections")
    sort_by: Optional[ApplicationSortBy] = Field(
        None, description="Field name to sort the applications returned"
    )
    order: Optional[str] = Field(
        None, description="Sort order of the applications returned"
    )
    connection_type: Optional[ConnectionType] = Field(
        None, description="Filter by connection type"
    )
    application_name: Optional[str] = Field(
        None, description="Search by application name"
    )


class ListApplicationsResponse(AIDefenseModel):
    """List applications response model."""

    applications: Applications = Field(
        description="List of applications with pagination"
    )


class UpdateApplicationRequest(AIDefenseModel):
    """Update application request model."""

    application_name: Optional[str] = Field(
        None, description="Application name (optional)"
    )
    description: Optional[str] = Field(None, description="Description (optional)")
