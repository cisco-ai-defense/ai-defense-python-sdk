"""
Example: Inspecting an OpenAI API HTTP request and response using HttpInspectionClient

This script demonstrates:
- Sending a prompt to the OpenAI API and receiving a response
- Inspecting the HTTP request and response using the AI Defense SDK
- Inspecting the same request using both the raw and high-level HTTP inspection methods
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

# config = Config(logger_params={"level": "DEBUG"})

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
print("HTTP Request (raw) is safe?", req_res.is_safe)

# --- Inspect the HTTP request ---
req_result = http_client.inspect_request(
    method="POST",
    url=OPENAI_API_URL,
    headers=openai_headers,
    body=raw_body,
)
print("HTTP Request is safe?", req_result.is_safe)

# --- Send the HTTP request and get the response ---
resp = requests.post(OPENAI_API_URL, headers=openai_headers, json=openai_payload)
resp.raise_for_status()
print(resp.content)

# --- Inspect the HTTP response (with request context) ---
resp_result = http_client.inspect_response(
    status_code=resp.status_code,
    url=OPENAI_API_URL,
    headers=dict(resp.headers),
    body=resp.content,
    request_method="POST",
    request_headers=openai_headers,
    request_body=raw_body,
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
