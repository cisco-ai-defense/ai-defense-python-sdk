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

"""Custom exceptions for agentsec."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .decision import Decision


class SecurityPolicyError(Exception):
    """
    Raised when a security policy blocks a request or response.
    
    This exception is raised in enforce mode when an LLM request/response
    or MCP tool call violates security policies.
    
    Attributes:
        decision: The Decision object that triggered this error
        message: Human-readable description of why the request was blocked
    """
    
    def __init__(self, decision: "Decision", message: str | None = None):
        self.decision = decision
        self.message = message or self._format_message(decision)
        super().__init__(self.message)
    
    def _format_message(self, decision: "Decision") -> str:
        """Format a human-readable message from the decision."""
        if decision.reasons:
            reasons_str = "; ".join(decision.reasons)
            return f"Security policy violation: {reasons_str}"
        return "Security policy violation: request blocked"
    
    def __str__(self) -> str:
        return self.message
    
    def __repr__(self) -> str:
        return f"SecurityPolicyError(action={self.decision.action!r}, reasons={self.decision.reasons!r})"
