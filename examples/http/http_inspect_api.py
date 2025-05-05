"""
Example: Using inspect for raw HTTP request/response dicts
"""

from aidefense import HttpInspectionClient
from aidefense.runtime.utils import to_base64_bytes

client = HttpInspectionClient(api_key="YOUR_API_KEY")

# Example HTTP request (as dict)
json_bytes = b'{"key": "value"}'
http_req = {
    "method": "POST",
    "headers": {"Content-Type": "application/json"},
    "body": to_base64_bytes(json_bytes),  # base64-encoded bytes using SDK utility
}

http_meta = {"url": "https://api.example.com/myendpoint"}
result = client.inspect(http_req=http_req, http_meta=http_meta)
print("Is safe?", result.is_safe)
print("Details:", result)
