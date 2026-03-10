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
    """Return the names of client modules that agentsec has patched.

    Each entry is an internal identifier such as ``"openai"``,
    ``"bedrock"``, or ``"mcp"`` — these correspond to the patcher
    modules, **not** the names you would use in ``import`` statements.

    Call this after ``protect()`` to verify which integrations are
    active.  An empty list means no clients were patched (e.g. all
    modes are off or ``patch_clients=False`` was passed).

    Returns:
        List of patcher-module names that have been applied.
    """
    with _registry_lock:
        return [name for name, patched in _patch_registry.items() if patched]


def reset_registry() -> None:
    """Reset the patch registry. Useful for testing (thread-safe)."""
    global _patch_registry
    with _registry_lock:
        _patch_registry = {}


def reset_all_patcher_inspectors() -> None:
    """Close and clear all cached inspector singletons across patcher modules.

    Must be called when global state is reset (e.g. ``_state.reset()``) so that
    the next LLM/MCP call creates a fresh inspector with the new configuration
    (fail_open, endpoint, api_key, etc.).
    """
    from ..inspectors import cleanup_all_inspectors
    cleanup_all_inspectors()

    from . import (
        openai, bedrock, cohere, mistral, vertexai,
        google_genai, azure_ai_inference, litellm, mcp,
    )
    for mod in (openai, bedrock, cohere, mistral, vertexai,
                google_genai, azure_ai_inference, litellm, mcp):
        if hasattr(mod, "_reset_inspector"):
            mod._reset_inspector()


# Import patch functions for easy access
from .openai import patch_openai
from .bedrock import patch_bedrock
from .mcp import patch_mcp
from .vertexai import patch_vertexai
from .google_genai import patch_google_genai
from .cohere import patch_cohere
from .mistral import patch_mistral
from .litellm import patch_litellm
from .azure_ai_inference import patch_azure_ai_inference

__all__ = [
    "is_patched",
    "mark_patched", 
    "get_patched_clients",
    "reset_registry",
    "reset_all_patcher_inspectors",
    "patch_openai",
    "patch_bedrock",
    "patch_mcp",
    "patch_vertexai",
    "patch_google_genai",
    "patch_cohere",
    "patch_mistral",
    "patch_litellm",
    "patch_azure_ai_inference",
]


