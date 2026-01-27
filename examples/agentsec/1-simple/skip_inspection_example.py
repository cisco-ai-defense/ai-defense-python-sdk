#!/usr/bin/env python3
"""
Example: Skip Inspection for LLM and MCP Calls

This example demonstrates how to exclude specific LLM and MCP calls from
AI Defense inspection using:
- skip_inspection() context manager
- no_inspection() decorator

Use cases:
- Health check calls that don't need inspection
- Internal/trusted calls that should bypass security checks
- Testing and debugging without inspection overhead

Usage:
    python skip_inspection_example.py
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)

# Import and activate agentsec BEFORE importing LLM clients
from aidefense.runtime import agentsec
from aidefense.runtime.agentsec import skip_inspection, no_inspection

agentsec.protect()

# Now import the OpenAI client (will be auto-patched)
from openai import OpenAI


def example_context_manager_skip_both():
    """Example: Skip both LLM and MCP inspection using context manager."""
    print("\n" + "=" * 60)
    print("Example 1: Skip BOTH LLM and MCP inspection")
    print("=" * 60)
    
    client = OpenAI()
    
    # This call WILL be inspected (normal behavior)
    print("\n[Normal call - WILL be inspected]")
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Say 'Hello from inspected call'"}],
            max_tokens=20,
        )
        print(f"Response: {response.choices[0].message.content}")
    except Exception as e:
        print(f"Error (expected if no API key): {e}")
    
    # This call will NOT be inspected
    print("\n[Inside skip_inspection() - NOT inspected]")
    with skip_inspection():
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Say 'Hello from skipped call'"}],
                max_tokens=20,
            )
            print(f"Response: {response.choices[0].message.content}")
        except Exception as e:
            print(f"Error (expected if no API key): {e}")
    
    print("\n[Back to normal - inspection resumed]")


def example_context_manager_skip_llm_only():
    """Example: Skip only LLM inspection, keep MCP inspection active."""
    print("\n" + "=" * 60)
    print("Example 2: Skip LLM only (MCP still inspected)")
    print("=" * 60)
    
    client = OpenAI()
    
    # Skip LLM inspection but keep MCP inspection active
    print("\n[Inside skip_inspection(llm=True, mcp=False)]")
    print("- LLM calls: NOT inspected")
    print("- MCP calls: STILL inspected")
    
    with skip_inspection(llm=True, mcp=False):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Say 'LLM not inspected'"}],
                max_tokens=20,
            )
            print(f"Response: {response.choices[0].message.content}")
        except Exception as e:
            print(f"Error (expected if no API key): {e}")


def example_context_manager_skip_mcp_only():
    """Example: Skip only MCP inspection, keep LLM inspection active."""
    print("\n" + "=" * 60)
    print("Example 3: Skip MCP only (LLM still inspected)")
    print("=" * 60)
    
    client = OpenAI()
    
    # Skip MCP inspection but keep LLM inspection active
    print("\n[Inside skip_inspection(llm=False, mcp=True)]")
    print("- LLM calls: STILL inspected")
    print("- MCP calls: NOT inspected")
    
    with skip_inspection(llm=False, mcp=True):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Say 'LLM inspected, MCP not'"}],
                max_tokens=20,
            )
            print(f"Response: {response.choices[0].message.content}")
        except Exception as e:
            print(f"Error (expected if no API key): {e}")


@no_inspection()
def health_check_function():
    """
    Example: Function decorated to always skip inspection.
    
    Use this for health check endpoints or internal utility functions
    that should never be inspected.
    """
    client = OpenAI()
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Health check: respond with 'OK'"}],
            max_tokens=10,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {e}"


@no_inspection(llm=True, mcp=False)
def llm_only_skip_function():
    """
    Example: Function that skips LLM inspection but keeps MCP inspection.
    """
    client = OpenAI()
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Say 'Decorator example'"}],
            max_tokens=20,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {e}"


def example_decorator():
    """Example: Using @no_inspection decorator."""
    print("\n" + "=" * 60)
    print("Example 4: Using @no_inspection decorator")
    print("=" * 60)
    
    print("\n[Calling @no_inspection() decorated function]")
    print("All calls inside this function are NOT inspected")
    result = health_check_function()
    print(f"Health check result: {result}")
    
    print("\n[Calling @no_inspection(llm=True, mcp=False) decorated function]")
    print("LLM calls NOT inspected, MCP calls STILL inspected")
    result = llm_only_skip_function()
    print(f"Result: {result}")


async def example_async_skip():
    """Example: Skip inspection in async code."""
    print("\n" + "=" * 60)
    print("Example 5: Async skip_inspection")
    print("=" * 60)
    
    from openai import AsyncOpenAI
    
    client = AsyncOpenAI()
    
    print("\n[Inside async with skip_inspection()]")
    async with skip_inspection():
        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Say 'Async skipped'"}],
                max_tokens=20,
            )
            print(f"Response: {response.choices[0].message.content}")
        except Exception as e:
            print(f"Error (expected if no API key): {e}")


@no_inspection()
async def async_health_check():
    """Async function decorated to skip inspection."""
    from openai import AsyncOpenAI
    
    client = AsyncOpenAI()
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Async health: respond 'OK'"}],
            max_tokens=10,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {e}"


def example_nested_contexts():
    """Example: Nested skip contexts."""
    print("\n" + "=" * 60)
    print("Example 6: Nested skip contexts")
    print("=" * 60)
    
    print("\n[Outer: skip_inspection(llm=True, mcp=False)]")
    with skip_inspection(llm=True, mcp=False):
        print("  - LLM: skipped, MCP: inspected")
        
        print("\n  [Inner: skip_inspection(llm=True, mcp=True)]")
        with skip_inspection(llm=True, mcp=True):
            print("    - LLM: skipped, MCP: skipped")
        
        print("\n  [Back to outer context]")
        print("  - LLM: skipped, MCP: inspected (restored)")
    
    print("\n[Outside all contexts]")
    print("- LLM: inspected, MCP: inspected (normal behavior)")


def main():
    """Run all examples."""
    print("=" * 60)
    print("Skip Inspection Examples")
    print("=" * 60)
    print("\nThis example demonstrates how to exclude specific calls")
    print("from AI Defense inspection using skip_inspection() and")
    print("@no_inspection decorator.")
    
    # Run sync examples
    example_context_manager_skip_both()
    example_context_manager_skip_llm_only()
    example_context_manager_skip_mcp_only()
    example_decorator()
    example_nested_contexts()
    
    # Run async example
    import asyncio
    print("\n" + "=" * 60)
    print("Async Examples")
    print("=" * 60)
    asyncio.run(example_async_skip())
    
    print("\n[Calling @no_inspection async decorated function]")
    result = asyncio.run(async_health_check())
    print(f"Async health check result: {result}")
    
    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()

