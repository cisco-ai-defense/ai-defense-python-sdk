"""
Example: Using inspect_conversation for chat conversation inspection
"""

from aidefense import ChatInspectionClient
from aidefense.runtime.models import Message, Role

client = ChatInspectionClient(api_key="YOUR_API_KEY")

conversation = [
    Message(role=Role.USER, content="Hi, can you help me with my account?"),
    Message(role=Role.ASSISTANT, content="Sure, what do you need help with?"),
]

result = client.inspect_conversation(conversation)
print("Is safe?", result.is_safe)
print("Details:", result)
