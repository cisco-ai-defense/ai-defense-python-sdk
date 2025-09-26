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
"""Internal route helpers for the AI Defense Management API.

These helpers centralize relative API paths used by the management clients.
They are intentionally kept internal (module is prefixed with an underscore)
so that end users do not override or depend on these paths directly.

All paths returned here are relative. `BaseClient._get_url()` is responsible
for adding the base URL and API version.
"""
from __future__ import annotations

# Top-level resource names (relative paths)
APPLICATIONS = "applications"
CONNECTIONS = "connections"
POLICIES = "policies"
EVENTS = "events"

# Applications


def application_by_id(application_id: str) -> str:
    return f"{APPLICATIONS}/{application_id}"


# Connections


def connection_by_id(connection_id: str) -> str:
    return f"{CONNECTIONS}/{connection_id}"


def connection_keys(connection_id: str) -> str:
    return f"{CONNECTIONS}/{connection_id}/keys"


# Policies


def policy_by_id(policy_id: str) -> str:
    return f"{POLICIES}/{policy_id}"


def policy_connections(policy_id: str) -> str:
    return f"{POLICIES}/{policy_id}/connections"


# Events


def event_by_id(event_id: str) -> str:
    return f"{EVENTS}/{event_id}"


def event_conversation(event_id: str) -> str:
    return f"{EVENTS}/{event_id}/conversation"


__all__ = [
    # Resources
    "APPLICATIONS",
    "CONNECTIONS",
    "POLICIES",
    "EVENTS",
    # Builders
    "application_by_id",
    "connection_by_id",
    "connection_keys",
    "policy_by_id",
    "policy_connections",
    "event_by_id",
    "event_conversation",
]
