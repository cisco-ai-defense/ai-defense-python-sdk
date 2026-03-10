"""Tests for agentsec exception hierarchy."""

import pytest

from aidefense.runtime.agentsec import (
    AgentsecError,
    ConfigurationError,
    ValidationError,
    InspectionTimeoutError,
    InspectionNetworkError,
    SecurityPolicyError,
    Decision,
)


class TestAgentsecErrorHierarchy:
    """Test exception class hierarchy."""

    def test_agentsec_error_is_base_exception(self):
        """Test AgentsecError is an Exception."""
        error = AgentsecError("test error")
        assert isinstance(error, Exception)
        assert str(error) == "test error"

    def test_configuration_error_inherits_agentsec_error(self):
        """Test ConfigurationError inherits from AgentsecError."""
        error = ConfigurationError("invalid config")
        assert isinstance(error, AgentsecError)
        assert isinstance(error, Exception)
        assert str(error) == "invalid config"

    def test_validation_error_inherits_agentsec_error(self):
        """Test ValidationError inherits from AgentsecError."""
        error = ValidationError("invalid input")
        assert isinstance(error, AgentsecError)
        assert str(error) == "invalid input"

    def test_inspection_timeout_error_inherits_agentsec_error(self):
        """Test InspectionTimeoutError inherits from AgentsecError."""
        error = InspectionTimeoutError("timeout after 1000ms", timeout_ms=1000)
        assert isinstance(error, AgentsecError)
        assert str(error) == "timeout after 1000ms"
        assert error.timeout_ms == 1000

    def test_inspection_network_error_inherits_agentsec_error(self):
        """Test InspectionNetworkError inherits from AgentsecError."""
        error = InspectionNetworkError("connection refused")
        assert isinstance(error, AgentsecError)
        assert str(error) == "connection refused"

    def test_security_policy_error_inherits_agentsec_error(self):
        """Test SecurityPolicyError inherits from AgentsecError."""
        decision = Decision.block(reasons=["violation"])
        error = SecurityPolicyError(decision)
        assert isinstance(error, AgentsecError)
        assert error.decision == decision


class TestInspectionTimeoutError:
    """Test InspectionTimeoutError specifics."""

    def test_timeout_error_with_timeout_ms(self):
        """Test InspectionTimeoutError stores timeout_ms."""
        error = InspectionTimeoutError("timed out", timeout_ms=5000)
        assert error.timeout_ms == 5000

    def test_timeout_error_without_timeout_ms(self):
        """Test InspectionTimeoutError with default timeout_ms."""
        error = InspectionTimeoutError("timed out")
        assert error.timeout_ms is None

    def test_timeout_error_repr(self):
        """Test InspectionTimeoutError repr."""
        error = InspectionTimeoutError("timed out", timeout_ms=1000)
        repr_str = repr(error)
        assert "timeout_ms=1000" in repr_str


class TestExceptionChaining:
    """Test exception chaining support."""

    def test_catch_all_agentsec_errors(self):
        """Test catching all agentsec errors with base class."""
        exceptions = [
            AgentsecError("base"),
            ConfigurationError("config"),
            ValidationError("validation"),
            InspectionTimeoutError("timeout", timeout_ms=1000),
            InspectionNetworkError("network"),
            SecurityPolicyError(Decision.block(reasons=["test"])),
        ]
        
        for exc in exceptions:
            try:
                raise exc
            except AgentsecError as e:
                assert isinstance(e, AgentsecError)
                assert e is exc
            except Exception:
                pytest.fail(f"{type(exc).__name__} not caught by AgentsecError")

    def test_exception_from_clause(self):
        """Test exception chaining with 'from' clause."""
        original = ValueError("original error")
        
        try:
            try:
                raise original
            except ValueError as e:
                raise InspectionNetworkError("wrapped") from e
        except InspectionNetworkError as e:
            assert e.__cause__ == original
