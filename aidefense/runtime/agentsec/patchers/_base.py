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

"""Base utilities for patching infrastructure."""

import functools
import logging
from typing import Any, Callable, Optional

import wrapt

logger = logging.getLogger("aidefense.runtime.agentsec.patchers")


def safe_import(module_name: str) -> Optional[Any]:
    """
    Safely import a module, returning None if not installed.
    
    Args:
        module_name: Full module path to import
        
    Returns:
        The imported module, or None if import fails
    """
    try:
        import importlib
        module = importlib.import_module(module_name)
        logger.debug(f"Successfully imported {module_name}")
        return module
    except ImportError:
        logger.debug(f"Module {module_name} not installed, skipping patch")
        return None


def apply_patch(
    module: Any,
    attr: str,
    wrapper: Callable,
) -> bool:
    """
    Apply a patch to a module attribute using wrapt.
    
    Args:
        module: The module containing the function to patch
        attr: The attribute name to patch
        wrapper: The wrapper function
        
    Returns:
        True if patch was applied, False otherwise
    """
    try:
        wrapt.wrap_function_wrapper(module, attr, wrapper)
        logger.debug(f"Applied patch to {module.__name__}.{attr}")
        return True
    except Exception as e:
        logger.warning(f"Failed to patch {module.__name__}.{attr}: {e}")
        return False


def create_sync_wrapper(
    pre_hook: Optional[Callable] = None,
    post_hook: Optional[Callable] = None,
) -> Callable:
    """
    Create a synchronous wrapper with pre and post hooks.
    
    Args:
        pre_hook: Called before the wrapped function with (args, kwargs)
        post_hook: Called after with (result, args, kwargs)
        
    Returns:
        A wrapt-compatible wrapper function
    """
    @wrapt.decorator
    def wrapper(wrapped, instance, args, kwargs):
        if pre_hook:
            pre_hook(instance, args, kwargs)
        
        result = wrapped(*args, **kwargs)
        
        if post_hook:
            result = post_hook(result, instance, args, kwargs)
        
        return result
    
    return wrapper


def create_async_wrapper(
    pre_hook: Optional[Callable] = None,
    post_hook: Optional[Callable] = None,
) -> Callable:
    """
    Create an async wrapper with pre and post hooks.
    
    Args:
        pre_hook: Called before the wrapped function (can be async)
        post_hook: Called after with (result, args, kwargs) (can be async)
        
    Returns:
        A wrapt-compatible async wrapper function
    """
    @wrapt.decorator
    async def wrapper(wrapped, instance, args, kwargs):
        import asyncio
        
        if pre_hook:
            if asyncio.iscoroutinefunction(pre_hook):
                await pre_hook(instance, args, kwargs)
            else:
                pre_hook(instance, args, kwargs)
        
        result = await wrapped(*args, **kwargs)
        
        if post_hook:
            if asyncio.iscoroutinefunction(post_hook):
                result = await post_hook(result, instance, args, kwargs)
            else:
                result = post_hook(result, instance, args, kwargs)
        
        return result
    
    return wrapper
