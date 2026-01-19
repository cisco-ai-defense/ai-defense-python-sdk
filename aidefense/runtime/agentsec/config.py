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

"""Configuration management for agentsec."""

import json
import os
from typing import Any, Dict, List, Optional

# Valid mode values for API mode
VALID_MODES = ("off", "on_monitor", "on_enforce")

# Valid mode values for Gateway mode (off/on only - gateway handles enforcement)
VALID_GATEWAY_MODES = ("off", "on")

# Valid integration mode values (api vs gateway)
VALID_INTEGRATION_MODES = ("api", "gateway")


def _parse_bool_env(value: Optional[str], default: bool) -> bool:
    """Parse boolean from environment variable string."""
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes", "on")


def _parse_mode_env(value: Optional[str], default: str) -> str:
    """Parse mode from environment variable string with validation."""
    if value is None:
        return default
    value = value.lower()
    if value not in VALID_MODES:
        raise ValueError(f"Invalid mode '{value}'. Must be one of: {', '.join(VALID_MODES)}")
    return value


def _parse_integration_mode_env(value: Optional[str], default: str = "api") -> str:
    """
    Parse integration mode from environment variable string with validation.
    
    Args:
        value: Environment variable value
        default: Default value if not set (default: "api")
        
    Returns:
        Validated integration mode ("api" or "gateway")
        
    Raises:
        ValueError: If value is not a valid integration mode
    """
    if value is None:
        return default
    value = value.lower()
    if value not in VALID_INTEGRATION_MODES:
        raise ValueError(f"Invalid integration mode '{value}'. Must be one of: {', '.join(VALID_INTEGRATION_MODES)}")
    return value


def _parse_gateway_mode_env(value: Optional[str], default: str = "on") -> str:
    """
    Parse gateway mode from environment variable string with validation.
    
    Gateway mode only supports off/on (not monitor/enforce) since the gateway
    handles enforcement internally.
    
    Args:
        value: Environment variable value
        default: Default value if not set (default: "on")
        
    Returns:
        Validated gateway mode ("off" or "on")
        
    Raises:
        ValueError: If value is not a valid gateway mode
    """
    if value is None:
        return default
    value = value.lower()
    if value not in VALID_GATEWAY_MODES:
        raise ValueError(f"Invalid gateway mode '{value}'. Must be one of: {', '.join(VALID_GATEWAY_MODES)}")
    return value


def _parse_rules_env(value: Optional[str]) -> Optional[List[Any]]:
    """
    Parse rules from environment variable string.
    
    Supports two formats:
    - JSON array: '["rule1", "rule2"]'
    - Comma-separated: 'rule1,rule2'
    
    Returns None if value is None or empty.
    """
    if not value or not value.strip():
        return None
    
    value = value.strip()
    
    # Try JSON array first
    if value.startswith("["):
        try:
            rules = json.loads(value)
            if isinstance(rules, list):
                return rules
        except json.JSONDecodeError:
            pass
    
    # Fall back to comma-separated
    rules = [r.strip() for r in value.split(",") if r.strip()]
    return rules if rules else None


def _load_provider_config(provider: str, mode: str) -> Dict[str, Optional[str]]:
    """
    Load provider-specific configuration from environment variables.
    
    Args:
        provider: Provider name (openai, azure_openai, vertexai, bedrock)
        mode: Configuration mode (api or gateway)
        
    Returns:
        Dictionary with url and api_key
    """
    # Map provider names to environment variable prefixes
    provider_prefix_map = {
        "openai": "OPENAI",
        "azure_openai": "AZURE_OPENAI",
        "vertexai": "VERTEXAI",
        "bedrock": "BEDROCK",
    }
    
    prefix = provider_prefix_map.get(provider, provider.upper())
    
    if mode == "gateway":
        url = os.environ.get(f"AGENTSEC_{prefix}_GATEWAY_URL")
        api_key = os.environ.get(f"AGENTSEC_{prefix}_GATEWAY_API_KEY")
    else:  # api mode
        url = os.environ.get(f"AGENTSEC_{prefix}_API_URL")
        api_key = os.environ.get(f"AGENTSEC_{prefix}_API_KEY")
    
    return {"url": url, "api_key": api_key}


def load_env_config() -> Dict[str, Any]:
    """
    Load configuration from environment variables.
    
    Returns:
        Dictionary with loaded environment variable values (None for unset vars)
        
    Environment Variables:
        # Integration Mode Selection
        AGENTSEC_LLM_INTEGRATION_MODE: Integration mode for LLM (api/gateway, default: api)
        AGENTSEC_MCP_INTEGRATION_MODE: Integration mode for MCP (api/gateway, default: api)
        
        # API Mode Configuration (when integration mode is 'api')
        AGENTSEC_API_MODE_LLM: Mode for LLM inspection in API mode (off/on_monitor/on_enforce)
        AGENTSEC_API_MODE_MCP: Mode for MCP tool inspection in API mode (off/on_monitor/on_enforce)
        AGENTSEC_API_MODE_FAIL_OPEN_LLM: Allow LLM requests on API errors (true/false)
        AGENTSEC_API_MODE_FAIL_OPEN_MCP: Allow MCP calls on API errors (true/false)
        AI_DEFENSE_API_MODE_LLM_API_KEY: API key for Cisco AI Defense (used for LLM and MCP if specific not set)
        AI_DEFENSE_API_MODE_LLM_ENDPOINT: API endpoint for Cisco AI Defense (used for LLM and MCP if specific not set)
        AI_DEFENSE_API_MODE_MCP_API_KEY: API key specifically for MCP inspection (overrides AI_DEFENSE_API_MODE_LLM_API_KEY)
        AI_DEFENSE_API_MODE_MCP_ENDPOINT: API endpoint specifically for MCP inspection (overrides AI_DEFENSE_API_MODE_LLM_ENDPOINT)
        
        # Gateway Mode Configuration (when integration mode is 'gateway')
        AGENTSEC_GATEWAY_MODE_LLM: Mode for LLM in gateway mode (off/on, default: on)
        AGENTSEC_GATEWAY_MODE_MCP: Mode for MCP in gateway mode (off/on, default: on)
        AGENTSEC_GATEWAY_MODE_FAIL_OPEN_LLM: Allow LLM requests on gateway errors (true/false)
        AGENTSEC_GATEWAY_MODE_FAIL_OPEN_MCP: Allow MCP calls on gateway errors (true/false)
        AGENTSEC_MCP_GATEWAY_URL: Gateway URL for MCP calls
        AGENTSEC_MCP_GATEWAY_API_KEY: Gateway API key for MCP calls
        
        # Provider-Specific Gateway Configuration
        AGENTSEC_OPENAI_GATEWAY_URL: Gateway URL for OpenAI calls
        AGENTSEC_OPENAI_GATEWAY_API_KEY: Gateway API key for OpenAI calls
        AGENTSEC_AZURE_OPENAI_GATEWAY_URL: Gateway URL for Azure OpenAI calls
        AGENTSEC_AZURE_OPENAI_GATEWAY_API_KEY: Gateway API key for Azure OpenAI calls
        AGENTSEC_VERTEXAI_GATEWAY_URL: Gateway URL for Vertex AI calls
        AGENTSEC_VERTEXAI_GATEWAY_API_KEY: Gateway API key for Vertex AI calls
        AGENTSEC_BEDROCK_GATEWAY_URL: Gateway URL for AWS Bedrock calls
        AGENTSEC_BEDROCK_GATEWAY_API_KEY: Gateway API key for AWS Bedrock calls
        
        # Provider-Specific API Configuration (for direct calls)
        AGENTSEC_OPENAI_API_URL: OpenAI API URL (default: https://api.openai.com/v1)
        AGENTSEC_OPENAI_API_KEY: OpenAI API key (or use OPENAI_API_KEY)
        AGENTSEC_AZURE_OPENAI_API_URL: Azure OpenAI endpoint URL
        AGENTSEC_AZURE_OPENAI_API_KEY: Azure OpenAI API key (or use AZURE_OPENAI_API_KEY)
        AGENTSEC_VERTEXAI_API_URL: Vertex AI endpoint URL (default: regional endpoint)
        AGENTSEC_BEDROCK_API_KEY: Not typically used - Bedrock uses AWS SDK auth
        
        # Other Settings
        AGENTSEC_LLM_RULES: Rules to enable for LLM inspection (JSON array or comma-separated)
    """
    # Get general API config (for AI Defense API mode inspection)
    general_api_key = os.environ.get("AI_DEFENSE_API_MODE_LLM_API_KEY")
    general_api_endpoint = os.environ.get("AI_DEFENSE_API_MODE_LLM_ENDPOINT")
    
    # Get MCP-specific API config with fallback to general
    mcp_api_key = os.environ.get("AI_DEFENSE_API_MODE_MCP_API_KEY") or general_api_key
    mcp_api_endpoint = os.environ.get("AI_DEFENSE_API_MODE_MCP_ENDPOINT") or general_api_endpoint
    
    # Load provider-specific gateway configuration
    provider_gateway_config = {}
    for provider in ["openai", "azure_openai", "vertexai", "bedrock"]:
        provider_gateway_config[provider] = _load_provider_config(provider, "gateway")
    
    # Load provider-specific API configuration
    provider_api_config = {}
    for provider in ["openai", "azure_openai", "vertexai", "bedrock"]:
        config = _load_provider_config(provider, "api")
        # Fall back to standard env vars for API keys
        if not config["api_key"]:
            if provider == "openai":
                config["api_key"] = os.environ.get("OPENAI_API_KEY")
            elif provider == "azure_openai":
                config["api_key"] = os.environ.get("AZURE_OPENAI_API_KEY")
        provider_api_config[provider] = config
    
    return {
        # Integration modes (api vs gateway) - determines which set of settings to use
        "llm_integration_mode": _parse_integration_mode_env(os.environ.get("AGENTSEC_LLM_INTEGRATION_MODE")),
        "mcp_integration_mode": _parse_integration_mode_env(os.environ.get("AGENTSEC_MCP_INTEGRATION_MODE")),
        
        # API Mode settings (used when integration_mode = 'api')
        "llm_mode": os.environ.get("AGENTSEC_API_MODE_LLM"),  # off/on_monitor/on_enforce
        "mcp_mode": os.environ.get("AGENTSEC_API_MODE_MCP"),  # off/on_monitor/on_enforce
        "llm_fail_open": _parse_bool_env(os.environ.get("AGENTSEC_API_MODE_FAIL_OPEN_LLM"), True),
        "mcp_fail_open": _parse_bool_env(os.environ.get("AGENTSEC_API_MODE_FAIL_OPEN_MCP"), True),
        
        # Gateway Mode settings (used when integration_mode = 'gateway')
        # Note: Gateway mode only has off/on - gateway handles enforcement internally
        "llm_gateway_mode": _parse_gateway_mode_env(os.environ.get("AGENTSEC_GATEWAY_MODE_LLM")),
        "mcp_gateway_mode": _parse_gateway_mode_env(os.environ.get("AGENTSEC_GATEWAY_MODE_MCP")),
        "llm_gateway_fail_open": _parse_bool_env(os.environ.get("AGENTSEC_GATEWAY_MODE_FAIL_OPEN_LLM"), True),
        "mcp_gateway_fail_open": _parse_bool_env(os.environ.get("AGENTSEC_GATEWAY_MODE_FAIL_OPEN_MCP"), True),
        
        # MCP Gateway URL and API key (single gateway for MCP)
        "mcp_gateway_url": os.environ.get("AGENTSEC_MCP_GATEWAY_URL"),
        "mcp_gateway_api_key": os.environ.get("AGENTSEC_MCP_GATEWAY_API_KEY"),
        
        # Provider-specific gateway configuration
        "provider_gateway_config": provider_gateway_config,
        
        # Provider-specific API configuration
        "provider_api_config": provider_api_config,
        
        # LLM rules (API mode only)
        "llm_rules": _parse_rules_env(os.environ.get("AGENTSEC_LLM_RULES")),
        
        # Other settings
        "tenant_id": os.environ.get("AGENTSEC_TENANT_ID"),
        "application_id": os.environ.get("AGENTSEC_APP_ID"),
        "log_level": os.environ.get("AGENTSEC_LOG_LEVEL"),
        "log_format": os.environ.get("AGENTSEC_LOG_FORMAT"),
        "log_file": os.environ.get("AGENTSEC_LOG_FILE"),
        
        # General API config (used for AI Defense API in API mode)
        "api_key": general_api_key,
        "api_endpoint": general_api_endpoint,
        
        # MCP-specific API config (with fallback to general)
        "mcp_api_key": mcp_api_key,
        "mcp_api_endpoint": mcp_api_endpoint,
        "mcp_enabled": _parse_bool_env(os.environ.get("AGENTSEC_MCP_ENABLED"), True),
        "redact_logs": _parse_bool_env(os.environ.get("AGENTSEC_REDACT_LOGS"), True),
    }
