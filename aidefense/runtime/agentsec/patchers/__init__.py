# Copyright 2025 Cisco Systems, Inc. and its affiliates
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

"""Patching infrastructure for autopatching LLM and MCP clients."""

import logging
from typing import List

logger = logging.getLogger("aidefense.runtime.agentsec.patchers")

# Registry of patched functions/clients
_patch_registry: dict[str, bool] = {}


def is_patched(name: str) -> bool:
    """Check if a client/function has already been patched."""
    return _patch_registry.get(name, False)


def mark_patched(name: str) -> None:
    """Mark a client/function as patched."""
    _patch_registry[name] = True
    logger.debug(f"Marked {name} as patched")


def get_patched_clients() -> List[str]:
    """
    Get list of successfully patched clients.
    
    Returns:
        List of client names that have been patched
    """
    return [name for name, patched in _patch_registry.items() if patched]


def reset_registry() -> None:
    """Reset the patch registry. Useful for testing."""
    global _patch_registry
    _patch_registry = {}


# Import patch functions for easy access
from .openai import patch_openai
from .bedrock import patch_bedrock
from .mcp import patch_mcp
from .vertexai import patch_vertexai

__all__ = [
    "is_patched",
    "mark_patched", 
    "get_patched_clients",
    "reset_registry",
    "patch_openai",
    "patch_bedrock",
    "patch_mcp",
    "patch_vertexai",
]
