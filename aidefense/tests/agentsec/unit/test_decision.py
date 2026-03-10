"""Tests for Decision type and SecurityPolicyError (Task 2.1, Task Group 6)."""

import pytest

from aidefense.runtime.agentsec import Decision, SecurityPolicyError


class TestDecision:
    """Test Decision NamedTuple."""

    def test_decision_all_action_types(self):
        """Test Decision creation with all action types."""
        allow = Decision(action="allow", reasons=[])
        block = Decision(action="block", reasons=["violation"])
        sanitize = Decision(action="sanitize", reasons=["pii"])
        monitor = Decision(action="monitor_only", reasons=["logged"])
        
        assert allow.action == "allow"
        assert block.action == "block"
        assert sanitize.action == "sanitize"
        assert monitor.action == "monitor_only"

    def test_decision_factory_methods(self):
        """Test Decision factory methods."""
        allow = Decision.allow()
        assert allow.action == "allow"
        assert allow.reasons == []
        
        block = Decision.block(reasons=["security violation"])
        assert block.action == "block"
        assert block.reasons == ["security violation"]
        
        sanitize = Decision.sanitize(reasons=["pii detected"])
        assert sanitize.action == "sanitize"
        
        monitor = Decision.monitor_only(reasons=["audit log"])
        assert monitor.action == "monitor_only"


class TestDecisionParameterized:
    """Parameterized tests for Decision (Task Group 6)."""

    @pytest.mark.parametrize("action,expected_allows", [
        ("allow", True),
        ("block", False),
        ("sanitize", True),  # sanitize allows with modified content
        ("monitor_only", True),  # monitor_only allows (just logs)
    ])
    def test_decision_allows(self, action: str, expected_allows: bool):
        """Test Decision.allows() for all action types."""
        decision = Decision(action=action, reasons=[], sanitized_content=None)
        assert decision.allows() == expected_allows

    @pytest.mark.parametrize("action", ["allow", "block", "sanitize", "monitor_only"])
    def test_decision_action_valid(self, action: str):
        """Test Decision creation with valid action types."""
        decision = Decision(action=action, reasons=["test_reason"])
        assert decision.action == action

    @pytest.mark.parametrize("reasons", [
        [],
        ["single_reason"],
        ["reason1", "reason2"],
        ["reason1", "reason2", "reason3"],
    ])
    def test_decision_with_reasons(self, reasons: list):
        """Test Decision with various reasons lists."""
        decision = Decision(action="block", reasons=reasons)
        assert decision.reasons == reasons

    @pytest.mark.parametrize("content", [
        None,
        "",
        "Sanitized content here",
        "Content with\nnewlines\nand special chars: <>\"'",
    ])
    def test_decision_with_sanitized_content(self, content):
        """Test Decision with various sanitized_content values."""
        decision = Decision(
            action="sanitize",
            reasons=["content_modified"],
            sanitized_content=content
        )
        assert decision.sanitized_content == content


class TestDecisionRichFields:
    """Test Decision with new rich result fields."""

    def test_decision_with_severity(self):
        """Test Decision with severity field."""
        decision = Decision(
            action="block",
            reasons=["violation"],
            severity="high",
        )
        assert decision.severity == "high"

    def test_decision_with_classifications(self):
        """Test Decision with classifications field."""
        decision = Decision(
            action="block",
            reasons=["pii detected"],
            classifications=["pii", "email"],
        )
        assert decision.classifications == ["pii", "email"]

    def test_decision_with_rules(self):
        """Test Decision with rules field."""
        rules = [
            {"rule_name": "PII", "classification": "VIOLATION"},
            {"rule_name": "jailbreak", "classification": "NONE"},
        ]
        decision = Decision(
            action="block",
            reasons=["rule triggered"],
            rules=rules,
        )
        assert decision.rules == rules

    def test_decision_with_explanation(self):
        """Test Decision with explanation field."""
        decision = Decision(
            action="block",
            reasons=["blocked"],
            explanation="Content contains personally identifiable information.",
        )
        assert decision.explanation == "Content contains personally identifiable information."

    def test_decision_with_event_id(self):
        """Test Decision with event_id field."""
        decision = Decision(
            action="allow",
            reasons=[],
            event_id="evt-12345-abcde",
        )
        assert decision.event_id == "evt-12345-abcde"

    def test_decision_all_rich_fields(self):
        """Test Decision with all rich result fields."""
        decision = Decision.block(
            reasons=["pii_detected"],
            severity="critical",
            classifications=["pii", "ssn"],
            rules=[{"rule_name": "PII", "classification": "CRITICAL_VIOLATION"}],
            explanation="Social security number detected in content.",
            event_id="evt-67890-fghij",
        )
        
        assert decision.action == "block"
        assert decision.severity == "critical"
        assert decision.classifications == ["pii", "ssn"]
        assert decision.rules == [{"rule_name": "PII", "classification": "CRITICAL_VIOLATION"}]
        assert decision.explanation == "Social security number detected in content."
        assert decision.event_id == "evt-67890-fghij"

    def test_decision_is_safe_property(self):
        """Test Decision.is_safe property."""
        allow = Decision(action="allow", reasons=[])
        block = Decision(action="block", reasons=["violation"])
        sanitize = Decision(action="sanitize", reasons=["pii"])
        monitor = Decision(action="monitor_only", reasons=["logged"])
        
        # is_safe should be True for all actions except block
        assert allow.is_safe is True
        assert block.is_safe is False
        assert sanitize.is_safe is True
        assert monitor.is_safe is True

    def test_decision_is_safe_matches_allows(self):
        """Test that is_safe property matches allows() method."""
        for action in ["allow", "block", "sanitize", "monitor_only"]:
            decision = Decision(action=action, reasons=["test"])
            assert decision.is_safe == decision.allows()

    def test_decision_equality_with_rich_fields(self):
        """Test Decision equality includes rich fields."""
        d1 = Decision(
            action="block",
            reasons=["x"],
            severity="high",
            classifications=["pii"],
            event_id="evt-1",
        )
        d2 = Decision(
            action="block",
            reasons=["x"],
            severity="high",
            classifications=["pii"],
            event_id="evt-1",
        )
        d3 = Decision(
            action="block",
            reasons=["x"],
            severity="low",  # Different severity
            classifications=["pii"],
            event_id="evt-1",
        )
        
        assert d1 == d2
        assert d1 != d3

    def test_decision_repr_with_rich_fields(self):
        """Test Decision repr includes rich fields when set."""
        decision = Decision(
            action="block",
            reasons=["violation"],
            severity="high",
            event_id="evt-123",
        )
        repr_str = repr(decision)
        
        assert "severity='high'" in repr_str
        assert "event_id='evt-123'" in repr_str


class TestSecurityPolicyError:
    """Test SecurityPolicyError exception."""

    def test_security_policy_error_has_decision(self):
        """Test SecurityPolicyError includes decision attribute."""
        decision = Decision.block(reasons=["test violation"])
        error = SecurityPolicyError(decision)
        
        assert error.decision is decision
        assert error.decision.action == "block"

    def test_security_policy_error_message_formatting(self):
        """Test SecurityPolicyError message formatting."""
        decision = Decision.block(reasons=["reason1", "reason2"])
        error = SecurityPolicyError(decision)
        
        assert "reason1" in str(error)
        assert "reason2" in str(error)
        
        # Test custom message
        error_custom = SecurityPolicyError(decision, message="Custom error")
        assert str(error_custom) == "Custom error"


