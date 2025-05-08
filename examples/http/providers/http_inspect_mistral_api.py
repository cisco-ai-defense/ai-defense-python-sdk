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
Example: Inspecting a Mistral AI API HTTP request and response using HttpInspectionClient

This script demonstrates:
- Sending a prompt to the Mistral AI API and receiving a response
- Inspecting the HTTP request and response using the AI Defense SDK
- Inspecting the same request using both the raw and high-level HTTP inspection methods
"""
import os
import requests
from aidefense import HttpInspectionClient, Config
from aidefense.runtime.utils import to_base64_bytes
import json

# --- Configuration ---
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "YOUR_MISTRAL_API_KEY")
AIDEFENSE_API_KEY = os.environ.get("AIDEFENSE_API_KEY", "YOUR_AIDEFENSE_API_KEY")
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"

# --- User Prompt ---
user_prompt = (
    "What are the main differences between supervised and unsupervised learning?"
)

# --- Create HTTP Inspection Client ---
http_client = HttpInspectionClient(api_key=AIDEFENSE_API_KEY)

try:
    # --- Prepare the HTTP request ---
    mistral_headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json",
    }

    mistral_payload = {
        "model": "mistral-large-latest",  # Or another available model
        "messages": [{"role": "user", "content": user_prompt}],
        "temperature": 0.7,
        "max_tokens": 500,
    }

    # --- Inspect the request using the raw method ---
    raw_body = json.dumps(mistral_payload).encode()
    http_req_dict = {
        "method": "POST",
        "headers": mistral_headers,
        "body": to_base64_bytes(raw_body),
    }
    http_meta = {"url": MISTRAL_API_URL}

    req_res = http_client.inspect(
        http_req=http_req_dict,
        http_meta=http_meta,
    )
    print("HTTP Request (raw) is safe?", req_res.is_safe)

    # --- Inspect the request using the high-level method ---
    req_result = http_client.inspect_request(
        method="POST",
        url=MISTRAL_API_URL,
        headers=mistral_headers,
        body=raw_body,
    )
    print("HTTP Request is safe?", req_result.is_safe)

    # --- Send the HTTP request and get the response ---
    resp = requests.post(MISTRAL_API_URL, headers=mistral_headers, json=mistral_payload)
    resp.raise_for_status()
    print(resp.content)

    # --- Inspect the HTTP response (with request context) ---
    resp_result = http_client.inspect_response(
        status_code=resp.status_code,
        url=MISTRAL_API_URL,
        headers=dict(resp.headers),
        body=resp.content,
        request_method="POST",
        request_headers=mistral_headers,
        request_body=raw_body,
    )
    print("HTTP Response is safe?", resp_result.is_safe)

    # --- Inspect using requests.PreparedRequest and requests.Response objects ---
    prepared = requests.Request(
        method="POST",
        url=MISTRAL_API_URL,
        headers=mistral_headers,
        data=raw_body,
    ).prepare()

    lib_req_result = http_client.inspect_request_from_http_library(prepared)
    print("Library Request is safe?", lib_req_result.is_safe)

    lib_resp_result = http_client.inspect_response_from_http_library(resp)
    print("Library Response is safe?", lib_resp_result.is_safe)
    if not lib_resp_result.is_safe:
        print("Violations: ", lib_resp_result.rules)

except Exception as e:
    print(f"\nError with Mistral AI API: {e}")
    print("Note: This example requires a valid Mistral AI API key.")

    # For demonstration purposes, we'll create a mock response
    print("\n--- Mock example for demonstration purposes ---")

    # Mocked payload and response
    mock_payload = {
        "model": "mistral-large-latest",
        "messages": [{"role": "user", "content": user_prompt}],
    }
    mock_raw_body = json.dumps(mock_payload).encode()
    mock_headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer mock_token",
    }

    # Inspect using high-level method
    mock_req_result = http_client.inspect_request(
        method="POST",
        url=MISTRAL_API_URL,
        headers=mock_headers,
        body=mock_raw_body,
    )
    print("Mock HTTP Request is safe?", mock_req_result.is_safe)
