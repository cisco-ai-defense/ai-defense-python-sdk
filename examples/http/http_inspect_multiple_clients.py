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
Example: Creating two HttpInspectionClient instances with a shared Config and calling different methods
"""

from aidefense import HttpInspectionClient, Config
from aidefense.runtime.utils import to_base64_bytes

config = Config(logger_params={"level": "INFO"})

client1 = HttpInspectionClient(api_key="YOUR_INSPECTION_API_KEY", config=config)
client2 = HttpInspectionClient(api_key="YOUR_INSPECTION_API_KEY", config=config)

# Use client1 to inspect a raw HTTP request (inspect)
json_bytes = b'{"key": "value"}'
http_req = {
    "method": "POST",
    "headers": {"Content-Type": "application/json"},
    "body": to_base64_bytes(json_bytes),
}
http_meta = {"url": "https://api.example.com/myendpoint"}
result1 = client1.inspect(http_req=http_req, http_meta=http_meta)
print("HTTP API is safe?", result1.is_safe)

# Use client2 to inspect a simplified HTTP request (inspect_request)
result2 = client2.inspect_request(
    method="GET",
    url="https://example.com/endpoint",
    headers={"Accept": "application/json"},
    body=None,
)
print("Simple HTTP request is safe?", result2.is_safe)
