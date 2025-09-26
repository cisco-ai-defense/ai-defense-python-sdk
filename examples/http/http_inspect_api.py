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
Example: Using inspect for raw HTTP request/response dicts
"""

from aidefense import HttpInspectionClient
from aidefense.runtime.utils import to_base64_bytes

client = HttpInspectionClient(api_key="YOUR_INSPECTION_API_KEY")

# Example HTTP request (as dict)
json_bytes = b'{"key": "value"}'
http_req = {
    "method": "POST",
    "headers": {"Content-Type": "application/json"},
    "body": to_base64_bytes(json_bytes),  # base64-encoded bytes using SDK utility
}

http_meta = {"url": "https://api.example.com/myendpoint"}
result = client.inspect(http_req=http_req, http_meta=http_meta)
print("Is safe?", result.is_safe)
print("Details:", result)
