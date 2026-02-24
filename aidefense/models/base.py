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

"""SDK-wide base Pydantic model utilities."""

import json
import warnings
from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_serializer


class AIDefenseModel(BaseModel):
    """Base model for all SDK models (Pydantic v2).

    - Serializes Enum fields to their .value automatically.
    - Allows using field names even when aliases are defined.
    """

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )

    @field_serializer("*", mode="wrap")
    def _serialize_datetime(self, value, handler):
        """Ensure datetimes are serialized with a trailing 'Z' (UTC)."""
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%dT%H:%M:%SZ")
        # Suppress PydanticSerializationUnexpectedValue warnings for enum fields
        # that have already been converted to strings by use_enum_values=True
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            return handler(value)

    # ---- Serialization helpers ----
    def to_params(self) -> dict:
        """Serialize this model to query params.

        - Excludes None values
        - Applies field aliases
        - Enums already flattened via Config.use_enum_values
        """
        return self.model_dump(by_alias=True, exclude_none=True)

    def to_body_dict(self, *, patch: bool = False) -> dict:
        """Serialize this model to a JSON-serializable dict for request bodies.

        Args:
            patch: If True, exclude fields that were not explicitly set (PATCH semantics)
        """
        # Use JSON round-trip so datetimes and other complex types are encoded
        # the same way as when sending an actual JSON payload.
        return json.loads(self.to_body_json(patch=patch))

    def to_body_json(self, *, patch: bool = False) -> str:
        """Serialize this model to a JSON string for request bodies."""
        return self.model_dump_json(by_alias=True, exclude_none=True, exclude_unset=patch)
