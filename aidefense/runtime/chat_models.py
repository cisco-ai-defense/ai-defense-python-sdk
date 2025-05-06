# Copyright 2025 Cisco Systems, Inc. and its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

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
