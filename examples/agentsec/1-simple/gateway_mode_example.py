#!/usr/bin/env python3
"""
Cisco AI Defense Configuration Examples - API Mode & Gateway Mode.

This file is a **reference catalog** of configuration snippets, not a script
that runs each example end-to-end.  Because ``protect()`` is idempotent (only
the first successful call takes effect), only the ``main()`` function at the
bottom actually initializes agentsec.  The individual ``example_*`` functions
above it are standalone code samples that show how you *would* configure each
mode — copy the one you need into your own application.

Demonstrates how to configure agentsec programmatically:
1. API Mode - Inspection via Cisco AI Defense API
2. Gateway Mode - Route through Cisco AI Defense Gateway

Both modes can be configured via:
- A YAML configuration file (recommended for production)
- Programmatic configuration via protect() parameters

Usage:
    python gateway_mode_example.py

Configuration:
    See agentsec.yaml for YAML configuration options
    See ../.env.example for environment variable reference
"""

import os
from pathlib import Path

# =============================================================================
# Option 1: YAML Configuration File (Recommended for Production)
# =============================================================================
# Create an agentsec.yaml file and pass its path to protect():
#
#   agentsec.protect(config="agentsec.yaml")
#
# See examples/agentsec/agentsec.yaml for a complete reference.


# =============================================================================
# Option 2: Programmatic Configuration (For Testing/Dynamic Config)
# =============================================================================

# --- API Mode Examples ---
# NOTE: Each example_* function below calls protect() independently.
# Because protect() is idempotent, only the FIRST call in a process wins.
# These functions are meant as copy-paste reference snippets — do NOT call
# more than one in the same process and expect different configurations.

def example_api_mode_programmatic():
    """Configure API mode entirely in code."""
    from aidefense.runtime import agentsec

    agentsec.protect(
        api_mode={
            "llm": {
                "mode": "enforce",  # Block policy violations
                "endpoint": "https://preview.api.inspect.aidefense.aiteam.cisco.com/api",
                "api_key": os.getenv("AI_DEFENSE_API_MODE_LLM_API_KEY"),
            },
            "mcp": {
                "mode": "monitor",  # Log but don't block
                # MCP falls back to LLM endpoint/key if not specified
            },
        },
        auto_dotenv=False,
    )

    # Now import and use OpenAI - calls are inspected via API
    from openai import OpenAI
    client = OpenAI()


def example_api_mode_separate_mcp():
    """Configure API mode with separate MCP credentials."""
    from aidefense.runtime import agentsec

    agentsec.protect(
        api_mode={
            "llm": {
                "mode": "enforce",
                "endpoint": "https://preview.api.inspect.aidefense.aiteam.cisco.com/api",
                "api_key": os.getenv("AI_DEFENSE_API_MODE_LLM_API_KEY"),
            },
            "mcp": {
                "mode": "enforce",
                "endpoint": "https://mcp.api.inspect.aidefense.aiteam.cisco.com/api",
                "api_key": os.getenv("AI_DEFENSE_API_MODE_MCP_API_KEY"),
            },
        },
        auto_dotenv=False,
    )


# --- Gateway Mode Examples ---

def example_openai_gateway_programmatic():
    """Configure OpenAI Gateway mode entirely in code."""
    from aidefense.runtime import agentsec

    agentsec.protect(
        llm_integration_mode="gateway",
        gateway_mode={
            "llm_gateways": {
                "openai-1": {
                    "gateway_url": "https://gateway.preview.aidefense.aiteam.cisco.com/{tenant}/connections/{openai-conn}",
                    "gateway_api_key": os.getenv("OPENAI_API_KEY"),
                    "auth_mode": "api_key",
                    "provider": "openai",
                    "default": True,
                },
            },
        },
        auto_dotenv=False,
    )

    # Now import and use OpenAI - calls go through gateway
    from openai import OpenAI
    client = OpenAI()
    # LLM calls are routed: client -> agentsec -> gateway -> OpenAI


def example_multi_provider_gateway():
    """Configure multiple providers for Gateway mode."""
    from aidefense.runtime import agentsec

    agentsec.protect(
        llm_integration_mode="gateway",
        gateway_mode={
            "llm_gateways": {
                "openai-1": {
                    "gateway_url": "https://gateway.../openai-conn",
                    "gateway_api_key": os.getenv("OPENAI_API_KEY"),
                    "auth_mode": "api_key",
                    "provider": "openai",
                    "default": True,
                },
                "azure-openai-1": {
                    "gateway_url": "https://gateway.../azure-conn",
                    "gateway_api_key": os.getenv("AZURE_OPENAI_API_KEY"),
                    "auth_mode": "api_key",
                    "provider": "azure_openai",
                    "default": True,
                },
                "vertexai-1": {
                    "gateway_url": "https://gateway.../vertexai-conn",
                    "auth_mode": "google_adc",
                    "provider": "vertexai",
                    "default": True,
                    # Per-gateway GCP ADC credentials (all optional)
                    "gcp_project": "my-project",
                    "gcp_location": "us-central1",
                    # Or explicit SA: "gcp_service_account_key_file": "/path/to/key.json",
                    # Or impersonation: "gcp_target_service_account": "sa@project.iam.gserviceaccount.com",
                },
                "bedrock-1": {
                    "gateway_url": "https://gateway.../bedrock-conn",
                    "auth_mode": "aws_sigv4",
                    "provider": "bedrock",
                    "default": True,
                    # Per-gateway AWS SigV4 credentials (all optional)
                    "aws_region": "us-east-1",
                    "aws_profile": "default",
                    # Or explicit: "aws_access_key_id": "...", "aws_secret_access_key": "...",
                    # Or assume-role: "aws_role_arn": "arn:aws:iam::123456789012:role/...",
                },
            },
        },
        auto_dotenv=False,
    )


def example_mcp_gateway_programmatic():
    """Configure MCP Gateway mode entirely in code.

    MCP gateways support three auth_mode values:
      - "none"                       — No authentication (default)
      - "api_key"                    — API key sent in "api-key" header
      - "oauth2_client_credentials"  — OAuth 2.0 Client Credentials grant
    """
    from aidefense.runtime import agentsec

    mcp_server_url = os.getenv("MCP_SERVER_URL", "https://remote.mcpservers.org/fetch/mcp")

    agentsec.protect(
        mcp_integration_mode="gateway",
        gateway_mode={
            "mcp_gateways": {
                mcp_server_url: {
                    "gateway_url": "https://gateway.agent.preview.aidefense.aiteam.cisco.com/mcp/tenant/{tenant}/connections/{connection}/server/{server}",
                    "auth_mode": "none",  # no auth needed for this MCP server
                },
            },
        },
        auto_dotenv=False,
    )

    # Now MCP connections go through gateway
    from mcp.client.streamable_http import streamablehttp_client
    # MCP calls are routed: client -> agentsec -> gateway -> MCP server


def example_both_gateway_programmatic():
    """Configure both LLM and MCP Gateway mode in code."""
    from aidefense.runtime import agentsec

    agentsec.protect(
        # LLM Gateway (provider-specific)
        llm_integration_mode="gateway",
        # MCP Gateway
        mcp_integration_mode="gateway",
        gateway_mode={
            "llm_gateways": {
                "openai-1": {
                    "gateway_url": "https://gateway.../openai-conn",
                    "gateway_api_key": os.getenv("OPENAI_API_KEY"),
                    "auth_mode": "api_key",
                    "provider": "openai",
                    "default": True,
                },
            },
            "mcp_gateways": {
                os.getenv("MCP_SERVER_URL", "https://remote.mcpservers.org/fetch/mcp"): {
                    "gateway_url": "https://gateway.agent.preview.aidefense.aiteam.cisco.com/mcp/...",
                    "auth_mode": "none",
                },
            },
        },
        auto_dotenv=False,
    )


def example_mixed_mode():
    """LLM via Gateway, MCP via API mode with enforcement."""
    from aidefense.runtime import agentsec

    agentsec.protect(
        # LLM: Route through gateway
        llm_integration_mode="gateway",
        gateway_mode={
            "llm_gateways": {
                "openai-1": {
                    "gateway_url": "https://gateway.../openai-conn",
                    "gateway_api_key": os.getenv("OPENAI_API_KEY"),
                    "auth_mode": "api_key",
                    "provider": "openai",
                    "default": True,
                },
            },
        },
        # MCP: Use API mode with enforcement
        mcp_integration_mode="api",
        api_mode={
            "mcp": {"mode": "enforce"},  # Block policy violations via API inspection
        },
        auto_dotenv=False,
    )


# =============================================================================
# Main: Show Configuration Options
# =============================================================================
def main():
    """Show configuration options and initialize agentsec."""
    print("=" * 70)
    print("Cisco AI Defense Configuration - API Mode & Gateway Mode")
    print("=" * 70)
    print()
    print("=" * 70)
    print("API MODE (Default)")
    print("=" * 70)
    print()
    print("API mode inspects LLM/MCP calls via Cisco AI Defense inspection API.")
    print()
    print("Programmatic (inline):")
    print("  from aidefense.runtime import agentsec")
    print("  agentsec.protect(")
    print('      api_mode={')
    print('          "llm": {')
    print('              "mode": "enforce",')
    print('              "endpoint": "https://preview.api.inspect.aidefense.aiteam.cisco.com/api",')
    print('              "api_key": "your-key",')
    print('          },')
    print('      },')
    print("  )")
    print()
    print("YAML config (recommended):")
    print('  agentsec.protect(config="agentsec.yaml")')
    print()
    print("=" * 70)
    print("GATEWAY MODE (Provider-Specific)")
    print("=" * 70)
    print()
    print("Gateway mode routes LLM/MCP calls through Cisco AI Defense Gateway,")
    print("which handles inspection and enforcement before proxying to providers.")
    print()
    print("Each provider gets a named gateway (e.g. openai-1) with 'default: true'.")
    print()
    print("Programmatic (inline):")
    print("  from aidefense.runtime import agentsec")
    print("  agentsec.protect(")
    print('      llm_integration_mode="gateway",')
    print('      gateway_mode={')
    print('          "llm_gateways": {')
    print('              "openai-1": {')
    print('                  "gateway_url": "https://gateway.../openai-conn",')
    print('                  "gateway_api_key": "your-key",')
    print('                  "auth_mode": "api_key",')
    print('                  "provider": "openai",')
    print('                  "default": True,')
    print('              },')
    print('          },')
    print('      },')
    print("  )")
    print()
    print("YAML config (recommended):")
    print('  agentsec.protect(config="agentsec.yaml")')
    print()
    print("-" * 70)
    print("All Parameters for protect():")
    print("-" * 70)
    print()
    print("API Mode (api_mode dict):")
    print("  llm.mode              : 'off', 'monitor', or 'enforce'")
    print("  llm.endpoint          : API endpoint for LLM inspection")
    print("  llm.api_key           : API key for LLM inspection")
    print("  mcp.mode              : 'off', 'monitor', or 'enforce'")
    print("  mcp.endpoint          : API endpoint for MCP (optional, falls back to LLM)")
    print("  mcp.api_key           : API key for MCP (optional, falls back to LLM)")
    print("  llm_defaults.fail_open: Whether to allow calls if inspection fails")
    print("  mcp_defaults.fail_open: Whether to allow calls if inspection fails")
    print()
    print("Gateway Mode (gateway_mode dict):")
    print("  llm_mode              : 'on' (default) or 'off' — enable/disable LLM gateway inspection")
    print("  mcp_mode              : 'on' (default) or 'off' — enable/disable MCP gateway inspection")
    print("  llm_gateways          : dict of named LLM gateways {name: {gateway_url, gateway_api_key, provider, default}}")
    print("  mcp_gateways          : dict of MCP gateway configs {mcp_server_url: {gateway_url, auth_mode, ...}}")
    print("    auth_mode           : 'none' (default), 'api_key', or 'oauth2_client_credentials'")
    print()
    print("Top-level:")
    print("  config                : path to agentsec.yaml")
    print("  llm_integration_mode  : 'api' (default) or 'gateway'")
    print("  mcp_integration_mode  : 'api' (default) or 'gateway'")
    print()
    print("Supported providers: 'openai', 'azure_openai', 'vertexai', 'bedrock', 'google_genai'")
    print()
    print("See agentsec.yaml for YAML configuration reference.")
    print()

    # Actually initialize agentsec for testing
    from aidefense.runtime import agentsec
    from dotenv import load_dotenv

    # Load environment variables from examples/.env
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)

    agentsec.protect(
        llm_integration_mode=os.getenv("AGENTSEC_LLM_INTEGRATION_MODE", "api"),
        mcp_integration_mode=os.getenv("AGENTSEC_MCP_INTEGRATION_MODE", "api"),
    )
    print("agentsec protection initialized")


if __name__ == "__main__":
    main()
