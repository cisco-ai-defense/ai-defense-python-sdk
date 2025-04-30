from dataclasses import dataclass
from typing import List, Optional
from enum import Enum

from .models import InspectionConfig, Metadata


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class Message:
    """
    Represents a message in a chat conversation.

    Attributes:
        role (Role): The role of the message sender (user, assistant, or system).
        content (str): The text content of the message.
    """

    role: Role
    content: str


@dataclass
class ChatInspectRequest:
    """
    Request object for chat inspection API.

    Attributes:
        messages (List[Message]): List of messages in the chat conversation.
        metadata (Optional[Metadata]): Optional metadata about the request (user, app, etc.).
        config (Optional[InspectionConfig]): Optional inspection configuration for the request.
    """

    messages: List[Message]
    metadata: Optional[Metadata] = None
    config: Optional[InspectionConfig] = None
