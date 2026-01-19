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
    """
    __slots__ = ("action", "reasons", "sanitized_content", "raw_response")
    
    def __init__(
        self,
        action: ActionType,
        reasons: Optional[List[str]] = None,
        sanitized_content: Optional[str] = None,
        raw_response: Any = None,
    ) -> None:
        self.action = action
        self.reasons = reasons or []
        self.sanitized_content = sanitized_content
        self.raw_response = raw_response
    
    def allows(self) -> bool:
        """
        Check if this decision allows the request to proceed.
        
        Returns:
            True if action is allow, sanitize, or monitor_only.
            False if action is block.
        """
        return self.action != "block"
    
    def __repr__(self) -> str:
        return (
            f"Decision(action={self.action!r}, reasons={self.reasons!r}, "
            f"sanitized_content={self.sanitized_content!r})"
        )
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Decision):
            return NotImplemented
        return (
            self.action == other.action
            and self.reasons == other.reasons
            and self.sanitized_content == other.sanitized_content
        )
    
    @classmethod
    def allow(
        cls,
        reasons: Optional[List[str]] = None,
        raw_response: Any = None,
    ) -> "Decision":
        """Create an allow decision."""
        return cls(action="allow", reasons=reasons, raw_response=raw_response)
    
    @classmethod
    def block(
        cls,
        reasons: List[str],
        raw_response: Any = None,
    ) -> "Decision":
        """Create a block decision."""
        return cls(action="block", reasons=reasons, raw_response=raw_response)
    
    @classmethod
    def sanitize(
        cls,
        reasons: List[str],
        sanitized_content: Optional[str] = None,
        raw_response: Any = None,
    ) -> "Decision":
        """Create a sanitize decision."""
        return cls(
            action="sanitize",
            reasons=reasons,
            sanitized_content=sanitized_content,
            raw_response=raw_response,
        )
    
    @classmethod
    def monitor_only(
        cls,
        reasons: List[str],
        raw_response: Any = None,
    ) -> "Decision":
        """Create a monitor_only decision."""
        return cls(action="monitor_only", reasons=reasons, raw_response=raw_response)
