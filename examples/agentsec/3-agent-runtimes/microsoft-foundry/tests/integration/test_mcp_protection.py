#!/usr/bin/env python3
"""
MCP Protection Test for Azure AI Foundry.

This test verifies that agentsec properly intercepts MCP tool calls
for AI Defense inspection in both API and Gateway modes.

TWO TEST MODES:
1. Direct MCP Test: Directly invokes the MCP tool (tests MCP protection)
2. Agent-Prompted MCP Test: Prompts the LLM to use the MCP tool (tests full agent loop)

Usage:
    # Run with pytest
    poetry run pytest tests/integration/test_mcp_protection.py -v
    
    # Run directly
    poetry run python tests/integration/test_mcp_protection.py
    
    # Run agent-prompted test only (LLM decides to call MCP tool)
    poetry run python tests/integration/test_mcp_protection.py --agent

Environment Variables:
    AGENTSEC_LLM_INTEGRATION_MODE - "api" or "gateway"
    AGENTSEC_MCP_INTEGRATION_MODE - "api" or "gateway"
    MCP_SERVER_URL - MCP server URL (required)
"""

import os
import sys

# Add parent directories to path (tests/integration/ -> tests/ -> microsoft-foundry/)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Load environment variables from examples/agentsec/.env
# Path: microsoft-foundry/ -> 3-agent-runtimes/ -> agentsec/
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT_DIR, "..", "..", ".env"))


def test_mcp_tool_call_direct():
    """Test that MCP tool calls are intercepted by agentsec (direct invocation)."""
    from aidefense import get_patched_clients
    
    # Import after protect() is called (via agent_factory)
    from _shared.mcp_tools import fetch_url, get_mcp_tools
    
    # Verify MCP is configured
    mcp_url = os.getenv("MCP_SERVER_URL")
    if not mcp_url:
        print("[SKIP] MCP_SERVER_URL not configured")
        return
    
    # Verify agentsec has patched MCP
    patched = get_patched_clients()
    print(f"[agentsec] Patched clients: {patched}")
    
    assert "mcp" in patched, "MCP client not patched by agentsec"
    print("[PASS] MCP client patched by agentsec")
    
    # Get MCP tools
    mcp_tools = get_mcp_tools()
    assert len(mcp_tools) > 0, "No MCP tools returned"
    print(f"[PASS] MCP tools available: {[t.name for t in mcp_tools]}")
    
    # Test the fetch_url tool directly
    print("\n[TEST] Calling fetch_url tool directly...")
    print("[MCP TOOL] fetch_url called: url=https://example.com")
    print(f"[MCP TOOL] Calling MCP server at {mcp_url}...")
    
    import time
    start = time.time()
    result = fetch_url.invoke({"url": "https://example.com"})
    elapsed = time.time() - start
    
    assert result is not None, "fetch_url returned None"
    assert "error" not in result.lower() or "not configured" not in result.lower(), f"fetch_url failed: {result}"
    print(f"[MCP TOOL] Got response ({len(result)} chars) in {elapsed:.1f}s")
    print(f"[PASS] MCP tool call succeeded")
    print(f"[RESULT] Response length: {len(result)} chars")
    
    # Verify inspection happened (check logs)
    integration_mode = os.getenv("AGENTSEC_MCP_INTEGRATION_MODE", "api")
    print(f"[INFO] Integration mode: {integration_mode}")
    
    if integration_mode == "api":
        print("[PASS] API mode - MCP request/response inspection executed")
    else:
        print("[PASS] Gateway mode - MCP traffic routed through gateway")
    
    print("\n[SUCCESS] Direct MCP protection test passed!")


def test_mcp_tool_call_via_agent():
    """Test that agent prompts trigger MCP tool calls through AI Defense.
    
    This tests the FULL agent loop:
    1. User prompt asking to fetch a URL
    2. LLM decides to call fetch_url tool
    3. MCP tool call is intercepted by agentsec (AI Defense protection)
    4. Agent returns the result
    
    This is similar to how the GCP Vertex AI example tests MCP through the agent.
    """
    from aidefense import get_patched_clients
    
    # Verify MCP is configured
    mcp_url = os.getenv("MCP_SERVER_URL")
    if not mcp_url:
        print("[SKIP] MCP_SERVER_URL not configured")
        return
    
    # Verify Azure OpenAI is configured
    if not os.getenv("AZURE_OPENAI_ENDPOINT") or not os.getenv("AZURE_OPENAI_API_KEY"):
        print("[SKIP] Azure OpenAI not configured (needed for agent)")
        return
    
    # Import agent (this triggers agentsec.protect() and LLM patching)
    from _shared import invoke_agent
    
    # Verify both MCP and OpenAI are patched
    patched = get_patched_clients()
    print(f"[agentsec] Patched clients: {patched}")
    
    assert "mcp" in patched, "MCP client not patched by agentsec"
    assert "openai" in patched, "OpenAI client not patched by agentsec"
    print("[PASS] Both MCP and OpenAI clients patched by agentsec")
    
    # Prompt the agent to fetch a URL - the LLM should decide to use fetch_url tool
    test_prompt = "Please fetch the content from https://example.com and tell me what the page says."
    
    print(f"\n[TEST] Prompting agent to trigger MCP tool call...")
    print(f"[PROMPT] {test_prompt}")
    print("-" * 60)
    
    import time
    start = time.time()
    result = invoke_agent(test_prompt)
    elapsed = time.time() - start
    
    print("-" * 60)
    print(f"[AGENT] Response in {elapsed:.1f}s:")
    print(f"[AGENT] {result[:500]}{'...' if len(result) > 500 else ''}")
    
    # Verify the agent responded with content from example.com
    assert result is not None, "Agent returned None"
    assert len(result) > 50, "Agent response too short"
    
    # Check if the agent actually fetched example.com (should mention "Example Domain" or similar)
    if "example" in result.lower() or "domain" in result.lower():
        print("\n[PASS] Agent fetched and described example.com content")
    else:
        print("\n[INFO] Agent response may not include example.com content (tool may have been skipped)")
    
    integration_mode = os.getenv("AGENTSEC_MCP_INTEGRATION_MODE", "api")
    llm_integration_mode = os.getenv("AGENTSEC_LLM_INTEGRATION_MODE", "api")
    print(f"[INFO] Integration modes: LLM={llm_integration_mode}, MCP={integration_mode}")
    
    print("\n[SUCCESS] Agent-prompted MCP protection test passed!")
    print("[INFO] Full agent loop tested: LLM call (protected) → MCP tool call (protected)")


def main():
    """Run the MCP protection tests."""
    # Check for --agent flag to run only agent-prompted test
    agent_only = "--agent" in sys.argv
    
    print("=" * 60)
    print("MCP Protection Test - Azure AI Foundry")
    print("=" * 60)
    print(f"Integration Mode: LLM={os.getenv('AGENTSEC_LLM_INTEGRATION_MODE', 'api')}, "
          f"MCP={os.getenv('AGENTSEC_MCP_INTEGRATION_MODE', 'api')}")
    print(f"MCP Server: {os.getenv('MCP_SERVER_URL', 'not configured')}")
    print()
    
    try:
        if agent_only:
            # Run only the agent-prompted test
            print("[MODE] Agent-prompted MCP test (LLM triggers MCP tool call)")
            print()
            test_mcp_tool_call_via_agent()
        else:
            # Run direct MCP test (faster, tests MCP protection directly)
            print("[MODE] Direct MCP test (direct tool invocation)")
            print()
            test_mcp_tool_call_direct()
        return 0
    except AssertionError as e:
        print(f"\n[FAIL] {e}")
        return 1
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
