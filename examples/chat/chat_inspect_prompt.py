"""
Example: Using inspect_prompt for chat prompt inspection
"""

from aidefense import ChatInspectionClient

client = ChatInspectionClient(api_key="YOUR_API_KEY")

result = client.inspect_prompt("How to make a bomb?¯")
print("Is safe?", result.is_safe)
print("Details:", result)
