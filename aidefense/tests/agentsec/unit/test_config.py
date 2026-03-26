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

"""Tests for agentsec config module (validation constants only)."""

from aidefense.runtime.agentsec.config import VALID_MODES, VALID_GATEWAY_MODES, VALID_INTEGRATION_MODES


def test_valid_modes():
    assert "off" in VALID_MODES
    assert "monitor" in VALID_MODES
    assert "enforce" in VALID_MODES


def test_valid_gateway_modes():
    assert "on" in VALID_GATEWAY_MODES
    assert "off" in VALID_GATEWAY_MODES


def test_valid_integration_modes():
    assert "api" in VALID_INTEGRATION_MODES
    assert "gateway" in VALID_INTEGRATION_MODES
