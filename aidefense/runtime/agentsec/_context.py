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

"""Context propagation infrastructure using contextvars."""

import asyncio
import functools
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, TypeVar

from .decision import Decision


@dataclass
class InspectionContext:
    """Context for inspection state during a request."""
    metadata: Dict[str, Any]
    decision: Optional[Decision]
    done: bool


# Context variables for thread-safe and async-safe context propagation
_inspection_metadata: ContextVar[Dict[str, Any]] = ContextVar(
    "_inspection_metadata", default={}
)
_inspection_decision: ContextVar[Optional[Decision]] = ContextVar(
    "_inspection_decision", default=None
)
_inspection_done: ContextVar[bool] = ContextVar(
    "_inspection_done", default=False
)

# Skip inspection context variables
_skip_llm: ContextVar[bool] = ContextVar("_skip_llm", default=False)
_skip_mcp: ContextVar[bool] = ContextVar("_skip_mcp", default=False)


def get_inspection_context() -> InspectionContext:
    """
    Get the current inspection context.
    
    Returns:
        InspectionContext with current metadata, decision, and done flag
    """
    return InspectionContext(
        metadata=_inspection_metadata.get(),
        decision=_inspection_decision.get(),
        done=_inspection_done.get(),
    )


def set_inspection_context(
    metadata: Optional[Dict[str, Any]] = None,
    decision: Optional[Decision] = None,
    done: Optional[bool] = None,
) -> None:
    """
    Set inspection context values.
    
    Args:
        metadata: Request metadata to store (agent name, role, session_id, etc.)
        decision: The inspection decision
        done: Whether inspection has been completed for this request
    """
    if metadata is not None:
        _inspection_metadata.set(metadata)
    if decision is not None:
        _inspection_decision.set(decision)
    if done is not None:
        _inspection_done.set(done)


def clear_inspection_context() -> None:
    """Clear all inspection context values."""
    _inspection_metadata.set({})
    _inspection_decision.set(None)
    _inspection_done.set(False)


def merge_metadata(additional: Dict[str, Any]) -> None:
    """
    Merge additional metadata into the current context.
    
    Args:
        additional: Additional metadata to merge
    """
    current = _inspection_metadata.get()
    _inspection_metadata.set({**current, **additional})


# =============================================================================
# Skip Inspection API
# =============================================================================

def is_llm_skip_active() -> bool:
    """
    Check if LLM inspection skip is currently active.
    
    Returns:
        True if LLM inspection should be skipped, False otherwise
    """
    return _skip_llm.get()


def is_mcp_skip_active() -> bool:
    """
    Check if MCP inspection skip is currently active.
    
    Returns:
        True if MCP inspection should be skipped, False otherwise
    """
    return _skip_mcp.get()


class skip_inspection:
    """
    Context manager to temporarily skip AI Defense inspection for LLM and/or MCP calls.
    
    Works with both sync and async code:
    
    Sync usage:
        with skip_inspection():
            response = client.chat.completions.create(...)
    
    Async usage:
        async with skip_inspection():
            response = await client.chat.completions.create(...)
    
    Granular control:
        with skip_inspection(llm=True, mcp=False):
            # Skip LLM inspection only, still inspect MCP
            response = client.chat.completions.create(...)
    
    Args:
        llm: If True, skip LLM inspection (default: True)
        mcp: If True, skip MCP inspection (default: True)
    """
    
    def __init__(self, llm: bool = True, mcp: bool = True):
        self._skip_llm = llm
        self._skip_mcp = mcp
        self._llm_token: Optional[Token[bool]] = None
        self._mcp_token: Optional[Token[bool]] = None
    
    def __enter__(self) -> "skip_inspection":
        """Enter sync context - set skip flags."""
        if self._skip_llm:
            self._llm_token = _skip_llm.set(True)
        if self._skip_mcp:
            self._mcp_token = _skip_mcp.set(True)
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit sync context - restore previous skip state."""
        if self._llm_token is not None:
            _skip_llm.reset(self._llm_token)
        if self._mcp_token is not None:
            _skip_mcp.reset(self._mcp_token)
    
    async def __aenter__(self) -> "skip_inspection":
        """Enter async context - set skip flags."""
        if self._skip_llm:
            self._llm_token = _skip_llm.set(True)
        if self._skip_mcp:
            self._mcp_token = _skip_mcp.set(True)
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context - restore previous skip state."""
        if self._llm_token is not None:
            _skip_llm.reset(self._llm_token)
        if self._mcp_token is not None:
            _skip_mcp.reset(self._mcp_token)


# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])


def no_inspection(llm: bool = True, mcp: bool = True) -> Callable[[F], F]:
    """
    Decorator to skip AI Defense inspection for all calls within a function.
    
    Works with both sync and async functions:
    
    Sync usage:
        @no_inspection
        def my_health_check():
            return client.chat.completions.create(...)
    
    Async usage:
        @no_inspection
        async def my_async_health_check():
            return await client.chat.completions.create(...)
    
    Granular control:
        @no_inspection(llm=True, mcp=False)
        def my_function():
            # Skip LLM inspection only
            ...
    
    Args:
        llm: If True, skip LLM inspection (default: True)
        mcp: If True, skip MCP inspection (default: True)
    
    Returns:
        Decorated function that skips inspection
    """
    def decorator(func: F) -> F:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                async with skip_inspection(llm=llm, mcp=mcp):
                    return await func(*args, **kwargs)
            return async_wrapper  # type: ignore
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                with skip_inspection(llm=llm, mcp=mcp):
                    return func(*args, **kwargs)
            return sync_wrapper  # type: ignore
    return decorator
