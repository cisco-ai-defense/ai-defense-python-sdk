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

"""Central logging module for agentsec with configurable formatters."""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging pipelines."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields if present
        if hasattr(record, "extra_fields") and record.extra_fields:
            log_data.update(record.extra_fields)
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


class TextFormatter(logging.Formatter):
    """Human-readable text formatter with key=value extras."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as text with optional extras."""
        base = f"[{record.name}] {record.levelname}: {record.getMessage()}"
        
        # Add extra fields if present
        if hasattr(record, "extra_fields") and record.extra_fields:
            extras = " ".join(f"{k}={v}" for k, v in record.extra_fields.items())
            base = f"{base} {extras}"
        
        # Add exception info if present
        if record.exc_info:
            base = f"{base}\n{self.formatException(record.exc_info)}"
        
        return base


def setup_logging(
    level: Optional[str] = None,
    format_type: Optional[str] = None,
    log_file: Optional[str] = None,
    redact: bool = True,
) -> logging.Logger:
    """
    Configure agentsec logging based on parameters or environment.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR). Defaults to env or WARNING.
        format_type: Log format (json, text). Defaults to env or text.
        log_file: Optional file path for logging. Defaults to env or None.
        redact: Whether to apply log redaction. Defaults to True.
    
    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger("aidefense.runtime.agentsec")
    
    # Avoid duplicate handlers on repeated calls
    if logger.handlers:
        return logger
    
    # Determine level from param, env, or default
    level_str = level or os.environ.get("AGENTSEC_LOG_LEVEL", "WARNING")
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }
    log_level = level_map.get(level_str.upper(), logging.WARNING)
    logger.setLevel(log_level)
    
    # Determine format from param, env, or default
    fmt = format_type or os.environ.get("AGENTSEC_LOG_FORMAT", "text")
    base_formatter: logging.Formatter
    if fmt.lower() == "json":
        base_formatter = JSONFormatter()
    else:
        base_formatter = TextFormatter()
    
    # Apply redaction wrapper if enabled
    formatter: logging.Formatter
    if redact:
        from ._redaction import RedactingFormatter
        formatter = RedactingFormatter(base_formatter)
    else:
        formatter = base_formatter
    
    # Always add stderr handler
    stderr_handler = logging.StreamHandler()
    stderr_handler.setFormatter(formatter)
    logger.addHandler(stderr_handler)
    
    # Add file handler if specified
    file_path = log_file or os.environ.get("AGENTSEC_LOG_FILE")
    if file_path:
        file_handler = logging.FileHandler(file_path)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger


def get_logger() -> logging.Logger:
    """Get the agentsec logger, creating it if needed."""
    logger = logging.getLogger("aidefense.runtime.agentsec")
    if not logger.handlers:
        setup_logging()
    return logger


class LogAdapter(logging.LoggerAdapter):
    """Logger adapter that supports extra_fields for structured logging."""
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """Add extra_fields to log record."""
        extra = kwargs.get("extra", {})
        if self.extra:
            extra["extra_fields"] = {**self.extra, **extra.get("extra_fields", {})}
        else:
            extra["extra_fields"] = extra.get("extra_fields", {})
        kwargs["extra"] = extra
        return msg, kwargs


def get_context_logger(**context: Any) -> LogAdapter:
    """
    Get a logger adapter with contextual fields.
    
    Args:
        **context: Key-value pairs to include in all log records.
    
    Returns:
        LogAdapter instance with context bound.
    """
    return LogAdapter(get_logger(), context)
