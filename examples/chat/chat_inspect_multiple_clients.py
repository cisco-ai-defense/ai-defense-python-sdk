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

"""
Example: Creating two ChatInspectionClient instances with a shared Config and calling different methods
"""

from aidefense import ChatInspectionClient, Config
from aidefense.runtime import Message, Role

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
