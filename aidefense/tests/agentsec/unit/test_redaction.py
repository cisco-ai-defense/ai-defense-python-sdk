"""Tests for the redaction module (Task Group 2)."""

import logging
import pytest

from aidefense.runtime.agentsec._redaction import (
    LogRedactor,
    RedactingFormatter,
    get_redactor,
    configure_redaction,
    reset_redactor,
    DEFAULT_REDACT_PATTERNS,
)
from aidefense.runtime.agentsec._logging import TextFormatter


class TestLogRedactor:
    """Tests for LogRedactor class."""

    @pytest.fixture(autouse=True)
    def reset(self):
        """Reset redactor before each test."""
        reset_redactor()
        yield
        reset_redactor()

    def test_redacts_api_key_equals(self):
        """Test that api_key=xxx patterns are redacted."""
        redactor = LogRedactor()
        text = "Making request with api_key=sk-abc123xyz"
        result = redactor.redact(text)
        assert "sk-abc123xyz" not in result
        assert "[REDACTED]" in result

    def test_redacts_bearer_tokens(self):
        """Test that Bearer tokens are redacted."""
        redactor = LogRedactor()
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        result = redactor.redact(text)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "[REDACTED]" in result

    def test_redacts_openai_sk_keys(self):
        """Test that OpenAI sk-* API keys are redacted."""
        redactor = LogRedactor()
        text = "Using key sk-proj-abcdefghij1234567890abcdefghij"
        result = redactor.redact(text)
        assert "sk-proj-abcdefghij1234567890abcdefghij" not in result
        assert "[REDACTED]" in result

    def test_enabled_false_skips_redaction(self):
        """Test that enabled=False skips all redaction."""
        redactor = LogRedactor(enabled=False)
        text = "Secret api_key=supersecret123"
        result = redactor.redact(text)
        assert result == text
        assert "supersecret123" in result

    def test_add_pattern_adds_custom_pattern(self):
        """Test that add_pattern() adds custom patterns."""
        redactor = LogRedactor()
        # Add pattern for custom format
        redactor.add_pattern(r"my-secret-\d+")
        
        text = "Found my-secret-12345 in config"
        result = redactor.redact(text)
        assert "my-secret-12345" not in result
        assert "[REDACTED]" in result

    def test_custom_replacement_string(self):
        """Test that custom replacement string is used."""
        redactor = LogRedactor(replacement="***")
        text = "api_key=secret123"
        result = redactor.redact(text)
        assert "***" in result
        assert "[REDACTED]" not in result


class TestRedactingFormatter:
    """Tests for RedactingFormatter wrapper."""

    @pytest.fixture(autouse=True)
    def reset(self):
        """Reset redactor before each test."""
        reset_redactor()
        yield
        reset_redactor()

    def test_wraps_base_formatter(self):
        """Test that RedactingFormatter wraps base formatter output."""
        base = TextFormatter()
        formatter = RedactingFormatter(base)
        
        record = logging.LogRecord(
            name="agentsec",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Request with api_key=secret123",
            args=(),
            exc_info=None,
        )
        
        output = formatter.format(record)
        
        # Should have formatted message
        assert "[agentsec] INFO:" in output
        # Should have redacted content
        assert "secret123" not in output
        assert "[REDACTED]" in output

    def test_preserves_non_sensitive_content(self):
        """Test that non-sensitive content is preserved."""
        base = TextFormatter()
        formatter = RedactingFormatter(base)
        
        record = logging.LogRecord(
            name="agentsec",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Normal log message with no secrets",
            args=(),
            exc_info=None,
        )
        
        output = formatter.format(record)
        assert "Normal log message with no secrets" in output


class TestGlobalRedactor:
    """Tests for global redactor functions."""

    @pytest.fixture(autouse=True)
    def reset(self):
        """Reset redactor before each test."""
        reset_redactor()
        yield
        reset_redactor()

    def test_get_redactor_returns_instance(self):
        """Test that get_redactor returns a LogRedactor."""
        redactor = get_redactor()
        assert isinstance(redactor, LogRedactor)

    def test_configure_redaction_disabled(self):
        """Test that configure_redaction can disable redaction."""
        configure_redaction(enabled=False)
        redactor = get_redactor()
        
        text = "api_key=secret"
        result = redactor.redact(text)
        assert result == text

    def test_configure_redaction_custom_patterns(self):
        """Test that configure_redaction accepts custom patterns."""
        configure_redaction(patterns=[r"custom-\d+"])
        redactor = get_redactor()
        
        # Should redact custom pattern
        assert "[REDACTED]" in redactor.redact("custom-123")
        # Should NOT redact default patterns anymore
        assert "api_key=secret" == redactor.redact("api_key=secret")


class TestDefaultPatterns:
    """Tests for default redaction patterns."""

    def test_default_patterns_exist(self):
        """Test that default patterns list is not empty."""
        assert len(DEFAULT_REDACT_PATTERNS) > 0

    def test_all_default_patterns_compile(self):
        """Test that all default patterns are valid regex."""
        import re
        for pattern in DEFAULT_REDACT_PATTERNS:
            # Should not raise
            re.compile(pattern)








