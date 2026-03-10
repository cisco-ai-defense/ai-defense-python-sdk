#!/usr/bin/env python3
"""
Cohere client with agentsec protection.

This example demonstrates how to use agentsec with the Cohere Python SDK (v2).
Call agentsec.protect() BEFORE importing the Cohere client.

Usage:
    python cohere_example.py

Environment variables are loaded from ../.env:
    COHERE_API_KEY: Your Cohere API key
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

# IMPORTANT: Enable protection BEFORE importing Cohere
from aidefense.runtime import agentsec
config_path = str(Path(__file__).parent.parent / "agentsec.yaml")
agentsec.protect(
    config=config_path,  # gateway URLs, API endpoints, timeouts
    llm_integration_mode=os.getenv("AGENTSEC_LLM_INTEGRATION_MODE", "api"),
    mcp_integration_mode=os.getenv("AGENTSEC_MCP_INTEGRATION_MODE", "api"),
    api_mode={"llm": {"mode": "monitor"}},  # override: use monitor mode
)


def main() -> None:
    """Demonstrate Cohere v2 client usage with agentsec protection."""
    patched = agentsec.get_patched_clients()
    print(f"Patched clients: {patched}")

    # Import Cohere AFTER calling protect()
    from cohere import Client, UserChatMessageV2

    api_key = os.environ.get("COHERE_API_KEY")
    if not api_key:
        raise ValueError("COHERE_API_KEY not set. Please check ../.env")

    client = Client(api_key=api_key)
    print("Cohere client ready with agentsec protection")
    print(f"Client patched: {'cohere' in patched}")
    print()

    print("Making API call (will be inspected by Cisco AI Defense)...")
    print()

    response = client.v2.chat(
        model="command-r-plus-08-2024",
        messages=[UserChatMessageV2(content="Say hello in exactly 3 words.")],
    )

    # Extract text from V2ChatResponse (message.content can be list of content items)
    content = response.message.content
    if isinstance(content, list):
        text = " ".join(getattr(item, "text", "") or "" for item in content)
    else:
        text = content or ""
    print(f"Response: {text.strip() or '(empty)'}")
    print()
    print("The call was automatically inspected by Cisco AI Defense!")


if __name__ == "__main__":
    main()
