"""Tests for context propagation infrastructure (Task 1.1)."""

import asyncio

import pytest

from aidefense.runtime.agentsec._context import (
    clear_inspection_context,
    get_inspection_context,
    merge_metadata,
    set_inspection_context,
)
from aidefense.runtime.agentsec.decision import Decision


@pytest.fixture(autouse=True)
def clear_context():
    """Clear context before and after each test."""
    clear_inspection_context()
    yield
    clear_inspection_context()


class TestContextPropagation:
    """Test context propagation with contextvars."""

    def test_set_get_inspection_context_sync(self):
        """Test set/get inspection context in sync code."""
        metadata = {"user": "test", "session": "123"}
        decision = Decision.allow()
        
        set_inspection_context(metadata=metadata, decision=decision, done=True)
        
        ctx = get_inspection_context()
        assert ctx.metadata == metadata
        assert ctx.decision == decision
        assert ctx.done is True

    @pytest.mark.asyncio
    async def test_set_get_inspection_context_async(self):
        """Test set/get inspection context in async code."""
        metadata = {"user": "async_test"}
        decision = Decision.block(reasons=["test"])
        
        set_inspection_context(metadata=metadata, decision=decision, done=False)
        
        # Await something to ensure we're in async context
        await asyncio.sleep(0)
        
        ctx = get_inspection_context()
        assert ctx.metadata == metadata
        assert ctx.decision == decision
        assert ctx.done is False

    @pytest.mark.asyncio
    async def test_context_isolation_concurrent(self):
        """Test context isolation between concurrent async calls."""
        results = []
        
        async def task(task_id: str):
            set_inspection_context(metadata={"task_id": task_id})
            await asyncio.sleep(0.01)  # Small delay to interleave
            ctx = get_inspection_context()
            results.append((task_id, ctx.metadata.get("task_id")))
        
        await asyncio.gather(
            task("task1"),
            task("task2"),
            task("task3"),
        )
        
        # Each task should see its own context
        for task_id, seen_id in results:
            assert task_id == seen_id, f"Task {task_id} saw {seen_id}"

    def test_decision_storage_retrieval(self):
        """Test decision storage and retrieval from context."""
        # Test with different decision types
        decisions = [
            Decision.allow(),
            Decision.block(reasons=["violation"]),
            Decision.sanitize(reasons=["pii"]),
            Decision.monitor_only(reasons=["logged"]),
        ]
        
        for decision in decisions:
            clear_inspection_context()
            set_inspection_context(decision=decision)
            
            ctx = get_inspection_context()
            assert ctx.decision == decision
            assert ctx.decision.action == decision.action


class TestMetadataMerge:
    """Test metadata merging."""

    def test_merge_metadata(self):
        """Test merging additional metadata."""
        set_inspection_context(metadata={"key1": "value1"})
        merge_metadata({"key2": "value2"})
        
        ctx = get_inspection_context()
        assert ctx.metadata == {"key1": "value1", "key2": "value2"}

    def test_merge_metadata_override(self):
        """Test that merge can override existing keys."""
        set_inspection_context(metadata={"key": "old"})
        merge_metadata({"key": "new"})
        
        ctx = get_inspection_context()
        assert ctx.metadata["key"] == "new"









