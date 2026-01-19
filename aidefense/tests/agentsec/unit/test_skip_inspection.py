"""Tests for skip_inspection context manager and no_inspection decorator."""

import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from aidefense.runtime.agentsec._context import (
    skip_inspection,
    no_inspection,
    is_llm_skip_active,
    is_mcp_skip_active,
    _skip_llm,
    _skip_mcp,
)


class TestSkipStateManagement:
    """Test skip state context variables and getters."""
    
    def test_is_llm_skip_active_default_false(self):
        """Test that LLM skip is False by default."""
        # Reset to default
        _skip_llm.set(False)
        assert is_llm_skip_active() is False
    
    def test_is_mcp_skip_active_default_false(self):
        """Test that MCP skip is False by default."""
        # Reset to default
        _skip_mcp.set(False)
        assert is_mcp_skip_active() is False
    
    def test_is_llm_skip_active_when_set(self):
        """Test that is_llm_skip_active returns True when set."""
        token = _skip_llm.set(True)
        try:
            assert is_llm_skip_active() is True
        finally:
            _skip_llm.reset(token)
    
    def test_is_mcp_skip_active_when_set(self):
        """Test that is_mcp_skip_active returns True when set."""
        token = _skip_mcp.set(True)
        try:
            assert is_mcp_skip_active() is True
        finally:
            _skip_mcp.reset(token)
    
    def test_skip_state_isolation(self):
        """Test that LLM and MCP skip states are independent."""
        _skip_llm.set(False)
        _skip_mcp.set(False)
        
        # Set only LLM skip
        llm_token = _skip_llm.set(True)
        try:
            assert is_llm_skip_active() is True
            assert is_mcp_skip_active() is False
        finally:
            _skip_llm.reset(llm_token)


class TestSkipInspectionContextManager:
    """Test skip_inspection context manager."""
    
    def test_sync_context_manager_skips_both(self):
        """Test sync context manager skips both LLM and MCP by default."""
        _skip_llm.set(False)
        _skip_mcp.set(False)
        
        assert is_llm_skip_active() is False
        assert is_mcp_skip_active() is False
        
        with skip_inspection():
            assert is_llm_skip_active() is True
            assert is_mcp_skip_active() is True
        
        # State should be restored after exit
        assert is_llm_skip_active() is False
        assert is_mcp_skip_active() is False
    
    def test_sync_context_manager_llm_only(self):
        """Test sync context manager with llm=True, mcp=False."""
        _skip_llm.set(False)
        _skip_mcp.set(False)
        
        with skip_inspection(llm=True, mcp=False):
            assert is_llm_skip_active() is True
            assert is_mcp_skip_active() is False
        
        assert is_llm_skip_active() is False
        assert is_mcp_skip_active() is False
    
    def test_sync_context_manager_mcp_only(self):
        """Test sync context manager with llm=False, mcp=True."""
        _skip_llm.set(False)
        _skip_mcp.set(False)
        
        with skip_inspection(llm=False, mcp=True):
            assert is_llm_skip_active() is False
            assert is_mcp_skip_active() is True
        
        assert is_llm_skip_active() is False
        assert is_mcp_skip_active() is False
    
    def test_nested_context_managers_restore_state(self):
        """Test that nested context managers properly restore state."""
        _skip_llm.set(False)
        _skip_mcp.set(False)
        
        with skip_inspection(llm=True, mcp=False):
            assert is_llm_skip_active() is True
            assert is_mcp_skip_active() is False
            
            # Nested context
            with skip_inspection(llm=True, mcp=True):
                assert is_llm_skip_active() is True
                assert is_mcp_skip_active() is True
            
            # Should restore to outer context state
            assert is_llm_skip_active() is True
            assert is_mcp_skip_active() is False
        
        # Should restore to original state
        assert is_llm_skip_active() is False
        assert is_mcp_skip_active() is False
    
    @pytest.mark.asyncio
    async def test_async_context_manager_skips_both(self):
        """Test async context manager skips both LLM and MCP by default."""
        _skip_llm.set(False)
        _skip_mcp.set(False)
        
        assert is_llm_skip_active() is False
        assert is_mcp_skip_active() is False
        
        async with skip_inspection():
            assert is_llm_skip_active() is True
            assert is_mcp_skip_active() is True
        
        assert is_llm_skip_active() is False
        assert is_mcp_skip_active() is False
    
    @pytest.mark.asyncio
    async def test_async_context_manager_granular(self):
        """Test async context manager with granular control."""
        _skip_llm.set(False)
        _skip_mcp.set(False)
        
        async with skip_inspection(llm=True, mcp=False):
            assert is_llm_skip_active() is True
            assert is_mcp_skip_active() is False
        
        assert is_llm_skip_active() is False
        assert is_mcp_skip_active() is False


class TestNoInspectionDecorator:
    """Test no_inspection decorator."""
    
    def test_sync_decorator_skips_both(self):
        """Test sync decorator skips both LLM and MCP by default."""
        _skip_llm.set(False)
        _skip_mcp.set(False)
        
        @no_inspection()
        def my_func():
            return (is_llm_skip_active(), is_mcp_skip_active())
        
        llm_skip, mcp_skip = my_func()
        assert llm_skip is True
        assert mcp_skip is True
        
        # State should be restored after function returns
        assert is_llm_skip_active() is False
        assert is_mcp_skip_active() is False
    
    def test_sync_decorator_granular(self):
        """Test sync decorator with granular control."""
        _skip_llm.set(False)
        _skip_mcp.set(False)
        
        @no_inspection(llm=True, mcp=False)
        def my_func():
            return (is_llm_skip_active(), is_mcp_skip_active())
        
        llm_skip, mcp_skip = my_func()
        assert llm_skip is True
        assert mcp_skip is False
    
    def test_sync_decorator_preserves_metadata(self):
        """Test that decorator preserves function metadata."""
        @no_inspection()
        def my_documented_func():
            """This is my docstring."""
            pass
        
        assert my_documented_func.__name__ == "my_documented_func"
        assert my_documented_func.__doc__ == "This is my docstring."
    
    @pytest.mark.asyncio
    async def test_async_decorator_skips_both(self):
        """Test async decorator skips both LLM and MCP by default."""
        _skip_llm.set(False)
        _skip_mcp.set(False)
        
        @no_inspection()
        async def my_async_func():
            return (is_llm_skip_active(), is_mcp_skip_active())
        
        llm_skip, mcp_skip = await my_async_func()
        assert llm_skip is True
        assert mcp_skip is True
        
        assert is_llm_skip_active() is False
        assert is_mcp_skip_active() is False
    
    @pytest.mark.asyncio
    async def test_async_decorator_granular(self):
        """Test async decorator with granular control."""
        _skip_llm.set(False)
        _skip_mcp.set(False)
        
        @no_inspection(llm=False, mcp=True)
        async def my_async_func():
            return (is_llm_skip_active(), is_mcp_skip_active())
        
        llm_skip, mcp_skip = await my_async_func()
        assert llm_skip is False
        assert mcp_skip is True


class TestPatcherSkipIntegration:
    """Test that patchers correctly check skip state."""
    
    def test_openai_should_inspect_respects_skip(self):
        """Test OpenAI patcher's _should_inspect respects skip state."""
        from aidefense.runtime.agentsec.patchers.openai import _should_inspect
        
        _skip_llm.set(False)
        
        # When not skipped and mode is enforce, should inspect
        with patch('aidefense.runtime.agentsec.patchers.openai._state') as mock_state:
            mock_state.get_llm_mode.return_value = "on_enforce"
            with patch('aidefense.runtime.agentsec.patchers.openai.get_inspection_context') as mock_ctx:
                mock_ctx.return_value = MagicMock(done=False)
                assert _should_inspect() is True
        
        # When skipped, should not inspect
        with skip_inspection(llm=True):
            assert _should_inspect() is False
    
    def test_openai_should_use_gateway_respects_skip(self):
        """Test OpenAI patcher's _should_use_gateway respects skip state."""
        from aidefense.runtime.agentsec.patchers.openai import _should_use_gateway
        
        _skip_llm.set(False)
        
        # When skipped, should not use gateway
        with skip_inspection(llm=True):
            assert _should_use_gateway() is False
    
    def test_mcp_should_inspect_respects_skip(self):
        """Test MCP patcher's _should_inspect respects skip state."""
        from aidefense.runtime.agentsec.patchers.mcp import _should_inspect
        
        _skip_mcp.set(False)
        
        # When not skipped and mode is enforce, should inspect
        with patch('aidefense.runtime.agentsec.patchers.mcp._state') as mock_state:
            mock_state.get_mcp_mode.return_value = "on_enforce"
            mock_state.get_config.return_value = MagicMock(mcp_enabled=True)
            assert _should_inspect() is True
        
        # When skipped, should not inspect
        with skip_inspection(mcp=True):
            assert _should_inspect() is False
    
    def test_mcp_should_use_gateway_respects_skip(self):
        """Test MCP patcher's _should_use_gateway respects skip state."""
        from aidefense.runtime.agentsec.patchers.mcp import _should_use_gateway
        
        _skip_mcp.set(False)
        
        # When skipped, should not use gateway
        with skip_inspection(mcp=True):
            assert _should_use_gateway() is False
    
    def test_bedrock_should_inspect_respects_skip(self):
        """Test Bedrock patcher's _should_inspect respects skip state."""
        from aidefense.runtime.agentsec.patchers.bedrock import _should_inspect
        
        _skip_llm.set(False)
        
        # When skipped, should not inspect
        with skip_inspection(llm=True):
            assert _should_inspect() is False
    
class TestEndToEndSkipScenarios:
    """End-to-end tests for skip inspection scenarios."""
    
    def test_skip_llm_but_not_mcp(self):
        """Test skipping LLM inspection while keeping MCP inspection active."""
        _skip_llm.set(False)
        _skip_mcp.set(False)
        
        with skip_inspection(llm=True, mcp=False):
            # LLM should be skipped
            from aidefense.runtime.agentsec.patchers.openai import _should_inspect as openai_should_inspect
            assert openai_should_inspect() is False
            
            # MCP should NOT be skipped (check mode)
            from aidefense.runtime.agentsec.patchers.mcp import _should_inspect as mcp_should_inspect
            with patch('aidefense.runtime.agentsec.patchers.mcp._state') as mock_state:
                mock_state.get_mcp_mode.return_value = "on_enforce"
                mock_state.get_config.return_value = MagicMock(mcp_enabled=True)
                assert mcp_should_inspect() is True
    
    def test_skip_mcp_but_not_llm(self):
        """Test skipping MCP inspection while keeping LLM inspection active."""
        _skip_llm.set(False)
        _skip_mcp.set(False)
        
        with skip_inspection(llm=False, mcp=True):
            # MCP should be skipped
            from aidefense.runtime.agentsec.patchers.mcp import _should_inspect as mcp_should_inspect
            assert mcp_should_inspect() is False
            
            # LLM should NOT be skipped (check mode)
            from aidefense.runtime.agentsec.patchers.openai import _should_inspect as openai_should_inspect
            with patch('aidefense.runtime.agentsec.patchers.openai._state') as mock_state:
                mock_state.get_llm_mode.return_value = "on_enforce"
                with patch('aidefense.runtime.agentsec.patchers.openai.get_inspection_context') as mock_ctx:
                    mock_ctx.return_value = MagicMock(done=False)
                    assert openai_should_inspect() is True
    
    @pytest.mark.asyncio
    async def test_async_skip_with_concurrent_tasks(self):
        """Test that skip state is properly isolated in concurrent async tasks."""
        _skip_llm.set(False)
        _skip_mcp.set(False)
        
        results = {}
        
        async def task_with_skip():
            async with skip_inspection():
                results['with_skip'] = (is_llm_skip_active(), is_mcp_skip_active())
                await asyncio.sleep(0.01)  # Simulate async work
        
        async def task_without_skip():
            await asyncio.sleep(0.005)  # Start slightly after
            results['without_skip'] = (is_llm_skip_active(), is_mcp_skip_active())
        
        await asyncio.gather(task_with_skip(), task_without_skip())
        
        # Task with skip should have seen skip active
        assert results['with_skip'] == (True, True)
        
        # Task without skip should NOT have seen skip active (contextvars are task-local)
        assert results['without_skip'] == (False, False)

