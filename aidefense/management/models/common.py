# Copyright 2025 Cisco Systems, Inc. and its affiliates
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

"""Common models for the AI Defense Management API."""

from enum import Enum
from pydantic import Field
from ...models.base import AIDefenseModel


class SortOrder(str, Enum):
    """Sort order for list operations."""

    ASCENDING = "asc"
    DESCENDING = "desc"


class Paging(AIDefenseModel):
    """
    Pagination information for list operations.

    Attributes:
        offset (int): The offset from which the list starts.
        count (int): The number of items in the list.
        total (int): The total number of items in the backend.
    """

    offset: int = Field(..., description="The offset from which the list starts")
    count: int = Field(..., description="The number of items in the list")
    total: int = Field(..., description="The total number of items in the backend")
