"""Patching infrastructure for autopatching LLM and MCP clients."""

import logging
import threading
from typing import List

logger = logging.getLogger("aidefense.runtime.agentsec.patchers")

# Registry of patched functions/clients with thread-safe access
_patch_registry: dict[str, bool] = {}
_registry_lock = threading.Lock()


def is_patched(name: str) -> bool:
    """Check if a client/function has already been patched (thread-safe)."""
    with _registry_lock:
        return _patch_registry.get(name, False)


def mark_patched(name: str) -> None:
    """Mark a client/function as patched (thread-safe)."""
    with _registry_lock:
        _patch_registry[name] = True
    logger.debug(f"Marked {name} as patched")


def get_patched_clients() -> List[str]:
    """
    Get list of successfully patched clients (thread-safe).
    
    Returns:
        List of client names that have been patched
    """
    with _registry_lock:
        return [name for name, patched in _patch_registry.items() if patched]


def reset_registry() -> None:
    """Reset the patch registry. Useful for testing (thread-safe)."""
    global _patch_registry
    with _registry_lock:
        _patch_registry = {}


# Import patch functions for easy access
from .openai import patch_openai
from .bedrock import patch_bedrock
from .mcp import patch_mcp
from .vertexai import patch_vertexai
from .google_genai import patch_google_genai

__all__ = [
    "is_patched",
    "mark_patched", 
    "get_patched_clients",
    "reset_registry",
    "patch_openai",
    "patch_bedrock",
    "patch_mcp",
    "patch_vertexai",
    "patch_google_genai",
]


