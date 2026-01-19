"""Tests for patching safety infrastructure (Task 2.1)."""

import pytest

from aidefense.runtime.agentsec.patchers import (
    get_patched_clients,
    is_patched,
    mark_patched,
    reset_registry,
)


@pytest.fixture(autouse=True)
def reset_patches():
    """Reset patch registry before and after each test."""
    reset_registry()
    yield
    reset_registry()


class TestPatchRegistry:
    """Test patch registry functionality."""

    def test_patch_registry_tracks_patched(self):
        """Test patch registry tracks patched functions."""
        assert not is_patched("test_client")
        
        mark_patched("test_client")
        
        assert is_patched("test_client")

    def test_double_patch_prevention(self):
        """Test double-patch prevention (same function not patched twice)."""
        mark_patched("openai")
        
        # Calling mark_patched again should not raise
        mark_patched("openai")
        
        # Should still be patched
        assert is_patched("openai")
        
        # Should only appear once in patched clients
        patched = get_patched_clients()
        assert patched.count("openai") == 1

    def test_graceful_skip_missing_library(self):
        """Test graceful skip when library not installed."""
        from aidefense.runtime.agentsec.patchers._base import safe_import
        
        # Import a non-existent module
        result = safe_import("nonexistent_module_xyz")
        
        assert result is None

    def test_get_patched_clients_returns_list(self):
        """Test get_patched_clients() returns correct list."""
        assert get_patched_clients() == []
        
        mark_patched("client1")
        mark_patched("client2")
        
        patched = get_patched_clients()
        assert "client1" in patched
        assert "client2" in patched
        assert len(patched) == 2

    def test_wrapt_compatibility(self):
        """Test compatibility with wrapt patterns."""
        import wrapt
        
        # Verify wrapt is available and works
        @wrapt.decorator
        def simple_wrapper(wrapped, instance, args, kwargs):
            return wrapped(*args, **kwargs)
        
        @simple_wrapper
        def test_func(x):
            return x * 2
        
        assert test_func(5) == 10


class TestSafeImport:
    """Test safe_import utility."""

    def test_safe_import_existing(self):
        """Test safe_import with existing module."""
        from aidefense.runtime.agentsec.patchers._base import safe_import
        
        result = safe_import("json")
        assert result is not None
        assert hasattr(result, "dumps")

    def test_safe_import_missing(self):
        """Test safe_import with missing module."""
        from aidefense.runtime.agentsec.patchers._base import safe_import
        
        result = safe_import("this_module_does_not_exist_12345")
        assert result is None









