"""Tests for config_file.py -- YAML config loading with ${ENV_VAR} substitution."""

import os
import tempfile

import pytest

from aidefense.runtime.agentsec.config_file import load_config_file
from aidefense.runtime.agentsec.exceptions import ConfigurationError


class TestLoadConfigFile:
    """Tests for load_config_file()."""

    def _write_yaml(self, content: str) -> str:
        """Write YAML content to a temp file and return its path."""
        fd, path = tempfile.mkstemp(suffix=".yaml")
        os.write(fd, content.encode())
        os.close(fd)
        return path

    def test_basic_yaml(self):
        path = self._write_yaml("llm_integration_mode: gateway\n")
        result = load_config_file(path)
        assert result == {"llm_integration_mode": "gateway"}
        os.unlink(path)

    def test_nested_yaml(self):
        content = """\
gateway_mode:
  llm_defaults:
    fail_open: true
    timeout: 3
  llm_gateways:
    openai-1:
      gateway_url: https://gw.example.com
      provider: openai
      default: true
"""
        path = self._write_yaml(content)
        result = load_config_file(path)
        assert result["gateway_mode"]["llm_defaults"]["fail_open"] is True
        assert result["gateway_mode"]["llm_defaults"]["timeout"] == 3
        assert result["gateway_mode"]["llm_gateways"]["openai-1"]["gateway_url"] == "https://gw.example.com"
        os.unlink(path)

    def test_env_var_substitution(self, monkeypatch):
        monkeypatch.setenv("TEST_GW_KEY", "my-secret-key")
        content = """\
gateway_mode:
  llm_gateways:
    openai-1:
      gateway_api_key: ${TEST_GW_KEY}
      provider: openai
      default: true
"""
        path = self._write_yaml(content)
        result = load_config_file(path)
        assert result["gateway_mode"]["llm_gateways"]["openai-1"]["gateway_api_key"] == "my-secret-key"
        os.unlink(path)

    def test_env_var_not_set_raises(self):
        content = """\
gateway_mode:
  llm_gateways:
    openai-1:
      gateway_api_key: ${NONEXISTENT_VAR_12345}
      provider: openai
      default: true
"""
        path = self._write_yaml(content)
        with pytest.raises(ConfigurationError, match="NONEXISTENT_VAR_12345"):
            load_config_file(path)
        os.unlink(path)

    def test_file_not_found(self):
        with pytest.raises(ConfigurationError, match="not found"):
            load_config_file("/nonexistent/agentsec.yaml")

    def test_empty_file(self):
        path = self._write_yaml("")
        result = load_config_file(path)
        assert result == {}
        os.unlink(path)

    def test_invalid_yaml(self):
        path = self._write_yaml(":\n  :\n  - ][")
        with pytest.raises(ConfigurationError, match="Invalid YAML"):
            load_config_file(path)
        os.unlink(path)

    def test_non_mapping_yaml(self):
        path = self._write_yaml("- item1\n- item2\n")
        with pytest.raises(ConfigurationError, match="must contain a YAML mapping"):
            load_config_file(path)
        os.unlink(path)

    def test_mixed_env_and_literal(self, monkeypatch):
        """String with ${VAR} embedded in other text."""
        monkeypatch.setenv("MY_HOST", "gw.example.com")
        content = """\
url: https://${MY_HOST}/v1
"""
        path = self._write_yaml(content)
        result = load_config_file(path)
        assert result["url"] == "https://gw.example.com/v1"
        os.unlink(path)

    def test_bedrock_gateway_aws_env_substitution(self, monkeypatch):
        """AWS credential fields resolve ${VAR} from environment."""
        monkeypatch.setenv("MY_REGION", "eu-west-1")
        monkeypatch.setenv("MY_PROFILE", "team-b")
        monkeypatch.setenv("MY_ACCESS_KEY", "AKIAEXAMPLE")
        monkeypatch.setenv("MY_SECRET_KEY", "secret123")
        monkeypatch.setenv("MY_SESSION_TOKEN", "token456")
        monkeypatch.setenv("MY_ROLE_ARN", "arn:aws:iam::123456789012:role/test")
        content = """\
gateway_mode:
  llm_gateways:
    bedrock-1:
      gateway_url: https://gw.example.com
      auth_mode: aws_sigv4
      provider: bedrock
      aws_region: ${MY_REGION}
      aws_profile: ${MY_PROFILE}
      aws_access_key_id: ${MY_ACCESS_KEY}
      aws_secret_access_key: ${MY_SECRET_KEY}
      aws_session_token: ${MY_SESSION_TOKEN}
      aws_role_arn: ${MY_ROLE_ARN}
"""
        path = self._write_yaml(content)
        result = load_config_file(path)
        gw = result["gateway_mode"]["llm_gateways"]["bedrock-1"]
        assert gw["aws_region"] == "eu-west-1"
        assert gw["aws_profile"] == "team-b"
        assert gw["aws_access_key_id"] == "AKIAEXAMPLE"
        assert gw["aws_secret_access_key"] == "secret123"
        assert gw["aws_session_token"] == "token456"
        assert gw["aws_role_arn"] == "arn:aws:iam::123456789012:role/test"
        os.unlink(path)

    def test_bedrock_gateway_aws_env_not_set_raises(self):
        """Unset env var in AWS field raises ConfigurationError."""
        content = """\
gateway_mode:
  llm_gateways:
    bedrock-1:
      gateway_url: https://gw.example.com
      aws_access_key_id: ${BEDROCK_UNSET_KEY}
"""
        path = self._write_yaml(content)
        with pytest.raises(ConfigurationError, match="BEDROCK_UNSET_KEY"):
            load_config_file(path)
        os.unlink(path)

    def test_vertexai_gateway_gcp_env_substitution(self, monkeypatch):
        """GCP credential fields resolve ${VAR} from environment."""
        monkeypatch.setenv("MY_GCP_PROJECT", "my-project-id")
        monkeypatch.setenv("MY_GCP_LOCATION", "europe-west4")
        monkeypatch.setenv("MY_SA_KEY_FILE", "/path/to/key.json")
        monkeypatch.setenv("MY_TARGET_SA", "sa@project.iam.gserviceaccount.com")
        content = """\
gateway_mode:
  llm_gateways:
    vertexai-1:
      gateway_url: https://gw.example.com
      auth_mode: google_adc
      provider: vertexai
      gcp_project: ${MY_GCP_PROJECT}
      gcp_location: ${MY_GCP_LOCATION}
      gcp_service_account_key_file: ${MY_SA_KEY_FILE}
      gcp_target_service_account: ${MY_TARGET_SA}
"""
        path = self._write_yaml(content)
        result = load_config_file(path)
        gw = result["gateway_mode"]["llm_gateways"]["vertexai-1"]
        assert gw["gcp_project"] == "my-project-id"
        assert gw["gcp_location"] == "europe-west4"
        assert gw["gcp_service_account_key_file"] == "/path/to/key.json"
        assert gw["gcp_target_service_account"] == "sa@project.iam.gserviceaccount.com"
        os.unlink(path)

    def test_vertexai_gateway_gcp_env_not_set_raises(self):
        """Unset env var in GCP field raises ConfigurationError."""
        content = """\
gateway_mode:
  llm_gateways:
    vertexai-1:
      gateway_url: https://gw.example.com
      gcp_project: ${VERTEXAI_UNSET_PROJECT}
"""
        path = self._write_yaml(content)
        with pytest.raises(ConfigurationError, match="VERTEXAI_UNSET_PROJECT"):
            load_config_file(path)
        os.unlink(path)

    def test_non_string_values_preserved(self):
        """Integers, booleans, lists pass through unchanged."""
        content = """\
timeout: 5
fail_open: true
status_codes: [429, 500]
"""
        path = self._write_yaml(content)
        result = load_config_file(path)
        assert result["timeout"] == 5
        assert result["fail_open"] is True
        assert result["status_codes"] == [429, 500]
        os.unlink(path)

    def test_mcp_gateway_auth_mode_none(self):
        """MCP gateway with auth_mode: none is parsed correctly."""
        content = """\
gateway_mode:
  mcp_gateways:
    https://mcp.example.com:
      gateway_url: https://gw.example.com/mcp
      auth_mode: none
"""
        path = self._write_yaml(content)
        result = load_config_file(path)
        gw = result["gateway_mode"]["mcp_gateways"]["https://mcp.example.com"]
        assert gw["gateway_url"] == "https://gw.example.com/mcp"
        assert gw["auth_mode"] == "none"
        os.unlink(path)

    def test_mcp_gateway_auth_mode_api_key(self, monkeypatch):
        """MCP gateway with auth_mode: api_key resolves env var."""
        monkeypatch.setenv("MY_MCP_KEY", "secret-mcp-key")
        content = """\
gateway_mode:
  mcp_gateways:
    https://mcp.example.com:
      gateway_url: https://gw.example.com/mcp
      auth_mode: api_key
      api_key: ${MY_MCP_KEY}
"""
        path = self._write_yaml(content)
        result = load_config_file(path)
        gw = result["gateway_mode"]["mcp_gateways"]["https://mcp.example.com"]
        assert gw["auth_mode"] == "api_key"
        assert gw["api_key"] == "secret-mcp-key"
        os.unlink(path)

    def test_mcp_gateway_auth_mode_oauth2(self, monkeypatch):
        """MCP gateway with auth_mode: oauth2_client_credentials resolves env vars."""
        monkeypatch.setenv("MY_OAUTH_CID", "client-123")
        monkeypatch.setenv("MY_OAUTH_SECRET", "secret-456")
        content = """\
gateway_mode:
  mcp_gateways:
    https://secure-mcp.example.com:
      gateway_url: https://gw.example.com/mcp/secure
      auth_mode: oauth2_client_credentials
      oauth2_token_url: https://auth.example.com/oauth/token
      oauth2_client_id: ${MY_OAUTH_CID}
      oauth2_client_secret: ${MY_OAUTH_SECRET}
      oauth2_scopes: "read write"
"""
        path = self._write_yaml(content)
        result = load_config_file(path)
        gw = result["gateway_mode"]["mcp_gateways"]["https://secure-mcp.example.com"]
        assert gw["auth_mode"] == "oauth2_client_credentials"
        assert gw["oauth2_token_url"] == "https://auth.example.com/oauth/token"
        assert gw["oauth2_client_id"] == "client-123"
        assert gw["oauth2_client_secret"] == "secret-456"
        assert gw["oauth2_scopes"] == "read write"
        os.unlink(path)

    def test_mcp_gateway_oauth2_env_not_set_raises(self):
        """Unset env var in OAuth2 field raises ConfigurationError."""
        content = """\
gateway_mode:
  mcp_gateways:
    https://mcp.example.com:
      gateway_url: https://gw.example.com/mcp
      auth_mode: oauth2_client_credentials
      oauth2_client_id: ${MCP_OAUTH_UNSET_CID}
"""
        path = self._write_yaml(content)
        with pytest.raises(ConfigurationError, match="MCP_OAUTH_UNSET_CID"):
            load_config_file(path)
        os.unlink(path)

    def test_pool_params_parsed_as_integers(self):
        """pool_max_connections and pool_max_keepalive are parsed as YAML integers."""
        content = """\
pool_max_connections: 50
pool_max_keepalive: 10
"""
        path = self._write_yaml(content)
        result = load_config_file(path)
        assert result["pool_max_connections"] == 50
        assert result["pool_max_keepalive"] == 10
        assert isinstance(result["pool_max_connections"], int)
        assert isinstance(result["pool_max_keepalive"], int)
        os.unlink(path)

    def test_pool_params_no_unknown_key_warning(self, caplog):
        """pool_max_connections and pool_max_keepalive are known keys (no warning)."""
        content = """\
pool_max_connections: 200
pool_max_keepalive: 30
"""
        path = self._write_yaml(content)
        import logging
        with caplog.at_level(logging.WARNING, logger="aidefense.runtime.agentsec.config_file"):
            load_config_file(path)
        assert "Unknown top-level key" not in caplog.text
        os.unlink(path)

    def test_pool_params_env_var_substitution(self, monkeypatch):
        """pool_max_connections from ${VAR} is a string after substitution."""
        monkeypatch.setenv("MY_POOL_CONN", "75")
        monkeypatch.setenv("MY_POOL_KEEP", "15")
        content = """\
pool_max_connections: ${MY_POOL_CONN}
pool_max_keepalive: ${MY_POOL_KEEP}
"""
        path = self._write_yaml(content)
        result = load_config_file(path)
        # After env var substitution, values are strings — caller must cast to int
        assert result["pool_max_connections"] == "75"
        assert result["pool_max_keepalive"] == "15"
        os.unlink(path)
