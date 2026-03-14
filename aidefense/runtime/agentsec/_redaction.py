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

"""Log redaction module for sensitive data protection."""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Pattern


# Default patterns to redact sensitive data
DEFAULT_REDACT_PATTERNS = [
    # API keys in various formats
    r"(?i)(api[_-]?key|apikey|secret|token|password)\s*[=:]\s*['\"]?[\w\-\.]+['\"]?",
    # Authorization headers
    r"(?i)authorization:\s*bearer\s+[\w\-\.]+",
    # OpenAI API keys (sk-..., sk-proj-..., etc.)
    r"sk-[a-zA-Z0-9\-_]{20,}",
    # Generic bearer tokens
    r"(?i)bearer\s+[a-zA-Z0-9\-_\.]+",
    # AWS-style keys
    r"(?i)(aws_access_key_id|aws_secret_access_key)\s*[=:]\s*['\"]?[\w\-]+['\"]?",
    # Connection strings with passwords
    r"(?i)://[^:]+:[^@]+@",
]


@dataclass
class LogRedactor:
    """Redacts sensitive data from log messages using regex patterns."""
    
    enabled: bool = True
    patterns: List[str] = field(default_factory=lambda: DEFAULT_REDACT_PATTERNS.copy())
    replacement: str = "[REDACTED]"
    _compiled: List[Pattern[str]] = field(default_factory=list, init=False, repr=False)
    
    def __post_init__(self) -> None:
        """Compile regex patterns after initialization."""
        self._compiled = [re.compile(p) for p in self.patterns]
    
    def redact(self, text: str) -> str:
        """
        Redact sensitive patterns from text.
        
        Args:
            text: Input text to redact.
        
        Returns:
            Text with sensitive data replaced by [REDACTED].
        """
        if not self.enabled:
            return text
        
        result = text
        for pattern in self._compiled:
            result = pattern.sub(self.replacement, result)
        return result
    
    def add_pattern(self, pattern: str) -> None:
        """
        Add a custom redaction pattern.
        
        Args:
            pattern: Regex pattern to add.
        """
        self.patterns.append(pattern)
        self._compiled.append(re.compile(pattern))


# Global redactor instance
_redactor: LogRedactor = LogRedactor()


def get_redactor() -> LogRedactor:
    """Get the global redactor instance."""
    return _redactor


def configure_redaction(
    enabled: bool = True,
    patterns: List[str] | None = None,
    replacement: str = "[REDACTED]",
) -> None:
    """
    Configure global redaction settings.
    
    Args:
        enabled: Whether redaction is enabled.
        patterns: Custom patterns to use (replaces defaults if provided).
        replacement: Replacement string for redacted content.
    """
    global _redactor
    if patterns is not None:
        _redactor = LogRedactor(enabled=enabled, patterns=patterns, replacement=replacement)
    else:
        _redactor.enabled = enabled
        _redactor.replacement = replacement


def reset_redactor() -> None:
    """Reset the global redactor to default settings."""
    global _redactor
    _redactor = LogRedactor()


class RedactingFormatter(logging.Formatter):
    """
    Logging formatter wrapper that applies redaction to output.
    
    Wraps any base formatter and redacts sensitive data from the
    formatted log message.
    """
    
    def __init__(self, base_formatter: logging.Formatter) -> None:
        """
        Initialize with a base formatter to wrap.
        
        Args:
            base_formatter: The formatter to wrap with redaction.
        """
        super().__init__()
        self.base = base_formatter
    
    def format(self, record: logging.LogRecord) -> str:
        """Format the record and redact sensitive data."""
        msg = self.base.format(record)
        return get_redactor().redact(msg)
