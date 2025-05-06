import pytest
from aidefense.runtime.inspection_client import InspectionClient
from aidefense.runtime.models import InspectResponse, Classification, Severity, Rule, RuleName
from aidefense.config import Config
from aidefense.exceptions import ValidationError
from typing import Dict, Any, Optional
import uuid


# Create a valid format dummy API key for testing (must be 64 characters)
TEST_API_KEY = "0123456789" * 6 + "0123"  # 64 characters


@pytest.fixture(autouse=True)
def reset_config_singleton():
    """Reset Config singleton before each test."""
    # Reset the singleton instance
    Config._instance = None
    yield
    # Clean up after test
    Config._instance = None


class TestInspectionClient(InspectionClient):
    """
    Test implementation of the abstract InspectionClient for testing purposes.
    """
    
    def __init__(self, api_key: str, config: Optional[Config] = None):
        super().__init__(api_key, config)
        self.endpoint = "https://test.endpoint/api/v1/inspect/test"
    
    def _inspect(self, *args, **kwargs):
        # Simple implementation for testing
        return {"result": "test"}


def test_parse_inspect_response_basic():
    """Test parsing a basic inspection response."""
    client = TestInspectionClient(TEST_API_KEY)
    
    response_data = {
        "is_safe": True,
        "classifications": [],
        "explanation": "No issues found"
    }
    
    result = client._parse_inspect_response(response_data)
    
    assert isinstance(result, InspectResponse)
    assert result.is_safe is True
    assert len(result.classifications) == 0
    assert result.explanation == "No issues found"


def test_parse_inspect_response_with_classifications():
    """Test parsing a response with classifications."""
    client = TestInspectionClient(TEST_API_KEY)
    
    response_data = {
        "is_safe": False,
        "classifications": ["SECURITY_VIOLATION", "PII"],
        "explanation": "Issues found"
    }
    
    result = client._parse_inspect_response(response_data)
    
    assert isinstance(result, InspectResponse)
    assert result.is_safe is False
    # Only SECURITY_VIOLATION is a valid Classification enum value, PII is invalid
    assert len(result.classifications) == 1
    assert Classification.SECURITY_VIOLATION in result.classifications
    # PII is not in Classification enum, so it shouldn't be included
    assert result.explanation == "Issues found"


def test_parse_inspect_response_with_invalid_classification():
    """Test parsing a response with an invalid classification type."""
    client = TestInspectionClient(TEST_API_KEY)
    
    response_data = {
        "is_safe": False,
        "classifications": ["SECURITY_VIOLATION", "INVALID_TYPE"],
        "explanation": "Issues found"
    }
    
    result = client._parse_inspect_response(response_data)
    
    # Should ignore the invalid classification
    assert len(result.classifications) == 1
    assert Classification.SECURITY_VIOLATION in result.classifications


def test_parse_inspect_response_with_rules():
    """Test parsing a response with rule information."""
    client = TestInspectionClient(TEST_API_KEY)
    
    response_data = {
        "is_safe": False,
        "rules": [
            {
                "rule_name": "PROMPT_INJECTION",
                "rule_id": 1,
                "classification": "SECURITY_VIOLATION"
            },
            {
                "rule_name": "PII",
                "rule_id": 2,
                "entity_types": ["EMAIL", "PHONE"],
                "classification": "PII"
            }
        ]
    }
    
    result = client._parse_inspect_response(response_data)
    
    assert len(result.rules) == 2
    # Compare using string value rather than enum since our implementation preserves the string
    assert result.rules[0].rule_name == "PROMPT_INJECTION"
    assert result.rules[0].rule_id == 1
    # Prompt Injection doesn't have entity types
    assert result.rules[0].classification == Classification.SECURITY_VIOLATION
    
    assert result.rules[1].rule_name == "PII"
    assert result.rules[1].rule_id == 2
    assert "EMAIL" in result.rules[1].entity_types
    assert "PHONE" in result.rules[1].entity_types
    # PII is not in Classification enum, so check string value
    assert result.rules[1].classification == "PII"


def test_parse_inspect_response_with_custom_rule_name():
    """Test parsing a response with a custom rule name not in the enum."""
    client = TestInspectionClient(TEST_API_KEY)
    
    response_data = {
        "is_safe": False,
        "rules": [
            {
                "rule_name": "Custom Rule",  # Not in RuleName enum
                "rule_id": 100,
                "classification": "SECURITY_VIOLATION"
            }
        ]
    }
    
    result = client._parse_inspect_response(response_data)
    
    # Should keep the string rule name if not in enum
    assert len(result.rules) == 1
    assert result.rules[0].rule_name == "Custom Rule"
    assert result.rules[0].rule_id == 100
    assert result.rules[0].classification == Classification.SECURITY_VIOLATION


def test_parse_inspect_response_with_severity():
    """Test parsing a response with severity information."""
    client = TestInspectionClient(TEST_API_KEY)
    
    response_data = {
        "is_safe": False,
        "severity": "HIGH",
        "explanation": "High severity issue detected"
    }
    
    result = client._parse_inspect_response(response_data)
    
    assert result.severity == Severity.HIGH
    assert result.explanation == "High severity issue detected"


def test_parse_inspect_response_with_invalid_severity():
    """Test parsing a response with invalid severity."""
    client = TestInspectionClient(TEST_API_KEY)
    
    response_data = {
        "is_safe": False,
        "severity": "UNKNOWN_LEVEL",  # Not in Severity enum
        "explanation": "Issue detected"
    }
    
    result = client._parse_inspect_response(response_data)
    
    # Invalid severity should be None
    assert result.severity is None


def test_parse_inspect_response_with_metadata():
    """Test parsing a response with transaction metadata."""
    client = TestInspectionClient(TEST_API_KEY)
    
    event_id = str(uuid.uuid4())
    transaction_id = "tx-12345"
    
    response_data = {
        "is_safe": True,
        "event_id": event_id,
        "client_transaction_id": transaction_id
    }
    
    result = client._parse_inspect_response(response_data)
    
    assert result.event_id == event_id
    assert result.client_transaction_id == transaction_id


def test_parse_inspect_response_with_attack_technique():
    """Test parsing a response with attack technique information."""
    client = TestInspectionClient(TEST_API_KEY)
    
    response_data = {
        "is_safe": False,
        "attack_technique": "INJECTION",
        "explanation": "Injection attempt detected"
    }
    
    result = client._parse_inspect_response(response_data)
    
    assert result.attack_technique == "INJECTION"
    assert result.explanation == "Injection attempt detected"


def test_parse_inspect_response_complex():
    """Test parsing a complex response with all possible fields."""
    client = TestInspectionClient(TEST_API_KEY)
    
    response_data = {
        "classifications": [
            "SECURITY_VIOLATION"
        ],
        "is_safe": False,
        "severity": "NONE_SEVERITY",
        "rules": [
            {
                "rule_name": "Prompt Injection",
                "rule_id": 0,
                "entity_types": [
                    ""
                ],
                "classification": "SECURITY_VIOLATION"
            }
        ],
        "attack_technique": "NONE_ATTACK_TECHNIQUE",
        "explanation": "Security violation detected",
        "client_transaction_id": "tx-9876",
        "event_id": "b403de99-8d19-408f-8184-ec6d7907f508"
    }
    
    result = client._parse_inspect_response(response_data)
    
    # Verify all fields were parsed correctly
    assert isinstance(result, InspectResponse)
    assert result.is_safe is False
    assert len(result.classifications) == 1
    assert Classification.SECURITY_VIOLATION in result.classifications
    assert result.severity == Severity.NONE_SEVERITY
    assert len(result.rules) == 1
    assert result.rules[0].rule_name == "Prompt Injection"
    assert result.rules[0].classification == Classification.SECURITY_VIOLATION
    assert result.attack_technique == "NONE_ATTACK_TECHNIQUE"
    assert result.explanation == "Security violation detected"
    assert result.client_transaction_id == "tx-9876"
    assert result.event_id == "b403de99-8d19-408f-8184-ec6d7907f508"
