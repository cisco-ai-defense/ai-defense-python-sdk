"""Tests for the shared resolve_gateway_settings() in patchers/_base.py."""

import pytest

from aidefense.runtime.agentsec import _state
from aidefense.runtime.agentsec._context import gateway
from aidefense.runtime.agentsec.exceptions import SecurityPolicyError
from aidefense.runtime.agentsec.patchers._base import resolve_gateway_settings


@pytest.fixture(autouse=True)
def reset_state():
    """Reset state before and after each test."""
    _state.reset()
    yield
    _state.reset()


class TestResolveGatewaySettings:
    """Tests for the shared LLM gateway resolver."""

    def test_returns_none_when_api_mode(self):
        """When integration mode is 'api', resolver returns None."""
        _state.set_state(
            initialized=True,
            llm_integration_mode="api",
        )
        assert resolve_gateway_settings("openai") is None

    def test_returns_none_when_gateway_mode_off(self):
        """When gateway mode is active but llm_mode is 'off', resolver returns None."""
        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            gateway_mode={
                "llm_mode": "off",
                "llm_gateways": {
                    "openai-1": {
                        "gateway_url": "https://gw/openai",
                        "gateway_api_key": "k",
                        "provider": "openai",
                        "default": True,
                    },
                },
            },
        )
        assert resolve_gateway_settings("openai") is None

    def test_raises_when_no_provider_config(self):
        """When gateway mode but no provider configured, raises SecurityPolicyError."""
        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
        )
        with pytest.raises(SecurityPolicyError, match="no gateway configuration found for provider"):
            resolve_gateway_settings("openai")

    def test_raises_when_gateways_exist_but_no_default(self):
        """Named gateways exist for provider, but none marked default -- raises."""
        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            gateway_mode={
                "llm_gateways": {
                    "openai-special": {
                        "gateway_url": "https://special.example.com",
                        "gateway_api_key": "key",
                        "provider": "openai",
                        # no default: true
                    },
                },
            },
        )
        # Without an active named gateway, raises because no default is set
        with pytest.raises(SecurityPolicyError, match="no gateway configuration found for provider"):
            resolve_gateway_settings("openai")

        # But with a named gateway context, it resolves
        with gateway("openai-special"):
            settings = resolve_gateway_settings("openai")
            assert settings is not None
            assert settings.url == "https://special.example.com"

    def test_returns_provider_default(self):
        """When provider is configured, returns its settings."""
        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            gateway_mode={
                "llm_gateways": {
                    "openai-1": {
                        "gateway_url": "https://gw.example.com/openai",
                        "gateway_api_key": "key-123",
                        "provider": "openai",
                        "default": True,
                    },
                },
            },
        )
        settings = resolve_gateway_settings("openai")
        assert settings is not None
        assert settings.url == "https://gw.example.com/openai"
        assert settings.api_key == "key-123"
        assert settings.auth_mode == "api_key"

    def test_named_gateway_overrides_provider(self):
        """When a named gateway is active and matches, it wins over provider."""
        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            gateway_mode={
                "llm_gateways": {
                    "openai-1": {
                        "gateway_url": "https://provider.example.com",
                        "gateway_api_key": "provider-key",
                        "provider": "openai",
                        "default": True,
                    },
                    "math-gw": {
                        "gateway_url": "https://math.example.com",
                        "gateway_api_key": "math-key",
                        "provider": "openai",
                    },
                },
            },
        )

        # Without gateway context, returns provider default
        settings = resolve_gateway_settings("openai")
        assert settings.url == "https://provider.example.com"

        # With gateway context, returns named gateway
        with gateway("math-gw"):
            settings = resolve_gateway_settings("openai")
            assert settings.url == "https://math.example.com"
            assert settings.api_key == "math-key"

    def test_named_gateway_provider_mismatch_falls_through(self):
        """Named gateway scoped to 'openai' is not used for 'bedrock' calls."""
        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            gateway_mode={
                "llm_gateways": {
                    "bedrock-1": {
                        "gateway_url": "https://bedrock-default.example.com",
                        "gateway_api_key": "bedrock-key",
                        "provider": "bedrock",
                        "default": True,
                    },
                    "openai-gw": {
                        "gateway_url": "https://openai.example.com",
                        "gateway_api_key": "openai-key",
                        "provider": "openai",
                    },
                },
            },
        )

        with gateway("openai-gw"):
            # For bedrock calls, the openai-scoped gateway doesn't apply
            settings = resolve_gateway_settings("bedrock")
            assert settings.url == "https://bedrock-default.example.com"

    def test_named_gateway_no_provider_field(self):
        """Named gateway without provider field applies to any provider."""
        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            gateway_mode={
                "llm_gateways": {
                    "catch-all-gw": {
                        "gateway_url": "https://catch-all.example.com",
                        "gateway_api_key": "catch-all-key",
                    },
                },
            },
        )
        with gateway("catch-all-gw"):
            settings = resolve_gateway_settings("openai")
            assert settings.url == "https://catch-all.example.com"
            settings = resolve_gateway_settings("bedrock")
            assert settings.url == "https://catch-all.example.com"

    def test_auth_mode_inherited_from_provider(self):
        """Named gateway inherits auth_mode from its provider config."""
        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            gateway_mode={
                "llm_gateways": {
                    "bedrock-1": {
                        "gateway_url": "https://bedrock.example.com",
                        "auth_mode": "aws_sigv4",
                        "provider": "bedrock",
                        "default": True,
                    },
                    "bedrock-2": {
                        "gateway_url": "https://analytics.example.com",
                        "provider": "bedrock",
                        # No auth_mode -- should inherit aws_sigv4
                    },
                },
            },
        )
        with gateway("bedrock-2"):
            settings = resolve_gateway_settings("bedrock")
            assert settings.auth_mode == "aws_sigv4"

    def test_settings_inherit_defaults(self):
        """Provider config with no timeout/retry inherits llm_defaults."""
        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            gateway_mode={
                "llm_defaults": {
                    "fail_open": False,
                    "timeout": 5,
                    "retry": {
                        "total": 10,
                    },
                },
                "llm_gateways": {
                    "openai-1": {
                        "gateway_url": "https://gw.example.com",
                        "gateway_api_key": "key",
                        "provider": "openai",
                        "default": True,
                    },
                },
            },
        )
        settings = resolve_gateway_settings("openai")
        assert settings.fail_open is False
        assert settings.timeout == 5
        assert settings.retry_total == 10

    def test_per_gateway_override_beats_defaults(self):
        """Per-gateway settings override llm_defaults."""
        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            gateway_mode={
                "llm_defaults": {
                    "fail_open": True,
                    "timeout": 1,
                },
                "llm_gateways": {
                    "openai-1": {
                        "gateway_url": "https://gw.example.com",
                        "gateway_api_key": "key",
                        "provider": "openai",
                        "default": True,
                        "fail_open": False,
                        "timeout": 99,
                    },
                },
            },
        )
        settings = resolve_gateway_settings("openai")
        assert settings.fail_open is False
        assert settings.timeout == 99

    def test_aws_fields_carried_through(self):
        """All six AWS fields are carried through to resolved GatewaySettings."""
        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            gateway_mode={
                "llm_gateways": {
                    "bedrock-1": {
                        "gateway_url": "https://bedrock.example.com",
                        "auth_mode": "aws_sigv4",
                        "provider": "bedrock",
                        "default": True,
                        "aws_region": "eu-west-1",
                        "aws_profile": "team-b",
                        "aws_access_key_id": "AKIAEXAMPLE",
                        "aws_secret_access_key": "secret123",
                        "aws_session_token": "token456",
                        "aws_role_arn": "arn:aws:iam::123456789012:role/test",
                    },
                },
            },
        )
        settings = resolve_gateway_settings("bedrock")
        assert settings.aws_region == "eu-west-1"
        assert settings.aws_profile == "team-b"
        assert settings.aws_access_key_id == "AKIAEXAMPLE"
        assert settings.aws_secret_access_key == "secret123"
        assert settings.aws_session_token == "token456"
        assert settings.aws_role_arn == "arn:aws:iam::123456789012:role/test"

    def test_aws_fields_none_when_not_set(self):
        """AWS fields default to None when not configured on the gateway."""
        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            gateway_mode={
                "llm_gateways": {
                    "bedrock-1": {
                        "gateway_url": "https://bedrock.example.com",
                        "auth_mode": "aws_sigv4",
                        "provider": "bedrock",
                        "default": True,
                    },
                },
            },
        )
        settings = resolve_gateway_settings("bedrock")
        assert settings.aws_region is None
        assert settings.aws_profile is None
        assert settings.aws_access_key_id is None
        assert settings.aws_secret_access_key is None
        assert settings.aws_session_token is None
        assert settings.aws_role_arn is None

    def test_gcp_fields_carried_through(self):
        """All 4 GCP fields are carried through when configured on the gateway."""
        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            gateway_mode={
                "llm_gateways": {
                    "vertexai-1": {
                        "gateway_url": "https://vertexai.example.com",
                        "auth_mode": "google_adc",
                        "provider": "vertexai",
                        "default": True,
                        "gcp_project": "my-project",
                        "gcp_location": "us-central1",
                        "gcp_service_account_key_file": "/path/to/key.json",
                        "gcp_target_service_account": "sa@project.iam.gserviceaccount.com",
                    },
                },
            },
        )
        settings = resolve_gateway_settings("vertexai")
        assert settings.gcp_project == "my-project"
        assert settings.gcp_location == "us-central1"
        assert settings.gcp_service_account_key_file == "/path/to/key.json"
        assert settings.gcp_target_service_account == "sa@project.iam.gserviceaccount.com"

    def test_gcp_fields_none_when_not_set(self):
        """GCP fields default to None when not configured on the gateway."""
        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            gateway_mode={
                "llm_gateways": {
                    "vertexai-1": {
                        "gateway_url": "https://vertexai.example.com",
                        "auth_mode": "google_adc",
                        "provider": "vertexai",
                        "default": True,
                    },
                },
            },
        )
        settings = resolve_gateway_settings("vertexai")
        assert settings.gcp_project is None
        assert settings.gcp_location is None
        assert settings.gcp_service_account_key_file is None
        assert settings.gcp_target_service_account is None

    def test_skip_inspection_returns_none(self):
        """When skip_inspection is active, resolver returns None."""
        from aidefense.runtime.agentsec._context import skip_inspection

        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            gateway_mode={
                "llm_gateways": {
                    "openai-1": {
                        "gateway_url": "https://gw.example.com",
                        "gateway_api_key": "key",
                        "provider": "openai",
                        "default": True,
                    },
                },
            },
        )
        with skip_inspection(llm=True):
            assert resolve_gateway_settings("openai") is None
