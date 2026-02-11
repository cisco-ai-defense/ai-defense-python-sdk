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
Example: Using MCPInspectionClient to inspect MCP JSON-RPC 2.0 messages

This example demonstrates how to inspect Model Context Protocol (MCP) messages
for security, privacy, and safety violations.

Environment Variables:
    AIDEFENSE_API_KEY: Your Cisco AI Defense API key
    AIDEFENSE_RUNTIME_URL: The runtime API base URL (e.g., https://your-instance.api.inspect.aidefense.aiteam.cisco.com)
"""

import os

from aidefense import MCPInspectionClient, Config
from aidefense.runtime import MCPMessage

# Get API key and URL from environment variables
api_key = os.environ.get("AIDEFENSE_API_KEY")
runtime_url = os.environ.get("AIDEFENSE_RUNTIME_URL")

if not api_key:
    raise ValueError("AIDEFENSE_API_KEY environment variable is required")

if not runtime_url:
    raise ValueError("AIDEFENSE_RUNTIME_URL environment variable is required")

# Initialize the MCP inspection client with custom config
config = Config(runtime_base_url=runtime_url)
client = MCPInspectionClient(api_key=api_key, config=config)

# Create an MCP request message to inspect
message = MCPMessage(
    jsonrpc="2.0",
    method="tools/call",
    params={
        "name": "search_documentation",
        "arguments": {
            "query": "How to make a bomb",
            "max_results": 10
        }
    },
    id=10
)

# Inspect the MCP message
result = client.inspect(message)

# Print the inspection results in a readable format
print("=" * 60)
print("MCP INSPECTION RESULT")
print("=" * 60)

if result.error:
    print(f"❌ Inspection Error:")
    print(f"   Code:    {result.error.code}")
    print(f"   Message: {result.error.message}")
    if result.error.data:
        print(f"   Data:    {result.error.data}")
elif result.result:
    r = result.result
    status = "✅ SAFE" if r.is_safe else "🚫 UNSAFE"
    print(f"Status:          {status}")
    print(f"Action:          {r.action.value if r.action else 'N/A'}")
    print(f"Severity:        {r.severity.value if r.severity else 'N/A'}")
    print(f"Event ID:        {r.event_id or 'N/A'}")

    if r.classifications:
        print(f"Classifications: {', '.join(c.value for c in r.classifications)}")

    if r.rules:
        print("\nTriggered Rules:")
        for rule in r.rules:
            rule_name = rule.rule_name.value if hasattr(rule.rule_name, 'value') else rule.rule_name
            print(f"   • {rule_name}")
            if rule.classification and rule.classification != "NONE_VIOLATION":
                classification = rule.classification.value if hasattr(rule.classification, 'value') else rule.classification
                print(f"     Classification: {classification}")

    if r.processed_rules:
        print(f"\nProcessed Rules ({len(r.processed_rules)} total):")
        for rule in r.processed_rules:
            rule_name = rule.rule_name.value if hasattr(rule.rule_name, 'value') else rule.rule_name
            print(f"   • {rule_name}")

    if r.attack_technique and r.attack_technique != "NONE_ATTACK_TECHNIQUE":
        print(f"\nAttack Technique: {r.attack_technique}")

    if r.explanation:
        print(f"\nExplanation: {r.explanation}")

print("=" * 60)

