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

"""AI-BOM (AI Bill of Materials) module for Cisco AI Defense.

This module provides client support for managing AI-BOM analyses, listing BOMs,
retrieving BOM details, and listing components.
"""

from .aibom_base import AIBom
from .routes import (
    aibom_analysis,
    aibom_boms,
    aibom_boms_summary,
    aibom_bom_by_id,
    aibom_bom_components,
)

__all__ = [
    "AIBom",
    "aibom_analysis",
    "aibom_boms",
    "aibom_boms_summary",
    "aibom_bom_by_id",
    "aibom_bom_components",
]
