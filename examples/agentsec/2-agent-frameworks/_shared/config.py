"""
Configuration loader with environment variable resolution.

Supports:
- YAML config files
- Environment variable resolution: ${VAR} and ${VAR:-default}
- CONFIG_FILE environment variable to select config file
"""

import os
import re
from pathlib import Path
from typing import Any, Optional

import yaml


def resolve_env_vars(value: Any) -> Any:
    """
    Recursively resolve ${VAR} and ${VAR:-default} references in config values.
    
    Examples:
        ${OPENAI_API_KEY} -> value of OPENAI_API_KEY env var
        ${OPENAI_API_KEY:-sk-default} -> value or 'sk-default' if not set
    """
    if isinstance(value, str):
        # Pattern matches ${VAR} or ${VAR:-default}
        pattern = r'\$\{([^}:]+)(?::-([^}]*))?\}'
        
        def replacer(match):
            var_name = match.group(1)
            default = match.group(2)  # May be None
            env_value = os.environ.get(var_name)
            
            if env_value is not None:
                return env_value
            elif default is not None:
                return default
            else:
                # Return empty string if var not found and no default
                return ''
        
        return re.sub(pattern, replacer, value)
    
    elif isinstance(value, dict):
        return {k: resolve_env_vars(v) for k, v in value.items()}
    
    elif isinstance(value, list):
        return [resolve_env_vars(item) for item in value]
    
    return value


def load_config(config_path: Optional[str] = None) -> dict:
    """
    Load configuration from YAML file with environment variable resolution.
    
    Args:
        config_path: Path to config file. If None, uses CONFIG_FILE env var
                    or defaults to 'config.yaml' in current directory.
    
    Returns:
        Parsed configuration dict with resolved environment variables.
    
    Raises:
        FileNotFoundError: If config file doesn't exist.
        yaml.YAMLError: If config file is invalid YAML.
    
    Example:
        # Load default config
        config = load_config()
        
        # Load specific config
        config = load_config('config-azure.yaml')
        
        # Use CONFIG_FILE env var
        # CONFIG_FILE=config-bedrock.yaml python agent.py
        config = load_config()
    """
    if config_path is None:
        # Check CONFIG_FILE environment variable
        config_path = os.environ.get('CONFIG_FILE', 'config.yaml')
    
    # Convert to Path for better handling
    path = Path(config_path)
    
    # If not absolute, try to find relative to current directory
    if not path.is_absolute():
        # Try current directory first
        if not path.exists():
            # Try looking in the script's directory
            script_dir = Path(__file__).parent.parent
            candidate = script_dir / config_path
            if candidate.exists():
                path = candidate
    
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            f"Set CONFIG_FILE environment variable or create config.yaml"
        )
    
    with open(path, 'r') as f:
        config = yaml.safe_load(f)
    
    if config is None:
        config = {}
    
    # Resolve environment variables
    config = resolve_env_vars(config)
    
    return config

