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
Example: Inspecting an Amazon Bedrock API HTTP request and response using HttpInspectionClient

This script demonstrates:
- Sending a prompt to Amazon Bedrock API and receiving a response
- Inspecting the HTTP request and response using the AI Defense SDK
- Inspecting the same request using both the raw and high-level HTTP inspection methods
"""
import os
import json
import requests
from aidefense import HttpInspectionClient, Config
from aidefense.runtime.utils import to_base64_bytes

# --- Configuration ---
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AIDEFENSE_API_KEY = os.environ.get("AIDEFENSE_API_KEY", "YOUR_AIDEFENSE_API_KEY")

# --- User Prompt ---
user_prompt = "Explain three key benefits of cloud computing."

# --- Create HTTP Inspection Client ---
http_client = HttpInspectionClient(api_key=AIDEFENSE_API_KEY)

try:
    # In a real application, you'd use the boto3 client
    # This example shows how to use raw HTTP for inspection purposes
    import boto3
    from botocore.auth import SigV4Auth
    from botocore.awsrequest import AWSRequest

    # Initialize a boto3 session to get credentials
    session = boto3.Session()
    credentials = session.get_credentials()

    # Define the AWS endpoint
    model_id = "anthropic.claude-v2"  # Claude model on Bedrock
    endpoint = f"https://bedrock-runtime.{AWS_REGION}.amazonaws.com/model/{model_id}/invoke"

    # --- Prepare the HTTP request ---
    bedrock_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    bedrock_payload = {
        "prompt": f"\n\nHuman: {user_prompt}\n\nAssistant:",
        "max_tokens_to_sample": 300,
        "temperature": 0.5,
        "top_p": 0.9
    }

    # --- Inspect the request using the raw method ---
    raw_body = json.dumps(bedrock_payload).encode()

    # Sign the request (for the actual API call later)
    aws_request = AWSRequest(method="POST", url=endpoint,
                             data=raw_body, headers=bedrock_headers)
    SigV4Auth(credentials, "bedrock", AWS_REGION).add_auth(aws_request)
    signed_headers = dict(aws_request.headers)

    # For inspection, we use both the original and signed headers
    http_req_dict = {
        "method": "POST",
        "headers": signed_headers,
        "body": to_base64_bytes(raw_body),
    }
    http_meta = {"url": endpoint}

    req_res = http_client.inspect(
        http_req=http_req_dict,
        http_meta=http_meta,
    )
    print("HTTP Request (raw) is safe?", req_res.is_safe)

    # --- Inspect the request using the high-level method ---
    req_result = http_client.inspect_request(
        method="POST",
        url=endpoint,
        headers=signed_headers,
        body=raw_body,
    )
    print("HTTP Request is safe?", req_result.is_safe)

    # --- Send the HTTP request and get the response using requests ---
    # We'll use the signed headers from our AWSRequest
    resp = requests.post(endpoint, headers=signed_headers, data=raw_body)
    resp.raise_for_status()
    print(resp.content)

    # --- Inspect the HTTP response (with request context) ---
    resp_result = http_client.inspect_response(
        status_code=resp.status_code,
        url=endpoint,
        headers=dict(resp.headers),
        body=resp.content,
        request_method="POST",
        request_headers=signed_headers,
        request_body=raw_body,
    )
    print("HTTP Response is safe?", resp_result.is_safe)

    # --- Inspect using requests.PreparedRequest and requests.Response objects ---
    # Create a fresh prepared request with our signed headers
    prepared = requests.Request(
        method="POST",
        url=endpoint,
        headers=signed_headers,
        data=raw_body,
    ).prepare()

    lib_req_result = http_client.inspect_request_from_http_library(prepared)
    print("Library Request is safe?", lib_req_result.is_safe)

    lib_resp_result = http_client.inspect_response_from_http_library(resp)
    print("Library Response is safe?", lib_resp_result.is_safe)
    if not lib_resp_result.is_safe:
        print("Violations: ", lib_resp_result.rules)

except Exception as e:
    print(f"\nError with Amazon Bedrock API: {e}")
    print("Note: This example requires AWS credentials and permissions to access Bedrock.")
    print("To run this example, you need to have the AWS CLI configured or appropriate environment variables set.")

    # For demonstration purposes, we'll create a mock response
    print("\n--- Mock example for demonstration purposes ---")

    # Mocked payload and response
    mock_payload = {
        "prompt": f"\n\nHuman: {user_prompt}\n\nAssistant:",
        "max_tokens_to_sample": 300
    }
    mock_raw_body = json.dumps(mock_payload).encode()
    mock_headers = {"Content-Type": "application/json"}

    # Inspect using high-level method
    mock_req_result = http_client.inspect_request(
        method="POST",
        url="https://bedrock-runtime.us-east-1.amazonaws.com/model/anthropic.claude-v2/invoke",
        headers=mock_headers,
        body=mock_raw_body,
    )
    print("Mock HTTP Request is safe?", mock_req_result.is_safe)
