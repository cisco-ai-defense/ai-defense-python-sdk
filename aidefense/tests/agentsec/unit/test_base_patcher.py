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
