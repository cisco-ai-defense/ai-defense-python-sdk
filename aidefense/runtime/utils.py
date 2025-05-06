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
Utility functions for encoding HTTP bodies and serializing objects for the AI Defense SDK.
"""

import base64
from typing import Union, Any, Optional, Dict
from dataclasses import asdict, is_dataclass
from enum import Enum

from .constants import HTTP_BODY


def to_base64_bytes(data: Union[str, bytes]) -> str:
    """
    Encode a string or bytes object to a base64-encoded string.

    Args:
        data (str or bytes): The input data to encode.

    Returns:
        str: Base64-encoded string representation of the input.

    Raises:
        ValueError: If data is not of type str or bytes.
    """
    if isinstance(data, bytes):
        return base64.b64encode(data).decode()
    elif isinstance(data, str):
        return base64.b64encode(data.encode()).decode()
    else:
        raise ValueError("Input must be str or bytes.")


def convert(obj: Any) -> Any:
    """
    Recursively convert dataclasses, enums, and other objects to dicts/values for JSON serialization.

    Handles nested dataclasses, enums, lists, and dicts. This is useful for preparing objects
    for serialization (e.g., when sending requests to the AI Defense API).

    Args:
        obj: The object to convert (can be a dataclass, enum, list, dict, or primitive).

    Returns:
        The converted object as a dict, value, or list suitable for JSON serialization.
    """

    if is_dataclass(obj):
        return {k: convert(v) for k, v in asdict(obj).items()}
    elif isinstance(obj, Enum):
        return obj.value
    elif isinstance(obj, dict):
        return {k: convert(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert(v) for v in obj]
    else:
        return obj


# Validate and encode bodies if necessary
def ensure_base64_body(d: Optional[Dict[str, Any]]) -> None:
    if d and d.get(HTTP_BODY):
        body = d[HTTP_BODY]
        if isinstance(body, bytes):
            d[HTTP_BODY] = to_base64_bytes(body)
        elif isinstance(body, str):
            # Heuristic: if not valid base64, treat as raw string and encode
            try:
                base64.b64decode(body)
                # Already base64
            except Exception:
                d[HTTP_BODY] = to_base64_bytes(body)
        elif body is None:
            d[HTTP_BODY] = ""
        else:
            raise ValueError("HTTP body must be bytes, str, or base64-encoded string.")
