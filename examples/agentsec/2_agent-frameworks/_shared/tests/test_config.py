"""
Tests for configuration loading and environment variable resolution.
"""

import sys
from pathlib import Path

# Add _shared to path for imports
_shared_dir = Path(__file__).parent.parent
if str(_shared_dir) not in sys.path:
    sys.path.insert(0, str(_shared_dir))

import os
import pytest
import tempfile

from config import resolve_env_vars, load_config


class TestResolveEnvVars:
    """Tests for environment variable resolution."""
    
    def test_simple_env_var(self, monkeypatch):
        """Test ${VAR} syntax resolves correctly."""
        monkeypatch.setenv("TEST_VAR", "hello")
        result = resolve_env_vars("${TEST_VAR}")
        assert result == "hello"
    
    def test_env_var_with_default_uses_value(self, monkeypatch):
        """Test ${VAR:-default} uses env value when set."""
        monkeypatch.setenv("TEST_VAR", "actual_value")
        result = resolve_env_vars("${TEST_VAR:-default_value}")
        assert result == "actual_value"
    
    def test_env_var_with_default_uses_default(self, monkeypatch):
        """Test ${VAR:-default} uses default when env not set."""
        monkeypatch.delenv("MISSING_VAR", raising=False)
        result = resolve_env_vars("${MISSING_VAR:-default_value}")
        assert result == "default_value"
    
    def test_missing_env_var_returns_empty(self, monkeypatch):
        """Test ${VAR} returns empty string when not set."""
        monkeypatch.delenv("MISSING_VAR", raising=False)
        result = resolve_env_vars("${MISSING_VAR}")
        assert result == ""
    
    def test_env_var_in_string(self, monkeypatch):
        """Test env var embedded in larger string."""
        monkeypatch.setenv("API_KEY", "secret123")
        result = resolve_env_vars("Bearer ${API_KEY}")
        assert result == "Bearer secret123"
    
    def test_multiple_env_vars(self, monkeypatch):
        """Test multiple env vars in one string."""
        monkeypatch.setenv("USER", "admin")
        monkeypatch.setenv("HOST", "localhost")
        result = resolve_env_vars("${USER}@${HOST}")
        assert result == "admin@localhost"
    
    def test_nested_dict_resolution(self, monkeypatch):
        """Test env vars resolved in nested dicts."""
        monkeypatch.setenv("DB_HOST", "myhost")
        monkeypatch.setenv("DB_PORT", "5432")
        
        config = {
            "database": {
                "host": "${DB_HOST}",
                "port": "${DB_PORT}",
            }
        }
        result = resolve_env_vars(config)
        
        assert result["database"]["host"] == "myhost"
        assert result["database"]["port"] == "5432"
    
    def test_list_resolution(self, monkeypatch):
        """Test env vars resolved in lists."""
        monkeypatch.setenv("ITEM1", "first")
        monkeypatch.setenv("ITEM2", "second")
        
        items = ["${ITEM1}", "${ITEM2}", "static"]
        result = resolve_env_vars(items)
        
        assert result == ["first", "second", "static"]
    
    def test_non_string_passthrough(self):
        """Test non-string values pass through unchanged."""
        assert resolve_env_vars(123) == 123
        assert resolve_env_vars(True) is True
        assert resolve_env_vars(None) is None


class TestLoadConfig:
    """Tests for YAML config loading."""
    
    def test_load_valid_config(self, tmp_path):
        """Test loading a valid YAML config file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
provider: openai
openai:
  model: gpt-4
llm_settings:
  temperature: 0.7
""")
        os.chdir(tmp_path)
        config = load_config(str(config_file))
        
        assert config["provider"] == "openai"
        assert config["openai"]["model"] == "gpt-4"
        assert config["llm_settings"]["temperature"] == 0.7
    
    def test_load_config_with_env_resolution(self, tmp_path, monkeypatch):
        """Test that env vars are resolved during loading."""
        monkeypatch.setenv("TEST_API_KEY", "sk-test123")
        
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
provider: openai
openai:
  api_key: ${TEST_API_KEY}
""")
        
        config = load_config(str(config_file))
        assert config["openai"]["api_key"] == "sk-test123"
    
    def test_missing_config_raises_error(self, tmp_path):
        """Test FileNotFoundError for missing config."""
        os.chdir(tmp_path)
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent.yaml")
    
    def test_config_file_env_var(self, tmp_path, monkeypatch):
        """Test CONFIG_FILE env var selects config."""
        config_file = tmp_path / "custom-config.yaml"
        config_file.write_text("provider: azure")
        
        monkeypatch.setenv("CONFIG_FILE", str(config_file))
        os.chdir(tmp_path)
        
        config = load_config()
        assert config["provider"] == "azure"
    
    def test_empty_config_returns_empty_dict(self, tmp_path):
        """Test empty YAML returns empty dict."""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")
        
        config = load_config(str(config_file))
        assert config == {}
    
    def test_default_with_empty_env_value(self, tmp_path, monkeypatch):
        """Test ${VAR:-default} with empty string env value."""
        monkeypatch.setenv("EMPTY_VAR", "")
        
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
value: ${EMPTY_VAR:-default}
""")
        
        config = load_config(str(config_file))
        # Empty string should be used, not default
        assert config["value"] == ""

