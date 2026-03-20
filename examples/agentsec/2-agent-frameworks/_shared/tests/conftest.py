# Copyright 2026 Cisco Systems, Inc. and its affiliates
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

"""Pytest configuration for _shared tests."""

import sys
from pathlib import Path

# Add _shared directory to path so imports work
_shared_dir = Path(__file__).parent.parent
_parent_dir = _shared_dir.parent  # 2_agent-frameworks

# Add both directories to ensure imports work
for path in [str(_shared_dir), str(_parent_dir)]:
    if path not in sys.path:
        sys.path.insert(0, path)
