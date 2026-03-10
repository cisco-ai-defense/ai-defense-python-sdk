"""YAML configuration file loader for agentsec.

Loads an agentsec.yaml configuration file and performs ${ENV_VAR}
substitution for secret values. Environment variables must already be
set (e.g., via python-dotenv loading a .env file) before calling
load_config_file().
"""

import logging
import os
import re
from typing import Any

import yaml

from .exceptions import ConfigurationError

logger = logging.getLogger("aidefense.runtime.agentsec.config_file")

# Pattern to match ${VAR_NAME} placeholders
_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")

# Known top-level keys in agentsec.yaml
_KNOWN_TOP_KEYS = {
    "llm_integration_mode",
    "mcp_integration_mode",
    "gateway_mode",
    "api_mode",
    "logging",
    "pool_max_connections",
    "pool_max_keepalive",
}


def load_config_file(path: str) -> dict:
    """Load and return an agentsec YAML config file with env var substitution.

    Args:
        path: Path to the YAML configuration file.

    Returns:
        A dictionary representing the parsed configuration.

    Raises:
        ConfigurationError: If the file cannot be read, parsed, or
            contains references to undefined environment variables.
    """
    try:
        with open(path, "r") as f:
            raw = yaml.safe_load(f)
    except FileNotFoundError:
        raise ConfigurationError(f"Configuration file not found: {path}")
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in configuration file {path}: {e}")

    if raw is None:
        return {}

    if not isinstance(raw, dict):
        raise ConfigurationError(
            f"Configuration file {path} must contain a YAML mapping, "
            f"got {type(raw).__name__}"
        )

    # Warn about unknown top-level keys (helps catch typos)
    for key in raw:
        if key not in _KNOWN_TOP_KEYS:
            logger.warning(
                "Unknown top-level key '%s' in %s. "
                "Known keys: %s. Check for typos.",
                key, path, ", ".join(sorted(_KNOWN_TOP_KEYS)),
            )

    resolved = _resolve_env_vars(raw)
    _normalize_yaml_booleans(resolved)
    return resolved


# YAML parses bare on/off/yes/no as booleans.  Map them back to the
# string values that the rest of the codebase expects.
_YAML_BOOL_TO_STR = {True: "on", False: "off"}


def _normalize_yaml_booleans(cfg: dict) -> None:
    """Normalize YAML boolean values back to string equivalents.

    YAML spec treats bare ``on`` / ``off`` / ``yes`` / ``no`` as booleans.
    Fields like ``gateway_mode.llm_mode`` and ``gateway_mode.mcp_mode``
    expect string ``"on"`` / ``"off"``, so we convert them here rather
    than forcing every user to quote their YAML values.
    """
    gw = cfg.get("gateway_mode")
    if isinstance(gw, dict):
        for key in ("llm_mode", "mcp_mode"):
            val = gw.get(key)
            if isinstance(val, bool):
                gw[key] = _YAML_BOOL_TO_STR[val]
                logger.debug(
                    "Normalized gateway_mode.%s from YAML boolean %r to '%s' "
                    "(quote the value in YAML to silence this)",
                    key, val, gw[key],
                )


def _resolve_env_vars(value: Any) -> Any:
    """Recursively replace ${VAR_NAME} placeholders with environment variable values.

    Args:
        value: A value from the parsed YAML. Can be a dict, list,
            string, or scalar.

    Returns:
        The value with all ${VAR_NAME} placeholders replaced.

    Raises:
        ConfigurationError: If a referenced environment variable is not set.
    """
    if isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_resolve_env_vars(item) for item in value]
    elif isinstance(value, str):
        return _substitute_env_string(value)
    else:
        # int, float, bool, None -- pass through unchanged
        return value


def _substitute_env_string(s: str) -> str:
    """Replace ${VAR_NAME} patterns in a string with env var values.

    If the entire string is a single ${VAR_NAME} reference, the raw
    env var value is returned (preserving type for strings). If the
    string contains mixed text and references, all references are
    interpolated into the string.

    Args:
        s: The string potentially containing ${VAR_NAME} placeholders.

    Returns:
        The string with placeholders replaced by environment variable values.

    Raises:
        ConfigurationError: If a referenced environment variable is not set.
    """

    def _replace_match(match: re.Match) -> str:
        var_name = match.group(1)
        value = os.environ.get(var_name)
        if value is None:
            raise ConfigurationError(
                f"Environment variable ${{{var_name}}} referenced in "
                f"configuration but not set. Add it to your .env file "
                f"or set it in the environment."
            )
        return value

    return _ENV_VAR_PATTERN.sub(_replace_match, s)
