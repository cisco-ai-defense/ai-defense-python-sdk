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

"""Policy models for the AI Defense Management API."""

from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import Field
from ...models.base import AIDefenseModel

from .common import Paging
from .connection import ConnectionType


class PolicySortBy(str, Enum):
    """Policy sort by enum."""

    policy_name = "policy_name"


class RuleStatus(str, Enum):
    """Rule status enum."""

    Enabled = "Enabled"
    Disabled = "Disabled"


class Direction(str, Enum):
    """Direction enum."""

    Prompt = "Prompt"
    Response = "Response"
    Both = "Both"


class Action(str, Enum):
    """Action enum."""

    Block = "Block"
    Allow = "Allow"


class GuardrailType(str, Enum):
    """Guardrail type enum."""

    Security = "Security"
    Privacy = "Privacy"
    Safety = "Safety"


class Entity(AIDefenseModel):
    """Entity model."""

    name: str = Field(description="Entity name")
    desc: str = Field(description="Entity description")


class GuardrailRule(AIDefenseModel):
    """Guardrail rule model."""

    ruleset_type: str = Field(description="Ruleset type")
    status: RuleStatus = Field(description="Rule status")
    direction: Direction = Field(description="Direction")
    action: Action = Field(description="Action")
    entity: Optional[Entity] = Field(None, description="Entity")


class Guardrail(AIDefenseModel):
    """Guardrail model."""

    guardrails_type: GuardrailType = Field(description="Guardrails type")
    items: List[GuardrailRule] = Field(
        default_factory=list, description="List of guardrail rules"
    )
    paging: Paging = Field(default=None, description="Pagination information")


class Guardrails(AIDefenseModel):
    """Guardrails model."""

    items: List[Guardrail] = Field(
        default_factory=list, description="List of guardrails"
    )
    paging: Paging = Field(default=None, description="Pagination information")


class Policy(AIDefenseModel):
    """Policy model."""

    policy_id: str = Field(description="Policy ID")
    policy_name: Optional[str] = Field(None, description="Policy name")
    description: Optional[str] = Field(None, description="Description")
    status: Optional[str] = Field(None, description="Status")
    connection_type: Optional[ConnectionType] = Field(
        None, description="Connection type"
    )
    updated_at: Optional[datetime] = Field(None, description="Updated timestamp")
    created_at: Optional[datetime] = Field(None, description="Created timestamp")
    language_type: Optional[str] = Field(None, description="Language type")
    updated_by: Optional[str] = Field(None, description="Updated by")
    guardrails: Optional[Guardrails] = Field(
        None, description="Guardrails associated with this policy"
    )


class Policies(AIDefenseModel):
    """Policies model."""

    items: List[Policy] = Field(default_factory=list, description="List of policies")
    paging: Paging = Field(default=None, description="Pagination information")


class ListPoliciesRequest(AIDefenseModel):
    """List policies request model."""

    limit: Optional[int] = Field(
        None, description="Number of records to retrieve, default and max value is 100"
    )
    offset: Optional[int] = Field(None, description="Offset for pagination")
    sort_by: Optional[PolicySortBy] = Field(
        None, description="Field name to sort the policies returned"
    )
    order: Optional[str] = Field(
        None, description="Sort order of the policies returned"
    )
    language_type: Optional[str] = Field(None, description="Filter by language type")
    connection_type: Optional[ConnectionType] = Field(
        None, description="Filter by connection type"
    )
    policy_status: Optional[str] = Field(None, description="Filter by policy status")
    policy_name: Optional[str] = Field(None, description="Filter by policy name")


class ListPoliciesResponse(AIDefenseModel):
    """List policies response model."""

    policies: Policies = Field(..., description="List of policies with pagination")


class UpdatePolicyRequest(AIDefenseModel):
    """Update policy request model."""

    name: Optional[str] = Field(None, description="Policy name")
    description: Optional[str] = Field(None, description="Description of the policy")
    status: Optional[str] = Field(None, description="Status of the policy")


class AddOrUpdatePolicyConnectionsRequest(AIDefenseModel):
    """Add or update policy connections request model."""

    connections_to_associate: Optional[List[str]] = Field(
        None, description="List of connection IDs to be added or updated to a policy"
    )
    connections_to_disassociate: Optional[List[str]] = Field(
        None, description="List of connection IDs to be removed from a policy"
    )
