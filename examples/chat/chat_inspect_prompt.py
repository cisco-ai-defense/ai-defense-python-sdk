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
Example: Using inspect_prompt for chat prompt inspection
"""

from aidefense import ChatInspectionClient

client = ChatInspectionClient(api_key="YOUR_API_KEY")

result = client.inspect_prompt("How to make a bomb?¯")
print("Is safe?", result.is_safe)
print("Details:", result)
