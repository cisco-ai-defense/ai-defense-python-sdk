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

"""
AI Defense Management API Models
Provides Pydantic models for the AI Defense Management API resources.
"""

from .application import Application, ApplicationSortBy, Applications
from .connection import (
    Connection,
    ConnectionSortBy,
    ConnectionStatus,
    ConnectionType,
    Connections,
    ApiKey,
    ApiKeys,
    ApiKeyRequest,
    ApiKeyResponse,
)
from .policy import (
    Policy,
    PolicySortBy,
    Policies,
    GuardrailType,
    Guardrail,
    GuardrailRule,
    Guardrails,
    RuleStatus,
    Action,
    Direction,
)
from .event import (
    Event,
    EventSortBy,
    Events,
    EventMessage,
    EventMessages,
    EventRuleMatch,
    EventRuleMatches,
    MatchFeedback,
)
from .common import Paging, SortOrder

__all__ = [
    # Application models
    "Application",
    "ApplicationSortBy",
    "Applications",
    # Connection models
    "Connection",
    "ConnectionSortBy",
    "ConnectionStatus",
    "ConnectionType",
    "Connections",
    "ApiKey",
    "ApiKeys",
    "ApiKeyRequest",
    "ApiKeyResponse",
    # Policy models
    "Policy",
    "PolicySortBy",
    "Policies",
    "GuardrailType",
    "Guardrail",
    "GuardrailRule",
    "Guardrails",
    "RuleStatus",
    "Action",
    "Direction",
    # Event models
    "Event",
    "EventSortBy",
    "Events",
    "EventMessage",
    "EventMessages",
    "EventRuleMatch",
    "EventRuleMatches",
    "MatchFeedback",
    # Common models
    "Paging",
    "SortOrder",
]
