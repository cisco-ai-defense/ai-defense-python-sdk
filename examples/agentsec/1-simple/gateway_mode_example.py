#!/usr/bin/env python3
"""
Cisco AI Defense Configuration Examples - API Mode & Gateway Mode.

This demonstrates how to configure agentsec programmatically:
1. API Mode - Inspection via Cisco AI Defense API
2. Gateway Mode - Route through Cisco AI Defense Gateway

Both modes can be configured via:
- Environment variables (recommended for production)
- Programmatic configuration via protect() parameters

Usage:
    python gateway_mode_example.py

Environment variables:
    Set in .env file - see ../.env.example for all options
"""

import os
from pathlib import Path

# =============================================================================
# Option 1: Environment Variables (Recommended for Production)
# =============================================================================
# Just set these in your .env file:
#
#   AGENTSEC_LLM_INTEGRATION_MODE=gateway
#   AGENTSEC_OPENAI_GATEWAY_URL=https://gateway.preview.aidefense.aiteam.cisco.com/...
#   AGENTSEC_OPENAI_GATEWAY_API_KEY=your-key
#
# Then use agentsec.protect() with no arguments - it reads from env automatically!


# =============================================================================
# Option 2: Programmatic Configuration (For Testing/Dynamic Config)
# =============================================================================

# --- API Mode Examples ---

def example_api_mode_programmatic():
    """Configure API mode entirely in code."""
    from aidefense.runtime import agentsec
    
    agentsec.protect(
        api_mode_llm="on_enforce",  # Block policy violations
        api_mode_llm_endpoint="https://preview.api.inspect.aidefense.aiteam.cisco.com/api",
        api_mode_llm_api_key="your-api-key",
        api_mode_mcp="on_monitor",  # Log but don't block
        # MCP falls back to LLM endpoint/key if not specified
        auto_dotenv=False,
    )
    
    # Now import and use OpenAI - calls are inspected via API
    from openai import OpenAI
    client = OpenAI()


def example_api_mode_separate_mcp():
    """Configure API mode with separate MCP credentials."""
    from aidefense.runtime import agentsec
    
    agentsec.protect(
        api_mode_llm="on_enforce",
        api_mode_llm_endpoint="https://preview.api.inspect.aidefense.aiteam.cisco.com/api",
        api_mode_llm_api_key="your-llm-api-key",
        api_mode_mcp="on_enforce",
        api_mode_mcp_endpoint="https://mcp.api.inspect.aidefense.aiteam.cisco.com/api",
        api_mode_mcp_api_key="your-mcp-api-key",
        auto_dotenv=False,
    )


# --- Gateway Mode Examples ---

def example_openai_gateway_programmatic():
    """Configure OpenAI Gateway mode entirely in code."""
    from aidefense.runtime import agentsec
    
    agentsec.protect(
        llm_integration_mode="gateway",
        providers={
            "openai": {
                "gateway_url": "https://gateway.preview.aidefense.aiteam.cisco.com/{tenant}/connections/{openai-conn}",
                "gateway_api_key": "your-openai-gateway-api-key",
            },
        },
        auto_dotenv=False,  # Don't load .env - we're configuring everything here
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
        providers={
            "openai": {
                "gateway_url": "https://gateway.../openai-conn",
                "gateway_api_key": "your-openai-gateway-key",
            },
            "azure_openai": {
                "gateway_url": "https://gateway.../azure-conn",
                "gateway_api_key": "your-azure-gateway-key",
            },
            "vertexai": {
                "gateway_url": "https://gateway.../vertexai-conn",
                # Vertex AI uses ADC OAuth2 token, no static API key
            },
            "bedrock": {
                "gateway_url": "https://gateway.../bedrock-conn",
                # Bedrock uses AWS Sig V4, no static API key
            },
        },
        auto_dotenv=False,
    )


def example_mcp_gateway_programmatic():
    """Configure MCP Gateway mode entirely in code."""
    from aidefense.runtime import agentsec
    
    agentsec.protect(
        mcp_integration_mode="gateway",
        gateway_mode_mcp_url="https://gateway.agent.preview.aidefense.aiteam.cisco.com/mcp/tenant/{tenant}/connections/{connection}/server/{server}",
        gateway_mode_mcp_api_key="your-mcp-gateway-key",
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
        providers={
            "openai": {
                "gateway_url": "https://gateway.../openai-conn",
                "gateway_api_key": "your-openai-key",
            },
        },
        # MCP Gateway
        mcp_integration_mode="gateway",
        gateway_mode_mcp_url="https://gateway.agent.preview.aidefense.aiteam.cisco.com/mcp/tenant/{tenant}/connections/{connection}/server/{server}",
        gateway_mode_mcp_api_key="your-mcp-key",
        auto_dotenv=False,
    )


def example_mixed_mode():
    """LLM via Gateway, MCP via API mode with enforcement."""
    from aidefense.runtime import agentsec
    
    agentsec.protect(
        # LLM: Route through gateway
        llm_integration_mode="gateway",
        providers={
            "openai": {
                "gateway_url": "https://gateway.../openai-conn",
                "gateway_api_key": "your-key",
            },
        },
        # MCP: Use API mode with enforcement
        mcp_integration_mode="api",
        api_mode_mcp="on_enforce",  # Block policy violations via API inspection
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
    print("Environment variables:")
    print("  AI_DEFENSE_API_MODE_LLM_ENDPOINT=https://preview.api.inspect.aidefense.aiteam.cisco.com/api")
    print("  AI_DEFENSE_API_MODE_LLM_API_KEY=your-key")
    print("  AGENTSEC_API_MODE_LLM=on_enforce  # or on_monitor, off")
    print()
    print("Programmatic:")
    print("  import agentsec")
    print("  agentsec.protect(")
    print('      api_mode_llm="on_enforce",')
    print('      api_mode_llm_endpoint="https://preview.api.inspect.aidefense.aiteam.cisco.com/api",')
    print('      api_mode_llm_api_key="your-key",')
    print("      auto_dotenv=False,")
    print("  )")
    print()
    print("=" * 70)
    print("GATEWAY MODE (Provider-Specific)")
    print("=" * 70)
    print()
    print("Gateway mode routes LLM/MCP calls through Cisco AI Defense Gateway,")
    print("which handles inspection and enforcement before proxying to providers.")
    print()
    print("Each provider has its own gateway connection URL and API key:")
    print()
    print("Environment variables:")
    print("  AGENTSEC_LLM_INTEGRATION_MODE=gateway")
    print("  AGENTSEC_OPENAI_GATEWAY_URL=https://gateway.../openai-conn")
    print("  AGENTSEC_OPENAI_GATEWAY_API_KEY=your-key")
    print("  AGENTSEC_AZURE_OPENAI_GATEWAY_URL=https://gateway.../azure-conn")
    print("  AGENTSEC_AZURE_OPENAI_GATEWAY_API_KEY=your-key")
    print("  AGENTSEC_VERTEXAI_GATEWAY_URL=https://gateway.../vertexai-conn")
    print("  # Vertex AI uses ADC OAuth2 token (no static API key)")
    print("  AGENTSEC_BEDROCK_GATEWAY_URL=https://gateway.../bedrock-conn")
    print("  # Bedrock uses AWS Sig V4 (no static API key)")
    print()
    print("Programmatic:")
    print("  import agentsec")
    print("  agentsec.protect(")
    print('      llm_integration_mode="gateway",')
    print("      providers={")
    print('          "openai": {')
    print('              "gateway_url": "https://gateway.../openai-conn",')
    print('              "gateway_api_key": "your-key",')
    print("          },")
    print("      },")
    print("      auto_dotenv=False,")
    print("  )")
    print()
    print("-" * 70)
    print("All Parameters for protect():")
    print("-" * 70)
    print()
    print("API Mode:")
    print("  api_mode_llm           : 'off', 'on_monitor', or 'on_enforce'")
    print("  api_mode_mcp           : 'off', 'on_monitor', or 'on_enforce'")
    print("  api_mode_llm_endpoint  : API endpoint for LLM inspection")
    print("  api_mode_llm_api_key   : API key for LLM inspection")
    print("  api_mode_mcp_endpoint  : API endpoint for MCP (optional, falls back to LLM)")
    print("  api_mode_mcp_api_key   : API key for MCP (optional, falls back to LLM)")
    print()
    print("Gateway Mode:")
    print("  llm_integration_mode   : 'api' (default) or 'gateway'")
    print("  mcp_integration_mode   : 'api' (default) or 'gateway'")
    print("  providers              : dict of provider configs {name: {gateway_url, gateway_api_key}}")
    print("  gateway_mode_mcp_url   : Gateway URL for MCP calls")
    print("  gateway_mode_mcp_api_key: API key for MCP gateway (optional)")
    print()
    print("Supported providers: 'openai', 'azure_openai', 'vertexai', 'bedrock'")
    print()
    print("See examples/.env.example for all environment variables.")
    print()
    
    # Actually initialize agentsec for testing
    from aidefense.runtime import agentsec
    from pathlib import Path
    from dotenv import load_dotenv
    
    # Load environment variables from examples/.env
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    
    agentsec.protect()
    print("✓ agentsec protection initialized")


if __name__ == "__main__":
    main()
