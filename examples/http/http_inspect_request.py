"""
Example: Using inspect_request for simplified HTTP request inspection
"""

from aidefense import HttpInspectionClient

client = HttpInspectionClient(api_key="YOUR_API_KEY")

result = client.inspect_request(
    method="POST",
    url="https://api.example.com/endpoint", # Replace with your actual URL
    headers={"Authorization": "Bearer TOKEN", "Content-Type": "application/json"},
    body="{'key': 'value'}", # Replace with your actual body
)
print("Is safe?", result.is_safe)
print("Details:", result)
