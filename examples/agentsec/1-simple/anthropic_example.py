#!/usr/bin/env python3
# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Anthropic Messages API with agentsec protection.

Install the optional provider dependency before running this example::

    pip install anthropic
"""

import os
from pathlib import Path

from dotenv import load_dotenv

env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)

# Protect before importing the Anthropic client.
from aidefense.runtime import agentsec

config_path = str(Path(__file__).parent.parent / "agentsec.yaml")
agentsec.protect(
    config=config_path,
    llm_integration_mode=os.getenv("AGENTSEC_LLM_INTEGRATION_MODE", "api"),
    mcp_integration_mode=os.getenv("AGENTSEC_MCP_INTEGRATION_MODE", "api"),
    api_mode={"llm": {"mode": "monitor"}},
)

from anthropic import Anthropic


def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set. Please check ../.env")

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=256,
        system="Answer briefly.",
        messages=[{"role": "user", "content": "Say hello in three words."}],
    )

    text = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    print(f"Patched clients: {agentsec.get_patched_clients()}")
    print(f"Response: {text}")


if __name__ == "__main__":
    main()
