"""Tests for agentsec inspection context, gateway auth headers, and config validation.

Covers:
- Inspection context reset preventing stale state leaks (_context.py)
- OpenAI gateway auth header builder backward compatibility (patchers/openai.py)
- Cohere gateway auth header builder backward compatibility (patchers/cohere.py)
- Config file known top-level keys (config_file.py)
- Gateway entry validation (__init__.py)
"""

import logging
import os
import tempfile
from dataclasses import dataclass
from typing import Optional
from unittest.mock import patch

import importlib

import pytest

from aidefense.runtime.agentsec._context import (
    clear_inspection_context,
    get_inspection_context,
    set_inspection_context,
)
from aidefense.runtime.agentsec.decision import Decision
from aidefense.runtime.agentsec.exceptions import ConfigurationError
from aidefense.runtime.agentsec.gateway_settings import GatewaySettings

_has_wrapt = importlib.util.find_spec("wrapt") is not None
_has_yaml = importlib.util.find_spec("yaml") is not None


# ── Inspection context leak fix ──────────────────────────────────────


class TestInspectionContextReset:
    """set_inspection_context(done=False) must clear stale metadata/decision."""

    def setup_method(self):
        clear_inspection_context()

    def test_done_false_resets_metadata_and_decision(self):
        set_inspection_context(
            metadata={"agent": "test"},
            decision=Decision.allow(reasons=["ok"]),
            done=True,
        )
        ctx = get_inspection_context()
        assert ctx.metadata == {"agent": "test"}
        assert ctx.decision is not None
        assert ctx.done is True

        set_inspection_context(done=False)

        ctx = get_inspection_context()
        assert ctx.metadata == {}
        assert ctx.decision is None
        assert ctx.done is False

    def test_done_false_with_new_metadata_does_not_clear(self):
        """When metadata is supplied alongside done=False, it should be kept."""
        set_inspection_context(
            metadata={"agent": "old"},
            decision=Decision.block(reasons=["bad"]),
            done=True,
        )

        set_inspection_context(metadata={"agent": "new"}, done=False)

        ctx = get_inspection_context()
        assert ctx.metadata == {"agent": "new"}
        assert ctx.done is False

    def test_done_true_preserves_existing_metadata(self):
        set_inspection_context(metadata={"session": "abc"})
        set_inspection_context(done=True)
        ctx = get_inspection_context()
        assert ctx.metadata == {"session": "abc"}
        assert ctx.done is True


# ── OpenAI gateway auth header builder ───────────────────────────────


@pytest.mark.skipif(
    not _has_wrapt, reason="wrapt not installed (agentsec extras required)"
)
class TestOpenAIGatewayAuthHeaders:
    """_build_gateway_auth_headers backward compat and custom header."""

    @staticmethod
    def _build(provider="openai", api_key_header="api-key", api_key="test-key"):
        from aidefense.runtime.agentsec.patchers.openai import (
            _build_gateway_auth_headers,
        )

        gw = GatewaySettings(url="https://gw.example.com", api_key=api_key, api_key_header=api_key_header)
        return _build_gateway_auth_headers(gw, provider, api_key)

    def test_openai_default_uses_bearer(self):
        headers = self._build(provider="openai")
        assert headers["Authorization"] == "Bearer test-key"
        assert "api-key" not in headers

    def test_azure_default_uses_api_key_header(self):
        headers = self._build(provider="azure_openai")
        assert headers["api-key"] == "test-key"
        assert "Authorization" not in headers

    def test_openai_custom_header_overrides_bearer(self):
        headers = self._build(provider="openai", api_key_header="X-Gateway-Key")
        assert headers["X-Gateway-Key"] == "test-key"
        assert "Authorization" not in headers

    def test_azure_custom_header_overrides_default(self):
        headers = self._build(provider="azure_openai", api_key_header="X-Custom")
        assert headers["X-Custom"] == "test-key"
        assert "api-key" not in headers

    def test_content_type_always_present(self):
        headers = self._build(provider="openai")
        assert headers["Content-Type"] == "application/json"


# ── Cohere gateway auth header builder ───────────────────────────────


@pytest.mark.skipif(
    not _has_wrapt, reason="wrapt not installed (agentsec extras required)"
)
class TestCohereGatewayAuthHeaders:
    """_build_cohere_gateway_auth_headers backward compat and custom header."""

    @staticmethod
    def _build(api_key_header="api-key", api_key="cohere-key"):
        from aidefense.runtime.agentsec.patchers.cohere import (
            _build_cohere_gateway_auth_headers,
        )

        gw = GatewaySettings(url="https://gw.example.com", api_key=api_key, api_key_header=api_key_header)
        return _build_cohere_gateway_auth_headers(gw, api_key)

    def test_default_uses_bearer(self):
        headers = self._build()
        assert headers["Authorization"] == "Bearer cohere-key"
        assert "api-key" not in headers

    def test_custom_header_overrides_bearer(self):
        headers = self._build(api_key_header="X-Cohere-Auth")
        assert headers["X-Cohere-Auth"] == "cohere-key"
        assert "Authorization" not in headers

    def test_content_type_always_present(self):
        headers = self._build()
        assert headers["Content-Type"] == "application/json"


# ── config_file: 'enabled' in _KNOWN_TOP_KEYS ───────────────────────


@pytest.mark.skipif(
    not _has_yaml, reason="PyYAML not installed (agentsec extras required)"
)
class TestConfigFileEnabledKey:
    """The 'enabled' top-level key should not trigger an unknown-key warning."""

    def test_enabled_key_not_warned(self, tmp_path):
        from aidefense.runtime.agentsec.config_file import load_config_file

        cfg_file = tmp_path / "agentsec.yaml"
        cfg_file.write_text("enabled: true\nllm_integration_mode: api\n")
        with patch("aidefense.runtime.agentsec.config_file.logger") as mock_logger:
            result = load_config_file(str(cfg_file))
            for call in mock_logger.warning.call_args_list:
                assert "Unknown top-level key 'enabled'" not in str(call)
        assert result["enabled"] is True

    def test_unknown_key_still_warned(self, tmp_path):
        from aidefense.runtime.agentsec.config_file import load_config_file

        cfg_file = tmp_path / "agentsec.yaml"
        cfg_file.write_text("totally_bogus_key: 123\nllm_integration_mode: api\n")
        with patch("aidefense.runtime.agentsec.config_file.logger") as mock_logger:
            load_config_file(str(cfg_file))
            warned_keys = " ".join(str(c) for c in mock_logger.warning.call_args_list)
            assert "totally_bogus_key" in warned_keys


# ── _validate_gateway_entries: reject non-dict ───────────────────────


class TestValidateGatewayEntries:
    """Non-dict gateway entries must raise ConfigurationError."""

    @staticmethod
    def _validate(llm_mode="gateway", mcp_mode="api", gateway_mode=None):
        from aidefense.runtime.agentsec import _validate_gateway_entries

        if gateway_mode is None:
            gateway_mode = {}
        _validate_gateway_entries(llm_mode, mcp_mode, gateway_mode)

    def test_valid_dict_entry_passes(self):
        self._validate(
            gateway_mode={
                "llm_gateways": {
                    "openai": {"gateway_url": "https://gw.example.com"}
                }
            }
        )

    def test_non_dict_llm_entry_raises(self):
        with pytest.raises(ConfigurationError, match="expected a mapping"):
            self._validate(
                gateway_mode={
                    "llm_gateways": {"openai": "https://gw.example.com"}
                }
            )

    def test_non_dict_mcp_entry_raises(self):
        with pytest.raises(ConfigurationError, match="expected a mapping"):
            self._validate(
                llm_mode="api",
                mcp_mode="gateway",
                gateway_mode={
                    "mcp_gateways": {"mcp1": ["not", "a", "dict"]}
                },
            )

    def test_missing_gateway_url_raises(self):
        with pytest.raises(ConfigurationError, match="gateway_url is required"):
            self._validate(
                gateway_mode={
                    "llm_gateways": {"openai": {"auth_mode": "api_key"}}
                }
            )

    def test_invalid_auth_mode_raises(self):
        with pytest.raises(ConfigurationError, match="invalid auth_mode"):
            self._validate(
                gateway_mode={
                    "llm_gateways": {
                        "openai": {
                            "gateway_url": "https://gw.example.com",
                            "auth_mode": "totally_invalid",
                        }
                    }
                }
            )

    def test_api_mode_skips_llm_validation(self):
        """When llm_integration_mode is 'api', llm_gateways are not validated."""
        self._validate(
            llm_mode="api",
            gateway_mode={
                "llm_gateways": {"openai": "this would fail if validated"}
            },
        )
