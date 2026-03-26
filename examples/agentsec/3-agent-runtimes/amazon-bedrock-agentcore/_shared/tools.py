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

"""Demo tools for the SRE agent.

These tools simulate SRE operations for demonstration purposes.
"""

import random
from strands import tool

STATUSES = ("healthy", "degraded", "down")


@tool
def add(a: float, b: float) -> float:
    """Add two numbers together.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        Sum of a and b
    """
    return a + b


@tool
def check_service_health(service: str) -> str:
    """Check the health status of a service.
    
    Args:
        service: Name of the service to check
        
    Returns:
        Health status message (simulated)
    """
    status = random.choice(STATUSES)
    return f"{service}: {status} (simulated)"


@tool
def summarize_log(text: str) -> str:
    """Summarize a log file or log text.
    
    Args:
        text: The log text to summarize
        
    Returns:
        Summary of the log (simulated)
    """
    summary = random.choice(("Good Summary", "Bad Summary", "Needs review"))
    text_length = len(text or "")
    return f"Summary ({text_length} chars): {summary} (simulated)"
