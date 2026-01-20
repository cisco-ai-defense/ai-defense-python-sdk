"""Global state management for agentsec."""

from typing import Any, Dict, List, Optional


# Supported LLM providers
SUPPORTED_PROVIDERS = ["openai", "azure_openai", "vertexai", "bedrock", "agentcore"]

# Global state
_initialized: bool = False

# LLM rules for API mode inspection
_llm_rules: Optional[List[Any]] = None

# Integration modes (api vs gateway) - common for both
_llm_integration_mode: str = "api"
_mcp_integration_mode: str = "api"

# API mode configuration
_api_mode_llm: Optional[str] = None  # off/on_monitor/on_enforce
_api_mode_mcp: Optional[str] = None  # off/on_monitor/on_enforce
_api_mode_llm_endpoint: Optional[str] = None
_api_mode_llm_api_key: Optional[str] = None
_api_mode_mcp_endpoint: Optional[str] = None
_api_mode_mcp_api_key: Optional[str] = None
_api_mode_fail_open_llm: bool = True
_api_mode_fail_open_mcp: bool = True

# Gateway mode configuration (general)
_gateway_mode_llm: str = "on"  # off/on
_gateway_mode_mcp: str = "on"  # off/on
_gateway_mode_mcp_url: Optional[str] = None
_gateway_mode_mcp_api_key: Optional[str] = None
_gateway_mode_fail_open_llm: bool = True
_gateway_mode_fail_open_mcp: bool = True

# Provider-specific gateway configuration
# Each provider has its own gateway URL and API key
# Note: AgentCore uses AWS Sig V4 authentication, so api_key is not used
_provider_gateway_config: Dict[str, Dict[str, Optional[str]]] = {
    "openai": {"url": None, "api_key": None},
    "azure_openai": {"url": None, "api_key": None},
    "vertexai": {"url": None, "api_key": None},
    "bedrock": {"url": None, "api_key": None},
    "agentcore": {"url": None, "api_key": None},  # api_key not used - AWS Sig V4
}

# Provider-specific API configuration (for direct calls in API mode)
_provider_api_config: Dict[str, Dict[str, Optional[str]]] = {
    "openai": {"url": None, "api_key": None},
    "azure_openai": {"url": None, "api_key": None},
    "vertexai": {"url": None, "api_key": None},
    "bedrock": {"url": None, "api_key": None},
    "agentcore": {"url": None, "api_key": None},
}


def is_initialized() -> bool:
    """Check if agentsec has been initialized."""
    return _initialized


def get_llm_rules() -> Optional[List[Any]]:
    """Get the current LLM rules for API mode inspection."""
    return _llm_rules


# Integration mode getters (common)
def get_llm_integration_mode() -> str:
    """Get the current LLM integration mode ('api' or 'gateway')."""
    return _llm_integration_mode


def get_mcp_integration_mode() -> str:
    """Get the current MCP integration mode ('api' or 'gateway')."""
    return _mcp_integration_mode


# API mode getters
def get_api_mode_llm() -> Optional[str]:
    """Get the current LLM API mode (off/monitor/enforce)."""
    return _api_mode_llm


def get_api_mode_mcp() -> Optional[str]:
    """Get the current MCP API mode (off/monitor/enforce)."""
    return _api_mode_mcp


def get_api_mode_llm_endpoint() -> Optional[str]:
    """Get the LLM API endpoint."""
    return _api_mode_llm_endpoint


def get_api_mode_llm_api_key() -> Optional[str]:
    """Get the LLM API key."""
    return _api_mode_llm_api_key


def get_api_mode_mcp_endpoint() -> Optional[str]:
    """Get the MCP API endpoint (falls back to LLM endpoint if not set)."""
    return _api_mode_mcp_endpoint or _api_mode_llm_endpoint


def get_api_mode_mcp_api_key() -> Optional[str]:
    """Get the MCP API key (falls back to LLM key if not set)."""
    return _api_mode_mcp_api_key or _api_mode_llm_api_key


def get_api_mode_fail_open_llm() -> bool:
    """Get the LLM API mode fail_open setting."""
    return _api_mode_fail_open_llm


def get_api_mode_fail_open_mcp() -> bool:
    """Get the MCP API mode fail_open setting."""
    return _api_mode_fail_open_mcp


# Gateway mode getters
def get_gateway_mode_llm() -> str:
    """Get the current LLM gateway mode ('off' or 'on')."""
    return _gateway_mode_llm


def get_gateway_mode_mcp() -> str:
    """Get the current MCP gateway mode ('off' or 'on')."""
    return _gateway_mode_mcp


def get_gateway_mode_mcp_url() -> Optional[str]:
    """Get the MCP gateway URL."""
    return _gateway_mode_mcp_url


def get_gateway_mode_mcp_api_key() -> Optional[str]:
    """Get the MCP gateway API key."""
    return _gateway_mode_mcp_api_key


def get_gateway_mode_fail_open_llm() -> bool:
    """Get the LLM gateway fail_open setting."""
    return _gateway_mode_fail_open_llm


def get_gateway_mode_fail_open_mcp() -> bool:
    """Get the MCP gateway fail_open setting."""
    return _gateway_mode_fail_open_mcp


# Provider-specific gateway config getters
def get_provider_gateway_url(provider: str) -> Optional[str]:
    """
    Get gateway URL for a specific provider.
    
    Args:
        provider: Provider name (openai, azure_openai, vertexai, bedrock)
        
    Returns:
        Gateway URL or None if not configured
    """
    return _provider_gateway_config.get(provider, {}).get("url")


def get_provider_gateway_api_key(provider: str) -> Optional[str]:
    """
    Get gateway API key for a specific provider.
    
    Args:
        provider: Provider name (openai, azure_openai, vertexai, bedrock)
        
    Returns:
        Gateway API key or None if not configured
    """
    return _provider_gateway_config.get(provider, {}).get("api_key")


def get_provider_api_url(provider: str) -> Optional[str]:
    """
    Get API URL for a specific provider (for direct calls in API mode).
    
    Args:
        provider: Provider name (openai, azure_openai, vertexai, bedrock)
        
    Returns:
        API URL or None if not configured
    """
    return _provider_api_config.get(provider, {}).get("url")


def get_provider_api_key(provider: str) -> Optional[str]:
    """
    Get API key for a specific provider (for direct calls in API mode).
    
    Args:
        provider: Provider name (openai, azure_openai, vertexai, bedrock)
        
    Returns:
        API key or None if not configured
    """
    return _provider_api_config.get(provider, {}).get("api_key")


def set_provider_gateway_config(provider: str, url: Optional[str], api_key: Optional[str]) -> None:
    """
    Set gateway configuration for a specific provider.
    
    Args:
        provider: Provider name (openai, azure_openai, vertexai, bedrock)
        url: Gateway URL
        api_key: Gateway API key
    """
    if provider in _provider_gateway_config:
        _provider_gateway_config[provider] = {"url": url, "api_key": api_key}


def set_provider_api_config(provider: str, url: Optional[str], api_key: Optional[str]) -> None:
    """
    Set API configuration for a specific provider (for direct calls in API mode).
    
    Args:
        provider: Provider name (openai, azure_openai, vertexai, bedrock)
        url: API URL
        api_key: API key
    """
    if provider in _provider_api_config:
        _provider_api_config[provider] = {"url": url, "api_key": api_key}


# Legacy getters (aliases for backward compatibility)
def get_llm_mode() -> Optional[str]:
    """Get the current LLM inspection mode (alias for get_api_mode_llm)."""
    return _api_mode_llm


def get_mcp_mode() -> Optional[str]:
    """Get the current MCP inspection mode (alias for get_api_mode_mcp)."""
    return _api_mode_mcp


def get_llm_api_endpoint() -> Optional[str]:
    """Get the LLM API endpoint (alias for get_api_mode_llm_endpoint)."""
    return _api_mode_llm_endpoint


def get_llm_api_key() -> Optional[str]:
    """Get the LLM API key (alias for get_api_mode_llm_api_key)."""
    return _api_mode_llm_api_key


def get_mcp_api_endpoint() -> Optional[str]:
    """Get the MCP API endpoint (alias for get_api_mode_mcp_endpoint)."""
    return _api_mode_mcp_endpoint or _api_mode_llm_endpoint


def get_mcp_api_key() -> Optional[str]:
    """Get the MCP API key (alias for get_api_mode_mcp_api_key)."""
    return _api_mode_mcp_api_key or _api_mode_llm_api_key


def get_mcp_gateway_url() -> Optional[str]:
    """Get the MCP gateway URL (alias for get_gateway_mode_mcp_url)."""
    return _gateway_mode_mcp_url


def get_mcp_gateway_api_key() -> Optional[str]:
    """Get the MCP gateway API key (alias for get_gateway_mode_mcp_api_key)."""
    return _gateway_mode_mcp_api_key


def get_llm_gateway_mode() -> str:
    """Get the LLM gateway mode (alias for get_gateway_mode_llm)."""
    return _gateway_mode_llm


def get_mcp_gateway_mode() -> str:
    """Get the MCP gateway mode (alias for get_gateway_mode_mcp)."""
    return _gateway_mode_mcp


def get_llm_gateway_fail_open() -> bool:
    """Get the LLM gateway fail_open (alias for get_gateway_mode_fail_open_llm)."""
    return _gateway_mode_fail_open_llm


def get_mcp_gateway_fail_open() -> bool:
    """Get the MCP gateway fail_open (alias for get_gateway_mode_fail_open_mcp)."""
    return _gateway_mode_fail_open_mcp


def set_state(
    initialized: bool,
    # LLM rules for API mode
    llm_rules: Optional[List[Any]] = None,
    # Integration modes
    llm_integration_mode: str = "api",
    mcp_integration_mode: str = "api",
    # API mode configuration
    api_mode_llm: Optional[str] = None,
    api_mode_mcp: Optional[str] = None,
    api_mode_llm_endpoint: Optional[str] = None,
    api_mode_llm_api_key: Optional[str] = None,
    api_mode_mcp_endpoint: Optional[str] = None,
    api_mode_mcp_api_key: Optional[str] = None,
    api_mode_fail_open_llm: bool = True,
    api_mode_fail_open_mcp: bool = True,
    # Gateway mode configuration
    gateway_mode_llm: str = "on",
    gateway_mode_mcp: str = "on",
    gateway_mode_mcp_url: Optional[str] = None,
    gateway_mode_mcp_api_key: Optional[str] = None,
    gateway_mode_fail_open_llm: bool = True,
    gateway_mode_fail_open_mcp: bool = True,
    # Provider-specific gateway configuration
    provider_gateway_config: Optional[Dict[str, Dict[str, Optional[str]]]] = None,
    # Provider-specific API configuration
    provider_api_config: Optional[Dict[str, Dict[str, Optional[str]]]] = None,
) -> None:
    """
    Set the global state.
    
    Args:
        initialized: Whether agentsec has been initialized
        llm_rules: LLM rules for API mode inspection
        llm_integration_mode: Integration mode for LLM (api/gateway)
        mcp_integration_mode: Integration mode for MCP (api/gateway)
        api_mode_llm: Mode for LLM in API mode (off/monitor/enforce)
        api_mode_mcp: Mode for MCP in API mode (off/monitor/enforce)
        api_mode_llm_endpoint: API endpoint for LLM inspection
        api_mode_llm_api_key: API key for LLM inspection
        api_mode_mcp_endpoint: API endpoint for MCP inspection
        api_mode_mcp_api_key: API key for MCP inspection
        api_mode_fail_open_llm: Allow LLM requests on API errors
        api_mode_fail_open_mcp: Allow MCP calls on API errors
        gateway_mode_llm: Mode for LLM in gateway mode (off/on)
        gateway_mode_mcp: Mode for MCP in gateway mode (off/on)
        gateway_mode_mcp_url: Gateway URL for MCP calls
        gateway_mode_mcp_api_key: Gateway API key for MCP calls
        gateway_mode_fail_open_llm: Allow LLM requests on gateway errors
        gateway_mode_fail_open_mcp: Allow MCP calls on gateway errors
        provider_gateway_config: Per-provider gateway config {provider: {url, api_key}}
        provider_api_config: Per-provider API config {provider: {url, api_key}}
    """
    global _initialized, _llm_rules
    global _llm_integration_mode, _mcp_integration_mode
    global _api_mode_llm, _api_mode_mcp
    global _api_mode_llm_endpoint, _api_mode_llm_api_key
    global _api_mode_mcp_endpoint, _api_mode_mcp_api_key
    global _api_mode_fail_open_llm, _api_mode_fail_open_mcp
    global _gateway_mode_llm, _gateway_mode_mcp
    global _gateway_mode_mcp_url, _gateway_mode_mcp_api_key
    global _gateway_mode_fail_open_llm, _gateway_mode_fail_open_mcp
    global _provider_gateway_config, _provider_api_config
    
    _initialized = initialized
    _llm_rules = llm_rules
    _llm_integration_mode = llm_integration_mode
    _mcp_integration_mode = mcp_integration_mode
    _api_mode_llm = api_mode_llm
    _api_mode_mcp = api_mode_mcp
    _api_mode_llm_endpoint = api_mode_llm_endpoint
    _api_mode_llm_api_key = api_mode_llm_api_key
    _api_mode_mcp_endpoint = api_mode_mcp_endpoint
    _api_mode_mcp_api_key = api_mode_mcp_api_key
    _api_mode_fail_open_llm = api_mode_fail_open_llm
    _api_mode_fail_open_mcp = api_mode_fail_open_mcp
    _gateway_mode_llm = gateway_mode_llm
    _gateway_mode_mcp = gateway_mode_mcp
    _gateway_mode_mcp_url = gateway_mode_mcp_url
    _gateway_mode_mcp_api_key = gateway_mode_mcp_api_key
    _gateway_mode_fail_open_llm = gateway_mode_fail_open_llm
    _gateway_mode_fail_open_mcp = gateway_mode_fail_open_mcp
    
    # Update provider-specific configs
    if provider_gateway_config:
        for provider, config in provider_gateway_config.items():
            if provider in _provider_gateway_config:
                _provider_gateway_config[provider] = config
    
    if provider_api_config:
        for provider, config in provider_api_config.items():
            if provider in _provider_api_config:
                _provider_api_config[provider] = config


def reset() -> None:
    """Reset global state. Useful for testing."""
    global _initialized, _llm_rules
    global _llm_integration_mode, _mcp_integration_mode
    global _api_mode_llm, _api_mode_mcp
    global _api_mode_llm_endpoint, _api_mode_llm_api_key
    global _api_mode_mcp_endpoint, _api_mode_mcp_api_key
    global _api_mode_fail_open_llm, _api_mode_fail_open_mcp
    global _gateway_mode_llm, _gateway_mode_mcp
    global _gateway_mode_mcp_url, _gateway_mode_mcp_api_key
    global _gateway_mode_fail_open_llm, _gateway_mode_fail_open_mcp
    global _provider_gateway_config, _provider_api_config
    
    _initialized = False
    _llm_rules = None
    _llm_integration_mode = "api"
    _mcp_integration_mode = "api"
    _api_mode_llm = None
    _api_mode_mcp = None
    _api_mode_llm_endpoint = None
    _api_mode_llm_api_key = None
    _api_mode_mcp_endpoint = None
    _api_mode_mcp_api_key = None
    _api_mode_fail_open_llm = True
    _api_mode_fail_open_mcp = True
    _gateway_mode_llm = "on"
    _gateway_mode_mcp = "on"
    _gateway_mode_mcp_url = None
    _gateway_mode_mcp_api_key = None
    _gateway_mode_fail_open_llm = True
    _gateway_mode_fail_open_mcp = True
    
    # Reset provider-specific configs
    _provider_gateway_config = {
        "openai": {"url": None, "api_key": None},
        "azure_openai": {"url": None, "api_key": None},
        "vertexai": {"url": None, "api_key": None},
        "bedrock": {"url": None, "api_key": None},
        "agentcore": {"url": None, "api_key": None},
    }
    _provider_api_config = {
        "openai": {"url": None, "api_key": None},
        "azure_openai": {"url": None, "api_key": None},
        "vertexai": {"url": None, "api_key": None},
        "bedrock": {"url": None, "api_key": None},
        "agentcore": {"url": None, "api_key": None},
    }
