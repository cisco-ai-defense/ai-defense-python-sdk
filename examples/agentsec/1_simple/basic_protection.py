#!/usr/bin/env python3
"""
Basic agentsec protection example.

This example demonstrates the minimal setup required to enable
agentsec protection for your AI agent application.

Usage:
    python basic_protection.py

Environment variables are loaded from ../.env
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
    """Demonstrate basic agentsec protection setup."""
    
    # Enable protection with enforce mode for LLM calls
    # This will autopatch supported LLM clients (OpenAI, Azure OpenAI, Bedrock, Vertex AI)
    agentsec.protect(api_mode_llm="on_enforce")
    
    # Alternative: Use Gateway mode instead of API mode
    # Each provider has its own gateway connection
    # agentsec.protect(
    #     llm_integration_mode="gateway",
    #     providers={
    #         "openai": {
    #             "gateway_url": "https://gateway.../openai-conn",
    #             "gateway_api_key": "your-openai-gateway-key",
    #         },
    #     },
    #     auto_dotenv=False,
    # )
    
    # Check what clients were successfully patched
    patched = agentsec.get_patched_clients()
    print(f"Patched clients: {patched}")
    
    # Your application code continues normally
    # All LLM calls are now automatically inspected!
    print("Protection enabled! All LLM calls will be inspected.")
    print()
    print("Modes available:")
    print("  - enforce: Block requests that violate policies")
    print("  - monitor: Log violations but don't block")
    print("  - off: Disable all inspection")


if __name__ == "__main__":
    main()
