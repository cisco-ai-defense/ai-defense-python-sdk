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

"""
Vertex AI Agent Engine entry point class.

Defined inside the _shared package to ensure it is included in the
Agent Engine extra_packages bundle and importable at runtime.
"""

from _shared.agent_factory import invoke_agent


class SREAgent:
    """
    Vertex AI Agent Engine compatible agent.

    Implements query() so it can be deployed as a custom agent.
    """

    def set_up(self) -> None:
        """Optional setup hook for Agent Engine."""
        return None

    def query(self, input: str) -> dict:
        """
        Process a single prompt and return a response.

        Args:
            input: User prompt.
        Returns:
            Dict with input/output fields.
        """
        try:
            result = invoke_agent(input)
            return {
                "input": input,
                "output": result,
                "status": "success",
            }
        except Exception as exc:
            return {
                "input": input,
                "output": str(exc),
                "status": "error",
            }
