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
