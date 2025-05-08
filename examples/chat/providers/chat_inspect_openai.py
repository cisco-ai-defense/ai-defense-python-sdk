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
Example: Inspecting an OpenAI prompt and response using ChatInspectionClient

This script demonstrates:
- Sending a prompt to the OpenAI API and receiving a response
- Inspecting both the prompt and the response separately
- Inspecting the full conversation (prompt + response) for safety
"""

import os
import requests
from aidefense import ChatInspectionClient
from aidefense.runtime.chat_models import Message, Role

# --- Configuration ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY")
AIDEFENSE_API_KEY = os.environ.get("AIDEFENSE_API_KEY", "YOUR_AIDEFENSE_API_KEY")
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

# --- User Prompt ---
user_prompt = "Tell me a fun fact about quantum computing."

# --- Inspect the user prompt ---
client = ChatInspectionClient(api_key=AIDEFENSE_API_KEY)
prompt_result = client.inspect_prompt(user_prompt)
print("\n----------------Inspect Prompt Result----------------")
print("Prompt is safe?", prompt_result.is_safe)
if not prompt_result.is_safe:
    print(
        f"Violated policies: {[rule.rule_name.value for rule in prompt_result.rules or []]}"
    )

# --- Call OpenAI API ---
openai_headers = {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "Content-Type": "application/json",
}
openai_payload = {
    "model": "gpt-4",
    "messages": [{"role": "user", "content": user_prompt}],
    "max_tokens": 150,
}
openai_response = requests.post(
    OPENAI_API_URL, headers=openai_headers, json=openai_payload
)
openai_response.raise_for_status()
openai_data = openai_response.json()
ai_response = openai_data.get("choices", [{}])[0].get("message", {}).get("content", "")

print("\n----------------OpenAI Response----------------")
print("Response:", ai_response)

# --- Inspect the AI response ---
response_result = client.inspect_response(ai_response)
print("\n----------------Inspect Response Result----------------")
print("Response is safe?", response_result.is_safe)
if not response_result.is_safe:
    print(
        f"Violated policies: {[rule.rule_name.value for rule in response_result.rules or []]}"
    )

# --- Inspect the full conversation ---
conversation = [
    Message(role=Role.USER, content=user_prompt),
    Message(role=Role.ASSISTANT, content=ai_response),
]
conversation_result = client.inspect_conversation(conversation)
print("\n----------------Inspect Conversation Result----------------")
print("Conversation is safe?", conversation_result.is_safe)
if not conversation_result.is_safe:
    print(
        f"Violated policies: {[rule.rule_name.value for rule in conversation_result.rules or []]}"
    )
