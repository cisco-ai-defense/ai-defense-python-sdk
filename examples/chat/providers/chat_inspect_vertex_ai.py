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
Example: Inspecting a Google Vertex AI prompt and response using ChatInspectionClient

This script demonstrates:
- Sending a prompt to the Vertex AI API and receiving a response
- Inspecting both the prompt and the response separately
- Inspecting the full conversation (prompt + response) for safety
"""

import os
import requests
import json
import google.auth
import google.auth.transport.requests
from aidefense import ChatInspectionClient
from aidefense.runtime.chat_models import Message, Role

# --- Configuration ---
# For Vertex AI, you typically need a Google Cloud project and credentials
# This example assumes you're using Application Default Credentials
# https://cloud.google.com/docs/authentication/application-default-credentials
GOOGLE_PROJECT_ID = os.environ.get("GOOGLE_PROJECT_ID", "YOUR_GOOGLE_PROJECT_ID")
AIDEFENSE_API_KEY = os.environ.get("AIDEFENSE_API_KEY", "YOUR_AIDEFENSE_API_KEY")
VERTEX_LOCATION = "us-central1"  # Adjust based on your preferred region
VERTEX_MODEL = "gemini-1.0-pro"
VERTEX_API_URL = f"https://{VERTEX_LOCATION}-aiplatform.googleapis.com/v1/projects/{GOOGLE_PROJECT_ID}/locations/{VERTEX_LOCATION}/publishers/google/models/{VERTEX_MODEL}:predict"

# --- User Prompt ---
user_prompt = "Explain the theory of relativity in simple terms."

# --- Inspect the user prompt ---
client = ChatInspectionClient(api_key=AIDEFENSE_API_KEY)
prompt_result = client.inspect_prompt(user_prompt)
print("\n----------------Inspect Prompt Result----------------")
print("Prompt is safe?", prompt_result.is_safe)
if not prompt_result.is_safe:
    print(
        f"Violated policies: {[rule.rule_name.value for rule in prompt_result.rules or []]}"
    )

# --- Call Vertex AI API ---
# Note: In a real application, you'd likely use the Google Cloud Python client library
# This example uses requests with Application Default Credentials
# You would need to have properly configured your Google Cloud credentials
try:
    # This is a simplified example using requests
    # In production, use google-auth and google-cloud-aiplatform packages

    credentials, project = google.auth.default()
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)

    vertex_headers = {
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type": "application/json",
    }

    vertex_payload = {
        "instances": [{"content": user_prompt}],
        "parameters": {
            "temperature": 0.2,
            "maxOutputTokens": 256,
            "topK": 40,
            "topP": 0.95,
        },
    }

    vertex_response = requests.post(
        VERTEX_API_URL, headers=vertex_headers, json=vertex_payload
    )
    vertex_response.raise_for_status()
    vertex_data = vertex_response.json()
    ai_response = vertex_data.get("predictions", [{}])[0].get("content", "")

    print("\n----------------Vertex AI Response----------------")
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

except Exception as e:
    print(f"\nError calling Vertex AI API: {e}")
    print(
        "Note: This example requires Google Cloud credentials and permissions to access Vertex AI."
    )
    print("For testing purposes, you can mock the API response as follows:")

    # Mock response for testing without actual API call
    ai_response = "Einstein's theory of relativity has two parts: Special Relativity and General Relativity. Special Relativity says that the laws of physics are the same for everyone, no matter how fast they're moving, and that the speed of light is constant. General Relativity explains that gravity is actually the bending of space and time by massive objects."

    print("\n----------------Mocked Vertex AI Response----------------")
    print("Response:", ai_response)

    # Continue with inspection as before
    response_result = client.inspect_response(ai_response)
    print("\n----------------Inspect Response Result----------------")
    print("Response is safe?", response_result.is_safe)

    conversation = [
        Message(role=Role.USER, content=user_prompt),
        Message(role=Role.ASSISTANT, content=ai_response),
    ]
    conversation_result = client.inspect_conversation(conversation)
    print("\n----------------Inspect Conversation Result----------------")
    print("Conversation is safe?", conversation_result.is_safe)
