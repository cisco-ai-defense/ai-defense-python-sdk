"""
Example: Using inspect_response_from_http_library with requests.Response
"""

from aidefense import HttpInspectionClient
import requests

client = HttpInspectionClient(api_key="YOUR_API_KEY")

# Simulate an HTTP response (in practice, get this from requests)
response = requests.get("https://httpbin.org/get")
result = client.inspect_response_from_http_library(response)
print("Is safe?", result.is_safe)
print("Details:", result)
