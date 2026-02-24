# Copyright 2026 Cisco Systems, Inc. and its affiliates
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

import uuid

import pytest

from aidefense.runtime.inspection_client import AsyncInspectionClient, BaseInspectionClient
from aidefense.runtime.chat_inspect import BaseChatInspectionClient
from aidefense.runtime.models import (
    InspectResponse,
    Classification,
    Severity,
    Rule,
    RuleName,
)
from aidefense.config import AsyncConfig
from aidefense.exceptions import ValidationError


# Create a valid format dummy API key for testing (must be 64 characters)
TEST_API_KEY = "0123456789" * 6 + "0123"  # 64 characters

# Apply the shared reset_async_config fixture from conftest.py to all tests in this module
pytestmark = pytest.mark.usefixtures("reset_async_config")


# ============================================================================
# Abstract Class Guard Tests
# ============================================================================


@pytest.mark.asyncio
async def test_base_inspection_client_cannot_be_instantiated():
    """Test that BaseInspectionClient raises TypeError when instantiated directly."""
    async_config = AsyncConfig()
    with pytest.raises(TypeError, match="cannot be instantiated directly"):
        BaseInspectionClient(api_key=TEST_API_KEY, config=async_config)


@pytest.mark.asyncio
async def test_async_inspection_client_cannot_be_instantiated():
    """Test that AsyncInspectionClient raises TypeError when instantiated directly."""
    async_config = AsyncConfig()
    with pytest.raises(TypeError, match="cannot be instantiated directly"):
        AsyncInspectionClient(api_key=TEST_API_KEY, config=async_config)


@pytest.mark.asyncio
async def test_base_chat_inspection_client_cannot_be_instantiated():
    """Test that BaseChatInspectionClient raises TypeError when instantiated directly."""
    async_config = AsyncConfig()
    with pytest.raises(TypeError, match="cannot be instantiated directly"):
        BaseChatInspectionClient(api_key=TEST_API_KEY, config=async_config)


# ============================================================================
# Test Implementation for Abstract Client
# ============================================================================


class AsyncInspectionClientImpl(AsyncInspectionClient):
    """
    Test implementation of the abstract AsyncInspectionClient for testing purposes.
    """

    def __init__(self, api_key: str, config: AsyncConfig):
        super().__init__(api_key, config)
        self.endpoint = "https://test.endpoint/api/v1/inspect/test"

    async def _inspect(self, *args, **kwargs):
        # Simple async implementation for testing
        return {"result": "test"}


@pytest.mark.asyncio
async def test_parse_inspect_response_basic():
    """Test parsing a basic async inspection response."""
    config = AsyncConfig()
    client = AsyncInspectionClientImpl(TEST_API_KEY, config)

    response_data = {
        "is_safe": True,
        "classifications": [],
        "explanation": "No issues found",
    }

    result = client._parse_inspect_response(response_data)

    assert isinstance(result, InspectResponse)
    assert result.is_safe is True
    assert len(result.classifications) == 0
    assert result.explanation == "No issues found"


@pytest.mark.asyncio
async def test_parse_inspect_response_with_classifications():
    """Test parsing an async response with classifications."""
    config = AsyncConfig()
    client = AsyncInspectionClientImpl(TEST_API_KEY, config)

    response_data = {
        "is_safe": False,
        "classifications": ["SECURITY_VIOLATION", "PII"],
        "explanation": "Issues found",
    }

    result = client._parse_inspect_response(response_data)

    assert isinstance(result, InspectResponse)
    assert result.is_safe is False
    # Only SECURITY_VIOLATION is a valid Classification enum value, PII is invalid
    assert len(result.classifications) == 1
    assert Classification.SECURITY_VIOLATION in result.classifications
    # PII is not in Classification enum, so it shouldn't be included
    assert result.explanation == "Issues found"


@pytest.mark.asyncio
async def test_parse_inspect_response_with_invalid_classification():
    """Test parsing an async response with an invalid classification type."""
    config = AsyncConfig()
    client = AsyncInspectionClientImpl(TEST_API_KEY, config)

    response_data = {
        "is_safe": False,
        "classifications": ["SECURITY_VIOLATION", "INVALID_TYPE"],
        "explanation": "Issues found",
    }

    result = client._parse_inspect_response(response_data)

    # Should ignore the invalid classification
    assert len(result.classifications) == 1
    assert Classification.SECURITY_VIOLATION in result.classifications


@pytest.mark.asyncio
async def test_parse_inspect_response_with_rules():
    """Test parsing an async response with rule information."""
    config = AsyncConfig()
    client = AsyncInspectionClientImpl(TEST_API_KEY, config)

    response_data = {
        "is_safe": False,
        "rules": [
            {
                "rule_name": "PROMPT_INJECTION",
                "rule_id": 1,
                "classification": "SECURITY_VIOLATION",
            },
            {
                "rule_name": "PII",
                "rule_id": 2,
                "entity_types": ["EMAIL", "PHONE"],
                "classification": "PII",
            },
        ],
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


@pytest.mark.asyncio
async def test_parse_inspect_response_with_custom_rule_name():
    """Test parsing an async response with a custom rule name not in the enum."""
    config = AsyncConfig()
    client = AsyncInspectionClientImpl(TEST_API_KEY, config)

    response_data = {
        "is_safe": False,
        "rules": [
            {
                "rule_name": "Custom Rule",  # Not in RuleName enum
                "rule_id": 100,
                "classification": "SECURITY_VIOLATION",
            }
        ],
    }

    result = client._parse_inspect_response(response_data)

    # Should keep the string rule name if not in enum
    assert len(result.rules) == 1
    assert result.rules[0].rule_name == "Custom Rule"
    assert result.rules[0].rule_id == 100
    assert result.rules[0].classification == Classification.SECURITY_VIOLATION


@pytest.mark.asyncio
async def test_parse_inspect_response_with_severity():
    """Test parsing an async response with severity information."""
    config = AsyncConfig()
    client = AsyncInspectionClientImpl(TEST_API_KEY, config)

    response_data = {
        "is_safe": False,
        "severity": "HIGH",
        "explanation": "High severity issue detected",
    }

    result = client._parse_inspect_response(response_data)

    assert result.severity == Severity.HIGH
    assert result.explanation == "High severity issue detected"


@pytest.mark.asyncio
async def test_parse_inspect_response_with_invalid_severity():
    """Test parsing an async response with invalid severity."""
    config = AsyncConfig()
    client = AsyncInspectionClientImpl(TEST_API_KEY, config)

    response_data = {
        "is_safe": False,
        "severity": "UNKNOWN_LEVEL",  # Not in Severity enum
        "explanation": "Issue detected",
    }

    result = client._parse_inspect_response(response_data)

    # Invalid severity should be None
    assert result.severity is None


@pytest.mark.asyncio
async def test_parse_inspect_response_with_metadata():
    """Test parsing an async response with transaction metadata."""
    config = AsyncConfig()
    client = AsyncInspectionClientImpl(TEST_API_KEY, config)

    event_id = str(uuid.uuid4())
    transaction_id = "tx-12345"

    response_data = {
        "is_safe": True,
        "event_id": event_id,
        "client_transaction_id": transaction_id,
    }

    result = client._parse_inspect_response(response_data)

    assert result.event_id == event_id
    assert result.client_transaction_id == transaction_id


@pytest.mark.asyncio
async def test_parse_inspect_response_with_attack_technique():
    """Test parsing an async response with attack technique information."""
    config = AsyncConfig()
    client = AsyncInspectionClientImpl(TEST_API_KEY, config)

    response_data = {
        "is_safe": False,
        "attack_technique": "INJECTION",
        "explanation": "Injection attempt detected",
    }

    result = client._parse_inspect_response(response_data)

    assert result.attack_technique == "INJECTION"
    assert result.explanation == "Injection attempt detected"


@pytest.mark.asyncio
async def test_parse_inspect_response_complex():
    """Test parsing a complex async response with all possible fields."""
    config = AsyncConfig()
    client = AsyncInspectionClientImpl(TEST_API_KEY, config)

    response_data = {
        "classifications": ["SECURITY_VIOLATION"],
        "is_safe": False,
        "severity": "NONE_SEVERITY",
        "rules": [
            {
                "rule_name": "Prompt Injection",
                "rule_id": 0,
                "entity_types": [""],
                "classification": "SECURITY_VIOLATION",
            }
        ],
        "attack_technique": "NONE_ATTACK_TECHNIQUE",
        "explanation": "Security violation detected",
        "client_transaction_id": "tx-9876",
        "event_id": "b403de99-8d19-408f-8184-ec6d7907f508",
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


@pytest.mark.asyncio
async def test_parse_inspect_response_with_multiple_classifications():
    """Test parsing an async response with multiple valid classifications."""
    config = AsyncConfig()
    client = AsyncInspectionClientImpl(TEST_API_KEY, config)

    response_data = {
        "is_safe": False,
        "classifications": ["SECURITY_VIOLATION", "PRIVACY_VIOLATION"],
        "explanation": "Multiple violations detected",
    }

    result = client._parse_inspect_response(response_data)

    assert result.is_safe is False
    assert len(result.classifications) == 2
    assert Classification.SECURITY_VIOLATION in result.classifications
    assert Classification.PRIVACY_VIOLATION in result.classifications


@pytest.mark.asyncio
async def test_parse_inspect_response_minimal():
    """Test parsing an async response with minimal required fields only."""
    config = AsyncConfig()
    client = AsyncInspectionClientImpl(TEST_API_KEY, config)

    response_data = {
        "is_safe": True,
    }

    result = client._parse_inspect_response(response_data)

    assert isinstance(result, InspectResponse)
    assert result.is_safe is True
    # All optional fields should be None or empty
    assert result.classifications == []
    assert result.rules is None
    assert result.severity is None
    assert result.explanation is None
