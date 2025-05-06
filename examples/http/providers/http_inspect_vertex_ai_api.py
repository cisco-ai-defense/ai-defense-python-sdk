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
Example: Inspecting a Google Vertex AI API HTTP request and response using HttpInspectionClient

This script demonstrates:
- Sending a prompt to the Vertex AI API and receiving a response
- Inspecting the HTTP request and response using the AI Defense SDK
- Inspecting the same request using both the raw and high-level HTTP inspection methods
"""
import os
import requests
import google.auth
import google.auth.transport.requests
from aidefense import HttpInspectionClient, Config
from aidefense.runtime.utils import to_base64_bytes
import json

# --- Configuration ---
GOOGLE_PROJECT_ID = os.environ.get("GOOGLE_PROJECT_ID", "YOUR_GOOGLE_PROJECT_ID")
AIDEFENSE_API_KEY = os.environ.get("AIDEFENSE_API_KEY", "YOUR_AIDEFENSE_API_KEY")
VERTEX_LOCATION = "us-central1"  # Adjust based on your preferred region
VERTEX_MODEL = "gemini-1.0-pro"
VERTEX_API_URL = f"https://{VERTEX_LOCATION}-aiplatform.googleapis.com/v1/projects/{GOOGLE_PROJECT_ID}/locations/{VERTEX_LOCATION}/publishers/google/models/{VERTEX_MODEL}:predict"

# --- User Prompt ---
user_prompt = "Explain the theory of relativity in simple terms."

# --- Create HTTP Inspection Client ---
http_client = HttpInspectionClient(api_key=AIDEFENSE_API_KEY)

try:
    # In a real application, you'd use the Google Cloud Python client library
    # This example shows how to use requests with proper authentication

    # Get credentials using Application Default Credentials
    credentials, project = google.auth.default()
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)

    # --- Prepare the HTTP request ---
    vertex_headers = {
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type": "application/json"
    }

    vertex_payload = {
        "instances": [
            {
                "content": user_prompt
            }
        ],
        "parameters": {
            "temperature": 0.2,
            "maxOutputTokens": 256,
            "topK": 40,
            "topP": 0.95
        }
    }

    # --- Inspect the request using the raw method ---
    raw_body = json.dumps(vertex_payload).encode()
    http_req_dict = {
        "method": "POST",
        "headers": vertex_headers,
        "body": to_base64_bytes(raw_body),
    }
    http_meta = {"url": VERTEX_API_URL}

    req_res = http_client.inspect(
        http_req=http_req_dict,
        http_meta=http_meta,
    )
    print("HTTP Request (raw) is safe?", req_res.is_safe)

    # --- Inspect the request using the high-level method ---
    req_result = http_client.inspect_request(
        method="POST",
        url=VERTEX_API_URL,
        headers=vertex_headers,
        body=raw_body,
    )
    print("HTTP Request is safe?", req_result.is_safe)

    # --- Send the HTTP request and get the response ---
    resp = requests.post(VERTEX_API_URL, headers=vertex_headers, json=vertex_payload)
    resp.raise_for_status()
    print(resp.content)

    # --- Inspect the HTTP response (with request context) ---
    resp_result = http_client.inspect_response(
        status_code=resp.status_code,
        url=VERTEX_API_URL,
        headers=dict(resp.headers),
        body=resp.content,
        request_method="POST",
        request_headers=vertex_headers,
        request_body=raw_body,
    )
    print("HTTP Response is safe?", resp_result.is_safe)

    # --- Inspect using requests.PreparedRequest and requests.Response objects ---
    prepared = requests.Request(
        method="POST",
        url=VERTEX_API_URL,
        headers=vertex_headers,
        data=raw_body,
    ).prepare()

    lib_req_result = http_client.inspect_request_from_http_library(prepared)
    print("Library Request is safe?", lib_req_result.is_safe)

    lib_resp_result = http_client.inspect_response_from_http_library(resp)
    print("Library Response is safe?", lib_resp_result.is_safe)
    if not lib_resp_result.is_safe:
        print("Violations: ", lib_resp_result.rules)

except Exception as e:
    print(f"\nError with Vertex AI API: {e}")
    print("Note: This example requires Google Cloud credentials and permissions to access Vertex AI.")
    print("To run this example, ensure you have properly configured Google Cloud credentials.")

    # For demonstration purposes, we'll create a mock response
    print("\n--- Mock example for demonstration purposes ---")

    # Mocked payload and response
    mock_payload = {
        "instances": [{"content": user_prompt}],
        "parameters": {"temperature": 0.2}
    }
    mock_raw_body = json.dumps(mock_payload).encode()
    mock_headers = {"Content-Type": "application/json", "Authorization": "Bearer mock_token"}

    # Inspect using high-level method
    mock_req_result = http_client.inspect_request(
        method="POST",
        url="https://example-vertex-api.googleapis.com/predict",
        headers=mock_headers,
        body=mock_raw_body,
    )
    print("Mock HTTP Request is safe?", mock_req_result.is_safe)
