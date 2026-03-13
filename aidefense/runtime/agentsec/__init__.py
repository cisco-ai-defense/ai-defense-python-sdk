"""
agentsec - Agent Runtime Security Sensor SDK

Provides runtime security enforcement and monitoring for LLM and MCP
interactions with minimal integration effort.

Usage (Simple - with YAML config):
    from aidefense.runtime import agentsec
    agentsec.protect(config="agentsec.yaml")

    from openai import OpenAI   # order doesn't matter; wrapt patches at class level
    client = OpenAI()

Usage (Programmatic):
    from aidefense.runtime import agentsec
    agentsec.protect(
        api_mode={
            "llm": {"mode": "monitor", "endpoint": "...", "api_key": "..."},
        },
    )

Usage (Named gateways):
    from aidefense.runtime import agentsec
    agentsec.protect(config="agentsec.yaml")

    with agentsec.gateway("math-gateway"):
        response = client.chat.completions.create(...)

For more information, see:
https://developer.cisco.com/docs/ai-defense/overview/
"""

import copy
import logging
import os
import sys
import threading
from typing import Any, Callable, Dict, List, Optional

from . import _state
from .decision import Decision
from .exceptions import (
    AgentsecError,
    ConfigurationError,
    ValidationError,
    InspectionTimeoutError,
    InspectionNetworkError,
    SecurityPolicyError,
)
from ._logging import setup_logging
from ._context import (
    skip_inspection,
    no_inspection,
    set_metadata,
    gateway,
    use_gateway,
    get_inspection_context,
    InspectionContext,
)

# Lock for thread-safe initialization of protect()
_protect_lock = threading.Lock()

__all__ = [
    "protect",
    "get_patched_clients",
    "set_metadata",
    "get_inspection_context",
    "InspectionContext",
    "Decision",
    # Exceptions
    "AgentsecError",
    "ConfigurationError",
    "ValidationError",
    "InspectionTimeoutError",
    "InspectionNetworkError",
    "SecurityPolicyError",
    # Context managers / decorators
    "skip_inspection",
    "no_inspection",
    "gateway",
    "use_gateway",
]

__version__ = "0.1.0"

# Logger - use the centralized logging module
logger = logging.getLogger("aidefense.runtime.agentsec")


def _auto_load_dotenv() -> bool:
    """Automatically load .env file if python-dotenv is installed.

    Searches for .env starting from the current working directory (usecwd=True).

    Returns:
        True if .env was loaded, False otherwise.
    """
    try:
        from dotenv import load_dotenv, find_dotenv

        dotenv_path = find_dotenv(usecwd=True)
        if dotenv_path:
            load_dotenv(dotenv_path)
            logger.debug(f"Auto-loaded .env file: {dotenv_path}")
        else:
            load_dotenv()
            logger.debug("No .env file found in current directory")
        return True
    except ImportError:
        logger.debug("python-dotenv not installed, skipping .env auto-load")
        return False


def _apply_patches(api_mode_llm: Optional[str], api_mode_mcp: Optional[str]) -> None:
    """Apply client patches based on the effective mode for each integration path.

    For each category (LLM / MCP), patching is applied when:
    - Gateway integration is active AND gateway mode is "on", OR
    - API integration is active AND api_mode is not "off".
    """
    from .patchers import (
        patch_openai,
        patch_bedrock,
        patch_mcp,
        patch_vertexai,
        patch_google_genai,
        patch_cohere,
        patch_mistral,
        patch_litellm,
        patch_azure_ai_inference,
    )

    llm_integration = _state.get_llm_integration_mode()
    mcp_integration = _state.get_mcp_integration_mode()

    # Determine if LLM patching is needed (None means not configured → off)
    llm_active = (
        (llm_integration == "gateway" and _state.get_gw_llm_mode() != "off")
        or (llm_integration == "api" and api_mode_llm is not None and api_mode_llm != "off")
    )
    if llm_active:
        patch_openai()
        patch_bedrock()
        patch_vertexai()
        patch_google_genai()
        patch_cohere()
        patch_mistral()
        patch_litellm()
        patch_azure_ai_inference()

    # Determine if MCP patching is needed (None means not configured → off)
    mcp_active = (
        (mcp_integration == "gateway" and _state.get_gw_mcp_mode() != "off")
        or (mcp_integration == "api" and api_mode_mcp is not None and api_mode_mcp != "off")
    )
    if mcp_active:
        patch_mcp()


def get_patched_clients() -> List[str]:
    """Get list of successfully patched clients.

    Returns:
        List of client names that have been patched.
    """
    from .patchers import get_patched_clients as _get_patched

    return _get_patched()


# =========================================================================
# Deep merge utility
# =========================================================================

def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively deep-merge *override* into *base*.

    - Leaf values from *override* replace *base* values.
    - ``None`` values in *override* are **skipped** (base value preserved).
    - Nested dicts are merged recursively.

    Returns a **new** dict (neither *base* nor *override* is mutated).
    """
    result = copy.deepcopy(base)
    for key, val in override.items():
        if val is None:
            continue
        if isinstance(val, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = copy.deepcopy(val)
    return result


# =========================================================================
# Eager input validation (runs before idempotency check)
# =========================================================================

_VALID_LOG_FORMATS = {"text", "json"}


def _validate_protect_args(
    *,
    config: Optional[str] = None,
    log_format: Optional[str] = None,
) -> None:
    """Validate protect() arguments that should always be checked.

    These validations run before the idempotency guard so that
    misconfigurations are surfaced even on repeated protect() calls.

    Only structural checks are performed here (file existence, YAML
    syntax, root type, log_format value).  Full env-var substitution
    is deferred to ``_protect_impl`` after ``.env`` has been loaded.

    Raises:
        FileNotFoundError: If config path does not exist on disk.
        ConfigurationError: If config file has invalid YAML or structure.
        ValueError: If log_format is not a supported value.
    """
    if config is not None:
        import os

        if not os.path.isfile(config):
            raise FileNotFoundError(
                f"Configuration file not found: {config}"
            )

        import yaml

        try:
            with open(config, "r") as f:
                raw = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigurationError(
                f"Invalid YAML in configuration file {config}: {e}"
            )
        if raw is not None and not isinstance(raw, dict):
            raise ConfigurationError(
                f"Configuration file {config} must contain a YAML mapping, "
                f"got {type(raw).__name__}"
            )

    if log_format is not None and log_format.lower() not in _VALID_LOG_FORMATS:
        raise ValueError(
            f"Invalid log_format: '{log_format}'. "
            f"Must be one of: {', '.join(sorted(_VALID_LOG_FORMATS))}"
        )


def _validate_gateway_entries(
    llm_integration_mode: str,
    mcp_integration_mode: str,
    gateway_mode: dict,
) -> None:
    """Validate gateway entries at init time.

    Checks that every gateway declared in ``llm_gateways`` or
    ``mcp_gateways`` has a non-empty ``gateway_url`` and, if
    ``auth_mode`` is specified, that it is one of the recognized values.

    Raises:
        ConfigurationError: On missing ``gateway_url`` or invalid ``auth_mode``.
    """
    from ._state import VALID_AUTH_MODES

    llm_gateways = gateway_mode.get("llm_gateways") or {}
    mcp_gateways = gateway_mode.get("mcp_gateways") or {}

    if llm_integration_mode == "gateway":
        for gw_name, gw_cfg in llm_gateways.items():
            if not isinstance(gw_cfg, dict):
                raise ConfigurationError(
                    f"gateway_mode.llm_gateways.{gw_name}: "
                    f"expected a mapping (dict), got {type(gw_cfg).__name__}"
                )
            gw_url = gw_cfg.get("gateway_url", "")
            if not gw_url or not isinstance(gw_url, str) or not gw_url.strip():
                raise ConfigurationError(
                    f"gateway_mode.llm_gateways.{gw_name}: "
                    f"gateway_url is required and must be a non-empty string"
                )
            auth = gw_cfg.get("auth_mode")
            if auth is not None and auth not in VALID_AUTH_MODES:
                raise ConfigurationError(
                    f"gateway_mode.llm_gateways.{gw_name}: "
                    f"invalid auth_mode '{auth}'. "
                    f"Must be one of: {', '.join(sorted(VALID_AUTH_MODES))}"
                )

    if mcp_integration_mode == "gateway":
        for gw_name, gw_cfg in mcp_gateways.items():
            if not isinstance(gw_cfg, dict):
                raise ConfigurationError(
                    f"gateway_mode.mcp_gateways.{gw_name}: "
                    f"expected a mapping (dict), got {type(gw_cfg).__name__}"
                )
            gw_url = gw_cfg.get("gateway_url", "")
            if not gw_url or not isinstance(gw_url, str) or not gw_url.strip():
                raise ConfigurationError(
                    f"gateway_mode.mcp_gateways.{gw_name}: "
                    f"gateway_url is required and must be a non-empty string"
                )
            auth = gw_cfg.get("auth_mode")
            if auth is not None and auth not in VALID_AUTH_MODES:
                raise ConfigurationError(
                    f"gateway_mode.mcp_gateways.{gw_name}: "
                    f"invalid auth_mode '{auth}'. "
                    f"Must be one of: {', '.join(sorted(VALID_AUTH_MODES))}"
                )


# =========================================================================
# protect() — public API
# =========================================================================

def protect(
    patch_clients: bool = True,
    *,
    enabled: Optional[bool] = None,
    auto_dotenv: bool = True,
    config: Optional[str] = None,
    llm_integration_mode: Optional[str] = None,
    mcp_integration_mode: Optional[str] = None,
    gateway_mode: Optional[dict] = None,
    api_mode: Optional[dict] = None,
    on_violation: Optional[Callable[["Decision"], None]] = None,
    pool_max_connections: Optional[int] = None,
    pool_max_keepalive: Optional[int] = None,
    custom_logger: Optional[logging.Logger] = None,
    log_file: Optional[str] = None,
    log_format: Optional[str] = None,
) -> None:
    """Enable agentsec protection for LLM and MCP interactions.

    This is the main entry point for agentsec. It is recommended to call
    this at the top of your application before creating LLM clients,
    though ``wrapt``-based patching works regardless of import order for
    standard usage patterns.

    Minimal usage (no config)::

        import agentsec
        agentsec.protect()

    YAML config::

        import agentsec
        agentsec.protect(config="agentsec.yaml")

    Programmatic::

        import agentsec
        agentsec.protect(
            api_mode={
                "llm": {"mode": "monitor", "endpoint": "...", "api_key": "..."},
            },
        )

    Monitor-mode callback::

        agentsec.protect(
            api_mode={"llm": {"mode": "monitor", ...}},
            on_violation=lambda decision: print(f"Flagged: {decision}"),
        )

    Disable agentsec (env var or parameter)::

        # Via env var:  AGENTSEC_DISABLED=true python app.py
        # Via parameter:
        agentsec.protect(enabled=False)

    This function is idempotent — calling it multiple times has no
    effect after the first successful call.

    Args:
        patch_clients: Whether to auto-patch LLM clients.
        enabled: Explicitly enable/disable agentsec. When ``False``,
            ``protect()`` returns immediately without patching.
            Also honours the ``AGENTSEC_DISABLED`` env var (``true``/``1``)
            and the ``enabled`` key in YAML config.
        auto_dotenv: Load .env before YAML parsing so ``${VAR}``
            references can resolve.
        config: Path to an ``agentsec.yaml`` configuration file.
        llm_integration_mode: ``"api"`` or ``"gateway"``.
        mcp_integration_mode: ``"api"`` or ``"gateway"``.
        gateway_mode: Dict matching the ``gateway_mode`` section in YAML
            (llm_defaults, mcp_defaults, llm_gateways, mcp_gateways).
        api_mode: Dict matching the ``api_mode`` section in YAML
            (llm_defaults, mcp_defaults, llm, mcp).
        on_violation: Optional callback invoked when a block decision
            is issued in monitor mode. Receives the ``Decision`` object.
        pool_max_connections: Max HTTP connections (global).
        pool_max_keepalive: Max keepalive connections (global).
        custom_logger: Custom ``logging.Logger`` instance.
        log_file: Log file path.
        log_format: ``"text"`` or ``"json"``.

    Raises:
        FileNotFoundError: If config file path does not exist.
        ConfigurationError: If config file contains invalid YAML,
            wrong root type, or invalid values.
        ValueError: If log_format is not a supported value.
    """
    # Check AGENTSEC_DISABLED env var
    if enabled is None:
        env_disabled = os.environ.get("AGENTSEC_DISABLED", "").lower()
        if env_disabled in ("true", "1", "yes"):
            logger.info("agentsec disabled via AGENTSEC_DISABLED env var")
            return

    if enabled is False:
        logger.info("agentsec disabled via enabled=False parameter")
        return
    # Validate inputs eagerly — these checks run even if protect() was
    # already called, so misconfigurations are never silently accepted.
    _validate_protect_args(config=config, log_format=log_format)

    # Idempotency check
    if _state.is_initialized():
        logger.debug("agentsec already initialized, skipping")
        return

    with _protect_lock:
        # Double-check after acquiring lock
        if _state.is_initialized():
            logger.debug("agentsec already initialized (after lock), skipping")
            return

        _protect_impl(
            patch_clients=patch_clients,
            auto_dotenv=auto_dotenv,
            config=config,
            llm_integration_mode=llm_integration_mode,
            mcp_integration_mode=mcp_integration_mode,
            gateway_mode=gateway_mode,
            api_mode=api_mode,
            on_violation=on_violation,
            pool_max_connections=pool_max_connections,
            pool_max_keepalive=pool_max_keepalive,
            custom_logger=custom_logger,
            log_file=log_file,
            log_format=log_format,
        )


def _protect_impl(
    patch_clients: bool,
    auto_dotenv: bool,
    config: Optional[str],
    llm_integration_mode: Optional[str],
    mcp_integration_mode: Optional[str],
    gateway_mode: Optional[dict],
    api_mode: Optional[dict],
    on_violation: Optional[Callable[["Decision"], None]],
    pool_max_connections: Optional[int],
    pool_max_keepalive: Optional[int],
    custom_logger: Optional[logging.Logger],
    log_file: Optional[str],
    log_format: Optional[str],
) -> None:
    """Internal implementation of protect(), called under lock."""

    # Step 1: Load .env so ${VAR} substitution can resolve in YAML
    if auto_dotenv:
        _auto_load_dotenv()

    # Step 2: Build merged config: hardcoded defaults -> YAML -> kwargs
    merged: Dict[str, Any] = {}

    if config is not None:
        from .config_file import load_config_file

        merged = load_config_file(config)

    # Overlay protect() kwargs (non-None only) via deep merge
    kwargs_overlay: Dict[str, Any] = {}
    if llm_integration_mode is not None:
        kwargs_overlay["llm_integration_mode"] = llm_integration_mode
    if mcp_integration_mode is not None:
        kwargs_overlay["mcp_integration_mode"] = mcp_integration_mode
    if gateway_mode is not None:
        kwargs_overlay["gateway_mode"] = gateway_mode
    if api_mode is not None:
        kwargs_overlay["api_mode"] = api_mode

    if kwargs_overlay:
        merged = _deep_merge(merged, kwargs_overlay)

    # Step 2b: Check YAML-level 'enabled' key
    if merged.get("enabled") is False:
        logger.info("agentsec disabled via 'enabled: false' in config")
        return

    # Step 3: Extract final values
    final_llm_integration = merged.get("llm_integration_mode", "api")
    final_mcp_integration = merged.get("mcp_integration_mode", "api")
    final_gateway_mode = merged.get("gateway_mode") or {}
    final_api_mode = merged.get("api_mode") or {}

    # Validate api_mode.llm / api_mode.mcp are dicts if present
    from .exceptions import ConfigurationError as _CfgErr

    _raw_llm = final_api_mode.get("llm")
    if _raw_llm is not None and not isinstance(_raw_llm, dict):
        raise _CfgErr(
            f"api_mode.llm must be a dict with keys like 'mode', 'endpoint', 'api_key'; "
            f"got {type(_raw_llm).__name__}: {_raw_llm!r}"
        )
    _raw_mcp = final_api_mode.get("mcp")
    if _raw_mcp is not None and not isinstance(_raw_mcp, dict):
        raise _CfgErr(
            f"api_mode.mcp must be a dict with keys like 'mode', 'endpoint', 'api_key'; "
            f"got {type(_raw_mcp).__name__}: {_raw_mcp!r}"
        )

    # Extract API mode strings for patching decisions
    api_llm_cfg = _raw_llm or {}
    api_mcp_cfg = _raw_mcp or {}
    api_mode_llm_str = api_llm_cfg.get("mode")
    api_mode_mcp_str = api_mcp_cfg.get("mode")

    # Validate known keys in api_mode.llm / api_mode.mcp to catch typos
    _KNOWN_API_MODE_KEYS = {
        "mode", "endpoint", "api_key", "fail_open",
        "rules", "entity_types", "timeout_ms",
        "retry_total", "retry_backoff", "retry_status_codes",
        "pool_max_connections", "pool_max_keepalive",
    }
    for section_name, section_cfg in [("api_mode.llm", api_llm_cfg), ("api_mode.mcp", api_mcp_cfg)]:
        unknown = set(section_cfg.keys()) - _KNOWN_API_MODE_KEYS
        if unknown:
            import difflib
            for key in sorted(unknown):
                close = difflib.get_close_matches(key, _KNOWN_API_MODE_KEYS, n=1, cutoff=0.6)
                hint = f" Did you mean '{close[0]}'?" if close else ""
                logger.warning(f"Unknown key '{key}' in {section_name}.{hint}")

    # Extract logging config from YAML
    logging_cfg = merged.get("logging") or {}
    final_log_file = log_file or logging_cfg.get("file")
    final_log_format = log_format or logging_cfg.get("format")
    log_level = logging_cfg.get("level")

    # Step 4: Setup logging
    setup_logging(
        level=log_level,
        format_type=final_log_format,
        log_file=final_log_file,
        custom_logger=custom_logger,
    )

    # Step 5: Resolve pool settings (kwargs > YAML > None)
    yaml_pool_max_conn = merged.get("pool_max_connections")
    yaml_pool_max_keep = merged.get("pool_max_keepalive")
    final_pool_max_connections = pool_max_connections
    if final_pool_max_connections is None and yaml_pool_max_conn is not None:
        try:
            final_pool_max_connections = int(yaml_pool_max_conn)
        except (ValueError, TypeError):
            raise ConfigurationError(
                f"Invalid pool_max_connections: {yaml_pool_max_conn!r}. "
                f"Must be an integer >= 1."
            )
    if final_pool_max_connections is not None and final_pool_max_connections < 1:
        raise ConfigurationError(
            f"Invalid pool_max_connections: {final_pool_max_connections}. "
            f"Must be an integer >= 1."
        )
    final_pool_max_keepalive = pool_max_keepalive
    if final_pool_max_keepalive is None and yaml_pool_max_keep is not None:
        try:
            final_pool_max_keepalive = int(yaml_pool_max_keep)
        except (ValueError, TypeError):
            raise ConfigurationError(
                f"Invalid pool_max_keepalive: {yaml_pool_max_keep!r}. "
                f"Must be an integer >= 1."
            )
    if final_pool_max_keepalive is not None and final_pool_max_keepalive < 1:
        raise ConfigurationError(
            f"Invalid pool_max_keepalive: {final_pool_max_keepalive}. "
            f"Must be an integer >= 1."
        )

    # Step 5b: Validate gateway entries early so misconfigurations
    # surface at protect() time rather than on the first LLM/MCP call.
    _validate_gateway_entries(
        final_llm_integration,
        final_mcp_integration,
        final_gateway_mode,
    )

    # Step 5c: Store on_violation callback in state
    if on_violation is not None:
        _state.set_on_violation(on_violation)

    # Step 5d: Log info if LLM clients were already imported
    _already_imported = [
        name for name in ("openai", "anthropic", "cohere", "mistralai", "google.generativeai", "boto3")
        if name in sys.modules
    ]
    if _already_imported:
        logger.info(
            f"LLM client libraries already imported: {_already_imported}. "
            f"This is fine — wrapt patches at the class level."
        )

    # Step 6: Store state BEFORE patching
    _state.set_state(
        initialized=True,
        llm_rules=api_llm_cfg.get("rules"),
        llm_entity_types=api_llm_cfg.get("entity_types"),
        llm_integration_mode=final_llm_integration,
        mcp_integration_mode=final_mcp_integration,
        gateway_mode=final_gateway_mode,
        api_mode=final_api_mode,
        pool_max_connections=final_pool_max_connections,
        pool_max_keepalive=final_pool_max_keepalive,
        log_file=final_log_file,
        log_format=final_log_format,
        custom_logger=custom_logger,
    )

    # Step 7: Apply client patches
    patched: List[str] = []
    if patch_clients:
        logger.debug("Applying client patches...")
        _apply_patches(api_mode_llm_str, api_mode_mcp_str)
        patched = get_patched_clients()

    # Step 8: Log initialization summary
    gw_llm_mode = final_gateway_mode.get("llm_mode", "on")
    gw_mcp_mode = final_gateway_mode.get("mcp_mode", "on")

    # Build display strings per integration path
    if final_llm_integration == "gateway":
        llm_display = f"gateway ({gw_llm_mode})"
    else:
        llm_display = api_mode_llm_str or "not configured"

    if final_mcp_integration == "gateway":
        mcp_display = f"gateway ({gw_mcp_mode})"
    else:
        mcp_display = api_mode_mcp_str or "not configured"

    logger.info(
        f"[agentsec] LLM: {llm_display} | MCP: {mcp_display} "
        f"| Patched: {patched}"
    )
    logger.info(
        f"agentsec initialized: llm={llm_display}, mcp={mcp_display}, "
        f"llm_integration={final_llm_integration}, "
        f"mcp_integration={final_mcp_integration}"
    )
