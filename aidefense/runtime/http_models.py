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

from typing import List, Optional
from dataclasses import dataclass
from aidefense.runtime.models import Metadata, InspectionConfig


@dataclass
class HttpHdrKvObject:
    key: str  # HTTP header key
    value: str  # HTTP header value


@dataclass
class HttpHdrObject:
    hdrKvs: Optional[List[HttpHdrKvObject]] = None


@dataclass
class HttpReqObject:
    method: Optional[str] = None
    headers: Optional[HttpHdrObject] = None
    body: str = ""
    split: Optional[bool] = None
    last: Optional[bool] = None


@dataclass
class HttpResObject:
    statusCode: int = 200
    statusString: Optional[str] = None
    headers: Optional[HttpHdrObject] = None
    body: str = ""
    split: Optional[bool] = None
    last: Optional[bool] = None


@dataclass
class HttpMetaObject:
    url: str = ""
    protocol: Optional[str] = None


@dataclass
class HttpInspectRequest:
    """
    Request object for HTTP inspection API.

    Attributes:
        http_req (Optional[HttpReqObject]): HTTP request details.
        http_res (Optional[HttpResObject]): HTTP response details.
        http_meta (Optional[HttpMetaObject]): HTTP metadata (e.g., URL).
        metadata (Optional[Metadata]): Additional metadata (user, app, etc.).
        config (Optional[InspectionConfig]): Inspection configuration for the request.
    """

    http_req: Optional[HttpReqObject] = None
    http_res: Optional[HttpResObject] = None
    http_meta: Optional[HttpMetaObject] = None
    metadata: Optional[Metadata] = None
    config: Optional[InspectionConfig] = None
