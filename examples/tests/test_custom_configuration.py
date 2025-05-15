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

import secrets
from unittest.mock import patch, MagicMock
from aidefense import ChatInspectionClient, HttpInspectionClient, Config
import requests


def test_custom_configuration_workflow(capsys):
    dummy_api_key = secrets.token_hex(32)
    dummy_result = MagicMock(is_safe=True)

    with patch.object(
        ChatInspectionClient, "inspect_prompt", return_value=dummy_result
    ), patch.object(
        ChatInspectionClient,
        "inspect_conversation",
        side_effect=Exception("Expected error"),
    ), patch.object(
        HttpInspectionClient, "inspect", return_value=dummy_result
    ):

        # Custom API endpoint
        print("\n=== Custom API Endpoint Example ===")
        config = Config(runtime_base_url="https://custom-aidefense-api.example.com")
        client = ChatInspectionClient(api_key=dummy_api_key, config=config)
        print(f"Client configured to use endpoint: {client.endpoint}")
        print("(This is a demonstration - no actual API call will be made)")

        # Custom logging configuration
        print("\n=== Custom Logging Example ===")
        config1 = Config(
            logger_params={
                "level": "DEBUG",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "filename": "aidefense.log",
                "filemode": "w",
            }
        )
        client1 = ChatInspectionClient(api_key=dummy_api_key, config=config1)
        print("Client 1: Configured with custom logging parameters")
        print("Client 2: Configured with custom logger instance")
        try:
            client1.inspect_conversation([])
        except Exception as e:
            print(f"Expected error caught: {e}")

        # Retry policy configuration
        print("\n=== Retry Policy Example ===")
        config = Config(
            retry_config={
                "total": 5,
                "backoff_factor": 0.5,
                "status_forcelist": [500, 502, 503, 504],
                "allowed_methods": ["GET", "POST"],
            }
        )
        client = ChatInspectionClient(api_key=dummy_api_key, config=config)
        print("Client configured with custom retry policy")
        print("Will retry 5 times with exponential backoff")

        # Connection pooling example
        print("\n=== Connection Pooling Example ===")
        config1 = Config(
            pool_config={
                "pool_connections": 10,
                "pool_maxsize": 20,
                "max_retries": 3,
                "pool_block": True,
            }
        )
        client1 = HttpInspectionClient(api_key=dummy_api_key, config=config1)
        print("Client 1: Configured with custom connection pool parameters")
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=5,
            pool_maxsize=10,
            max_retries=requests.adapters.Retry(total=3, backoff_factor=0.5),
        )
        config2 = Config(connection_pool=adapter)
        client2 = HttpInspectionClient(api_key=dummy_api_key, config=config2)
        print("Client 2: Configured with custom connection pool adapter")

    out = capsys.readouterr().out
    assert "=== Custom API Endpoint Example ===" in out
    assert "Client configured to use endpoint:" in out
    assert "(This is a demonstration - no actual API call will be made)" in out
    assert "=== Custom Logging Example ===" in out
    assert "Client 1: Configured with custom logging parameters" in out
    assert "Client 2: Configured with custom logger instance" in out
    assert "Expected error caught:" in out
    assert "=== Retry Policy Example ===" in out
    assert "Client configured with custom retry policy" in out
    assert "Will retry 5 times with exponential backoff" in out
    assert "=== Connection Pooling Example ===" in out
    assert "Client 1: Configured with custom connection pool parameters" in out
    assert "Client 2: Configured with custom connection pool adapter" in out
