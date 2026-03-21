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

"""Tests for package structure and imports (Task 1.1)."""

import sys
from importlib import metadata

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
        """Test that Python version is 3.9+."""
        assert sys.version_info >= (3, 9), "Python 3.9+ required"

    def test_agentsec_version_matches_distribution(self):
        """Keep runtime version metadata aligned with the installed package."""
        from aidefense.runtime import agentsec

        assert agentsec.__version__ == metadata.version("cisco-aidefense-sdk")
