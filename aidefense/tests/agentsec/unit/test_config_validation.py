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

"""Tests for configuration validation in _state.py, config_file.py, and _logging.py.

Covers type checks, range checks, enum validation, unknown-key warnings,
and gateway_url / auth_mode / provider / log_format validation.
"""

import logging
import os
import tempfile

import pytest

from aidefense.runtime.agentsec import _state
from aidefense.runtime.agentsec._state import (
    _unpack_defaults,
    _validate_defaults,
    resolve_llm_gateway_settings,
    resolve_mcp_gateway_settings,
    VALID_AUTH_MODES,
    VALID_LOG_FORMATS,
)
from aidefense.runtime.agentsec.config_file import load_config_file
from aidefense.runtime.agentsec.exceptions import ConfigurationError


@pytest.fixture(autouse=True)
def reset_state():
    _state.reset()
    yield
    _state.reset()


# ===========================================================================
# _validate_defaults: timeout
# ===========================================================================

class TestValidateDefaultsTimeout:
    """Timeout must be a number, > 0, and <= 3600."""

    def test_timeout_zero_raises(self):
        with pytest.raises(ConfigurationError, match="timeout.*> 0"):
            _validate_defaults("test", {"timeout": 0})

    def test_timeout_negative_raises(self):
        with pytest.raises(ConfigurationError, match="timeout.*> 0"):
            _validate_defaults("test", {"timeout": -5})

    def test_timeout_string_raises(self):
        with pytest.raises(ConfigurationError, match="timeout.*type str"):
            _validate_defaults("test", {"timeout": "slow"})

    def test_timeout_exceeds_max_raises(self):
        with pytest.raises(ConfigurationError, match="timeout.*<= 3600"):
            _validate_defaults("test", {"timeout": 5000})

    def test_timeout_valid_int_ok(self):
        _validate_defaults("test", {"timeout": 30})  # no error

    def test_timeout_valid_float_ok(self):
        _validate_defaults("test", {"timeout": 0.5})  # no error

    def test_timeout_max_boundary_ok(self):
        _validate_defaults("test", {"timeout": 3600})  # no error


# ===========================================================================
# _validate_defaults: fail_open
# ===========================================================================

class TestValidateDefaultsFailOpen:
    """fail_open must be a boolean."""

    def test_fail_open_string_raises(self):
        with pytest.raises(ConfigurationError, match="fail_open.*boolean"):
            _validate_defaults("test", {"fail_open": "yes"})

    def test_fail_open_int_raises(self):
        with pytest.raises(ConfigurationError, match="fail_open.*boolean"):
            _validate_defaults("test", {"fail_open": 1})

    def test_fail_open_true_ok(self):
        _validate_defaults("test", {"fail_open": True})  # no error

    def test_fail_open_false_ok(self):
        _validate_defaults("test", {"fail_open": False})  # no error


# ===========================================================================
# _validate_defaults: retry_total
# ===========================================================================

class TestValidateDefaultsRetryTotal:
    """retry.total must be an int, >= 1, and <= 50."""

    def test_retry_total_zero_raises(self):
        with pytest.raises(ConfigurationError, match="retry.total.*>= 1"):
            _validate_defaults("test", {"retry_total": 0})

    def test_retry_total_negative_raises(self):
        with pytest.raises(ConfigurationError, match="retry.total.*>= 1"):
            _validate_defaults("test", {"retry_total": -1})

    def test_retry_total_exceeds_max_raises(self):
        with pytest.raises(ConfigurationError, match="retry.total.*<= 50"):
            _validate_defaults("test", {"retry_total": 100})

    def test_retry_total_string_raises(self):
        with pytest.raises(ConfigurationError, match="retry.total.*type str"):
            _validate_defaults("test", {"retry_total": "three"})

    def test_retry_total_bool_raises(self):
        """Booleans are technically ints in Python but should be rejected."""
        with pytest.raises(ConfigurationError, match="retry.total.*type bool"):
            _validate_defaults("test", {"retry_total": True})

    def test_retry_total_valid_ok(self):
        _validate_defaults("test", {"retry_total": 5})  # no error

    def test_retry_total_max_boundary_ok(self):
        _validate_defaults("test", {"retry_total": 50})  # no error


# ===========================================================================
# _validate_defaults: retry_backoff
# ===========================================================================

class TestValidateDefaultsRetryBackoff:
    """retry.backoff_factor must be a number >= 0."""

    def test_retry_backoff_negative_raises(self):
        with pytest.raises(ConfigurationError, match="backoff_factor.*>= 0"):
            _validate_defaults("test", {"retry_backoff": -0.5})

    def test_retry_backoff_string_raises(self):
        with pytest.raises(ConfigurationError, match="backoff_factor.*type str"):
            _validate_defaults("test", {"retry_backoff": "fast"})

    def test_retry_backoff_bool_raises(self):
        with pytest.raises(ConfigurationError, match="backoff_factor.*type bool"):
            _validate_defaults("test", {"retry_backoff": True})

    def test_retry_backoff_zero_ok(self):
        _validate_defaults("test", {"retry_backoff": 0})  # no error

    def test_retry_backoff_positive_ok(self):
        _validate_defaults("test", {"retry_backoff": 1.5})  # no error


# ===========================================================================
# _validate_defaults: retry_status_codes
# ===========================================================================

class TestValidateDefaultsRetryStatusCodes:
    """retry.status_codes must be a list of ints in 100-599."""

    def test_status_codes_string_raises(self):
        with pytest.raises(ConfigurationError, match="status_codes.*list"):
            _validate_defaults("test", {"retry_status_codes": "500"})

    def test_status_codes_not_int_element_raises(self):
        with pytest.raises(ConfigurationError, match="status_codes\\[0\\].*type str"):
            _validate_defaults("test", {"retry_status_codes": ["five hundred"]})

    def test_status_codes_out_of_range_raises(self):
        with pytest.raises(ConfigurationError, match="status_codes\\[0\\].*100-599"):
            _validate_defaults("test", {"retry_status_codes": [99999]})

    def test_status_codes_below_range_raises(self):
        with pytest.raises(ConfigurationError, match="status_codes\\[0\\].*100-599"):
            _validate_defaults("test", {"retry_status_codes": [50]})

    def test_status_codes_valid_ok(self):
        _validate_defaults("test", {"retry_status_codes": [429, 500, 502]})  # no error

    def test_status_codes_empty_list_ok(self):
        _validate_defaults("test", {"retry_status_codes": []})  # no error


# ===========================================================================
# _validate_defaults: valid full config (regression guard)
# ===========================================================================

class TestValidateDefaultsRegression:
    """All valid values together should pass without error."""

    def test_valid_full_config(self):
        _validate_defaults("test", {
            "fail_open": True,
            "timeout": 10,
            "retry_total": 3,
            "retry_backoff": 0.5,
            "retry_status_codes": [429, 500, 502, 503, 504],
        })  # no error

    def test_empty_dict_ok(self):
        _validate_defaults("test", {})  # no error


# ===========================================================================
# set_state wires validation for all four defaults blocks
# ===========================================================================

class TestSetStateDefaultsValidation:
    """set_state() should raise ConfigurationError for invalid defaults."""

    def test_gw_llm_defaults_invalid_timeout(self):
        with pytest.raises(ConfigurationError, match="gateway_mode.llm_defaults.timeout"):
            _state.set_state(
                initialized=True,
                gateway_mode={"llm_defaults": {"timeout": -1}},
            )

    def test_gw_mcp_defaults_invalid_retry(self):
        with pytest.raises(ConfigurationError, match="gateway_mode.mcp_defaults.retry.total"):
            _state.set_state(
                initialized=True,
                gateway_mode={"mcp_defaults": {"retry": {"total": 0}}},
            )

    def test_api_llm_defaults_invalid_fail_open(self):
        with pytest.raises(ConfigurationError, match="api_mode.llm_defaults.fail_open"):
            _state.set_state(
                initialized=True,
                api_mode={"llm_defaults": {"fail_open": "yes"}},
            )

    def test_api_mcp_defaults_invalid_backoff(self):
        with pytest.raises(ConfigurationError, match="api_mode.mcp_defaults.retry.backoff_factor"):
            _state.set_state(
                initialized=True,
                api_mode={"mcp_defaults": {"retry": {"backoff_factor": -1.0}}},
            )


# ===========================================================================
# Auth mode validation
# ===========================================================================

class TestAuthModeValidation:
    """auth_mode must be one of VALID_AUTH_MODES."""

    def test_llm_gateway_invalid_auth_mode_raises(self):
        with pytest.raises(ConfigurationError, match="Invalid auth_mode.*banana"):
            resolve_llm_gateway_settings({
                "gateway_url": "https://gw.example.com",
                "auth_mode": "banana",
            })

    def test_mcp_gateway_invalid_auth_mode_raises(self):
        with pytest.raises(ConfigurationError, match="Invalid auth_mode.*banana"):
            resolve_mcp_gateway_settings({
                "gateway_url": "https://gw.example.com",
                "auth_mode": "banana",
            })

    def test_all_valid_auth_modes_pass_llm(self):
        for mode in VALID_AUTH_MODES:
            settings = resolve_llm_gateway_settings({
                "gateway_url": "https://gw.example.com",
                "auth_mode": mode,
            })
            assert settings.auth_mode == mode

    def test_all_valid_auth_modes_pass_mcp(self):
        for mode in VALID_AUTH_MODES:
            settings = resolve_mcp_gateway_settings({
                "gateway_url": "https://gw.example.com",
                "auth_mode": mode,
            })
            assert settings.auth_mode == mode


# ===========================================================================
# Provider validation
# ===========================================================================

class TestProviderValidation:
    """provider in llm_gateways must be a recognized provider."""

    def test_invalid_provider_raises(self):
        with pytest.raises(ConfigurationError, match="Invalid provider.*chatgpt.*gateway.*my-gw"):
            _state.set_state(
                initialized=True,
                gateway_mode={
                    "llm_gateways": {
                        "my-gw": {
                            "gateway_url": "https://gw.example.com",
                            "provider": "chatgpt",
                            "default": True,
                        },
                    },
                },
            )

    def test_valid_providers_pass(self):
        for provider in _state.SUPPORTED_PROVIDERS:
            _state.reset()
            _state.set_state(
                initialized=True,
                gateway_mode={
                    "llm_gateways": {
                        "test-gw": {
                            "gateway_url": "https://gw.example.com",
                            "provider": provider,
                            "default": True,
                        },
                    },
                },
            )
            p = _state.get_default_gateway_for_provider(provider)
            assert p is not None


# ===========================================================================
# Gateway URL validation
# ===========================================================================

class TestGatewayUrlValidation:
    """gateway_url must be a non-empty string in resolve functions."""

    def test_llm_empty_gateway_url_raises(self):
        with pytest.raises(ConfigurationError, match="gateway_url.*required.*non-empty"):
            resolve_llm_gateway_settings({"gateway_url": ""})

    def test_llm_missing_gateway_url_raises(self):
        with pytest.raises(ConfigurationError, match="gateway_url.*required.*non-empty"):
            resolve_llm_gateway_settings({})

    def test_llm_whitespace_gateway_url_raises(self):
        with pytest.raises(ConfigurationError, match="gateway_url.*required.*non-empty"):
            resolve_llm_gateway_settings({"gateway_url": "   "})

    def test_mcp_empty_gateway_url_raises(self):
        with pytest.raises(ConfigurationError, match="gateway_url.*required.*non-empty"):
            resolve_mcp_gateway_settings({"gateway_url": ""})

    def test_mcp_missing_gateway_url_raises(self):
        with pytest.raises(ConfigurationError, match="gateway_url.*required.*non-empty"):
            resolve_mcp_gateway_settings({})

    def test_llm_valid_gateway_url_ok(self):
        settings = resolve_llm_gateway_settings({
            "gateway_url": "https://gw.example.com",
        })
        assert settings.url == "https://gw.example.com"

    def test_mcp_valid_gateway_url_ok(self):
        settings = resolve_mcp_gateway_settings({
            "gateway_url": "https://gw.example.com",
        })
        assert settings.url == "https://gw.example.com"


# ===========================================================================
# Logging validation
# ===========================================================================

class TestLogFormatValidation:
    """log_format must be 'text' or 'json' in set_state()."""

    def test_invalid_log_format_raises(self):
        with pytest.raises(ConfigurationError, match="logging.format.*xml"):
            _state.set_state(
                initialized=True,
                log_format="xml",
            )

    def test_valid_log_format_text_ok(self):
        _state.set_state(initialized=True, log_format="text")
        assert _state.get_log_format() == "text"

    def test_valid_log_format_json_ok(self):
        _state.set_state(initialized=True, log_format="json")
        assert _state.get_log_format() == "json"


class TestLogLevelWarning:
    """setup_logging() should warn on unknown log levels (not raise)."""

    def test_unknown_level_warns(self, capsys):
        from aidefense.runtime.agentsec._logging import setup_logging

        import logging as _logging
        _logger = _logging.getLogger("aidefense.runtime.agentsec")
        _logger.handlers.clear()

        setup_logging(level="VERBOSE")

        captured = capsys.readouterr()
        assert "Unknown logging level" in captured.err

        # Cleanup
        _logger.handlers.clear()


# ===========================================================================
# Unknown key warnings
# ===========================================================================

def _enable_propagation(*logger_names):
    """Context manager to temporarily enable propagation for loggers.

    The parent logger 'aidefense.runtime.agentsec' has propagate=False
    (set by setup_logging), which prevents caplog from capturing records.
    This helper enables propagation on the full logger chain during tests.
    """
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        loggers = []
        for name in logger_names:
            lgr = logging.getLogger(name)
            loggers.append((lgr, lgr.propagate))
            lgr.propagate = True
        # Also enable on the parent so records reach root (where caplog lives)
        parent = logging.getLogger("aidefense.runtime.agentsec")
        loggers.append((parent, parent.propagate))
        parent.propagate = True
        try:
            yield
        finally:
            for lgr, orig in loggers:
                lgr.propagate = orig

    return _ctx()


class TestUnknownKeyWarnings:
    """Unknown keys in defaults and top-level should produce warnings."""

    def test_unknown_key_in_defaults_warns(self, caplog):
        with _enable_propagation("aidefense.runtime.agentsec._state"):
            with caplog.at_level(logging.WARNING):
                _unpack_defaults({"timout": 5}, prefix="test_section")
            assert any("Unknown key 'timout'" in msg for msg in caplog.messages)

    def test_unknown_key_in_retry_warns(self, caplog):
        with _enable_propagation("aidefense.runtime.agentsec._state"):
            with caplog.at_level(logging.WARNING):
                _unpack_defaults({"retry": {"retyr": 3}}, prefix="test_section")
            assert any("Unknown key 'retyr'" in msg for msg in caplog.messages)

    def test_known_keys_no_warning(self, caplog):
        with _enable_propagation("aidefense.runtime.agentsec._state"):
            with caplog.at_level(logging.WARNING):
                _unpack_defaults({
                    "fail_open": True,
                    "timeout": 10,
                    "retry": {"total": 3, "backoff_factor": 0.5, "status_codes": [500]},
                }, prefix="test_section")
            assert not any("Unknown key" in msg for msg in caplog.messages)


class TestUnknownTopLevelKeyWarnings:
    """Unknown top-level keys in config file should produce warnings."""

    def _write_yaml(self, content: str) -> str:
        fd, path = tempfile.mkstemp(suffix=".yaml")
        os.write(fd, content.encode())
        os.close(fd)
        return path

    def test_unknown_top_level_key_warns(self, caplog):
        with _enable_propagation("aidefense.runtime.agentsec.config_file"):
            path = self._write_yaml("gatway_mode:\n  llm_defaults:\n    timeout: 5\n")
            with caplog.at_level(logging.WARNING):
                load_config_file(path)
            os.unlink(path)
            assert any("Unknown top-level key 'gatway_mode'" in msg for msg in caplog.messages)

    def test_known_top_level_keys_no_warning(self, caplog):
        with _enable_propagation("aidefense.runtime.agentsec.config_file"):
            path = self._write_yaml("llm_integration_mode: api\nmcp_integration_mode: api\n")
            with caplog.at_level(logging.WARNING):
                load_config_file(path)
            os.unlink(path)
            assert not any("Unknown top-level key" in msg for msg in caplog.messages)


# ===========================================================================
# GatewayClient retry_backoff clamping
# ===========================================================================

class TestGatewayClientBackoffClamping:
    """GatewayClient should clamp retry_backoff to max(0.0, value)."""

    def test_negative_backoff_clamped_to_zero(self):
        from aidefense.runtime.agentsec.inspectors.gateway_llm import GatewayClient

        client = GatewayClient(
            gateway_url="https://gw.example.com",
            api_key="test-key",
            retry_backoff=-2.0,
        )
        assert client.retry_backoff == 0.0

    def test_positive_backoff_unchanged(self):
        from aidefense.runtime.agentsec.inspectors.gateway_llm import GatewayClient

        client = GatewayClient(
            gateway_url="https://gw.example.com",
            api_key="test-key",
            retry_backoff=1.5,
        )
        assert client.retry_backoff == 1.5


# ===========================================================================
# AIFW-18899: Pool config validation
# ===========================================================================

class TestPoolConfigValidation:
    """Non-numeric pool_max_connections / pool_max_keepalive from YAML
    should raise ConfigurationError, not bare ValueError."""

    def test_pool_max_connections_non_numeric_raises(self, tmp_path):
        from aidefense.runtime.agentsec import _state, protect
        from aidefense.runtime.agentsec.exceptions import ConfigurationError

        yaml_file = tmp_path / "agentsec.yaml"
        yaml_file.write_text("pool_max_connections: auto\n")

        _state.reset()
        with pytest.raises(ConfigurationError, match="pool_max_connections.*auto"):
            protect(config=str(yaml_file), patch_clients=False, auto_dotenv=False)
        _state.reset()

    def test_pool_max_keepalive_non_numeric_raises(self, tmp_path):
        from aidefense.runtime.agentsec import _state, protect
        from aidefense.runtime.agentsec.exceptions import ConfigurationError

        yaml_file = tmp_path / "agentsec.yaml"
        yaml_file.write_text("pool_max_keepalive: lots\n")

        _state.reset()
        with pytest.raises(ConfigurationError, match="pool_max_keepalive.*lots"):
            protect(config=str(yaml_file), patch_clients=False, auto_dotenv=False)
        _state.reset()

    def test_pool_max_connections_zero_raises(self, tmp_path):
        from aidefense.runtime.agentsec import _state, protect
        from aidefense.runtime.agentsec.exceptions import ConfigurationError

        yaml_file = tmp_path / "agentsec.yaml"
        yaml_file.write_text("pool_max_connections: 0\n")

        _state.reset()
        with pytest.raises(ConfigurationError, match="pool_max_connections.*0"):
            protect(config=str(yaml_file), patch_clients=False, auto_dotenv=False)
        _state.reset()

    def test_pool_max_connections_valid_int_accepted(self, tmp_path):
        from aidefense.runtime.agentsec import _state, protect

        yaml_file = tmp_path / "agentsec.yaml"
        yaml_file.write_text("pool_max_connections: 10\n")

        _state.reset()
        protect(config=str(yaml_file), patch_clients=False, auto_dotenv=False)
        _state.reset()
