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

import secrets
from unittest.mock import patch, MagicMock
from aidefense import ChatInspectionClient, Config
from aidefense.runtime.models import InspectionConfig, Rule, RuleName, Metadata
from aidefense.exceptions import ValidationError
import uuid


def test_advanced_usage_workflow(capsys):
    dummy_api_key = secrets.token_hex(32)
    dummy_result = MagicMock(
        is_safe=True,
        rules=None,
        classifications=None,
        explanation=None,
        event_id="evt-123",
        severity=None,
    )
    dummy_http_result = MagicMock(is_safe=True)

    with patch.object(
        ChatInspectionClient, "inspect_prompt", return_value=dummy_result
    ), patch.object(
        ChatInspectionClient,
        "inspect_conversation",
        side_effect=ValidationError("Validation error: Empty conversation"),
    ):
        # Custom rules example
        print("\n=== Custom Rules and Entity Types Example ===")
        config = InspectionConfig(
            enabled_rules=[
                Rule(
                    rule_name=RuleName.PII,
                    entity_types=["EMAIL", "PHONE_NUMBER", "CREDIT_CARD"],
                ),
                Rule(rule_name=RuleName.PROMPT_INJECTION),
            ]
        )
        client = ChatInspectionClient(api_key=dummy_api_key)
        result = client.inspect_prompt(
            "My email is john.doe@example.com and my phone is 555-123-4567",
            config=config,
        )
        print(f"Is safe? {result.is_safe}")

        # Error handling example
        print("\n=== Error Handling Example ===")
        try:
            client.inspect_conversation([])
        except ValidationError as e:
            print(f"Validation error: {e}")
        try:
            raise Exception("Timeout or other error: Simulated timeout")
        except Exception as e:
            print(f"Timeout or other error: {e}")

        # Detailed result processing
        print("\n=== Detailed Result Processing Example ===")
        result = client.inspect_prompt(
            "How to hack into a computer system? Also, here's my SSN: 123-45-6789"
        )
        if result.is_safe:
            print("Prompt is safe to use")
        else:
            print(f"Prompt violates policies - Severity: {result.severity}")
            print("Classifications:", result.classifications)
            print("Rule violations:", result.rules)
            print(f"Explanation: {result.explanation}")

        # Metadata usage example
        print("\n=== Metadata Usage Example ===")
        metadata = Metadata(
            user="user-123",
            src_app="example-app",
            client_transaction_id=str(uuid.uuid4()),
        )
        result = client.inspect_prompt("Is this a safe prompt?", metadata=metadata)
        print(f"Request with metadata - is safe? {result.is_safe}")
        print(f"Event ID from response: {result.event_id}")
        print(f"Transaction ID for tracking: {metadata.client_transaction_id}")

        # Timeout configuration
        print("\n=== Timeout Configuration Example ===")
        config = Config(timeout=10)
        client = ChatInspectionClient(api_key=dummy_api_key, config=config)
        result1 = client.inspect_prompt("This is a normal prompt")
        print(f"Using default timeout - is safe? {result1.is_safe}")
        result2 = client.inspect_prompt(
            "This is a prompt with custom timeout", timeout=15
        )
        print(f"Using custom timeout - is safe? {result2.is_safe}")

    out = capsys.readouterr().out
    assert "=== Custom Rules and Entity Types Example ===" in out
    assert "Is safe? True" in out
    assert "=== Error Handling Example ===" in out
    assert "Validation error: Empty conversation" in out
    assert "Timeout or other error: Simulated timeout" in out
    assert "=== Detailed Result Processing Example ===" in out
    assert "Prompt is safe to use" in out or "Prompt violates policies" in out
    assert "=== Metadata Usage Example ===" in out
    assert "Request with metadata - is safe? True" in out
    assert "Event ID from response: evt-123" in out
    assert "=== Timeout Configuration Example ===" in out
    assert "Using default timeout - is safe? True" in out
    assert "Using custom timeout - is safe? True" in out
