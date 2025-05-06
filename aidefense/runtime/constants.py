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

# aidefense.runtime.constants
# Central location for runtime-wide constant keys
HTTP_REQ = "http_req"
HTTP_RES = "http_res"
HTTP_META = "http_meta"
HTTP_METHOD = "method"
VALID_HTTP_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
HTTP_STATUS_CODE = "statusCode"
HTTP_BODY = "body"
HTTP_HEADERS = "headers"

INTEGRATION_DETAILS = [
    "integration_profile_id",
    "integration_profile_version",
    "integration_tenant_id",
    "integration_type",
]
