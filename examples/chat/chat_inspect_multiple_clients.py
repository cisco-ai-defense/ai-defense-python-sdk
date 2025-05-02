"""
Example: Creating two ChatInspectionClient instances with a shared Config and calling different methods
"""

from aidefense import ChatInspectionClient, Config
from aidefense.runtime.models import Message, Role

config = Config(logger_params={"level": "DEBUG"})

client1 = ChatInspectionClient(api_key="YOUR_API_KEY", config=config)
client2 = ChatInspectionClient(api_key="YOUR_API_KEY", config=config)

# Use client1 to inspect a prompt
result1 = client1.inspect_prompt("Is this a safe prompt?")
print("Prompt is safe?", result1.is_safe)

# Use client2 to inspect a conversation
conversation = [
    Message(role=Role.USER, content="Hi, can you help?"),
    Message(role=Role.ASSISTANT, content="Sure, what do you need?"),
]
result2 = client2.inspect_conversation(conversation)
print("Conversation is safe?", result2.is_safe)
