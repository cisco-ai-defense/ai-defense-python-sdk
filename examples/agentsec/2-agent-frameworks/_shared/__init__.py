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
Shared provider infrastructure for agentsec examples.

This module provides a unified way to configure and use different LLM providers
(AWS Bedrock, Azure OpenAI, GCP Vertex AI, OpenAI) across all agent examples.

Usage:
    from _shared import load_config, create_provider
    
    config = load_config()  # Loads from CONFIG_FILE env var or config.yaml
    provider = create_provider(config)
    
    # Use provider with your framework
    llm = provider.get_langchain_llm()  # For LangGraph
    llm = provider.get_crewai_llm()     # For CrewAI
    model_id = provider.get_strands_model_id()  # For Strands
    client = provider.get_openai_client()  # For OpenAI/AutoGen
"""

from .config import load_config
from .providers import create_provider, PROVIDERS
from .security import validate_url, URLValidationError, safe_fetch_url_wrapper

__all__ = ['load_config', 'create_provider', 'PROVIDERS', 'validate_url', 'URLValidationError', 'safe_fetch_url_wrapper']

