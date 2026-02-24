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

from enum import Enum
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

# --- Entity type lists for rules that require them ---
PII_ENTITIES = [
    "Email Address",
    "IP Address",
    "Phone Number",
    "Driver's License Number (US)",
    "Passport Number (US)",
    "Social Security Number (SSN) (US)",
]
PCI_ENTITIES = [
    "Individual Taxpayer Identification Number (ITIN) (US)",
    "International Bank Account Number (IBAN)",
    "American Bankers Association (ABA) Routing Number (US)",
    "Credit Card Number",
    "Bank Account Number (US)",
]
PHI_ENTITIES = ["Medical License Number (US)", "National Health Service (NHS) Number"]


class Action(str, Enum):
    """
    Actions for violations detected in inspections.
    """

    ALLOW = "Allow"
    BLOCK = "Block"


class Classification(str, Enum):
    """
    Classifications for violations detected in inspections.
    """

    SECURITY_VIOLATION = "SECURITY_VIOLATION"
    PRIVACY_VIOLATION = "PRIVACY_VIOLATION"
    SAFETY_VIOLATION = "SAFETY_VIOLATION"
    RELEVANCE_VIOLATION = "RELEVANCE_VIOLATION"


class Severity(str, Enum):
    """
    Severity levels for violations detected in inspections.
    """

    NONE_SEVERITY = "NONE_SEVERITY"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RuleName(str, Enum):
    """
    Available rule names in AI Defense.
    """

    CODE_DETECTION = "Code Detection"
    HARASSMENT = "Harassment"
    HATE_SPEECH = "Hate Speech"
    PCI = "PCI"
    PHI = "PHI"
    PII = "PII"
    PROMPT_INJECTION = "Prompt Injection"
    PROFANITY = "Profanity"
    SEXUAL_CONTENT_EXPLOITATION = "Sexual Content & Exploitation"
    SOCIAL_DIVISION_POLARIZATION = "Social Division & Polarization"
    VIOLENCE_PUBLIC_SAFETY_THREATS = "Violence & Public Safety Threats"


@dataclass
class Rule:
    """
    Inspection rule configuration.

    Attributes:
        rule_name (Optional[RuleName]): The name of the rule to apply.
        entity_types (Optional[List[str]]): List of entity types (e.g., PII, PCI) to inspect for this rule.
        rule_id (Optional[int]): Unique identifier for the rule.
        classification (Optional[Classification]): The classification of the rule (e.g., PII, PCI).
    One of rule_name or rule_id must be provided.
    """

    rule_name: Optional[RuleName] = None
    entity_types: Optional[List[str]] = None
    rule_id: Optional[int] = None
    classification: Optional[Classification] = None


@dataclass
class Metadata:
    """
    Additional information about the request, such as user identity and application identity.

    Attributes:
        user (Optional[str]): The user associated with the request.
        created_at (Optional[datetime]): When the request was created.
        src_app (Optional[str]): Source application name.
        dst_app (Optional[str]): Destination application name.
        sni (Optional[str]): Server Name Indication (SNI) value.
        dst_ip (Optional[str]): Destination IP address.
        src_ip (Optional[str]): Source IP address.
        dst_host (Optional[str]): Destination host name.
        user_agent (Optional[str]): User agent string.
        client_transaction_id (Optional[str]): Unique client transaction identifier.
    """

    user: Optional[str] = None
    created_at: Optional[datetime] = None
    src_app: Optional[str] = None
    dst_app: Optional[str] = None
    sni: Optional[str] = None
    dst_ip: Optional[str] = None
    src_ip: Optional[str] = None
    dst_host: Optional[str] = None
    user_agent: Optional[str] = None
    client_transaction_id: Optional[str] = None


@dataclass
class InspectionConfig:
    """
    Configuration for inspection requests.
    Either enabled_rules or integration_profile details must be provided.

    Attributes:
        enabled_rules (Optional[List[Rule]]): List of enabled inspection rules.
        integration_profile_id (Optional[str]): ID of the integration profile to use.
        integration_profile_version (Optional[str]): Version of the integration profile.
        integration_tenant_id (Optional[str]): Tenant ID for multi-tenant scenarios.
        integration_type (Optional[str]): Type of integration (e.g., HTTP, chat).
    """

    enabled_rules: Optional[List[Rule]] = None
    integration_profile_id: Optional[str] = None
    integration_profile_version: Optional[str] = None
    integration_tenant_id: Optional[str] = None
    integration_type: Optional[str] = None


@dataclass
class InspectResponse:
    """
    Response from the inspection API.

    Attributes:
        classifications (List[Classification]): List of detected classifications (e.g., PII, PCI, PHI).
        is_safe (bool): Whether the inspected content is considered safe.
        severity (Optional[Severity]): Severity level of the detected issue (if any).
        rules (Optional[List[Rule]]): List of rules that matched during inspection.
        attack_technique (Optional[str]): Attack technique detected, if applicable.
        explanation (Optional[str]): Human-readable explanation of the inspection result.
        client_transaction_id (Optional[str]): Unique client-provided transaction ID for tracing.
        event_id (Optional[str]): Unique event ID assigned by the backend.
    """

    classifications: List[Classification]
    is_safe: bool
    action: Action
    severity: Optional[Severity] = None
    rules: Optional[List[Rule]] = None
    attack_technique: Optional[str] = None
    explanation: Optional[str] = None
    client_transaction_id: Optional[str] = None
    event_id: Optional[str] = None
