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

"""
Example: Advanced usage scenarios for AI Defense SDK

This script demonstrates:
- Custom inspection rules and entity types
- Error handling
- Detailed inspection result processing
- Using metadata
- Timeout configuration
"""

import uuid
from aidefense import ChatInspectionClient, HttpInspectionClient, Config
from aidefense.runtime.models import (
    Metadata,
    InspectionConfig,
    Rule,
    RuleName,
    Classification
)
from aidefense.exceptions import ValidationError
from aidefense.runtime.chat_models import Message, Role


def custom_rules_example():
    """Example of using custom inspection rules and entity types."""
    print("\n=== Custom Rules and Entity Types Example ===")

    # Create a client
    client = ChatInspectionClient(api_key="YOUR_API_KEY")

    # Create a custom inspection configuration with specific rules
    config = InspectionConfig(
        enabled_rules=[
            # Only check for PII with specific entity types
            Rule(
                rule_name=RuleName.PII,
                entity_types=["EMAIL", "PHONE_NUMBER", "CREDIT_CARD"]
            ),
            # Check for prompt injection
            Rule(rule_name=RuleName.PROMPT_INJECTION)
        ]
    )

    # Inspect a prompt with the custom rules
    prompt = "My email is john.doe@example.com and my phone is 555-123-4567"
    result = client.inspect_prompt(prompt, config=config)

    print(f"Is safe? {result.is_safe}")
    if not result.is_safe:
        print("Violated rules:")
        for rule in result.rules or []:
            print(f"  - {rule.rule_name}: {rule.entity_types}")


def error_handling_example():
    """Example of handling different types of errors."""
    print("\n=== Error Handling Example ===")

    client = ChatInspectionClient(api_key="YOUR_API_KEY")

    # Validation error example
    try:
        # Empty list of messages will cause validation error
        client.inspect_conversation([])
    except ValidationError as e:
        print(f"Validation error: {e}")

    # Handling timeout
    try:
        # Set a very short timeout to demonstrate timeout handling
        result = client.inspect_prompt(
            "This is a prompt that will cause a timeout",
            timeout=1  # 1 second timeout (very short)
        )
    except Exception as e:
        print(f"Timeout or other error: {e}")


def detailed_result_processing():
    """Example of processing inspection results in detail."""
    print("\n=== Detailed Result Processing Example ===")

    client = ChatInspectionClient(api_key="YOUR_API_KEY")

    # Use a prompt that might trigger policy violations
    prompt = "How to hack into a computer system? Also, here's my SSN: 123-45-6789"
    result = client.inspect_prompt(prompt)

    # Process the result in detail
    if result.is_safe:
        print("Prompt is safe to use")
    else:
        print(f"Prompt violates policies - Severity: {result.severity}")

        # Process classifications
        if result.classifications:
            print("Classifications:")
            for classification in result.classifications:
                print(f"  - {classification.name}")

        # Process rule violations
        if result.rules:
            print("Rule violations:")
            for rule in result.rules:
                print(f"  - Rule: {rule.rule_name}")
                if rule.entity_types:
                    print(f"    Entity types: {', '.join(rule.entity_types)}")
                if hasattr(rule, 'is_violated') and rule.is_violated:
                    print(f"    Is violated: {rule.is_violated}")

        # Get explanation
        if result.explanation:
            print(f"Explanation: {result.explanation}")


def metadata_usage_example():
    """Example of using metadata with inspection requests."""
    print("\n=== Metadata Usage Example ===")

    client = ChatInspectionClient(api_key="YOUR_API_KEY")

    # Create metadata for the request
    metadata = Metadata(
        user="user-123",
        src_app="example-app",
        client_transaction_id=str(uuid.uuid4()),
        # Add any additional key-value pairs
        custom_field="custom value"
    )

    # Use metadata with the inspection request
    result = client.inspect_prompt(
        "Is this a safe prompt?",
        metadata=metadata
    )

    print(f"Request with metadata - is safe? {result.is_safe}")
    print(f"Event ID from response: {result.event_id}")

    # Metadata can be tracked by your application for analytics or logging
    print(f"Transaction ID for tracking: {metadata.client_transaction_id}")


def timeout_configuration():
    """Example of configuring timeouts."""
    print("\n=== Timeout Configuration Example ===")

    # Create a client with a default timeout
    config = Config(timeout=10)  # 10 second default timeout
    client = ChatInspectionClient(api_key="YOUR_API_KEY", config=config)

    # This will use the 10-second default timeout from config
    result1 = client.inspect_prompt("This is a normal prompt")
    print(f"Using default timeout - is safe? {result1.is_safe}")

    # Override the timeout for a specific request
    result2 = client.inspect_prompt(
        "This is a prompt with custom timeout",
        timeout=15  # 15 second timeout for this specific request
    )
    print(f"Using custom timeout - is safe? {result2.is_safe}")


if __name__ == "__main__":
    print("AI Defense SDK Advanced Usage Examples")
    print("=====================================")
    print("Note: Replace 'YOUR_API_KEY' with an actual API key before running")

    # Run the examples
    custom_rules_example()
    error_handling_example()
    detailed_result_processing()
    metadata_usage_example()
    timeout_configuration()
