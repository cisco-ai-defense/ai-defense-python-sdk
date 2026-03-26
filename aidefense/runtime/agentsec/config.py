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

"""Configuration constants for agentsec.

Note: Configuration is loaded from YAML files (via config_file.py)
and/or protect() kwargs. The old load_env_config() function and
AGENTSEC_* environment variable parsing have been removed.
"""

# Valid mode values for API mode
VALID_MODES = ("off", "monitor", "enforce")

# Valid mode values for Gateway mode
VALID_GATEWAY_MODES = ("on", "off")

# Valid integration mode values (api vs gateway)
VALID_INTEGRATION_MODES = ("api", "gateway")
