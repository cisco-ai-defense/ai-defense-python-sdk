"""Tests for the logging module (Task Group 1)."""

import json
import logging
import os
import tempfile
from unittest.mock import patch

import pytest

from aidefense.runtime.agentsec._logging import (
    JSONFormatter,
    TextFormatter,
    setup_logging,
    get_logger,
)


class TestJSONFormatter:
    """Tests for JSONFormatter."""

    def test_outputs_valid_json(self):
        """Test that JSONFormatter outputs valid parseable JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="aidefense.runtime.agentsec",
            level=logging.WARNING,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        output = formatter.format(record)
        parsed = json.loads(output)
        
        assert parsed["level"] == "WARNING"
        assert parsed["logger"] == "aidefense.runtime.agentsec"
        assert parsed["message"] == "Test message"
        assert "timestamp" in parsed

    def test_includes_extra_fields(self):
        """Test that extra_fields are included in JSON output."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="aidefense.runtime.agentsec",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.extra_fields = {"action": "block", "user_id": "123"}
        
        output = formatter.format(record)
        parsed = json.loads(output)
        
        assert parsed["action"] == "block"
        assert parsed["user_id"] == "123"


class TestTextFormatter:
    """Tests for TextFormatter."""

    def test_outputs_correct_format(self):
        """Test that TextFormatter outputs [logger] LEVEL: message format."""
        formatter = TextFormatter()
        record = logging.LogRecord(
            name="aidefense.runtime.agentsec",
            level=logging.WARNING,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        output = formatter.format(record)
        
        assert output == "[aidefense.runtime.agentsec] WARNING: Test message"

    def test_includes_extra_fields(self):
        """Test that extra_fields are appended as key=value pairs."""
        formatter = TextFormatter()
        record = logging.LogRecord(
            name="aidefense.runtime.agentsec",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.extra_fields = {"action": "allow"}
        
        output = formatter.format(record)
        
        assert "[aidefense.runtime.agentsec] INFO: Test" in output
        assert "action=allow" in output


class TestSetupLogging:
    """Tests for setup_logging function."""

    @pytest.fixture(autouse=True)
    def reset_logger(self):
        """Reset the agentsec logger before each test."""
        logger = logging.getLogger("aidefense.runtime.agentsec")
        logger.handlers.clear()
        logger.setLevel(logging.NOTSET)
        yield
        logger.handlers.clear()

    def test_default_level_is_warning(self):
        """Test that default log level is WARNING."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("AGENTSEC_LOG_LEVEL", None)
            logger = setup_logging(redact=False)
            assert logger.level == logging.WARNING

    def test_log_level_from_env(self):
        """Test that AGENTSEC_LOG_LEVEL env var sets log level."""
        with patch.dict(os.environ, {"AGENTSEC_LOG_LEVEL": "DEBUG"}, clear=False):
            logger = setup_logging(redact=False)
            assert logger.level == logging.DEBUG

    def test_log_level_from_param(self):
        """Test that level parameter overrides env."""
        logger = setup_logging(level="ERROR", redact=False)
        assert logger.level == logging.ERROR

    def test_json_format_from_env(self):
        """Test that AGENTSEC_LOG_FORMAT=json uses JSONFormatter."""
        with patch.dict(os.environ, {"AGENTSEC_LOG_FORMAT": "json"}, clear=False):
            logger = setup_logging(redact=False)
            # Check the base formatter (may be wrapped)
            handler = logger.handlers[0]
            formatter = handler.formatter
            assert isinstance(formatter, JSONFormatter)

    def test_text_format_is_default(self):
        """Test that text format is default."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("AGENTSEC_LOG_FORMAT", None)
            logger = setup_logging(redact=False)
            handler = logger.handlers[0]
            formatter = handler.formatter
            assert isinstance(formatter, TextFormatter)

    def test_file_logging_from_env(self):
        """Test that AGENTSEC_LOG_FILE creates file handler."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".log") as f:
            log_file = f.name
        
        try:
            with patch.dict(os.environ, {"AGENTSEC_LOG_FILE": log_file}, clear=False):
                logger = setup_logging(redact=False)
                
                # Should have 2 handlers: stderr + file
                assert len(logger.handlers) == 2
                
                # Log something and check file
                logger.warning("Test file logging")
                
                # Flush handlers
                for handler in logger.handlers:
                    handler.flush()
                
                with open(log_file) as f:
                    content = f.read()
                    assert "Test file logging" in content
        finally:
            os.unlink(log_file)


class TestGetLogger:
    """Tests for get_logger function."""

    @pytest.fixture(autouse=True)
    def reset_logger(self):
        """Reset the agentsec logger before each test."""
        logger = logging.getLogger("aidefense.runtime.agentsec")
        logger.handlers.clear()
        yield
        logger.handlers.clear()

    def test_returns_configured_logger(self):
        """Test that get_logger returns a configured logger."""
        logger = get_logger()
        assert logger.name == "aidefense.runtime.agentsec"
        assert len(logger.handlers) > 0








