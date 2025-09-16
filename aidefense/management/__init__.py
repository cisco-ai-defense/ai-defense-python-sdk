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

"""
AI Defense Management API
Provides access to the AI Defense Management API for managing applications, connections, policies, and events.
"""

from .management_client import ManagementClient
from .applications import ApplicationManagementClient
from .connections import ConnectionManagementClient
from .policies import PolicyManagementClient
from .events import EventManagementClient

__all__ = [
    "ManagementClient",
    "ApplicationManagementClient",
    "ConnectionManagementClient",
    "PolicyManagementClient",
    "EventManagementClient",
]
