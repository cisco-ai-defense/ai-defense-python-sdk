#!/usr/bin/env python3
"""
Mistral AI client with agentsec protection.

This example demonstrates how to use agentsec with the Mistral AI Python SDK.
Call agentsec.protect() BEFORE importing the Mistral client.

Usage:
    python mistral_example.py

Environment variables are loaded from ../.env:
    MISTRAL_API_KEY: Your Mistral API key
    AI_DEFENSE_API_MODE_LLM_API_KEY: Your Cisco AI Defense API key
    AI_DEFENSE_API_MODE_LLM_ENDPOINT: API endpoint URL
"""

import os
from pathlib import Path

# Load environment variables from shared .env file
from dotenv import load_dotenv
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"Loaded environment from {env_file}")

# IMPORTANT: Enable protection BEFORE importing Mistral
from aidefense.runtime import agentsec
config_path = str(Path(__file__).parent.parent / "agentsec.yaml")
agentsec.protect(
    config=config_path,  # gateway URLs, API endpoints, timeouts
    llm_integration_mode=os.getenv("AGENTSEC_LLM_INTEGRATION_MODE", "api"),
    mcp_integration_mode=os.getenv("AGENTSEC_MCP_INTEGRATION_MODE", "api"),
    api_mode={"llm": {"mode": "monitor"}},  # override: use monitor mode
)


def main() -> None:
    """Demonstrate Mistral client usage with agentsec protection."""
    patched = agentsec.get_patched_clients()
    print(f"Patched clients: {patched}")

    # Import Mistral AFTER calling protect()
    from mistralai import Mistral

    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError("MISTRAL_API_KEY not set. Please check ../.env")

    client = Mistral(api_key=api_key)
    print("Mistral client ready with agentsec protection")
    print(f"Client patched: {'mistral' in patched}")
    print()

    print("Making API call (will be inspected by Cisco AI Defense)...")
    print()

    response = client.chat.complete(
        model="mistral-large-latest",
        messages=[{"role": "user", "content": "Say hello in exactly 3 words."}],
    )

    content = response.choices[0].message.content if response.choices else ""
    print(f"Response: {content or '(empty)'}")
    print()
    print("The call was automatically inspected by Cisco AI Defense!")


if __name__ == "__main__":
    main()
