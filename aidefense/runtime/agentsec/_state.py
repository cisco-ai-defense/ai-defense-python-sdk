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

"""Global state management for agentsec."""

import logging
import threading
from typing import Any, Callable, Dict, List, Optional

from .gateway_settings import GatewaySettings


logger = logging.getLogger("aidefense.runtime.agentsec._state")

# Thread lock for state mutations
_state_lock = threading.Lock()

# Supported LLM providers
SUPPORTED_PROVIDERS = [
    "openai", "azure_openai", "vertexai", "bedrock",
    "google_genai", "cohere", "mistral",
]

# Valid configuration values — import canonical definitions from config.py
# to avoid duplicate definitions that could drift.
from .config import (
    VALID_MODES as _VALID_MODES_TUPLE,
    VALID_GATEWAY_MODES as _VALID_GATEWAY_MODES_TUPLE,
    VALID_INTEGRATION_MODES as _VALID_INTEGRATION_MODES_TUPLE,
)

VALID_API_MODES = set(_VALID_MODES_TUPLE)
VALID_GATEWAY_MODES = set(_VALID_GATEWAY_MODES_TUPLE)
VALID_INTEGRATION_MODES = set(_VALID_INTEGRATION_MODES_TUPLE)
VALID_AUTH_MODES = {"none", "api_key", "aws_sigv4", "google_adc", "oauth2_client_credentials", "client"}
VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}
VALID_LOG_FORMATS = {"text", "json"}

# ---------------------------------------------------------------------------
# Global state variables
# ---------------------------------------------------------------------------

_initialized: bool = False

# LLM rules for API mode inspection
_llm_rules: Optional[List[Any]] = None

# LLM entity types for filtering
_llm_entity_types: Optional[List[str]] = None

# Metadata defaults
_metadata_user: Optional[str] = None
_metadata_src_app: Optional[str] = None
_metadata_client_transaction_id: Optional[str] = None

# Connection pool configuration (global, not per-gateway)
_pool_max_connections: Optional[int] = None  # Default: 100
_pool_max_keepalive: Optional[int] = None  # Default: 20

# Logger configuration
_log_file: Optional[str] = None
_log_format: Optional[str] = None
_custom_logger: Optional[Any] = None

# Integration modes (api vs gateway)
_llm_integration_mode: str = "api"
_mcp_integration_mode: str = "api"

# API mode configuration (mode strings, endpoints, keys)
_api_mode_llm: Optional[str] = None  # off/monitor/enforce
_api_mode_mcp: Optional[str] = None  # off/monitor/enforce
_api_mode_llm_endpoint: Optional[str] = None
_api_mode_llm_api_key: Optional[str] = None
_api_mode_mcp_endpoint: Optional[str] = None
_api_mode_mcp_api_key: Optional[str] = None

# ---------------------------------------------------------------------------
# Gateway mode: on/off switches (from gateway_mode.llm_mode / mcp_mode)
# ---------------------------------------------------------------------------

_gw_llm_mode: str = "on"   # on/off
_gw_mcp_mode: str = "on"   # on/off

# ---------------------------------------------------------------------------
# Gateway mode defaults (from gateway_mode.llm_defaults / mcp_defaults)
# ---------------------------------------------------------------------------

_gw_llm_fail_open: bool = True
_gw_llm_timeout: int = 60  # Gateway proxies to LLM; needs time for inference
_gw_llm_retry_total: int = 3
_gw_llm_retry_backoff: float = 0.5
_gw_llm_retry_status_codes: List[int] = [429, 500, 502, 503, 504]

_gw_mcp_fail_open: bool = True
_gw_mcp_timeout: int = 10
_gw_mcp_retry_total: int = 2
_gw_mcp_retry_backoff: float = 1.0
_gw_mcp_retry_status_codes: List[int] = [429, 500, 502, 503, 504]

# Gateway mode: named gateways and provider-default index
_llm_gateways: Dict[str, dict] = {}
_provider_default_gateways: Dict[str, dict] = {}  # provider -> gateway config (built from llm_gateways with default: true)
_mcp_gateway_map: Dict[str, dict] = {}

# ---------------------------------------------------------------------------
# API mode per-category defaults (from api_mode.llm_defaults / mcp_defaults)
# ---------------------------------------------------------------------------

_api_llm_fail_open: bool = False
_api_llm_timeout: int = 5
_api_llm_retry_total: int = 2
_api_llm_retry_backoff: float = 0.5
_api_llm_retry_status_codes: List[int] = [429, 500, 502, 503, 504]

_api_mcp_fail_open: bool = True
_api_mcp_timeout: int = 5
_api_mcp_retry_total: int = 2
_api_mcp_retry_backoff: float = 0.5
_api_mcp_retry_status_codes: List[int] = [429, 500, 502, 503, 504]

# Monitor-mode violation callback
_on_violation: Optional[Callable] = None


# ===========================================================================
# Getters — preserved
# ===========================================================================

def is_initialized() -> bool:
    """Check if agentsec has been initialized."""
    return _initialized


def get_on_violation() -> Optional[Callable]:
    """Get the on_violation callback for monitor-mode block decisions."""
    return _on_violation


def set_on_violation(callback: Optional[Callable]) -> None:
    """Set the on_violation callback for monitor-mode block decisions."""
    global _on_violation
    _on_violation = callback


def get_llm_rules() -> Optional[List[Any]]:
    """Get the current LLM rules for API mode inspection."""
    return _llm_rules


def get_llm_entity_types() -> Optional[List[str]]:
    """Get the LLM entity types for filtering."""
    return _llm_entity_types


# Metadata getters
def get_metadata_user() -> Optional[str]:
    """Get the default metadata user."""
    return _metadata_user


def get_metadata_src_app() -> Optional[str]:
    """Get the default metadata source application."""
    return _metadata_src_app


def get_metadata_client_transaction_id() -> Optional[str]:
    """Get the default metadata client transaction ID."""
    return _metadata_client_transaction_id


# Connection pool getters (global)
def get_pool_max_connections() -> Optional[int]:
    """Get the pool max connections. None means use default (100)."""
    return _pool_max_connections


def get_pool_max_keepalive() -> Optional[int]:
    """Get the pool max keepalive connections. None means use default (20)."""
    return _pool_max_keepalive


# Logger getters
def get_log_file() -> Optional[str]:
    """Get the log file path."""
    return _log_file


def get_log_format() -> Optional[str]:
    """Get the log format ('text' or 'json')."""
    return _log_format


def get_custom_logger() -> Optional[Any]:
    """Get the custom logger instance."""
    return _custom_logger


# Integration mode getters
def get_llm_integration_mode() -> str:
    """Get the current LLM integration mode ('api' or 'gateway')."""
    return _llm_integration_mode


def get_mcp_integration_mode() -> str:
    """Get the current MCP integration mode ('api' or 'gateway')."""
    return _mcp_integration_mode


# Gateway mode on/off getters
def get_gw_llm_mode() -> str:
    """Get the current gateway LLM mode ('on' or 'off')."""
    return _gw_llm_mode


def get_gw_mcp_mode() -> str:
    """Get the current gateway MCP mode ('on' or 'off')."""
    return _gw_mcp_mode


# API mode getters (mode strings, endpoints, keys)
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
    """Get the MCP API endpoint (no fallback to LLM endpoint)."""
    return _api_mode_mcp_endpoint


def get_api_mode_mcp_api_key() -> Optional[str]:
    """Get the MCP API key (no fallback to LLM key)."""
    return _api_mode_mcp_api_key


# Legacy aliases for API mode (used by patchers as get_llm_mode / get_mcp_mode)
def get_llm_mode() -> Optional[str]:
    """Get the current LLM inspection mode (alias for get_api_mode_llm)."""
    return _api_mode_llm


def get_mcp_mode() -> Optional[str]:
    """Get the current MCP inspection mode (alias for get_api_mode_mcp)."""
    return _api_mode_mcp


# ===========================================================================
# New getters — gateway mode
# ===========================================================================

def get_default_gateway_for_provider(provider: str) -> Optional[dict]:
    """Get the default LLM gateway config for a provider.

    Returns the gateway entry from ``llm_gateways`` that has
    ``provider: <name>`` and ``default: true``.

    Args:
        provider: Provider name (e.g. "openai", "bedrock").

    Returns:
        Gateway config dict or None if no default is configured.
    """
    return _provider_default_gateways.get(provider)


def get_llm_gateway(name: str) -> Optional[dict]:
    """Get a named LLM gateway config from gateway_mode.llm_gateways.

    Args:
        name: Gateway name (e.g. "math-gateway").

    Returns:
        Gateway config dict or None if not configured.
    """
    return _llm_gateways.get(name)


def get_mcp_gateway_for_url(url: str) -> Optional[dict]:
    """Look up the MCP gateway config for a specific MCP server URL.

    Args:
        url: The original MCP server URL.

    Returns:
        Gateway config dict or None if no mapping exists for this URL.
    """
    return _mcp_gateway_map.get(url)


# ===========================================================================
# New getters — API mode per-category defaults
# ===========================================================================

def get_api_llm_fail_open() -> bool:
    """Get the LLM API mode fail_open setting."""
    return _api_llm_fail_open


def get_api_llm_timeout() -> int:
    """Get the LLM API mode timeout in seconds."""
    return _api_llm_timeout


def get_api_llm_retry_total() -> int:
    """Get the LLM API mode retry total."""
    return _api_llm_retry_total


def get_api_llm_retry_backoff() -> float:
    """Get the LLM API mode retry backoff factor."""
    return _api_llm_retry_backoff


def get_api_llm_retry_status_codes() -> List[int]:
    """Get the LLM API mode retry status codes."""
    return _api_llm_retry_status_codes


def get_api_mcp_fail_open() -> bool:
    """Get the MCP API mode fail_open setting."""
    return _api_mcp_fail_open


def get_api_mcp_timeout() -> int:
    """Get the MCP API mode timeout in seconds."""
    return _api_mcp_timeout


def get_api_mcp_retry_total() -> int:
    """Get the MCP API mode retry total."""
    return _api_mcp_retry_total


def get_api_mcp_retry_backoff() -> float:
    """Get the MCP API mode retry backoff factor."""
    return _api_mcp_retry_backoff


def get_api_mcp_retry_status_codes() -> List[int]:
    """Get the MCP API mode retry status codes."""
    return _api_mcp_retry_status_codes


# ===========================================================================
# New getters — gateway mode defaults (used by resolve functions)
# ===========================================================================

def get_gw_llm_fail_open() -> bool:
    """Get the gateway mode LLM fail_open default."""
    return _gw_llm_fail_open


def get_gw_mcp_fail_open() -> bool:
    """Get the gateway mode MCP fail_open default."""
    return _gw_mcp_fail_open


# ===========================================================================
# Resolve functions — merge raw config with defaults into GatewaySettings
# ===========================================================================

def resolve_llm_gateway_settings(
    raw_config: dict,
    provider: Optional[str] = None,
) -> GatewaySettings:
    """Resolve a raw LLM gateway config dict into a GatewaySettings object.

    Merges per-gateway overrides with gateway_mode.llm_defaults, then
    resolves auth_mode from the provider config if not explicitly set.

    Args:
        raw_config: A dict with keys like gateway_url, gateway_api_key,
            auth_mode, fail_open, timeout, retry (sub-dict).
        provider: Optional provider name for auth_mode inheritance.

    Returns:
        A fully-resolved GatewaySettings object.

    Raises:
        ConfigurationError: If gateway_url is empty or auth_mode is invalid.
    """
    from .exceptions import ConfigurationError

    retry = raw_config.get("retry", {}) or {}

    # Validate gateway_url is non-empty
    gateway_url = raw_config.get("gateway_url", "")
    if not gateway_url or not isinstance(gateway_url, str) or not gateway_url.strip():
        raise ConfigurationError(
            "gateway_url is required and must be a non-empty string "
            "in LLM gateway configuration."
        )

    # Resolve auth_mode: explicit > default gateway for provider > "api_key"
    auth_mode = raw_config.get("auth_mode")
    if not auth_mode and provider:
        default_gw = _provider_default_gateways.get(provider, {})
        auth_mode = default_gw.get("auth_mode")
    if not auth_mode:
        auth_mode = "api_key"

    # Validate auth_mode
    if auth_mode not in VALID_AUTH_MODES:
        raise ConfigurationError(
            f"Invalid auth_mode: '{auth_mode}'. "
            f"Must be one of: {', '.join(sorted(VALID_AUTH_MODES))}"
        )

    return GatewaySettings(
        url=raw_config.get("gateway_url", ""),
        api_key=raw_config.get("gateway_api_key"),
        api_key_header=raw_config.get("gateway_api_key_header", "api-key"),
        auth_mode=auth_mode,
        fail_open=raw_config.get("fail_open", _gw_llm_fail_open),
        timeout=raw_config.get("timeout", _gw_llm_timeout),
        retry_total=retry.get("total", _gw_llm_retry_total),
        retry_backoff=retry.get("backoff_factor", _gw_llm_retry_backoff),
        retry_status_codes=retry.get("status_codes", _gw_llm_retry_status_codes),
        aws_region=raw_config.get("aws_region"),
        aws_profile=raw_config.get("aws_profile"),
        aws_access_key_id=raw_config.get("aws_access_key_id"),
        aws_secret_access_key=raw_config.get("aws_secret_access_key"),
        aws_session_token=raw_config.get("aws_session_token"),
        aws_role_arn=raw_config.get("aws_role_arn"),
        gcp_project=raw_config.get("gcp_project"),
        gcp_location=raw_config.get("gcp_location"),
        gcp_service_account_key_file=raw_config.get("gcp_service_account_key_file"),
        gcp_target_service_account=raw_config.get("gcp_target_service_account"),
        gateway_model=raw_config.get("gateway_model"),
    )


def resolve_mcp_gateway_settings(raw_config: dict) -> GatewaySettings:
    """Resolve a raw MCP gateway config dict into a GatewaySettings object.

    Merges per-gateway overrides with gateway_mode.mcp_defaults.

    Auth mode inference:
    - If ``auth_mode`` is explicitly set, use it as-is.
    - If ``auth_mode`` is absent but ``api_key`` is present,
      infer ``auth_mode = "api_key"``.
    - Otherwise default to ``"none"`` (no auth).

    Args:
        raw_config: A dict with keys like gateway_url, api_key,
            api_key_header, auth_mode, fail_open, timeout, retry (sub-dict),
            oauth2_token_url, oauth2_client_id, oauth2_client_secret,
            oauth2_scopes.

    Returns:
        A fully-resolved GatewaySettings object.

    Raises:
        ConfigurationError: If gateway_url is empty or auth_mode is invalid.
    """
    from .exceptions import ConfigurationError

    retry = raw_config.get("retry", {}) or {}

    # Validate gateway_url is non-empty
    gateway_url = raw_config.get("gateway_url", "")
    if not gateway_url or not isinstance(gateway_url, str) or not gateway_url.strip():
        raise ConfigurationError(
            "gateway_url is required and must be a non-empty string "
            "in MCP gateway configuration."
        )

    mcp_api_key = raw_config.get("api_key")
    mcp_api_key_header = raw_config.get("api_key_header") or "api-key"

    # Infer auth_mode for backward compatibility
    explicit_auth_mode = raw_config.get("auth_mode")
    if explicit_auth_mode is not None:
        auth_mode = explicit_auth_mode
    elif mcp_api_key:
        auth_mode = "api_key"
    else:
        auth_mode = "none"

    # Validate auth_mode
    if auth_mode not in VALID_AUTH_MODES:
        raise ConfigurationError(
            f"Invalid auth_mode: '{auth_mode}'. "
            f"Must be one of: {', '.join(sorted(VALID_AUTH_MODES))}"
        )

    return GatewaySettings(
        url=raw_config.get("gateway_url", ""),
        api_key=mcp_api_key,
        api_key_header=mcp_api_key_header,
        auth_mode=auth_mode,
        fail_open=raw_config.get("fail_open", _gw_mcp_fail_open),
        timeout=raw_config.get("timeout", _gw_mcp_timeout),
        retry_total=retry.get("total", _gw_mcp_retry_total),
        retry_backoff=retry.get("backoff_factor", _gw_mcp_retry_backoff),
        retry_status_codes=retry.get("status_codes", _gw_mcp_retry_status_codes),
        # OAuth2 Client Credentials fields
        oauth2_token_url=raw_config.get("oauth2_token_url"),
        oauth2_client_id=raw_config.get("oauth2_client_id"),
        oauth2_client_secret=raw_config.get("oauth2_client_secret"),
        oauth2_scopes=raw_config.get("oauth2_scopes"),
    )


# ===========================================================================
# set_state / reset
# ===========================================================================

# Known keys for defaults and retry sub-dicts (used for unknown-key warnings)
_KNOWN_DEFAULT_KEYS = {"fail_open", "timeout", "retry"}
_KNOWN_RETRY_KEYS = {"total", "backoff_factor", "status_codes"}


def _unpack_defaults(defaults_dict: Optional[dict], prefix: str = "") -> dict:
    """Unpack a defaults dict (llm_defaults or mcp_defaults) into flat keys.

    Returns dict with keys: fail_open, timeout, retry_total,
    retry_backoff, retry_status_codes (any of which may be absent).

    Also warns about unknown keys that may indicate typos.
    """
    if not defaults_dict:
        return {}

    # Warn about unknown top-level keys in the defaults dict
    for key in defaults_dict:
        if key not in _KNOWN_DEFAULT_KEYS:
            logger.warning(
                f"Unknown key '{key}' in {prefix or 'defaults'}. "
                f"Known keys: {', '.join(sorted(_KNOWN_DEFAULT_KEYS))}. "
                f"Check for typos."
            )

    result = {}
    if "fail_open" in defaults_dict:
        result["fail_open"] = defaults_dict["fail_open"]
    if "timeout" in defaults_dict:
        result["timeout"] = defaults_dict["timeout"]
    retry = defaults_dict.get("retry", {}) or {}

    # Warn about unknown keys in the retry sub-dict
    for key in retry:
        if key not in _KNOWN_RETRY_KEYS:
            retry_prefix = f"{prefix}.retry" if prefix else "retry"
            logger.warning(
                f"Unknown key '{key}' in {retry_prefix}. "
                f"Known keys: {', '.join(sorted(_KNOWN_RETRY_KEYS))}. "
                f"Check for typos."
            )

    if "total" in retry:
        result["retry_total"] = retry["total"]
    if "backoff_factor" in retry:
        result["retry_backoff"] = retry["backoff_factor"]
    if "status_codes" in retry:
        result["retry_status_codes"] = retry["status_codes"]
    return result


def _validate_defaults(prefix: str, unpacked: dict) -> None:
    """Validate unpacked defaults values for type and range.

    Args:
        prefix: Human-readable location for error messages
            (e.g., "gateway_mode.llm_defaults", "api_mode.mcp_defaults").
        unpacked: The dict produced by ``_unpack_defaults()``.

    Raises:
        ConfigurationError: If any value has the wrong type or is
            out of the allowed range.
    """
    from .exceptions import ConfigurationError

    # -- fail_open --
    if "fail_open" in unpacked:
        val = unpacked["fail_open"]
        if not isinstance(val, bool):
            raise ConfigurationError(
                f"Invalid {prefix}.fail_open: {val!r} (type {type(val).__name__}). "
                f"Must be a boolean (true/false)."
            )

    # -- timeout --
    if "timeout" in unpacked:
        val = unpacked["timeout"]
        if not isinstance(val, (int, float)):
            raise ConfigurationError(
                f"Invalid {prefix}.timeout: {val!r} (type {type(val).__name__}). "
                f"Must be a number (seconds)."
            )
        if val <= 0:
            raise ConfigurationError(
                f"Invalid {prefix}.timeout: {val}. Must be > 0."
            )
        if val > 3600:
            raise ConfigurationError(
                f"Invalid {prefix}.timeout: {val}. Must be <= 3600 (1 hour)."
            )

    # -- retry_total --
    if "retry_total" in unpacked:
        val = unpacked["retry_total"]
        if not isinstance(val, int) or isinstance(val, bool):
            raise ConfigurationError(
                f"Invalid {prefix}.retry.total: {val!r} (type {type(val).__name__}). "
                f"Must be an integer."
            )
        if val < 1:
            raise ConfigurationError(
                f"Invalid {prefix}.retry.total: {val}. Must be >= 1."
            )
        if val > 50:
            raise ConfigurationError(
                f"Invalid {prefix}.retry.total: {val}. Must be <= 50."
            )

    # -- retry_backoff --
    if "retry_backoff" in unpacked:
        val = unpacked["retry_backoff"]
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            raise ConfigurationError(
                f"Invalid {prefix}.retry.backoff_factor: {val!r} (type {type(val).__name__}). "
                f"Must be a number."
            )
        if val < 0:
            raise ConfigurationError(
                f"Invalid {prefix}.retry.backoff_factor: {val}. Must be >= 0."
            )

    # -- retry_status_codes --
    if "retry_status_codes" in unpacked:
        val = unpacked["retry_status_codes"]
        if not isinstance(val, list):
            raise ConfigurationError(
                f"Invalid {prefix}.retry.status_codes: {val!r} (type {type(val).__name__}). "
                f"Must be a list of HTTP status codes."
            )
        for i, code in enumerate(val):
            if not isinstance(code, int) or isinstance(code, bool):
                raise ConfigurationError(
                    f"Invalid {prefix}.retry.status_codes[{i}]: {code!r} "
                    f"(type {type(code).__name__}). Must be an integer."
                )
            if code < 100 or code > 599:
                raise ConfigurationError(
                    f"Invalid {prefix}.retry.status_codes[{i}]: {code}. "
                    f"Must be a valid HTTP status code (100-599)."
                )


def set_state(
    initialized: bool,
    *,
    # LLM rules / entity types
    llm_rules: Optional[List[Any]] = None,
    llm_entity_types: Optional[List[str]] = None,
    # Integration modes
    llm_integration_mode: str = "api",
    mcp_integration_mode: str = "api",
    # Gateway mode config (hierarchical dict from YAML / protect kwargs)
    gateway_mode: Optional[dict] = None,
    # API mode config (hierarchical dict from YAML / protect kwargs)
    api_mode: Optional[dict] = None,
    # Metadata
    metadata_user: Optional[str] = None,
    metadata_src_app: Optional[str] = None,
    metadata_client_transaction_id: Optional[str] = None,
    # Connection pool (global)
    pool_max_connections: Optional[int] = None,
    pool_max_keepalive: Optional[int] = None,
    # Logger
    log_file: Optional[str] = None,
    log_format: Optional[str] = None,
    custom_logger: Optional[Any] = None,
) -> None:
    """Set the global state from merged config.

    Args:
        initialized: Whether agentsec has been initialized.
        llm_rules: LLM rules for API mode inspection.
        llm_entity_types: LLM entity types for filtering.
        llm_integration_mode: Integration mode for LLM (api/gateway).
        mcp_integration_mode: Integration mode for MCP (api/gateway).
        gateway_mode: Dict with llm_defaults, mcp_defaults,
            llm_gateways, mcp_gateways.
        api_mode: Dict with llm_defaults, mcp_defaults, llm, mcp.
        metadata_user: Default metadata user.
        metadata_src_app: Default metadata source application.
        metadata_client_transaction_id: Default metadata client transaction ID.
        pool_max_connections: Pool max connections.
        pool_max_keepalive: Pool max keepalive connections.
        log_file: Log file path.
        log_format: Log format ('text' or 'json').
        custom_logger: Custom logger instance.

    Raises:
        ConfigurationError: If any configuration value is invalid.
    """
    from .exceptions import ConfigurationError

    # Input validation
    if llm_integration_mode not in VALID_INTEGRATION_MODES:
        raise ConfigurationError(
            f"Invalid llm_integration_mode: '{llm_integration_mode}'. "
            f"Must be one of: {', '.join(VALID_INTEGRATION_MODES)}"
        )
    if mcp_integration_mode not in VALID_INTEGRATION_MODES:
        raise ConfigurationError(
            f"Invalid mcp_integration_mode: '{mcp_integration_mode}'. "
            f"Must be one of: {', '.join(VALID_INTEGRATION_MODES)}"
        )

    # Validate pool settings
    if pool_max_connections is not None and pool_max_connections < 1:
        raise ConfigurationError(
            f"Invalid pool_max_connections: {pool_max_connections}. Must be >= 1"
        )
    if pool_max_keepalive is not None and pool_max_keepalive < 0:
        raise ConfigurationError(
            f"Invalid pool_max_keepalive: {pool_max_keepalive}. Must be >= 0"
        )

    # Validate log_format if provided
    if log_format is not None and log_format.lower() not in VALID_LOG_FORMATS:
        raise ConfigurationError(
            f"Invalid logging.format: '{log_format}'. "
            f"Must be one of: {', '.join(sorted(VALID_LOG_FORMATS))}"
        )

    # Unpack gateway_mode dict
    gw = gateway_mode or {}
    gw_llm_mode_val = gw.get("llm_mode", "on")
    gw_mcp_mode_val = gw.get("mcp_mode", "on")

    # Normalise YAML boolean → string.
    # PyYAML (YAML 1.1) parses "on"/"off"/"yes"/"no" as Python booleans.
    # Map True → "on", False → "off" so users can write `llm_mode: on`
    # without quoting.
    _BOOL_TO_GW_MODE = {True: "on", False: "off"}
    if isinstance(gw_llm_mode_val, bool):
        gw_llm_mode_val = _BOOL_TO_GW_MODE[gw_llm_mode_val]
    if isinstance(gw_mcp_mode_val, bool):
        gw_mcp_mode_val = _BOOL_TO_GW_MODE[gw_mcp_mode_val]

    if gw_llm_mode_val not in VALID_GATEWAY_MODES:
        raise ConfigurationError(
            f"Invalid gateway_mode.llm_mode: '{gw_llm_mode_val}'. "
            f"Must be one of: {', '.join(sorted(VALID_GATEWAY_MODES))}"
        )
    if gw_mcp_mode_val not in VALID_GATEWAY_MODES:
        raise ConfigurationError(
            f"Invalid gateway_mode.mcp_mode: '{gw_mcp_mode_val}'. "
            f"Must be one of: {', '.join(sorted(VALID_GATEWAY_MODES))}"
        )
    gw_llm_defs = _unpack_defaults(gw.get("llm_defaults"), prefix="gateway_mode.llm_defaults")
    gw_mcp_defs = _unpack_defaults(gw.get("mcp_defaults"), prefix="gateway_mode.mcp_defaults")
    _validate_defaults("gateway_mode.llm_defaults", gw_llm_defs)
    _validate_defaults("gateway_mode.mcp_defaults", gw_mcp_defs)
    llm_gateways_dict = gw.get("llm_gateways") or {}
    mcp_gateways_dict = gw.get("mcp_gateways") or {}

    # Build provider-default index from llm_gateways entries with default: true
    provider_defaults: Dict[str, dict] = {}
    for _gw_name, _gw_cfg in llm_gateways_dict.items():
        if isinstance(_gw_cfg, dict):
            # Validate provider if present
            _gw_provider = _gw_cfg.get("provider")
            if _gw_provider is not None and _gw_provider not in SUPPORTED_PROVIDERS:
                raise ConfigurationError(
                    f"Invalid provider '{_gw_provider}' in gateway '{_gw_name}'. "
                    f"Must be one of: {', '.join(SUPPORTED_PROVIDERS)}"
                )
            if _gw_cfg.get("default") and _gw_provider:
                provider_defaults[_gw_provider] = _gw_cfg

    # Unpack api_mode dict
    am = api_mode or {}
    api_llm_defs = _unpack_defaults(am.get("llm_defaults"), prefix="api_mode.llm_defaults")
    api_mcp_defs = _unpack_defaults(am.get("mcp_defaults"), prefix="api_mode.mcp_defaults")
    _validate_defaults("api_mode.llm_defaults", api_llm_defs)
    _validate_defaults("api_mode.mcp_defaults", api_mcp_defs)

    _raw_llm = am.get("llm")
    if _raw_llm is not None and not isinstance(_raw_llm, dict):
        raise ConfigurationError(
            f"api_mode.llm must be a dict with keys like 'mode', 'endpoint', 'api_key'; "
            f"got {type(_raw_llm).__name__}: {_raw_llm!r}"
        )
    _raw_mcp = am.get("mcp")
    if _raw_mcp is not None and not isinstance(_raw_mcp, dict):
        raise ConfigurationError(
            f"api_mode.mcp must be a dict with keys like 'mode', 'endpoint', 'api_key'; "
            f"got {type(_raw_mcp).__name__}: {_raw_mcp!r}"
        )
    api_llm_cfg = _raw_llm or {}
    api_mcp_cfg = _raw_mcp or {}

    # Validate API modes if provided
    api_mode_llm_val = api_llm_cfg.get("mode")
    api_mode_mcp_val = api_mcp_cfg.get("mode")
    if api_mode_llm_val is not None and api_mode_llm_val not in VALID_API_MODES:
        raise ConfigurationError(
            f"Invalid api_mode.llm.mode: '{api_mode_llm_val}'. "
            f"Must be one of: {', '.join(VALID_API_MODES)}"
        )
    if api_mode_mcp_val is not None and api_mode_mcp_val not in VALID_API_MODES:
        raise ConfigurationError(
            f"Invalid api_mode.mcp.mode: '{api_mode_mcp_val}'. "
            f"Must be one of: {', '.join(VALID_API_MODES)}"
        )

    # Globals
    global _initialized, _llm_rules, _llm_entity_types
    global _llm_integration_mode, _mcp_integration_mode
    global _api_mode_llm, _api_mode_mcp
    global _api_mode_llm_endpoint, _api_mode_llm_api_key
    global _api_mode_mcp_endpoint, _api_mode_mcp_api_key
    global _metadata_user, _metadata_src_app, _metadata_client_transaction_id
    global _pool_max_connections, _pool_max_keepalive
    global _log_file, _log_format, _custom_logger
    # Gateway mode on/off and defaults
    global _gw_llm_mode, _gw_mcp_mode
    global _gw_llm_fail_open, _gw_llm_timeout
    global _gw_llm_retry_total, _gw_llm_retry_backoff, _gw_llm_retry_status_codes
    global _gw_mcp_fail_open, _gw_mcp_timeout
    global _gw_mcp_retry_total, _gw_mcp_retry_backoff, _gw_mcp_retry_status_codes
    global _llm_gateways, _provider_default_gateways, _mcp_gateway_map
    # API mode per-category defaults
    global _api_llm_fail_open, _api_llm_timeout
    global _api_llm_retry_total, _api_llm_retry_backoff, _api_llm_retry_status_codes
    global _api_mcp_fail_open, _api_mcp_timeout
    global _api_mcp_retry_total, _api_mcp_retry_backoff, _api_mcp_retry_status_codes

    with _state_lock:
        _initialized = initialized
        _llm_rules = llm_rules
        _llm_entity_types = llm_entity_types
        _llm_integration_mode = llm_integration_mode
        _mcp_integration_mode = mcp_integration_mode

        # API mode config (mode strings, endpoints, keys)
        _api_mode_llm = api_mode_llm_val
        _api_mode_mcp = api_mode_mcp_val
        _api_mode_llm_endpoint = api_llm_cfg.get("endpoint")
        _api_mode_llm_api_key = api_llm_cfg.get("api_key")
        _api_mode_mcp_endpoint = api_mcp_cfg.get("endpoint")
        _api_mode_mcp_api_key = api_mcp_cfg.get("api_key")

        # Metadata
        _metadata_user = metadata_user
        _metadata_src_app = metadata_src_app
        _metadata_client_transaction_id = metadata_client_transaction_id

        # Pool (global)
        _pool_max_connections = pool_max_connections
        _pool_max_keepalive = pool_max_keepalive

        # Logger
        _log_file = log_file
        _log_format = log_format
        _custom_logger = custom_logger

        # Gateway mode: on/off switches
        _gw_llm_mode = gw_llm_mode_val
        _gw_mcp_mode = gw_mcp_mode_val

        # Gateway mode: LLM defaults
        _gw_llm_fail_open = gw_llm_defs.get("fail_open", True)
        _gw_llm_timeout = gw_llm_defs.get("timeout", 60)
        _gw_llm_retry_total = gw_llm_defs.get("retry_total", 3)
        _gw_llm_retry_backoff = gw_llm_defs.get("retry_backoff", 0.5)
        _gw_llm_retry_status_codes = gw_llm_defs.get(
            "retry_status_codes", [429, 500, 502, 503, 504]
        )

        # Gateway mode: MCP defaults
        _gw_mcp_fail_open = gw_mcp_defs.get("fail_open", True)
        _gw_mcp_timeout = gw_mcp_defs.get("timeout", 10)
        _gw_mcp_retry_total = gw_mcp_defs.get("retry_total", 2)
        _gw_mcp_retry_backoff = gw_mcp_defs.get("retry_backoff", 1.0)
        _gw_mcp_retry_status_codes = gw_mcp_defs.get(
            "retry_status_codes", [429, 500, 502, 503, 504]
        )

        # Gateway mode: named gateways, provider-default index, MCP map
        _llm_gateways = dict(llm_gateways_dict)
        _provider_default_gateways = dict(provider_defaults)
        _mcp_gateway_map = dict(mcp_gateways_dict)

        # API mode: LLM defaults
        _api_llm_fail_open = api_llm_defs.get("fail_open", False)
        _api_llm_timeout = api_llm_defs.get("timeout", 5)
        _api_llm_retry_total = api_llm_defs.get("retry_total", 2)
        _api_llm_retry_backoff = api_llm_defs.get("retry_backoff", 0.5)
        _api_llm_retry_status_codes = api_llm_defs.get(
            "retry_status_codes", [429, 500, 502, 503, 504]
        )

        # API mode: MCP defaults
        _api_mcp_fail_open = api_mcp_defs.get("fail_open", True)
        _api_mcp_timeout = api_mcp_defs.get("timeout", 5)
        _api_mcp_retry_total = api_mcp_defs.get("retry_total", 2)
        _api_mcp_retry_backoff = api_mcp_defs.get("retry_backoff", 0.5)
        _api_mcp_retry_status_codes = api_mcp_defs.get(
            "retry_status_codes", [429, 500, 502, 503, 504]
        )

        # Note: _llm_rules and _llm_entity_types are set from the
        # llm_rules / llm_entity_types parameters above (lines 767-768).
        # The caller (protect()) already extracts these from
        # api_mode["llm"], so there is no need to re-extract here.


def reset() -> None:
    """Reset global state to defaults. Useful for testing."""
    global _initialized, _llm_rules, _llm_entity_types
    global _llm_integration_mode, _mcp_integration_mode
    global _api_mode_llm, _api_mode_mcp
    global _api_mode_llm_endpoint, _api_mode_llm_api_key
    global _api_mode_mcp_endpoint, _api_mode_mcp_api_key
    global _metadata_user, _metadata_src_app, _metadata_client_transaction_id
    global _pool_max_connections, _pool_max_keepalive
    global _log_file, _log_format, _custom_logger
    global _gw_llm_mode, _gw_mcp_mode
    global _gw_llm_fail_open, _gw_llm_timeout
    global _gw_llm_retry_total, _gw_llm_retry_backoff, _gw_llm_retry_status_codes
    global _gw_mcp_fail_open, _gw_mcp_timeout
    global _gw_mcp_retry_total, _gw_mcp_retry_backoff, _gw_mcp_retry_status_codes
    global _llm_gateways, _provider_default_gateways, _mcp_gateway_map
    global _api_llm_fail_open, _api_llm_timeout
    global _api_llm_retry_total, _api_llm_retry_backoff, _api_llm_retry_status_codes
    global _api_mcp_fail_open, _api_mcp_timeout
    global _api_mcp_retry_total, _api_mcp_retry_backoff, _api_mcp_retry_status_codes
    global _on_violation

    with _state_lock:
        _initialized = False
        _llm_rules = None
        _llm_entity_types = None
        _llm_integration_mode = "api"
        _mcp_integration_mode = "api"
        _api_mode_llm = None
        _api_mode_mcp = None
        _api_mode_llm_endpoint = None
        _api_mode_llm_api_key = None
        _api_mode_mcp_endpoint = None
        _api_mode_mcp_api_key = None
        _metadata_user = None
        _metadata_src_app = None
        _metadata_client_transaction_id = None
        _pool_max_connections = None
        _pool_max_keepalive = None
        _log_file = None
        _log_format = None
        _custom_logger = None

        # Gateway mode on/off
        _gw_llm_mode = "on"
        _gw_mcp_mode = "on"

        # Gateway mode defaults
        _gw_llm_fail_open = True
        _gw_llm_timeout = 60
        _gw_llm_retry_total = 3
        _gw_llm_retry_backoff = 0.5
        _gw_llm_retry_status_codes = [429, 500, 502, 503, 504]
        _gw_mcp_fail_open = True
        _gw_mcp_timeout = 10
        _gw_mcp_retry_total = 2
        _gw_mcp_retry_backoff = 1.0
        _gw_mcp_retry_status_codes = [429, 500, 502, 503, 504]

        # Gateway mode: named gateways, provider-default index, MCP map
        _llm_gateways = {}
        _provider_default_gateways = {}
        _mcp_gateway_map = {}

        # API mode per-category defaults
        _api_llm_fail_open = False
        _api_llm_timeout = 5
        _api_llm_retry_total = 2
        _api_llm_retry_backoff = 0.5
        _api_llm_retry_status_codes = [429, 500, 502, 503, 504]
        _api_mcp_fail_open = True
        _api_mcp_timeout = 5
        _api_mcp_retry_total = 2
        _api_mcp_retry_backoff = 0.5
        _api_mcp_retry_status_codes = [429, 500, 502, 503, 504]

        _on_violation = None

    # Clear cached inspector singletons so re-protect() creates fresh ones
    from .patchers import reset_all_patcher_inspectors
    reset_all_patcher_inspectors()
