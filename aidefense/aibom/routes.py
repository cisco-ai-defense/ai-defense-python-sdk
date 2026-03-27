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

AI_BOMS = "/aibom/boms"
AI_BOM_ANALYSIS = "/aibom/analysis"

def analysis() -> str:
    """Route to submit an analysis report."""
    return AI_BOM_ANALYSIS

def boms() -> str:
    """Route to retrieve all BOMs."""
    return AI_BOMS

def bom_by_id(analysis_id: str) -> str:
    """Route to retrieve a BOM details."""
    return f"{AI_BOMS}/{analysis_id}"

def bom_components(analysis_id: str) -> str:
    """Route to retrieve the components of a BOM."""
    return f"{AI_BOMS}/{analysis_id}/components"

def boms_summary() -> str:
    """Route to retrieve the summary stats of all BOMs."""
    return f"{AI_BOMS}:summary"
