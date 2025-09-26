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

import pytest

from aidefense.management.routes import (
    APPLICATIONS,
    CONNECTIONS,
    POLICIES,
    EVENTS,
    application_by_id,
    connection_by_id,
    connection_keys,
    policy_by_id,
    policy_connections,
    event_by_id,
    event_conversation,
)


class TestRoutes:
    def test_constants(self):
        assert APPLICATIONS == "applications"
        assert CONNECTIONS == "connections"
        assert POLICIES == "policies"
        assert EVENTS == "events"

    def test_applications_routes(self):
        assert application_by_id("app-123") == "applications/app-123"

    def test_connections_routes(self):
        assert connection_by_id("conn-123") == "connections/conn-123"
        assert connection_keys("conn-123") == "connections/conn-123/keys"

    def test_policies_routes(self):
        assert policy_by_id("pol-123") == "policies/pol-123"
        assert policy_connections("pol-123") == "policies/pol-123/connections"

    def test_events_routes(self):
        assert event_by_id("evt-123") == "events/evt-123"
        assert event_conversation("evt-123") == "events/evt-123/conversation"
