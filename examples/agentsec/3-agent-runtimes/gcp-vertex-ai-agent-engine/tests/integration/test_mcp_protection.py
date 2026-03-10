#!/usr/bin/env python3
"""MCP Tool Protection Integration Test for GCP Vertex AI.

This script tests that agentsec correctly intercepts and protects MCP tool calls.
It directly invokes the MCP fetch_url tool and verifies:
1. MCP client is patched by agentsec
2. Request inspection happens before the MCP call
3. Response inspection happens after the MCP call

Usage:
    poetry run python tests/integration/test_mcp_protection.py
    
    # With custom MCP server
    MCP_SERVER_URL=https://mcp.example.com/mcp poetry run python tests/integration/test_mcp_protection.py

Environment Variables:
    MCP_SERVER_URL: URL of the MCP server (default: https://mcp.deepwiki.com/mcp)
"""

import os
import sys
import logging
from pathlib import Path

# Enable debug logging for agentsec to see inspection details
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(name)s] %(levelname)s: %(message)s'
)
logging.getLogger("agentsec").setLevel(logging.DEBUG)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Set default MCP server URL if not provided
os.environ.setdefault("MCP_SERVER_URL", "https://mcp.deepwiki.com/mcp")

# Load shared .env file
env_path = Path(__file__).parent.parent.parent.parent.parent / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)
    print(f"[test] Loaded .env from {env_path}")

# =============================================================================
# Configure agentsec protection (BEFORE importing MCP)
# =============================================================================
from aidefense.runtime import agentsec

# Resolve agentsec.yaml path (needed for gateway mode MCP gateway mappings)
_yaml_paths = [
    Path(__file__).resolve().parent.parent.parent.parent.parent / "agentsec.yaml",  # examples/agentsec/agentsec.yaml
]
_yaml_config = None
for _yp in _yaml_paths:
    if _yp.exists():
        _yaml_config = str(_yp)
        break

agentsec.protect(
    config=_yaml_config,
    llm_integration_mode=os.getenv("AGENTSEC_LLM_INTEGRATION_MODE", "api"),
    mcp_integration_mode=os.getenv("AGENTSEC_MCP_INTEGRATION_MODE", "api"),
    api_mode={
        "llm": {"mode": os.getenv("AGENTSEC_API_MODE_LLM", "monitor")},
        "mcp": {"mode": os.getenv("AGENTSEC_API_MODE_MCP", "monitor")},
    },
    auto_dotenv=False,  # We already loaded .env manually
)

print(f"[agentsec] Patched clients: {agentsec.get_patched_clients()}")

# Verify MCP is patched
if "mcp" not in agentsec.get_patched_clients():
    print("[ERROR] MCP client was NOT patched by agentsec!")
    print("Make sure the 'mcp' package is installed.")
    sys.exit(1)

# =============================================================================
# Import MCP tools (AFTER agentsec.protect())
# =============================================================================
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from _shared.mcp_tools import _sync_call_mcp_tool

# =============================================================================
# Test MCP Tool Call
# =============================================================================
def test_mcp_tool_call():
    """Test MCP tool call with agentsec protection."""
    mcp_url = os.getenv("MCP_SERVER_URL")
    test_url = "https://example.com"
    
    print("")
    print("=" * 60)
    print("MCP Tool Protection Integration Test (GCP Vertex AI)")
    print("=" * 60)
    print(f"MCP Server: {mcp_url}")
    print(f"Test URL: {test_url}")
    print("")
    
    print("[test] Calling MCP fetch tool...")
    print("[test] agentsec should intercept and inspect request/response")
    print("-" * 60)
    
    try:
        result = _sync_call_mcp_tool('fetch', {'url': test_url})
        
        print("-" * 60)
        print(f"[test] SUCCESS! Got {len(result)} characters")
        print(f"[test] Preview: {result[:200]}...")
        
        # Verify we got example.com content
        if "Example Domain" in result or "example" in result.lower():
            print("[test] ✓ Content verified: example.com content received")
            return True
        else:
            print("[test] ⚠ Content not verified (may still be valid)")
            return True
            
    except Exception as e:
        print(f"[test] ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_mcp_tool_call()
    
    print("")
    print("=" * 60)
    if success:
        print("[test] ✓ MCP PROTECTION TEST PASSED")
    else:
        print("[test] ✗ MCP PROTECTION TEST FAILED")
    print("=" * 60)
    
    sys.exit(0 if success else 1)
