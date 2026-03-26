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

"""Security inspectors for LLM and MCP interactions."""

import atexit
import logging
from typing import List, Any

# API Mode Inspectors
from .api_llm import LLMInspector
from .api_mcp import MCPInspector

# Gateway Mode Inspectors
from .gateway_llm import GatewayClient
from .gateway_mcp import MCPGatewayInspector

__all__ = [
    "LLMInspector", 
    "MCPInspector", 
    "GatewayClient", 
    "MCPGatewayInspector",
    "register_inspector_for_cleanup",
    "cleanup_all_inspectors",
]

logger = logging.getLogger("aidefense.runtime.agentsec.inspectors")

# Global registry of inspector instances for cleanup on shutdown
_inspector_registry: List[Any] = []


def register_inspector_for_cleanup(inspector: Any) -> None:
    """
    Register an inspector instance for cleanup on interpreter shutdown.
    
    This ensures HTTP clients are properly closed when the Python interpreter
    exits, preventing resource leaks.
    
    Args:
        inspector: An inspector instance with a close() method
    """
    if inspector not in _inspector_registry:
        _inspector_registry.append(inspector)


def cleanup_all_inspectors() -> None:
    """
    Close all registered inspector instances.
    
    Called automatically on interpreter shutdown via atexit.
    Can also be called manually for testing or early cleanup.
    """
    global _inspector_registry
    for inspector in _inspector_registry:
        try:
            if hasattr(inspector, 'close'):
                inspector.close()
                logger.debug(f"Closed inspector: {type(inspector).__name__}")
        except Exception as e:
            logger.debug(f"Error closing inspector {type(inspector).__name__}: {e}")
    _inspector_registry = []


# Register cleanup handler to run on interpreter shutdown
atexit.register(cleanup_all_inspectors)
