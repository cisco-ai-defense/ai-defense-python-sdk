"""Tests for Bedrock patcher."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from aidefense.runtime.agentsec.decision import Decision
from aidefense.runtime.agentsec.exceptions import SecurityPolicyError
from aidefense.runtime.agentsec.gateway_settings import GatewaySettings


class TestBuildAwsSession:
    """Tests for the _build_aws_session helper function."""

    @patch("boto3.Session")
    def test_default_fallback(self, mock_session_cls):
        """No AWS fields set: boto3.Session() called with no args, region falls back."""
        from aidefense.runtime.agentsec.patchers.bedrock import _build_aws_session

        mock_session = MagicMock()
        mock_session.get_credentials.return_value = MagicMock()
        mock_session.region_name = None
        mock_session_cls.return_value = mock_session

        gw = GatewaySettings(url="https://gw.example.com", auth_mode="aws_sigv4")
        session, credentials, region = _build_aws_session(gw)

        mock_session_cls.assert_called_once_with()
        assert region == "us-east-1"  # fallback default
        assert credentials is not None

    @patch("boto3.Session")
    def test_profile_based(self, mock_session_cls):
        """aws_region + aws_profile: Session created with both kwargs."""
        from aidefense.runtime.agentsec.patchers.bedrock import _build_aws_session

        mock_session = MagicMock()
        mock_session.get_credentials.return_value = MagicMock()
        mock_session.region_name = "eu-west-1"
        mock_session_cls.return_value = mock_session

        gw = GatewaySettings(
            url="https://gw.example.com",
            auth_mode="aws_sigv4",
            aws_region="eu-west-1",
            aws_profile="team-b",
        )
        session, credentials, region = _build_aws_session(gw)

        mock_session_cls.assert_called_once_with(
            region_name="eu-west-1", profile_name="team-b"
        )
        assert region == "eu-west-1"

    @patch("boto3.Session")
    def test_explicit_keys(self, mock_session_cls):
        """Explicit access key + secret key: Session created with key kwargs."""
        from aidefense.runtime.agentsec.patchers.bedrock import _build_aws_session

        mock_session = MagicMock()
        mock_session.get_credentials.return_value = MagicMock()
        mock_session.region_name = "us-west-2"
        mock_session_cls.return_value = mock_session

        gw = GatewaySettings(
            url="https://gw.example.com",
            auth_mode="aws_sigv4",
            aws_region="us-west-2",
            aws_access_key_id="AKIAEXAMPLE",
            aws_secret_access_key="secret123",
        )
        session, credentials, region = _build_aws_session(gw)

        mock_session_cls.assert_called_once_with(
            region_name="us-west-2",
            aws_access_key_id="AKIAEXAMPLE",
            aws_secret_access_key="secret123",
        )

    @patch("boto3.Session")
    def test_explicit_keys_with_session_token(self, mock_session_cls):
        """Explicit keys + session token: all four kwargs passed."""
        from aidefense.runtime.agentsec.patchers.bedrock import _build_aws_session

        mock_session = MagicMock()
        mock_session.get_credentials.return_value = MagicMock()
        mock_session.region_name = "us-east-1"
        mock_session_cls.return_value = mock_session

        gw = GatewaySettings(
            url="https://gw.example.com",
            auth_mode="aws_sigv4",
            aws_region="us-east-1",
            aws_access_key_id="AKIAEXAMPLE",
            aws_secret_access_key="secret123",
            aws_session_token="token456",
        )
        _build_aws_session(gw)

        mock_session_cls.assert_called_once_with(
            region_name="us-east-1",
            aws_access_key_id="AKIAEXAMPLE",
            aws_secret_access_key="secret123",
            aws_session_token="token456",
        )

    @patch("boto3.Session")
    def test_explicit_keys_ignores_profile(self, mock_session_cls):
        """When both explicit keys AND profile are set, explicit keys take precedence."""
        from aidefense.runtime.agentsec.patchers.bedrock import _build_aws_session

        mock_session = MagicMock()
        mock_session.get_credentials.return_value = MagicMock()
        mock_session.region_name = "us-east-1"
        mock_session_cls.return_value = mock_session

        gw = GatewaySettings(
            url="https://gw.example.com",
            auth_mode="aws_sigv4",
            aws_access_key_id="AKIAEXAMPLE",
            aws_secret_access_key="secret123",
            aws_profile="should-be-ignored",
        )
        _build_aws_session(gw)

        # profile_name should NOT be in the call kwargs
        call_kwargs = mock_session_cls.call_args[1]
        assert "profile_name" not in call_kwargs
        assert call_kwargs["aws_access_key_id"] == "AKIAEXAMPLE"

    @patch("boto3.Session")
    def test_assume_role(self, mock_session_cls):
        """aws_role_arn: calls sts.assume_role and creates a second session."""
        from aidefense.runtime.agentsec.patchers.bedrock import _build_aws_session

        # First session (base)
        mock_base_session = MagicMock()
        mock_base_session.region_name = "us-east-1"
        mock_sts = MagicMock()
        mock_sts.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "ASIAEXAMPLE",
                "SecretAccessKey": "assumed-secret",
                "SessionToken": "assumed-token",
            }
        }
        mock_base_session.client.return_value = mock_sts

        # Second session (assumed)
        mock_assumed_session = MagicMock()
        mock_assumed_session.get_credentials.return_value = MagicMock()
        mock_assumed_session.region_name = "us-east-1"

        mock_session_cls.side_effect = [mock_base_session, mock_assumed_session]

        gw = GatewaySettings(
            url="https://gw.example.com",
            auth_mode="aws_sigv4",
            aws_profile="base-account",
            aws_role_arn="arn:aws:iam::123456789012:role/cross-role",
        )
        session, credentials, region = _build_aws_session(gw)

        # Verify STS was called
        mock_sts.assume_role.assert_called_once_with(
            RoleArn="arn:aws:iam::123456789012:role/cross-role",
            RoleSessionName="agentsec-gateway",
        )
        # Second session should use temp creds
        assert mock_session_cls.call_count == 2
        second_call_kwargs = mock_session_cls.call_args_list[1][1]
        assert second_call_kwargs["aws_access_key_id"] == "ASIAEXAMPLE"
        assert second_call_kwargs["aws_secret_access_key"] == "assumed-secret"
        assert second_call_kwargs["aws_session_token"] == "assumed-token"

    @patch("boto3.Session")
    def test_missing_credentials_returns_none(self, mock_session_cls):
        """When session.get_credentials() returns None, credentials is None."""
        from aidefense.runtime.agentsec.patchers.bedrock import _build_aws_session

        mock_session = MagicMock()
        mock_session.get_credentials.return_value = None
        mock_session.region_name = "us-east-1"
        mock_session_cls.return_value = mock_session

        gw = GatewaySettings(url="https://gw.example.com", auth_mode="aws_sigv4")
        session, credentials, region = _build_aws_session(gw)

        assert credentials is None

    @patch("aidefense.runtime.agentsec.patchers.bedrock._build_aws_session")
    @patch("httpx.Client")
    def test_gateway_mode_aws_sigv4_uses_build_session(self, mock_httpx_client, mock_build):
        """Gateway mode with aws_sigv4 calls _build_aws_session with gw_settings."""
        from aidefense.runtime.agentsec.patchers.bedrock import _handle_bedrock_gateway_call

        mock_credentials = MagicMock()
        mock_credentials.access_key = "AKIAEXAMPLE"
        mock_credentials.secret_key = "secret"
        mock_credentials.token = None
        mock_build.return_value = (MagicMock(), mock_credentials, "us-east-1")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "output": {"message": {"content": [{"text": "Hi"}]}},
            "ResponseMetadata": {},
        }
        mock_client_instance = MagicMock()
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_client_instance.post.return_value = mock_response
        mock_httpx_client.return_value = mock_client_instance

        gw_settings = GatewaySettings(
            url="https://gateway.example.com",
            auth_mode="aws_sigv4",
            aws_region="eu-west-1",
            aws_profile="team-b",
        )

        with patch("botocore.auth.SigV4Auth"):
            _handle_bedrock_gateway_call(
                operation_name="Converse",
                api_params={
                    "modelId": "anthropic.claude-3-haiku-20240307-v1:0",
                    "messages": [{"role": "user", "content": [{"text": "test"}]}],
                },
                gw_settings=gw_settings,
            )

        mock_build.assert_called_once_with(gw_settings)


class TestBedrockPatcher:
    """Test Bedrock patching functionality."""

    def test_patch_skips_when_not_installed(self):
        """Test patching is skipped when boto3 is not installed."""
        with patch("aidefense.runtime.agentsec.patchers.bedrock.safe_import", return_value=None):
            from aidefense.runtime.agentsec.patchers.bedrock import patch_bedrock
            
            result = patch_bedrock()
            assert result is False

    def test_patch_skips_when_already_patched(self):
        """Test patching is skipped when already patched."""
        with patch("aidefense.runtime.agentsec.patchers.bedrock.is_patched", return_value=True):
            from aidefense.runtime.agentsec.patchers.bedrock import patch_bedrock
            
            result = patch_bedrock()
            assert result is True

    @patch("aidefense.runtime.agentsec.patchers.bedrock._state")
    def test_should_inspect_returns_false_when_off(self, mock_state):
        """Test _should_inspect returns False when mode is off."""
        from aidefense.runtime.agentsec.patchers.bedrock import _should_inspect
        
        mock_state.get_llm_mode.return_value = "off"
        
        assert _should_inspect() is False

    @patch("aidefense.runtime.agentsec.patchers.bedrock._state")
    def test_should_inspect_returns_true_when_monitor(self, mock_state):
        """Test _should_inspect returns True when mode is monitor."""
        from aidefense.runtime.agentsec.patchers.bedrock import _should_inspect
        
        mock_state.get_llm_mode.return_value = "monitor"
        
        with patch("aidefense.runtime.agentsec.patchers.bedrock.get_inspection_context") as mock_ctx:
            mock_ctx.return_value = MagicMock(done=False)
            assert _should_inspect() is True

    @patch("aidefense.runtime.agentsec.patchers._base._state")
    def test_integration_mode_affects_resolve_gateway(self, mock_state):
        """Test resolve_gateway_settings returns None when integration mode is api."""
        from aidefense.runtime.agentsec.patchers._base import resolve_gateway_settings
        
        mock_state.get_llm_integration_mode.return_value = "api"
        # When api mode, resolve_gateway_settings returns None regardless of providers
        result = resolve_gateway_settings("bedrock")
        assert result is None
        
        mock_state.get_llm_integration_mode.return_value = "gateway"
        # When gateway mode but no default gateway for provider, raises SecurityPolicyError
        mock_state.get_llm_gateway.return_value = None
        mock_state.get_default_gateway_for_provider.return_value = None
        with pytest.raises(SecurityPolicyError, match="no gateway configuration found for provider"):
            resolve_gateway_settings("bedrock")


class TestBedrockMessageParsing:
    """Test message parsing functions."""

    def test_parse_converse_messages(self):
        """Test parsing Converse API messages to standard format."""
        from aidefense.runtime.agentsec.patchers.bedrock import _parse_converse_messages
        
        api_params = {
            "modelId": "anthropic.claude-3-haiku-20240307-v1:0",
            "messages": [
                {"role": "user", "content": [{"text": "Hello"}]},
                {"role": "assistant", "content": [{"text": "Hi there"}]},
            ]
        }
        
        result = _parse_converse_messages(api_params)
        
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello"
        assert result[1]["role"] == "assistant"

    def test_parse_converse_messages_with_tool_use(self):
        """Test parsing messages with tool use blocks."""
        from aidefense.runtime.agentsec.patchers.bedrock import _parse_converse_messages
        
        api_params = {
            "modelId": "anthropic.claude-3-haiku-20240307-v1:0",
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {"text": "Let me check that for you."},
                        {"toolUse": {"toolUseId": "123", "name": "weather", "input": {}}}
                    ]
                }
            ]
        }
        
        result = _parse_converse_messages(api_params)
        
        assert len(result) == 1
        # Should include text content
        assert "Let me check" in result[0]["content"]


class TestBedrockInspection:
    """Test Bedrock inspection flow."""

    def test_wrap_make_api_call_skips_non_bedrock_ops(self):
        """Test make_api_call wrapper skips non-Bedrock operations."""
        from aidefense.runtime.agentsec.patchers.bedrock import _wrap_make_api_call
        
        mock_response = {"Models": []}
        mock_wrapped = MagicMock(return_value=mock_response)
        mock_instance = MagicMock()
        
        with patch("aidefense.runtime.agentsec.patchers.bedrock._is_bedrock_operation", return_value=False):
            result = _wrap_make_api_call(
                mock_wrapped, mock_instance,
                ("ListFoundationModels",),
                {}
            )
        
        # Should call wrapped directly without inspection
        mock_wrapped.assert_called_once()

    @patch("aidefense.runtime.agentsec.patchers.bedrock._state")
    def test_enforce_decision_raises_on_block(self, mock_state):
        """Test _enforce_decision raises SecurityPolicyError on block."""
        from aidefense.runtime.agentsec.patchers.bedrock import _enforce_decision
        
        mock_state.get_llm_mode.return_value = "enforce"
        
        decision = Decision(action="block", reasons=["policy_violation"])
        
        with pytest.raises(SecurityPolicyError):
            _enforce_decision(decision)

    @patch("aidefense.runtime.agentsec.patchers.bedrock._state")
    def test_enforce_decision_allows_in_monitor_mode(self, mock_state):
        """Test _enforce_decision allows even blocked content in monitor mode."""
        from aidefense.runtime.agentsec.patchers.bedrock import _enforce_decision
        
        mock_state.get_llm_mode.return_value = "monitor"
        
        decision = Decision(action="block", reasons=["policy_violation"])
        
        # Should not raise - monitor mode allows everything
        _enforce_decision(decision)


class TestBedrockGatewayMode:
    """Test Bedrock gateway mode functionality."""

    @patch("aidefense.runtime.agentsec.patchers._base._state")
    def test_resolve_gateway_settings_checks_mode_and_provider(self, mock_state):
        """Test resolve_gateway_settings returns GatewaySettings when gateway mode + provider configured."""
        from aidefense.runtime.agentsec.patchers._base import resolve_gateway_settings
        
        with patch("aidefense.runtime.agentsec.patchers._base.is_llm_skip_active", return_value=False):
            with patch("aidefense.runtime.agentsec.patchers._base.get_active_gateway", return_value=None):
                # Gateway mode with provider config
                mock_state.get_llm_integration_mode.return_value = "gateway"
                mock_state.get_default_gateway_for_provider.return_value = {
                    "gateway_url": "https://gateway.example.com",
                    "gateway_api_key": "test-key",
                }
                mock_state.resolve_llm_gateway_settings.side_effect = lambda cfg, **kw: MagicMock(
                    url=cfg.get("gateway_url", ""),
                    api_key=cfg.get("gateway_api_key"),
                )
                result = resolve_gateway_settings("bedrock")
                assert result is not None
                assert result.url == "https://gateway.example.com"
                assert result.api_key == "test-key"
                
                # API mode returns None
                mock_state.get_llm_integration_mode.return_value = "api"
                result = resolve_gateway_settings("bedrock")
                assert result is None

    @patch("httpx.Client")
    def test_gateway_mode_sends_native_format(self, mock_httpx_client):
        """Test gateway mode sends native Bedrock request to gateway."""
        from aidefense.runtime.agentsec.patchers.bedrock import _handle_bedrock_gateway_call
        from aidefense.runtime.agentsec.gateway_settings import GatewaySettings
        
        gw_settings = GatewaySettings(
            url="https://gateway.example.com",
            api_key="test-key",
            fail_open=True,
        )
        
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "output": {"message": {"content": [{"text": "Hi"}]}},
            "ResponseMetadata": {}
        }
        mock_client_instance = MagicMock()
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_client_instance.post.return_value = mock_response
        mock_httpx_client.return_value = mock_client_instance
        
        result = _handle_bedrock_gateway_call(
            operation_name="Converse",
            api_params={
                "modelId": "anthropic.claude-3-haiku-20240307-v1:0",
                "messages": [{"role": "user", "content": [{"text": "test"}]}]
            },
            gw_settings=gw_settings,
        )
        
        # Verify HTTP call was made
        mock_client_instance.post.assert_called_once()


class TestBedrockResponseParsing:
    """Test response parsing functions."""

    def test_parse_bedrock_response(self):
        """Test parsing content from Bedrock InvokeModel response."""
        from aidefense.runtime.agentsec.patchers.bedrock import _parse_bedrock_response
        import json
        
        # Simulate InvokeModel response body (Anthropic format)
        response_body = json.dumps({
            "content": [{"type": "text", "text": "Hello world"}],
            "stop_reason": "end_turn"
        }).encode()
        
        result = _parse_bedrock_response(response_body, "anthropic.claude-3-haiku-20240307-v1:0")
        
        assert "Hello world" in result

    def test_is_bedrock_operation(self):
        """Test checking if operation is a Bedrock LLM operation."""
        from aidefense.runtime.agentsec.patchers.bedrock import _is_bedrock_operation
        
        # Converse operations
        assert _is_bedrock_operation("Converse") is True
        assert _is_bedrock_operation("ConverseStream") is True
        
        # Non-Bedrock operations
        assert _is_bedrock_operation("ListModels") is False

