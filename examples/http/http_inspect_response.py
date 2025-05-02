"""
Example: Using inspect_response for simplified HTTP response inspection
"""

from aidefense import HttpInspectionClient

client = HttpInspectionClient(api_key="YOUR_API_KEY")

result = client.inspect_response(
    status_code=200,
    url="https://api.example.com/endpoint",
    headers={"Content-Type": "application/json"},
    body="{" "key" ": " "value" "}",
)
print("Is safe?", result.is_safe)
print("Details:", result)
