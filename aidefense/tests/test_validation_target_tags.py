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

from unittest.mock import AsyncMock, MagicMock

import pytest

from aidefense.pydantic.validation.ai_validation.v1.ai_validation_pydantic import (
    CreateTargetRequest,
    CreateTargetResponse,
    GetTargetResponse,
    ListTargetsRequest,
    ListTargetsResponse,
    Tag,
    TargetSummary,
    TargetUpdate,
    UpdateTargetResponse,
)
from aidefense.validation.targets import Targets


TARGET_ID = "123e4567-e89b-12d3-a456-426614174000"


def _api(response):
    api = MagicMock()
    api.request = AsyncMock(return_value=response)
    api.parse.side_effect = lambda model, data, _context: model.model_validate(data)
    return api


@pytest.mark.asyncio
async def test_create_serializes_tags_and_parses_response():
    api = _api({"target_id": TARGET_ID})
    targets = Targets(api)

    response = await targets.create(
        CreateTargetRequest(
            name="tagged-target",
            tags=[Tag(key="agent_id", value="wd-agent-18422")],
        )
    )

    api.request.assert_awaited_once_with(
        "POST",
        "ai-validation/targets",
        data={
            "name": "tagged-target",
            "tags": [{"key": "agent_id", "value": "wd-agent-18422"}],
        },
    )
    assert response == CreateTargetResponse(target_id=TARGET_ID)


@pytest.mark.asyncio
async def test_list_serializes_filters_and_parses_target_tags():
    api = _api(
        {
            "targets": [
                {
                    "target_id": TARGET_ID,
                    "name": "tagged-target",
                    "tags": [{"key": "agent_id", "value": "wd-agent-18422"}],
                }
            ]
        }
    )
    targets = Targets(api)

    response = await targets.list(
        ListTargetsRequest(tag_key="agent_id", tag_value="wd-agent-18422")
    )

    api.request.assert_awaited_once_with(
        "GET",
        "ai-validation/targets",
        params={"tag_key": "agent_id", "tag_value": "wd-agent-18422"},
    )
    assert response == ListTargetsResponse(
        targets=[
            TargetSummary(
                target_id=TARGET_ID,
                name="tagged-target",
                tags=[Tag(key="agent_id", value="wd-agent-18422")],
            )
        ]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("target_update", "expected_data"),
    [
        (
            TargetUpdate(tags=[Tag(key="team", value="validation")]),
            {"tags": [{"key": "team", "value": "validation"}]},
        ),
        (
            TargetUpdate(remove_tag_keys=["environment"]),
            {"remove_tag_keys": ["environment"]},
        ),
        (
            TargetUpdate(
                tags=[Tag(key="environment", value="production")],
                remove_tag_keys=["team"],
            ),
            {
                "tags": [{"key": "environment", "value": "production"}],
                "remove_tag_keys": ["team"],
            },
        ),
    ],
    ids=["merge", "remove", "merge-and-remove"],
)
async def test_update_serializes_tag_mutations(target_update, expected_data):
    api = _api({})
    targets = Targets(api)

    response = await targets.update(TARGET_ID, target_update)

    api.ensure_uuid.assert_called_once_with(TARGET_ID, "target_id")
    api.request.assert_awaited_once_with(
        "PATCH",
        f"ai-validation/targets/{TARGET_ID}",
        data=expected_data,
    )
    assert response == UpdateTargetResponse()


def test_get_target_response_parses_tags():
    response = GetTargetResponse.model_validate(
        {
            "target_id": TARGET_ID,
            "name": "tagged-target",
            "tags": [
                {"key": "agent_id", "value": "wd-agent-18422"},
                {"key": "environment", "value": "production"},
            ],
        }
    )

    assert response.tags == [
        Tag(key="agent_id", value="wd-agent-18422"),
        Tag(key="environment", value="production"),
    ]
