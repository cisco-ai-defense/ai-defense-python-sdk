#!/usr/bin/env python3
"""
Streaming response example with agentsec protection.

This example demonstrates how agentsec handles streaming LLM responses.
For OpenAI, response chunks are inspected periodically (every N chunks)
and a final inspection runs when the stream completes.  For other
providers (Vertex AI, Cohere, Mistral), chunks are buffered and
inspected once after the stream completes.

Usage:
    python streaming_example.py

Environment variables are loaded from ../.env:
    OPENAI_API_KEY: Your OpenAI API key
    AI_DEFENSE_API_MODE_LLM_API_KEY: Your Cisco AI Defense API key
"""

import os
from pathlib import Path

# Load environment variables from shared .env file
from dotenv import load_dotenv
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"Loaded environment from {env_file}")

# Enable protection before importing clients
from aidefense.runtime import agentsec
config_path = str(Path(__file__).parent.parent / "agentsec.yaml")
agentsec.protect(
    config=config_path,  # gateway URLs, API endpoints, timeouts
    llm_integration_mode=os.getenv("AGENTSEC_LLM_INTEGRATION_MODE", "api"),
    mcp_integration_mode=os.getenv("AGENTSEC_MCP_INTEGRATION_MODE", "api"),
)


def main() -> None:
    """Demonstrate streaming with agentsec protection."""
    
    print("Streaming Example with agentsec Protection")
    print("=" * 50)
    print()
    
    patched = agentsec.get_patched_clients()
    print(f"Patched clients: {patched}")
    print()
    
    from openai import OpenAI
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set. Please check ../.env")
    
    client = OpenAI(api_key=api_key)
    
    print("Making streaming request...")
    print("(OpenAI: inspected periodically during stream + final inspection at completion)")
    print()
    print("Response:", end=" ")
    
    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": "Say hello in exactly 5 words."}
        ],
        stream=True,
    )
    
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            print(content, end="", flush=True)
    
    print()
    print()
    print("Streaming complete! All chunks were inspected by Cisco AI Defense.")


if __name__ == "__main__":
    main()
