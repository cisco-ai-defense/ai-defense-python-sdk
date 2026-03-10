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

"""Decision type for security inspection results."""

from typing import Any, List, Literal, Optional


ActionType = Literal["allow", "block", "sanitize", "monitor_only"]


class Decision:
    """
    Represents the result of a security inspection.
    
    Attributes:
        action: The action to take - allow, block, sanitize, or monitor_only
        reasons: List of reasons explaining the decision
        sanitized_content: Modified content if action is sanitize
        raw_response: The raw response from the inspection API (if any)
        severity: Severity level of the violation (e.g., "low", "medium", "high", "critical")
        classifications: List of violation classifications (e.g., ["pii", "prompt_injection"])
        rules: List of rules that were triggered, with details
        explanation: Human-readable explanation of the decision
        event_id: Unique identifier for this inspection event (for correlation/audit)
    """
    __slots__ = (
        "action",
        "reasons",
        "sanitized_content",
        "raw_response",
        # New fields for rich result processing
        "severity",
        "classifications",
        "rules",
        "explanation",
        "event_id",
    )
    
    def __init__(
        self,
        action: ActionType,
        reasons: Optional[List[str]] = None,
        sanitized_content: Optional[str] = None,
        raw_response: Any = None,
        # New fields - all optional with None defaults for backward compatibility
        severity: Optional[str] = None,
        classifications: Optional[List[str]] = None,
        rules: Optional[List[Any]] = None,
        explanation: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> None:
        self.action = action
        self.reasons = reasons or []
        self.sanitized_content = sanitized_content
        self.raw_response = raw_response
        # New fields
        self.severity = severity
        self.classifications = classifications
        self.rules = rules
        self.explanation = explanation
        self.event_id = event_id
    
    def allows(self) -> bool:
        """
        Check if this decision allows the request to proceed.
        
        Returns:
            True if action is allow, sanitize, or monitor_only.
            False if action is block.
        """
        return self.action != "block"
    
    @property
    def is_safe(self) -> bool:
        """
        Check if this decision indicates the content is safe.
        
        This is an alias for allows() that provides compatibility
        with the InspectResponse interface from ChatInspectionClient.
        
        Returns:
            True if action is allow, sanitize, or monitor_only.
            False if action is block.
        """
        return self.action != "block"
    
    def __repr__(self) -> str:
        # Include new fields only if they have values (to keep output concise)
        parts = [
            f"action={self.action!r}",
            f"reasons={self.reasons!r}",
            f"sanitized_content={self.sanitized_content!r}",
        ]
        if self.severity is not None:
            parts.append(f"severity={self.severity!r}")
        if self.classifications is not None:
            parts.append(f"classifications={self.classifications!r}")
        if self.rules is not None:
            parts.append(f"rules={self.rules!r}")
        if self.explanation is not None:
            parts.append(f"explanation={self.explanation!r}")
        if self.event_id is not None:
            parts.append(f"event_id={self.event_id!r}")
        return f"Decision({', '.join(parts)})"
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Decision):
            return NotImplemented
        # Note: raw_response is intentionally excluded — it is an implementation
        # detail (full API response) and not part of the decision's semantic identity.
        return (
            self.action == other.action
            and self.reasons == other.reasons
            and self.sanitized_content == other.sanitized_content
            and self.severity == other.severity
            and self.classifications == other.classifications
            and self.rules == other.rules
            and self.explanation == other.explanation
            and self.event_id == other.event_id
        )
    
    @classmethod
    def allow(
        cls,
        reasons: Optional[List[str]] = None,
        raw_response: Any = None,
        severity: Optional[str] = None,
        classifications: Optional[List[str]] = None,
        rules: Optional[List[Any]] = None,
        explanation: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> "Decision":
        """Create an allow decision."""
        return cls(
            action="allow",
            reasons=reasons,
            raw_response=raw_response,
            severity=severity,
            classifications=classifications,
            rules=rules,
            explanation=explanation,
            event_id=event_id,
        )
    
    @classmethod
    def block(
        cls,
        reasons: List[str],
        raw_response: Any = None,
        severity: Optional[str] = None,
        classifications: Optional[List[str]] = None,
        rules: Optional[List[Any]] = None,
        explanation: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> "Decision":
        """Create a block decision."""
        return cls(
            action="block",
            reasons=reasons,
            raw_response=raw_response,
            severity=severity,
            classifications=classifications,
            rules=rules,
            explanation=explanation,
            event_id=event_id,
        )
    
    @classmethod
    def sanitize(
        cls,
        reasons: List[str],
        sanitized_content: Optional[str] = None,
        raw_response: Any = None,
        severity: Optional[str] = None,
        classifications: Optional[List[str]] = None,
        rules: Optional[List[Any]] = None,
        explanation: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> "Decision":
        """Create a sanitize decision."""
        return cls(
            action="sanitize",
            reasons=reasons,
            sanitized_content=sanitized_content,
            raw_response=raw_response,
            severity=severity,
            classifications=classifications,
            rules=rules,
            explanation=explanation,
            event_id=event_id,
        )
    
    @classmethod
    def monitor_only(
        cls,
        reasons: List[str],
        raw_response: Any = None,
        severity: Optional[str] = None,
        classifications: Optional[List[str]] = None,
        rules: Optional[List[Any]] = None,
        explanation: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> "Decision":
        """Create a monitor_only decision."""
        return cls(
            action="monitor_only",
            reasons=reasons,
            raw_response=raw_response,
            severity=severity,
            classifications=classifications,
            rules=rules,
            explanation=explanation,
            event_id=event_id,
        )
