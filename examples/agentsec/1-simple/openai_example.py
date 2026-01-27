#!/usr/bin/env python3
"""
OpenAI client with agentsec protection.

This example demonstrates how to use agentsec with the OpenAI Python client.
The key is to call agentsec.protect() BEFORE importing the OpenAI client.

Usage:
    python openai_example.py

Environment variables are loaded from ../.env:
    OPENAI_API_KEY: Your OpenAI API key
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

# IMPORTANT: Enable protection BEFORE importing OpenAI
# This ensures the client gets patched correctly
from aidefense.runtime import agentsec
agentsec.protect(api_mode_llm="on_monitor")  # Use monitor mode for this example


def main() -> None:
    """Demonstrate OpenAI client usage with agentsec protection."""
    
    # Check if OpenAI client was patched
    patched = agentsec.get_patched_clients()
    print(f"Patched clients: {patched}")
    
    # Import OpenAI AFTER calling protect()
    from openai import OpenAI
    
    # Create client (will use OPENAI_API_KEY from environment)
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set. Please check ../.env")
    
    client = OpenAI(api_key=api_key)
    
    print("OpenAI client ready with agentsec protection")
    print(f"Client patched: {'openai' in patched}")
    print()
    
    # Make a real API call - this will be inspected by AI Defense!
    print("Making API call (will be inspected by Cisco AI Defense)...")
    print()
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Say hello in exactly 3 words."}]
    )
    
    print(f"Response: {response.choices[0].message.content}")
    print()
    print("The call was automatically inspected by Cisco AI Defense!")


if __name__ == "__main__":
    main()
