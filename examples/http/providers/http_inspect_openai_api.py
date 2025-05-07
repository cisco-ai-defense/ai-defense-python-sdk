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
Example: Inspecting an OpenAI API HTTP request and response using HttpInspectionClient

# This script demonstrates how to use the AI Defense SDK to inspect HTTP requests/responses
# at various points in the OpenAI API interaction:
# 1. Inspecting the request before sending it (both raw and using dictionary body)
# 2. Inspecting the response with full request context (using dictionary for request context)
# 3. Demonstrating automatic JSON serialization of dictionary bodies
"""
import os
import requests
from aidefense import HttpInspectionClient, Config
from aidefense.runtime.utils import to_base64_bytes
import json

# --- Configuration ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY")
AIDEFENSE_API_KEY = os.environ.get("AIDEFENSE_API_KEY", "YOUR_AIDEFENSE_API_KEY")
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

# --- User Prompt ---
user_prompt = "Tell me a fun fact about space."
# user_prompt = "How to make a bomb?"  # Example of a potentially unsafe prompt

# --- Prepare the HTTP request ---
openai_headers = {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "Content-Type": "application/json",
}
openai_payload = {
    "model": "gpt-4",
    "messages": [{"role": "user", "content": user_prompt}],
    "max_tokens": 150
}

# --- Inspect the outgoing HTTP request (before sending) ---
http_client = HttpInspectionClient(api_key=AIDEFENSE_API_KEY)

# Method 1: Using the low-level inspect() method (manual encoding required)
raw_body = json.dumps(openai_payload).encode()
http_req_dict = {
    "method": "POST",
    "headers": openai_headers,
    "body": to_base64_bytes(raw_body),
}
http_meta = {"url": OPENAI_API_URL}

req_res = http_client.inspect(
    http_req=http_req_dict,
    http_meta=http_meta,
)
print("HTTP Request is safe?", req_res.is_safe)

# Method 2: Using the high-level inspect_request() method with dictionary body
# The dictionary is automatically JSON-serialized - no manual encoding needed
req_result = http_client.inspect_request(
    method="POST",
    url=OPENAI_API_URL,
    headers=openai_headers,
    body=openai_payload,  # Pass the dictionary directly - SDK handles serialization
)
print("HTTP Request is safe?", req_result.is_safe)

# --- Send the HTTP request and get the response ---
resp = requests.post(OPENAI_API_URL, headers=openai_headers, json=openai_payload)
resp.raise_for_status()
print(resp.content)

# --- Inspect the HTTP response (with request context) ---
# Method 1: Using response.content (bytes) directly
resp_result = http_client.inspect_response(
    status_code=resp.status_code,
    url=OPENAI_API_URL,
    headers=dict(resp.headers),
    body=resp.content,  # Using bytes
    request_method="POST",
    request_headers=openai_headers,
    request_body=openai_payload,  # Using dictionary directly for request context

)
print("HTTP Response is safe?", resp_result.is_safe)

# --- Inspect using requests.PreparedRequest and requests.Response objects ---
prepared = requests.Request(
    method="POST",
    url=OPENAI_API_URL,
    headers=openai_headers,
    data=raw_body,
).prepare()

lib_req_result = http_client.inspect_request_from_http_library(prepared)
print("Library Request is safe?", lib_req_result.is_safe)

lib_resp_result = http_client.inspect_response_from_http_library(resp)
print("Library Response is safe?", lib_resp_result.is_safe)
if not lib_resp_result.is_safe:
    print("violations: ", lib_resp_result.rules)
