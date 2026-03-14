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

from typing import TYPE_CHECKING, Optional, Union

if TYPE_CHECKING:
    from .decision import Decision


class AgentsecError(Exception):
    """
    Base exception for all agentsec errors.
    
    All agentsec-specific exceptions inherit from this class,
    allowing users to catch all agentsec errors with a single except clause.
    
    Example:
        try:
            agentsec.protect()
            # ... use protected clients ...
        except AgentsecError as e:
            print(f"Agentsec error: {e}")
    """
    pass


class ConfigurationError(AgentsecError):
    """
    Raised when agentsec configuration is invalid.
    
    This exception is raised during protect() initialization
    if configuration parameters or environment variables are invalid.
    
    Example:
        try:
            agentsec.protect(retry_total=-1)  # Invalid!
        except ConfigurationError as e:
            print(f"Configuration error: {e}")
    """
    pass


class ValidationError(AgentsecError):
    """
    Raised when input validation fails.
    
    This exception is raised when invalid input is passed to
    inspection methods (e.g., empty messages, invalid metadata).
    
    Example:
        try:
            inspector.inspect_conversation([])  # Empty messages!
        except ValidationError as e:
            print(f"Validation error: {e}")
    """
    pass


class InspectionTimeoutError(AgentsecError):
    """
    Raised when the inspection API times out.
    
    This exception is raised when fail_open=False and the
    inspection API request times out.
    
    Attributes:
        timeout_ms: The timeout value that was exceeded (in milliseconds)
    
    Example:
        try:
            decision = inspector.inspect_conversation(messages, metadata)
        except InspectionTimeoutError as e:
            print(f"Inspection timed out: {e}")
    """
    
    def __init__(self, message: str, timeout_ms: Optional[int] = None):
        super().__init__(message)
        self.timeout_ms = timeout_ms
    
    def __repr__(self) -> str:
        return f"InspectionTimeoutError({self.args[0]!r}, timeout_ms={self.timeout_ms!r})"


class InspectionNetworkError(AgentsecError):
    """
    Raised when a network error occurs during inspection.
    
    This exception is raised when fail_open=False and a network
    error occurs while connecting to the inspection API (e.g.,
    connection refused, DNS resolution failure).
    
    Example:
        try:
            decision = inspector.inspect_conversation(messages, metadata)
        except InspectionNetworkError as e:
            print(f"Network error during inspection: {e}")
    """
    pass


class SecurityPolicyError(AgentsecError):
    """
    Raised when a security policy blocks a request or response.
    
    This exception is raised in enforce mode when an LLM request/response
    or MCP tool call violates security policies.
    
    Accepts either a Decision object or a plain string message, following
    standard Python exception conventions.
    
    Attributes:
        decision: The Decision object that triggered this error (None if
            constructed with a plain string)
        message: Human-readable description of why the request was blocked
    
    Example:
        try:
            response = client.chat.completions.create(...)
        except SecurityPolicyError as e:
            print(f"Blocked: {e}")
            print(f"Decision: {e.decision}")
    """
    
    def __init__(self, decision_or_message: "Union[Decision, str]", message: Optional[str] = None):
        from .decision import Decision

        if isinstance(decision_or_message, str):
            self.decision = None
            self.message = decision_or_message
        elif isinstance(decision_or_message, Decision):
            self.decision = decision_or_message
            self.message = message or self._format_message(decision_or_message)
        else:
            self.decision = decision_or_message
            self.message = message or "Security policy violation: request blocked"
        super().__init__(self.message)
    
    def _format_message(self, decision: "Decision") -> str:
        """Format a human-readable message from the decision."""
        parts = ["Security policy violation"]

        if decision.reasons:
            parts.append(": " + "; ".join(decision.reasons))

        details = []
        if decision.severity:
            details.append(f"severity={decision.severity}")
        if decision.classifications:
            details.append(f"classifications={decision.classifications}")
        if decision.explanation:
            details.append(f"explanation={decision.explanation!r}")

        if details:
            parts.append(f" [{', '.join(details)}]")
        elif not decision.reasons:
            parts.append(": request blocked")

        return "".join(parts)
    
    def __str__(self) -> str:
        return self.message
    
    def __repr__(self) -> str:
        if self.decision is not None:
            return f"SecurityPolicyError(action={self.decision.action!r}, reasons={self.decision.reasons!r})"
        return f"SecurityPolicyError({self.message!r})"
