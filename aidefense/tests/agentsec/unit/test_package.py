"""Tests for package structure and imports (Task 1.1)."""

import sys

import pytest


class TestPackageStructure:
    """Test package structure and imports."""

    def test_agentsec_importable(self):
        """Test that agentsec package is importable."""
        from aidefense.runtime import agentsec
        assert agentsec is not None

    def test_public_api_exports(self):
        """Test that public API exports are accessible."""
        from aidefense.runtime.agentsec import Decision, SecurityPolicyError, protect, skip_inspection, no_inspection
        
        assert callable(protect)
        assert Decision is not None
        assert SecurityPolicyError is not None
        assert callable(skip_inspection)
        assert callable(no_inspection)

    def test_python_version(self):
        """Test that Python version is 3.10+."""
        assert sys.version_info >= (3, 10), "Python 3.10+ required"









