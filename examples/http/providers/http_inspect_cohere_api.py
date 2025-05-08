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
Example: Inspecting a Cohere API HTTP request and response using HttpInspectionClient

This script demonstrates:
- Sending a prompt to the Cohere API and receiving a response
- Inspecting the HTTP request and response using the AI Defense SDK
- Inspecting the same request using both the raw and high-level HTTP inspection methods
"""
import os
import requests
from aidefense import HttpInspectionClient, Config
from aidefense.runtime.utils import to_base64_bytes
import json

# --- Configuration ---
COHERE_API_KEY = os.environ.get("COHERE_API_KEY", "YOUR_COHERE_API_KEY")
AIDEFENSE_API_KEY = os.environ.get("AIDEFENSE_API_KEY", "YOUR_AIDEFENSE_API_KEY")
COHERE_API_URL = "https://api.cohere.com/v1/chat"

# config = Config(logger_params={"level": "DEBUG"})

# --- User Prompt ---
user_prompt = "Gimme python code to generate a random password"
# user_prompt = "How to make a bomb?"

# --- Prepare the HTTP request ---
cohere_headers = {
    "Authorization": f"Bearer {COHERE_API_KEY}",
    "Content-Type": "application/json",
}
cohere_payload = {"message": user_prompt}

# --- Inspect the outgoing HTTP request (before sending) ---
http_client = HttpInspectionClient(api_key=AIDEFENSE_API_KEY)

raw_body = json.dumps(cohere_payload).encode()
http_req_dict = {
    "method": "POST",
    "headers": {
        "Authorization": f"Bearer {COHERE_API_KEY}",
        "Content-Type": "application/json",
    },
    "body": to_base64_bytes(raw_body),
}
http_meta = {"url": COHERE_API_URL}

req_res = http_client.inspect(
    http_req=http_req_dict,
    http_meta=http_meta,
)
print("HTTP Request (raw) is safe?", req_res.is_safe)

# --- Inspect the HTTP request ---
req_result = http_client.inspect_request(
    method="POST",
    url=COHERE_API_URL,
    headers=cohere_headers,
    body=raw_body,
)
print("HTTP Request is safe?", req_result.is_safe)

# --- Send the HTTP request and get the response ---
resp = requests.post(COHERE_API_URL, headers=cohere_headers, json=cohere_payload)
resp.raise_for_status()
print(resp.content)

# --- Inspect the HTTP response (with request context) ---
resp_result = http_client.inspect_response(
    status_code=resp.status_code,
    url=COHERE_API_URL,
    headers=dict(resp.headers),
    body=resp.content,
    request_method="POST",
    request_headers=cohere_headers,
    request_body=raw_body,
)
print("HTTP Response is safe?", resp_result.is_safe)

# --- Inspect using requests.PreparedRequest and requests.Response objects ---
prepared = requests.Request(
    method="POST",
    url=COHERE_API_URL,
    headers=cohere_headers,
    data=raw_body,
).prepare()

lib_req_result = http_client.inspect_request_from_http_library(prepared)
print("Library Request is safe?", lib_req_result.is_safe)

lib_resp_result = http_client.inspect_response_from_http_library(resp)
print("Library Response is safe?", lib_resp_result.is_safe)
if not lib_resp_result.is_safe:
    print("violations: ", lib_resp_result.rules)
