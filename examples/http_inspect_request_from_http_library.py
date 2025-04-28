"""
Example: Using inspect_request_from_http_library with requests.PreparedRequest
"""

from aidefense import HttpInspectionClient
import requests

client = HttpInspectionClient(api_key="YOUR_API_KEY")

req = requests.Request("GET", "https://example.com").prepare()
result = client.inspect_request_from_http_library(req)
print("Is safe?", result.is_safe)
print("Details:", result)
