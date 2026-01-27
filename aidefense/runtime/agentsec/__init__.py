"""
agentsec - Agent Runtime Security Sensor SDK

Provides runtime security enforcement and monitoring for LLM and MCP
interactions with minimal integration effort.

Usage (Simple - Recommended):
    import agentsec
    agentsec.protect()  # Auto-configures from environment
    
    # Now import your LLM client
    from openai import OpenAI

Usage (Fine-Grained Control):
    import agentsec
    agentsec.protect(
        api_mode_llm="on_enforce",    # Enforce LLM inspection
        api_mode_mcp="on_monitor",    # Monitor MCP tools
        api_mode_llm_rules=["jailbreak", "prompt_injection"],  # Optional rules
    )

For more information, see:
https://developer.cisco.com/docs/ai-defense/overview/
"""

import logging
from typing import Any, List, Optional

from . import _state
from .config import load_env_config, VALID_MODES, VALID_GATEWAY_MODES
from .decision import Decision
from .exceptions import SecurityPolicyError
from ._logging import setup_logging
from ._context import skip_inspection, no_inspection

__all__ = [
    "protect",
    "get_patched_clients",
    "Decision",
    "SecurityPolicyError",
    "skip_inspection",
    "no_inspection",
]

__version__ = "0.1.0"

# Logger - use the centralized logging module
logger = logging.getLogger("aidefense.runtime.agentsec")


def _auto_load_dotenv() -> bool:
    """
    Automatically load .env file if python-dotenv is installed.
    
    Searches for .env starting from the current working directory (usecwd=True),
    which is typically where the user's application runs from.
    
    Returns:
        True if .env was loaded, False otherwise.
    """
    try:
        from dotenv import load_dotenv, find_dotenv
        # find_dotenv() defaults to searching from __file__, which would be
        # the agentsec package. Use usecwd=True to search from the current
        # working directory where the user's .env file is located.
        dotenv_path = find_dotenv(usecwd=True)
        if dotenv_path:
            load_dotenv(dotenv_path)
            logger.debug(f"Auto-loaded .env file: {dotenv_path}")
        else:
            # Fall back to default behavior if no .env found
            load_dotenv()
            logger.debug("No .env file found in current directory")
        return True
    except ImportError:
        logger.debug("python-dotenv not installed, skipping .env auto-load")
        return False


def _apply_patches(llm_mode: str, mcp_mode: str) -> None:
    """Apply client patches based on modes."""
    from .patchers import (
        patch_openai,
        patch_bedrock,
        patch_mcp,
        patch_vertexai,
        patch_google_genai,
    )
    
    # Patch LLM clients if not off
    if llm_mode != "off":
        patch_openai()
        patch_bedrock()
        patch_vertexai()
        patch_google_genai()
    
    # Patch MCP client if not off
    if mcp_mode != "off":
        patch_mcp()


def get_patched_clients() -> List[str]:
    """
    Get list of successfully patched clients.
    
    Returns:
        List of client names that have been patched (e.g., ["openai", "litellm"])
    """
    from .patchers import get_patched_clients as _get_patched
    return _get_patched()


def protect(
    patch_clients: bool = True,
    *,
    auto_dotenv: bool = True,
    # Integration mode (common for both API and Gateway)
    llm_integration_mode: Optional[str] = None,  # AGENTSEC_LLM_INTEGRATION_MODE
    mcp_integration_mode: Optional[str] = None,  # AGENTSEC_MCP_INTEGRATION_MODE
    # API mode configuration
    api_mode_llm: Optional[str] = None,  # AGENTSEC_API_MODE_LLM (off/on_monitor/on_enforce)
    api_mode_mcp: Optional[str] = None,  # AGENTSEC_API_MODE_MCP (off/on_monitor/on_enforce)
    api_mode_llm_endpoint: Optional[str] = None,  # AI_DEFENSE_API_MODE_LLM_ENDPOINT
    api_mode_llm_api_key: Optional[str] = None,  # AI_DEFENSE_API_MODE_LLM_API_KEY
    api_mode_mcp_endpoint: Optional[str] = None,  # AI_DEFENSE_API_MODE_MCP_ENDPOINT
    api_mode_mcp_api_key: Optional[str] = None,  # AI_DEFENSE_API_MODE_MCP_API_KEY
    api_mode_fail_open_llm: Optional[bool] = None,  # AGENTSEC_API_MODE_FAIL_OPEN_LLM
    api_mode_fail_open_mcp: Optional[bool] = None,  # AGENTSEC_API_MODE_FAIL_OPEN_MCP
    api_mode_llm_rules: Optional[List[Any]] = None,  # AGENTSEC_LLM_RULES
    # Gateway mode configuration
    gateway_mode_llm: Optional[str] = None,  # AGENTSEC_GATEWAY_MODE_LLM (off/on)
    gateway_mode_mcp: Optional[str] = None,  # AGENTSEC_GATEWAY_MODE_MCP (off/on)
    gateway_mode_mcp_url: Optional[str] = None,  # AGENTSEC_MCP_GATEWAY_URL
    gateway_mode_mcp_api_key: Optional[str] = None,  # AGENTSEC_MCP_GATEWAY_API_KEY
    gateway_mode_fail_open_llm: Optional[bool] = None,  # AGENTSEC_GATEWAY_MODE_FAIL_OPEN_LLM
    gateway_mode_fail_open_mcp: Optional[bool] = None,  # AGENTSEC_GATEWAY_MODE_FAIL_OPEN_MCP
    # Provider-specific gateway configuration
    providers: Optional[dict] = None,  # Per-provider gateway config
) -> None:
    """
    Enable agentsec protection for LLM and MCP interactions.
    
    This is the main entry point for agentsec. Call this once at the top of your
    application, BEFORE importing any LLM clients.
    
    Minimal usage:
        import agentsec
        agentsec.protect()
        
        # Now import your framework
        from openai import OpenAI
    
    API mode (inspection via Cisco AI Defense API):
        import agentsec
        agentsec.protect(
            api_mode_llm="on_enforce",    # Block LLM policy violations
            api_mode_mcp="on_monitor",    # Log MCP tools, don't block
            api_mode_llm_endpoint="https://preview.api.inspect.aidefense.aiteam.cisco.com/api",
            api_mode_llm_api_key="your-api-key",
            auto_dotenv=False,
        )
    
    Gateway mode (routes through Cisco AI Defense Gateway):
        import agentsec
        agentsec.protect(
            llm_integration_mode="gateway",
            providers={
                "openai": {"gateway_url": "https://gateway.../openai-conn", "gateway_api_key": "key1"},
                "vertexai": {"gateway_url": "https://gateway.../vertexai-conn", "gateway_api_key": "key2"},
                "bedrock": {"gateway_url": "https://gateway.../bedrock-conn", "gateway_api_key": "key3"},
            },
            mcp_integration_mode="gateway",
            gateway_mode_mcp_url="https://gateway.agent.preview.aidefense.aiteam.cisco.com/...",
            auto_dotenv=False,
        )
    
    This function is idempotent - calling it multiple times has no effect
    after the first successful call.
    
    Args:
        patch_clients: Whether to autopatch LLM clients (openai, boto3, litellm, mcp)
        auto_dotenv: Automatically load .env file if python-dotenv is installed.
            Set to False if you manage environment loading yourself.
        
        Integration Mode (common):
        llm_integration_mode: Integration mode for LLM - "api" or "gateway"
            If None, reads from AGENTSEC_LLM_INTEGRATION_MODE env var (default: "api")
        mcp_integration_mode: Integration mode for MCP - "api" or "gateway"
            If None, reads from AGENTSEC_MCP_INTEGRATION_MODE env var (default: "api")
        
        API Mode:
        api_mode_llm: Mode for LLM inspection - "off", "on_monitor", or "on_enforce"
            If None, reads from AGENTSEC_API_MODE_LLM env var (default: "on_monitor")
        api_mode_mcp: Mode for MCP tool inspection - "off", "on_monitor", or "on_enforce"
            If None, reads from AGENTSEC_API_MODE_MCP env var (default: "on_monitor")
        api_mode_llm_endpoint: API endpoint for LLM inspection
            If None, reads from AI_DEFENSE_API_MODE_LLM_ENDPOINT env var
        api_mode_llm_api_key: API key for LLM inspection
            If None, reads from AI_DEFENSE_API_MODE_LLM_API_KEY env var
        api_mode_mcp_endpoint: API endpoint for MCP inspection (optional, falls back to LLM)
            If None, reads from AI_DEFENSE_API_MODE_MCP_ENDPOINT env var
        api_mode_mcp_api_key: API key for MCP inspection (optional, falls back to LLM)
            If None, reads from AI_DEFENSE_API_MODE_MCP_API_KEY env var
        api_mode_fail_open_llm: Allow LLM requests on API errors
            If None, reads from AGENTSEC_API_MODE_FAIL_OPEN_LLM env var (default: True)
        api_mode_fail_open_mcp: Allow MCP calls on API errors
            If None, reads from AGENTSEC_API_MODE_FAIL_OPEN_MCP env var (default: True)
        api_mode_llm_rules: Rules to enable for LLM inspection (e.g., ["jailbreak", "prompt_injection"])
            If None, reads from AGENTSEC_LLM_RULES env var (JSON array or comma-separated)
        
        Gateway Mode:
        gateway_mode_llm: Mode for LLM gateway - "off" or "on"
            If None, reads from AGENTSEC_GATEWAY_MODE_LLM env var (default: "on")
        gateway_mode_mcp: Mode for MCP gateway - "off" or "on"
            If None, reads from AGENTSEC_GATEWAY_MODE_MCP env var (default: "on")
        gateway_mode_mcp_url: Gateway URL for MCP calls
            If None, reads from AGENTSEC_MCP_GATEWAY_URL env var
        gateway_mode_mcp_api_key: API key for MCP gateway
            If None, reads from AGENTSEC_MCP_GATEWAY_API_KEY env var
        gateway_mode_fail_open_llm: Allow LLM requests on gateway errors
            If None, reads from AGENTSEC_GATEWAY_MODE_FAIL_OPEN_LLM env var (default: True)
        gateway_mode_fail_open_mcp: Allow MCP calls on gateway errors
            If None, reads from AGENTSEC_GATEWAY_MODE_FAIL_OPEN_MCP env var (default: True)
        providers: Per-provider gateway and API configuration dict
            Example: {"openai": {"gateway_url": "...", "gateway_api_key": "..."}}
        
    Raises:
        ValueError: If any mode is not one of "off", "on_monitor", "on_enforce"
        ValueError: If integration_mode is not one of "api", "gateway"
        
    Environment Variables:
        AGENTSEC_API_MODE_LLM: Mode for LLM inspection (default: "on_monitor")
        AGENTSEC_API_MODE_MCP: Mode for MCP inspection (default: "on_monitor")
        AGENTSEC_API_MODE_FAIL_OPEN_LLM: Allow LLM calls on API errors (default: "true")
        AGENTSEC_API_MODE_FAIL_OPEN_MCP: Allow MCP calls on API errors (default: "true")
        AGENTSEC_LOG_LEVEL: Logging level (default: "INFO")
        AGENTSEC_LLM_INTEGRATION_MODE: Integration mode for LLM - "api" or "gateway" (default: "api")
        AGENTSEC_MCP_INTEGRATION_MODE: Integration mode for MCP - "api" or "gateway" (default: "api")
        AI_DEFENSE_API_MODE_LLM_API_KEY: API key for AI Defense inspection service
        AI_DEFENSE_API_MODE_LLM_ENDPOINT: Endpoint URL for AI Defense API
        AI_DEFENSE_GATEWAY_MODE_LLM_URL: Gateway URL for LLM calls (gateway mode only)
        AI_DEFENSE_GATEWAY_MODE_LLM_API_KEY: Gateway API key for LLM calls (gateway mode only)
        AI_DEFENSE_GATEWAY_MODE_MCP_URL: Gateway URL for MCP calls (gateway mode only)
        AI_DEFENSE_GATEWAY_MODE_MCP_API_KEY: Gateway API key for MCP calls (gateway mode only)
    """
    # Idempotency check
    if _state.is_initialized():
        logger.debug("agentsec already initialized, skipping")
        return
    
    # Step 1: Auto-load .env file (before reading env vars)
    if auto_dotenv:
        _auto_load_dotenv()
    
    # Step 2: Load environment config
    env_config = load_env_config()
    
    # Step 3: Get integration modes from parameters or env config (default: "api")
    if llm_integration_mode is None:
        llm_integration_mode = env_config.get("llm_integration_mode", "api")
    if mcp_integration_mode is None:
        mcp_integration_mode = env_config.get("mcp_integration_mode", "api")
    
    # Validate integration modes
    valid_integration_modes = ("api", "gateway")
    for name, mode in [("llm_integration_mode", llm_integration_mode), ("mcp_integration_mode", mcp_integration_mode)]:
        if mode not in valid_integration_modes:
            raise ValueError(
                f"Invalid {name} '{mode}'. Must be one of: {', '.join(valid_integration_modes)}"
            )
    
    # Step 4: Get API mode settings from parameters or env config
    if api_mode_llm is None:
        api_mode_llm = env_config.get("llm_mode") or "on_monitor"
    if api_mode_mcp is None:
        api_mode_mcp = env_config.get("mcp_mode") or "on_monitor"
    
    # Validate API modes
    for name, mode in [("api_mode_llm", api_mode_llm), ("api_mode_mcp", api_mode_mcp)]:
        if mode not in VALID_MODES:
            raise ValueError(
                f"Invalid {name} '{mode}'. Must be one of: {', '.join(VALID_MODES)}"
            )
    
    # Get API endpoints and keys from parameters or env config
    if api_mode_llm_endpoint is None:
        api_mode_llm_endpoint = env_config.get("api_endpoint")
    if api_mode_llm_api_key is None:
        api_mode_llm_api_key = env_config.get("api_key")
    if api_mode_mcp_endpoint is None:
        api_mode_mcp_endpoint = env_config.get("mcp_api_endpoint") or api_mode_llm_endpoint
    if api_mode_mcp_api_key is None:
        api_mode_mcp_api_key = env_config.get("mcp_api_key") or api_mode_llm_api_key
    
    # Get API mode fail_open settings
    if api_mode_fail_open_llm is None:
        api_mode_fail_open_llm = env_config.get("llm_fail_open", True)
    if api_mode_fail_open_mcp is None:
        api_mode_fail_open_mcp = env_config.get("mcp_fail_open", True)
    
    # Step 5: Get gateway mode settings from parameters or env config
    if gateway_mode_llm is None:
        gateway_mode_llm = env_config.get("llm_gateway_mode", "on")
    if gateway_mode_mcp is None:
        gateway_mode_mcp = env_config.get("mcp_gateway_mode", "on")
    
    # Validate gateway modes
    for name, mode in [("gateway_mode_llm", gateway_mode_llm), ("gateway_mode_mcp", gateway_mode_mcp)]:
        if mode not in VALID_GATEWAY_MODES:
            raise ValueError(
                f"Invalid {name} '{mode}'. Must be one of: {', '.join(VALID_GATEWAY_MODES)}"
            )
    
    # Get MCP gateway URL and API key
    if gateway_mode_mcp_url is None:
        gateway_mode_mcp_url = env_config.get("mcp_gateway_url")
    if gateway_mode_mcp_api_key is None:
        gateway_mode_mcp_api_key = env_config.get("mcp_gateway_api_key")
    
    # Get gateway mode fail_open settings
    if gateway_mode_fail_open_llm is None:
        gateway_mode_fail_open_llm = env_config.get("llm_gateway_fail_open", True)
    if gateway_mode_fail_open_mcp is None:
        gateway_mode_fail_open_mcp = env_config.get("mcp_gateway_fail_open", True)
    
    # Build provider-specific gateway config from parameters or env
    env_provider_gateway_config = env_config.get("provider_gateway_config", {})
    env_provider_api_config = env_config.get("provider_api_config", {})
    
    provider_gateway_config = {}
    provider_api_config = {}
    
    for provider in ["openai", "azure_openai", "vertexai", "bedrock", "agentcore", "google_genai"]:
        # Gateway config from providers parameter or env
        if providers and provider in providers:
            provider_config = providers[provider]
            provider_gateway_config[provider] = {
                "url": provider_config.get("gateway_url"),
                "api_key": provider_config.get("gateway_api_key"),
            }
            provider_api_config[provider] = {
                "url": provider_config.get("api_url"),
                "api_key": provider_config.get("api_key"),
            }
        else:
            # Fall back to env config
            provider_gateway_config[provider] = env_provider_gateway_config.get(provider, {"url": None, "api_key": None})
            provider_api_config[provider] = env_provider_api_config.get(provider, {"url": None, "api_key": None})
    
    # Get LLM rules from parameter or env config
    if api_mode_llm_rules is None:
        api_mode_llm_rules = env_config.get("llm_rules")
    
    # Handle all-off mode - minimal initialization
    if api_mode_llm == "off" and api_mode_mcp == "off":
        _state.set_state(
            initialized=True, 
            llm_rules=None, 
            api_mode_llm="off",
            api_mode_mcp="off",
            llm_integration_mode=llm_integration_mode,
            mcp_integration_mode=mcp_integration_mode,
            api_mode_llm_endpoint=api_mode_llm_endpoint,
            api_mode_llm_api_key=api_mode_llm_api_key,
            api_mode_mcp_endpoint=api_mode_mcp_endpoint,
            api_mode_mcp_api_key=api_mode_mcp_api_key,
            api_mode_fail_open_llm=api_mode_fail_open_llm,
            api_mode_fail_open_mcp=api_mode_fail_open_mcp,
            gateway_mode_llm=gateway_mode_llm,
            gateway_mode_mcp=gateway_mode_mcp,
            gateway_mode_mcp_url=gateway_mode_mcp_url,
            gateway_mode_mcp_api_key=gateway_mode_mcp_api_key,
            gateway_mode_fail_open_llm=gateway_mode_fail_open_llm,
            gateway_mode_fail_open_mcp=gateway_mode_fail_open_mcp,
            provider_gateway_config=provider_gateway_config,
            provider_api_config=provider_api_config,
        )
        logger.debug("agentsec disabled (all modes=off)")
        return
    
    # Setup logging using centralized module
    setup_logging(
        level=env_config.get("log_level"),
        format_type=env_config.get("log_format"),
        log_file=env_config.get("log_file"),
        redact=env_config.get("redact_logs", True),
    )
    
    # Store state BEFORE patching (so patchers can access config)
    _state.set_state(
        initialized=True, 
        llm_rules=api_mode_llm_rules, 
        api_mode_llm=api_mode_llm,
        api_mode_mcp=api_mode_mcp,
        llm_integration_mode=llm_integration_mode,
        mcp_integration_mode=mcp_integration_mode,
        api_mode_llm_endpoint=api_mode_llm_endpoint,
        api_mode_llm_api_key=api_mode_llm_api_key,
        api_mode_mcp_endpoint=api_mode_mcp_endpoint,
        api_mode_mcp_api_key=api_mode_mcp_api_key,
        api_mode_fail_open_llm=api_mode_fail_open_llm,
        api_mode_fail_open_mcp=api_mode_fail_open_mcp,
        gateway_mode_llm=gateway_mode_llm,
        gateway_mode_mcp=gateway_mode_mcp,
        gateway_mode_mcp_url=gateway_mode_mcp_url,
        gateway_mode_mcp_api_key=gateway_mode_mcp_api_key,
        gateway_mode_fail_open_llm=gateway_mode_fail_open_llm,
        gateway_mode_fail_open_mcp=gateway_mode_fail_open_mcp,
        provider_gateway_config=provider_gateway_config,
        provider_api_config=provider_api_config,
    )
    
    # Apply client patches
    patched = []
    if patch_clients:
        logger.debug("Applying client patches...")
        _apply_patches(api_mode_llm, api_mode_mcp)
        patched = get_patched_clients()
    
    # Log initialization with per-type modes
    # Include integration mode info if gateway mode is used
    integration_info = ""
    if llm_integration_mode == "gateway" or mcp_integration_mode == "gateway":
        integration_info = f" | Integration: LLM={llm_integration_mode}, MCP={mcp_integration_mode}"
    
    print(f"[agentsec] LLM: {api_mode_llm} | MCP: {api_mode_mcp} | Patched: {patched}{integration_info}")
    logger.info(
        f"agentsec initialized: api_mode_llm={api_mode_llm}, api_mode_mcp={api_mode_mcp}, "
        f"llm_integration={llm_integration_mode}, mcp_integration={mcp_integration_mode}"
    )
