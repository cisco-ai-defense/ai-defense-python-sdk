# Copyright 2025 Cisco Systems, Inc. and its affiliates
# SPDX-License-Identifier: Apache-2.0

import pytest
from unittest.mock import MagicMock
from datetime import datetime

from aidefense.management.validation_client import AiValidationClient
from aidefense.management.models.validation import (
    StartAiValidationRequest,
    StartAiValidationResponse,
    GetAiValidationJobResponse,
    ListAllAiValidationConfigResponse,
    GetAiValidationConfigResponse,
    AssetType,
    AWSRegion,
    JobStatus,
    Header,
)
from aidefense.exceptions import ApiError


TEST_API_KEY = "0123456789" * 6 + "0123"


@pytest.fixture
def mock_request_handler():
    handler = MagicMock()
    # Provide a valid set of HTTP methods if BaseClient validates against it
    if not hasattr(handler, "VALID_HTTP_METHODS"):
        handler.VALID_HTTP_METHODS = {"GET", "POST", "PUT", "DELETE"}
    return handler


@pytest.fixture
def validation_client(mock_request_handler):
    client = AiValidationClient(
        api_key=TEST_API_KEY, request_handler=mock_request_handler
    )
    client.make_request = MagicMock()
    return client


class TestAiValidationClient:
    def test_start_ai_validation(self, validation_client):
        mock_response = {"task_id": "task-123"}
        validation_client.make_request.return_value = mock_response

        req = StartAiValidationRequest(
            asset_type=AssetType.APPLICATION,
            application_id="app-123",
            validation_scan_name="My Scan",
            model_provider="OpenAI",
            headers=[Header(key="Authorization", value="Bearer xyz")],
            model_endpoint_url_model_id="gpt-4",
            model_request_template='{"messages": ...}',
            description="validation run",
            aws_region=AWSRegion.AWS_REGION_US_EAST_1,
            max_tokens=100,
            temperature=0.2,
            top_p=0.9,
            stop_sequences=["<END>"],
        )

        resp = validation_client.start_ai_validation(req)

        expected_data = req.to_body_dict()

        validation_client.make_request.assert_called_once_with(
            "POST",
            "ai-validation/start",
            data=expected_data,
        )

        assert isinstance(resp, StartAiValidationResponse)
        assert resp.task_id == "task-123"

    def test_get_ai_validation_job(self, validation_client):
        mock_response = {
            "task_id": "task-123",
            "tenant_id": "tenant-1",
            "config_id": "cfg-1",
            "run_count": 1,
            "status": "JOB_IN_PROGRESS",
            "progress": 50,
            "total_num_prompts": 100,
            "error_message": "",
            "created_at": "2025-01-01T00:00:00Z",
            "started_at": "2025-01-01T00:05:00Z",
            "completed_at": None,
        }
        validation_client.make_request.return_value = mock_response

        resp = validation_client.get_ai_validation_job("task-123")

        validation_client.make_request.assert_called_once_with(
            "GET", "ai-validation/job/task-123"
        )

        assert isinstance(resp, GetAiValidationJobResponse)
        assert resp.status == JobStatus.JOB_IN_PROGRESS
        assert resp.progress == 50

    def test_list_all_ai_validation_config(self, validation_client):
        mock_response = {
            "config": [
                {
                    "config_id": "cfg-1",
                    "tenant_id": "tenant-1",
                    "asset_type": "APPLICATION",
                    "application_id": "app-123",
                    "ai_asset_name": "name",
                    "validation_scan_name": "scan-1",
                    "model_provider": "OpenAI",
                    "model_endpoint_url_model_id": "gpt-4",
                    "model_request_template": "{}",
                    "model_response_json_path": "choices[0].message.content",
                    "created_at": "2025-01-01T00:00:00Z",
                    "updated_at": "2025-01-01T00:10:00Z",
                }
            ]
        }
        validation_client.make_request.return_value = mock_response

        resp = validation_client.list_all_ai_validation_config()

        validation_client.make_request.assert_called_once_with(
            "GET", "ai-validation/config"
        )

        assert isinstance(resp, ListAllAiValidationConfigResponse)
        assert len(resp.config) == 1
        assert resp.config[0].config_id == "cfg-1"

    def test_get_ai_validation_config(self, validation_client):
        mock_response = {
            "config_id": "cfg-1",
            "tenant_id": "tenant-1",
            "asset_type": "MODEL",
            "application_id": "",
            "ai_asset_name": "model_name",
            "validation_scan_name": "scan-2",
            "model_provider": "Anthropic",
            "model_endpoint_url_model_id": "claude-3-sonnet",
            "model_request_template": "{}",
            "model_response_json_path": "content",
            "created_at": "2025-02-01T00:00:00Z",
            "updated_at": "2025-02-01T00:05:00Z",
        }
        validation_client.make_request.return_value = mock_response

        resp = validation_client.get_ai_validation_config("task-xyz")

        validation_client.make_request.assert_called_once_with(
            "GET", "ai-validation/config/task-xyz"
        )

        assert isinstance(resp, GetAiValidationConfigResponse)
        assert resp.config_id == "cfg-1"
        assert resp.asset_type == AssetType.MODEL

    def test_error_propagation(self, validation_client):
        validation_client.make_request.side_effect = ApiError("API Error")

        with pytest.raises(ApiError):
            validation_client.get_ai_validation_job("task-err")
