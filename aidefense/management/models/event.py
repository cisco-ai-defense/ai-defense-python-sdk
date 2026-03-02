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

"""Event models for the AI Defense Management API."""

from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import Field
from ...models.base import AIDefenseModel

from .common import Paging
from .application import Application
from .policy import Policy
from .connection import Connection, ConnectorDetails


class EventSortBy(str, Enum):
    """Event sort by enum."""

    rule_action = "rule_action"
    event_timestamp = "event_timestamp"
    message_type = "message_type"


class ViolationMetadata(AIDefenseModel):
    """Violation metadata model."""

    standards: Optional[List[str]] = Field(
        default_factory=list, description="List of standards violated"
    )
    techniques: Optional[List[str]] = Field(
        default_factory=list, description="List of techniques"
    )


class MatchFeedback(AIDefenseModel):
    """Match feedback model."""

    rating: Optional[str] = Field(None, description="Rating of the match")


class EventRuleMatch(AIDefenseModel):
    """Event rule match model."""

    guardrail_type: Optional[str] = Field(None, description="Guardrail type")
    guardrail_ruleset_type: Optional[str] = Field(
        None, description="Guardrail ruleset type"
    )
    guardrail_entity: Optional[str] = Field(None, description="Guardrail entity")
    guardrail_action: Optional[str] = Field(None, description="Guardrail action")
    metadata: Optional[ViolationMetadata] = Field(
        None, description="Violation metadata"
    )
    feedback: Optional[MatchFeedback] = Field(None, description="Match feedback")


class EventRuleMatches(AIDefenseModel):
    """Event rule matches model."""

    items: List[EventRuleMatch] = Field(
        default_factory=list, description="List of rule matches"
    )


class Event(AIDefenseModel):
    """Event model."""

    event_id: str = Field(description="Event ID")
    event_date: Optional[datetime] = Field(None, description="Event date")
    application_id: Optional[str] = Field(None, description="Application ID")
    policy_id: Optional[str] = Field(None, description="Policy ID")
    connection_id: Optional[str] = Field(None, description="Connection ID")
    event_action: Optional[str] = Field(None, description="Event action")
    message_id: Optional[str] = Field(None, description="Message ID")
    direction: Optional[str] = Field(None, description="Message direction")
    model_name: Optional[str] = Field(None, description="Model name")
    rule_matches: Optional[EventRuleMatches] = Field(None, description="Rule matches")
    application: Optional[Application] = Field(None, description="Application details")
    policy: Optional[Policy] = Field(None, description="Policy details")
    connection: Optional[Connection] = Field(None, description="Connection details")
    connector_details: Optional[ConnectorDetails] = Field(
        None, description="Connector information"
    )


class Events(AIDefenseModel):
    """Events model."""

    items: List[Event] = Field(default_factory=list, description="List of events")
    paging: Paging = Field(default=None, description="Pagination information")


class EventMessage(AIDefenseModel):
    """Event message model."""

    message_id: str = Field(description="Message ID")
    event_id: str = Field(description="Event ID")
    message_date: Optional[datetime] = Field(None, description="Message date")
    content: str = Field(description="Message content")
    direction: str = Field(description="Message direction")
    role: Optional[str] = Field(None, description="Message role")


class EventMessages(AIDefenseModel):
    """Event messages model."""

    items: List[EventMessage] = Field(
        default_factory=list, description="List of event messages"
    )
    paging: Paging = Field(default=None, description="Pagination information")


class ListEventsRequest(AIDefenseModel):
    """List events request model."""

    limit: Optional[int] = Field(None, description="Number of records to retrieve")
    offset: Optional[int] = Field(None, description="Offset for pagination")
    start_date: Optional[datetime] = Field(
        None, description="Start date for filtering events"
    )
    end_date: Optional[datetime] = Field(
        None, description="End date for filtering events"
    )
    expanded: Optional[bool] = Field(None, description="Whether to expand events")
    sort_by: Optional[EventSortBy] = Field(
        None, description="Field name to sort the events returned"
    )
    order: Optional[str] = Field(None, description="Sort order of the events returned")
