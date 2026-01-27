"""Tests for base patcher utilities."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import sys


class TestSafeImport:
    """Test safe_import function."""

    def test_safe_import_existing_module(self):
        """Test importing an existing module."""
        from aidefense.runtime.agentsec.patchers._base import safe_import
        
        result = safe_import("json")
        
        assert result is not None
        assert hasattr(result, "dumps")

    def test_safe_import_nonexistent_module(self):
        """Test importing a nonexistent module returns None."""
        from aidefense.runtime.agentsec.patchers._base import safe_import
        
        result = safe_import("nonexistent_module_xyz")
        
        assert result is None


class TestApplyPatch:
    """Test apply_patch function."""

    def test_apply_patch_success(self):
        """Test successful patch application."""
        from aidefense.runtime.agentsec.patchers._base import apply_patch
        
        # Create a mock module
        mock_module = MagicMock()
        mock_module.__name__ = "test_module"
        mock_module.test_func = lambda x: x
        
        def wrapper(wrapped, instance, args, kwargs):
            return wrapped(*args, **kwargs)
        
        with patch("aidefense.runtime.agentsec.patchers._base.wrapt.wrap_function_wrapper") as mock_wrap:
            result = apply_patch(mock_module, "test_func", wrapper)
        
        assert result is True
        mock_wrap.assert_called_once()

    def test_apply_patch_failure(self):
        """Test patch failure returns False."""
        from aidefense.runtime.agentsec.patchers._base import apply_patch
        
        mock_module = MagicMock()
        mock_module.__name__ = "test_module"
        
        with patch("aidefense.runtime.agentsec.patchers._base.wrapt.wrap_function_wrapper", side_effect=Exception("fail")):
            result = apply_patch(mock_module, "test_func", lambda: None)
        
        assert result is False


class TestCreateSyncWrapper:
    """Test create_sync_wrapper function."""

    def test_sync_wrapper_no_hooks(self):
        """Test sync wrapper with no hooks."""
        from aidefense.runtime.agentsec.patchers._base import create_sync_wrapper
        
        wrapper = create_sync_wrapper()
        
        def original(x):
            return x * 2
        
        # The wrapper returns a decorator that wraps the function
        wrapped = wrapper(original)
        result = wrapped(5)
        
        assert result == 10

    def test_sync_wrapper_with_pre_hook(self):
        """Test sync wrapper with pre hook."""
        from aidefense.runtime.agentsec.patchers._base import create_sync_wrapper
        
        pre_called = []
        
        def pre_hook(instance, args, kwargs):
            pre_called.append(True)
        
        wrapper = create_sync_wrapper(pre_hook=pre_hook)
        
        def original(x):
            return x * 2
        
        wrapped = wrapper(original)
        result = wrapped(5)
        
        assert result == 10
        assert len(pre_called) == 1

    def test_sync_wrapper_with_post_hook(self):
        """Test sync wrapper with post hook that modifies result."""
        from aidefense.runtime.agentsec.patchers._base import create_sync_wrapper
        
        def post_hook(result, instance, args, kwargs):
            return result + 1
        
        wrapper = create_sync_wrapper(post_hook=post_hook)
        
        def original(x):
            return x * 2
        
        wrapped = wrapper(original)
        result = wrapped(5)
        
        assert result == 11  # (5 * 2) + 1

    def test_sync_wrapper_with_both_hooks(self):
        """Test sync wrapper with both pre and post hooks."""
        from aidefense.runtime.agentsec.patchers._base import create_sync_wrapper
        
        call_order = []
        
        def pre_hook(instance, args, kwargs):
            call_order.append("pre")
        
        def post_hook(result, instance, args, kwargs):
            call_order.append("post")
            return result
        
        wrapper = create_sync_wrapper(pre_hook=pre_hook, post_hook=post_hook)
        
        def original(x):
            call_order.append("original")
            return x
        
        wrapped = wrapper(original)
        wrapped(5)
        
        assert call_order == ["pre", "original", "post"]


class TestCreateAsyncWrapper:
    """Test create_async_wrapper function."""

    @pytest.mark.asyncio
    async def test_async_wrapper_no_hooks(self):
        """Test async wrapper with no hooks."""
        from aidefense.runtime.agentsec.patchers._base import create_async_wrapper
        
        wrapper = create_async_wrapper()
        
        async def original(x):
            return x * 2
        
        wrapped = wrapper(original)
        result = await wrapped(5)
        
        assert result == 10

    @pytest.mark.asyncio
    async def test_async_wrapper_with_sync_pre_hook(self):
        """Test async wrapper with synchronous pre hook."""
        from aidefense.runtime.agentsec.patchers._base import create_async_wrapper
        
        pre_called = []
        
        def pre_hook(instance, args, kwargs):
            pre_called.append(True)
        
        wrapper = create_async_wrapper(pre_hook=pre_hook)
        
        async def original(x):
            return x * 2
        
        wrapped = wrapper(original)
        result = await wrapped(5)
        
        assert result == 10
        assert len(pre_called) == 1

    @pytest.mark.asyncio
    async def test_async_wrapper_with_async_pre_hook(self):
        """Test async wrapper with async pre hook."""
        from aidefense.runtime.agentsec.patchers._base import create_async_wrapper
        
        pre_called = []
        
        async def pre_hook(instance, args, kwargs):
            pre_called.append(True)
        
        wrapper = create_async_wrapper(pre_hook=pre_hook)
        
        async def original(x):
            return x * 2
        
        wrapped = wrapper(original)
        result = await wrapped(5)
        
        assert result == 10
        assert len(pre_called) == 1

    @pytest.mark.asyncio
    async def test_async_wrapper_with_sync_post_hook(self):
        """Test async wrapper with synchronous post hook."""
        from aidefense.runtime.agentsec.patchers._base import create_async_wrapper
        
        def post_hook(result, instance, args, kwargs):
            return result + 1
        
        wrapper = create_async_wrapper(post_hook=post_hook)
        
        async def original(x):
            return x * 2
        
        wrapped = wrapper(original)
        result = await wrapped(5)
        
        assert result == 11

    @pytest.mark.asyncio
    async def test_async_wrapper_with_async_post_hook(self):
        """Test async wrapper with async post hook."""
        from aidefense.runtime.agentsec.patchers._base import create_async_wrapper
        
        async def post_hook(result, instance, args, kwargs):
            return result + 1
        
        wrapper = create_async_wrapper(post_hook=post_hook)
        
        async def original(x):
            return x * 2
        
        wrapped = wrapper(original)
        result = await wrapped(5)
        
        assert result == 11

    @pytest.mark.asyncio
    async def test_async_wrapper_with_both_hooks(self):
        """Test async wrapper with both pre and post hooks."""
        from aidefense.runtime.agentsec.patchers._base import create_async_wrapper
        
        call_order = []
        
        async def pre_hook(instance, args, kwargs):
            call_order.append("pre")
        
        async def post_hook(result, instance, args, kwargs):
            call_order.append("post")
            return result
        
        wrapper = create_async_wrapper(pre_hook=pre_hook, post_hook=post_hook)
        
        async def original(x):
            call_order.append("original")
            return x
        
        wrapped = wrapper(original)
        await wrapped(5)
        
        assert call_order == ["pre", "original", "post"]


