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

"""Route helpers for AI-BOM API endpoints."""

AIBOM_PREFIX = "aibom"


def aibom_analysis() -> str:
    """Route for creating an AI-BOM analysis."""
    return f"{AIBOM_PREFIX}/analysis"


def aibom_boms() -> str:
    """Route for listing AI-BOMs."""
    return f"{AIBOM_PREFIX}/boms"


def aibom_boms_summary() -> str:
    """Route for getting AI-BOM summary stats."""
    return f"{AIBOM_PREFIX}/boms:summary"


def aibom_bom_by_id(analysis_id: str) -> str:
    """Route for getting or deleting an AI-BOM by analysis ID."""
    return f"{AIBOM_PREFIX}/boms/{analysis_id}"


def aibom_bom_components(analysis_id: str) -> str:
    """Route for listing components of an AI-BOM."""
    return f"{AIBOM_PREFIX}/boms/{analysis_id}/components"
