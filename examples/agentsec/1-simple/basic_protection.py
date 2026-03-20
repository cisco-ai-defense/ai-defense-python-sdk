#!/usr/bin/env python3
# Copyright 2026 Cisco Systems, Inc. and its affiliates
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
    config_path = str(Path(__file__).parent.parent / "agentsec.yaml")
    agentsec.protect(
        config=config_path,  # gateway URLs, API endpoints, timeouts
        llm_integration_mode=os.getenv("AGENTSEC_LLM_INTEGRATION_MODE", "api"),
        mcp_integration_mode=os.getenv("AGENTSEC_MCP_INTEGRATION_MODE", "api"),
    )
    
    # Alternative: Use Gateway mode instead of API mode
    # Each provider gets a named gateway with full explicit config
    # agentsec.protect(
    #     llm_integration_mode="gateway",
    #     gateway_mode={
    #         "llm_gateways": {
    #             "openai-1": {
    #                 "gateway_url": "https://gateway.../openai-conn",
    #                 "gateway_api_key": "your-openai-gateway-key",
    #                 "auth_mode": "api_key",
    #                 "provider": "openai",
    #                 "default": True,
    #             },
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
