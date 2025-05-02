"""
Example: Using inspect_response for chat AI response inspection
"""

from aidefense import ChatInspectionClient

client = ChatInspectionClient(api_key="YOUR_API_KEY")

result = client.inspect_response("Here is some code ...")
print("Is safe?", result.is_safe)
print("Details:", result)
