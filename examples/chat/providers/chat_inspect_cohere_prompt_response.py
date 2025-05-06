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
Example: Inspecting a Cohere prompt and response using ChatInspectionClient

This script demonstrates:
- Sending a prompt to the Cohere API and receiving a response
- Inspecting both the prompt and the response separately
- Inspecting the full conversation (prompt + response) for safety
"""
import os
import requests
from aidefense import ChatInspectionClient
from aidefense.runtime.chat_models import Message, Role

# --- Configuration ---
COHERE_API_KEY = os.environ.get("COHERE_API_KEY", "YOUR_COHERE_API_KEY")
AIDEFENSE_API_KEY = os.environ.get("AIDEFENSE_API_KEY", "YOUR_AIDEFENSE_API_KEY")
COHERE_API_URL = "https://api.cohere.com/v1/chat"

# --- User Prompt ---
user_prompt = "Tell me a fun fact about space."

# --- Inspect the user prompt ---
client = ChatInspectionClient(api_key=AIDEFENSE_API_KEY)
prompt_result = client.inspect_prompt(user_prompt)
print("Prompt is safe?", prompt_result.is_safe)

# --- Call Cohere API ---
cohere_headers = {
    "Authorization": f"Bearer {COHERE_API_KEY}",
    "Content-Type": "application/json",
}
cohere_payload = {"message": user_prompt}
cohere_response = requests.post(COHERE_API_URL, headers=cohere_headers, json=cohere_payload)
cohere_response.raise_for_status()
cohere_data = cohere_response.json()
ai_response = cohere_data.get("text") or cohere_data.get("reply") or cohere_data.get("response") or ""

print("Cohere AI Response:", ai_response)

# 2. Inspect the AI response
response_result = client.inspect_response(ai_response)
print("Response is safe?", response_result.is_safe)

# 3. Inspect the full conversation
conversation = [
    Message(role=Role.USER, content=user_prompt),
    Message(role=Role.ASSISTANT, content=ai_response),
]
conversation_result = client.inspect_conversation(conversation)
print("Conversation is safe?", conversation_result.is_safe)
