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

"""Regression tests for optional AIBOM dependency behavior."""

from __future__ import annotations

import builtins
import importlib
import sys

import pytest


TEST_API_KEY = "0123456789" * 6 + "0123"


def test_aibom_package_imports_when_optional_cli_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Importing aidefense.aibom should not fail when aibom.cli is unavailable."""
    original_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "aibom.cli" or (name == "aibom" and fromlist and "cli" in fromlist):
            raise ModuleNotFoundError("No module named 'aibom'")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.delitem(sys.modules, "aidefense.aibom", raising=False)
    monkeypatch.delitem(sys.modules, "aidefense.aibom.aibom_client", raising=False)

    module = importlib.import_module("aidefense.aibom")

    assert hasattr(module, "AiBom")
    assert hasattr(module, "AiBomClient")


def test_analyze_raises_clear_error_when_optional_cli_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """AiBomClient.analyze should raise an actionable error without cisco-aibom."""
    original_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "aibom.cli" or (name == "aibom" and fromlist and "cli" in fromlist):
            raise ModuleNotFoundError("No module named 'aibom'")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.delitem(sys.modules, "aidefense.aibom", raising=False)
    monkeypatch.delitem(sys.modules, "aidefense.aibom.aibom_client", raising=False)

    module = importlib.import_module("aidefense.aibom")
    client = module.AiBomClient(api_key=TEST_API_KEY)

    with pytest.raises(ModuleNotFoundError, match="cisco-aibom"):
        client.analyze(["."])
