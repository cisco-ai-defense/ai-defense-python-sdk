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
from unittest.mock import patch, MagicMock
import secrets
from aidefense import ChatInspectionClient
from aidefense.runtime.chat_models import Message, Role


def test_chat_inspect_mistral_workflow(capsys):
    user_prompt = (
        "What are the main differences between supervised and unsupervised learning?"
    )
    dummy_api_key = secrets.token_hex(32)
    client = ChatInspectionClient(api_key=dummy_api_key)

    # Mock the Mistral API response
    fake_mistral_response = MagicMock()
    fake_mistral_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "Supervised uses labeled data; unsupervised does not."
                }
            }
        ]
    }
    fake_mistral_response.raise_for_status.return_value = None

    with patch.object(
        ChatInspectionClient, "inspect_prompt", return_value=MagicMock(is_safe=True)
    ), patch.object(
        ChatInspectionClient, "inspect_response", return_value=MagicMock(is_safe=True)
    ), patch.object(
        ChatInspectionClient,
        "inspect_conversation",
        return_value=MagicMock(is_safe=True),
    ), patch(
        "requests.post", return_value=fake_mistral_response
    ):

        # --- Inspect the user prompt ---
        prompt_result = client.inspect_prompt(user_prompt)
        print("\n----------------Inspect Prompt Result----------------")
        print("Prompt is safe?", prompt_result.is_safe)
        if not prompt_result.is_safe:
            print("Violated policies: ...")

        # --- Call Mistral API (mocked) ---
        import requests

        MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
        mistral_headers = {
            "Authorization": f"Bearer fake-key",
            "Content-Type": "application/json",
        }
        mistral_payload = {
            "model": "mistral-large-latest",
            "messages": [{"role": "user", "content": user_prompt}],
            "temperature": 0.7,
            "max_tokens": 500,
        }
        mistral_response = requests.post(
            MISTRAL_API_URL, headers=mistral_headers, json=mistral_payload
        )
        mistral_response.raise_for_status()
        mistral_data = mistral_response.json()
        ai_response = (
            mistral_data.get("choices", [{}])[0].get("message", {}).get("content", "")
        )

        print("\n----------------Mistral AI Response----------------")
        print("Response:", ai_response)

        # --- Inspect the AI response ---
        response_result = client.inspect_response(ai_response)
        print("\n----------------Inspect Response Result----------------")
        print("Response is safe?", response_result.is_safe)

        # --- Inspect the full conversation ---
        conversation = [
            Message(role=Role.USER, content=user_prompt),
            Message(role=Role.ASSISTANT, content=ai_response),
        ]
        conversation_result = client.inspect_conversation(conversation)
        print("\n----------------Inspect Conversation Result----------------")
        print("Conversation is safe?", conversation_result.is_safe)

    out = capsys.readouterr().out
    assert "----------------Inspect Prompt Result----------------" in out
    assert "Prompt is safe? True" in out
    assert "----------------Mistral AI Response----------------" in out
    assert "Response: Supervised uses labeled data; unsupervised does not." in out
    assert "----------------Inspect Response Result----------------" in out
    assert "Response is safe? True" in out
    assert "----------------Inspect Conversation Result----------------" in out
    assert "Conversation is safe? True" in out
