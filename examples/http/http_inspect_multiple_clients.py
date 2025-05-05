"""
Example: Creating two HttpInspectionClient instances with a shared Config and calling different methods
"""

from aidefense import HttpInspectionClient, Config
from aidefense.runtime.utils import to_base64_bytes

config = Config(logger_params={"level": "INFO"})

client1 = HttpInspectionClient(api_key="YOUR_API_KEY", config=config)
client2 = HttpInspectionClient(api_key="YOUR_API_KEY", config=config)

# Use client1 to inspect a raw HTTP request (inspect)
json_bytes = b'{"key": "value"}'
http_req = {
    "method": "POST",
    "headers": {"Content-Type": "application/json"},
    "body": to_base64_bytes(json_bytes),
}
http_meta = {"url": "https://api.example.com/myendpoint"}
result1 = client1.inspect(http_req=http_req, http_meta=http_meta)
print("HTTP API is safe?", result1.is_safe)

# Use client2 to inspect a simplified HTTP request (inspect_request)
result2 = client2.inspect_request(
    method="GET",
    url="https://example.com/endpoint",
    headers={"Accept": "application/json"},
    body=None,
)
print("Simple HTTP request is safe?", result2.is_safe)
