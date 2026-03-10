#!/usr/bin/env python3
"""
Custom Inspection Rules Example

Demonstrates how to control which AI Defense inspection rules are evaluated
when using API mode. By default, ALL rules are evaluated. This example shows
how to select specific rules via protect() kwargs, which is useful for:

- Reducing false positives (e.g., excluding Prompt Injection for agent frameworks
  whose system prompts trigger the detector)
- Focusing inspection on the threats most relevant to your application
- Filtering PII detection to specific entity types (e.g., only Email and Phone)

The example makes two real OpenAI calls to show that only the selected rules
(PII, Code Detection) are evaluated while others (Prompt Injection, etc.) are not.

Usage:
    python custom_rules_example.py

Environment variables are loaded from ../.env:
    OPENAI_API_KEY: Your OpenAI API key
    AI_DEFENSE_API_MODE_LLM_API_KEY: Your Cisco AI Defense API key
    AI_DEFENSE_API_MODE_LLM_ENDPOINT: API endpoint URL
"""

import os
from pathlib import Path

# Load environment variables from shared .env file BEFORE importing agentsec
from dotenv import load_dotenv
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"Loaded environment from {env_file}")
else:
    print(f"Warning: {env_file} not found")

from aidefense.runtime import agentsec


def main() -> None:
    """Demonstrate custom inspection rules configuration."""

    # =========================================================================
    # Option 1: Selective rules via protect() kwargs
    # =========================================================================
    # Override api_mode.llm.rules to inspect ONLY for PII and Code Detection.
    # Prompt Injection, Harassment, Toxicity, etc. are NOT evaluated.
    #
    # This is useful when your application's system prompts trigger false
    # positives on the Prompt Injection rule (common with agent frameworks
    # like AutoGen that use control keywords like TERMINATE).
    config_path = str(Path(__file__).parent.parent / "agentsec.yaml")
    agentsec.protect(
        config=config_path,
        llm_integration_mode=os.getenv("AGENTSEC_LLM_INTEGRATION_MODE", "api"),
        mcp_integration_mode=os.getenv("AGENTSEC_MCP_INTEGRATION_MODE", "api"),
        api_mode={
            "llm": {
                "rules": [
                    {"rule_name": "PII"},
                    {"rule_name": "Code Detection"},
                ]
            }
        },
    )

    # Check what clients were successfully patched
    patched = agentsec.get_patched_clients()
    print(f"Patched clients: {patched}")

    print()
    print("=" * 60)
    print("  Custom Inspection Rules Example")
    print("=" * 60)
    print()
    print("Active rules: PII, Code Detection")
    print("Inactive rules: Prompt Injection, Harassment, Toxicity, ...")
    print()

    # =========================================================================
    # Make real LLM calls to exercise the custom rules
    # =========================================================================
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set. Please check ../.env")

    client = OpenAI(api_key=api_key)

    # Call 1: A prompt that would normally trigger PII detection
    # Only PII and Code Detection rules are active, so only those are evaluated.
    print("Call 1: Prompt with PII content (inspected by PII rule)")
    print("-" * 60)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": "Say hello and mention that the email is test@example.com"}
        ],
        max_tokens=50,
    )
    print(f"  Response: {response.choices[0].message.content}")
    print()

    # Call 2: A prompt that asks for code (inspected by Code Detection rule)
    print("Call 2: Prompt requesting code (inspected by Code Detection rule)")
    print("-" * 60)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": "Write a one-line Python hello world program."}
        ],
        max_tokens=50,
    )
    print(f"  Response: {response.choices[0].message.content}")
    print()

    print("Both calls were inspected by Cisco AI Defense using ONLY the")
    print("selected rules (PII, Code Detection). Other rules like Prompt")
    print("Injection, Harassment, etc. were NOT evaluated.")
    print()

    # =========================================================================
    # Reference: Configuration options (not executed)
    # =========================================================================
    print("=" * 60)
    print("  Configuration Reference")
    print("=" * 60)
    print()
    print("This configuration is set via protect() kwargs:")
    print()
    print('  agentsec.protect(')
    print('      config="agentsec.yaml",')
    print('      api_mode={')
    print('          "llm": {')
    print('              "rules": [')
    print('                  {"rule_name": "PII"},')
    print('                  {"rule_name": "Code Detection"},')
    print('              ]')
    print('          }')
    print('      },')
    print('  )')
    print()
    print("Supported rule formats:")
    print('  - Simple strings:  ["PII", "Code Detection"]')
    print('  - Dict:            [{"rule_name": "PII"}]')
    print('  - With entities:   [{"rule_name": "PII", "entity_types": ["Email Address"]}]')
    print()
    print("All supported rule names:")
    print("  Prompt Injection, PII, PCI, PHI, Code Detection, Harassment,")
    print("  Hate Speech, Profanity, Toxicity, Sexual Content & Exploitation,")
    print("  Social Division & Polarization, Violence & Public Safety Threats")
    print()
    print("When rules is omitted (default), ALL rules are evaluated.")
    print("When rules is specified, ONLY those rules are evaluated.")


if __name__ == "__main__":
    main()
