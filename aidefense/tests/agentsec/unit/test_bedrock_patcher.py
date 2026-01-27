"""Tests for Bedrock patcher."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from aidefense.runtime.agentsec.decision import Decision
from aidefense.runtime.agentsec.exceptions import SecurityPolicyError


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
        
        mock_state.get_llm_mode.return_value = "on_monitor"
        
        with patch("aidefense.runtime.agentsec.patchers.bedrock.get_inspection_context") as mock_ctx:
            mock_ctx.return_value = MagicMock(done=False)
            assert _should_inspect() is True

    @patch("aidefense.runtime.agentsec.patchers.bedrock._state")
    def test_is_gateway_mode(self, mock_state):
        """Test _is_gateway_mode returns correct value."""
        from aidefense.runtime.agentsec.patchers.bedrock import _is_gateway_mode
        
        mock_state.get_llm_integration_mode.return_value = "gateway"
        assert _is_gateway_mode() is True
        
        mock_state.get_llm_integration_mode.return_value = "api"
        assert _is_gateway_mode() is False


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
        
        mock_state.get_llm_mode.return_value = "on_enforce"
        
        decision = Decision(action="block", reasons=["policy_violation"])
        
        with pytest.raises(SecurityPolicyError):
            _enforce_decision(decision)

    @patch("aidefense.runtime.agentsec.patchers.bedrock._state")
    def test_enforce_decision_allows_in_monitor_mode(self, mock_state):
        """Test _enforce_decision allows even blocked content in monitor mode."""
        from aidefense.runtime.agentsec.patchers.bedrock import _enforce_decision
        
        mock_state.get_llm_mode.return_value = "on_monitor"
        
        decision = Decision(action="block", reasons=["policy_violation"])
        
        # Should not raise - monitor mode allows everything
        _enforce_decision(decision)


class TestBedrockGatewayMode:
    """Test Bedrock gateway mode functionality."""

    @patch("aidefense.runtime.agentsec.patchers.bedrock._state")
    def test_should_use_gateway_checks_config(self, mock_state):
        """Test _should_use_gateway checks both mode and credentials."""
        from aidefense.runtime.agentsec.patchers.bedrock import _should_use_gateway
        
        # Gateway mode but no credentials
        mock_state.get_llm_integration_mode.return_value = "gateway"
        mock_state.get_provider_gateway_url.return_value = None
        mock_state.get_provider_gateway_api_key.return_value = None
        assert _should_use_gateway() is False
        
        # Gateway mode with credentials
        mock_state.get_provider_gateway_url.return_value = "https://gateway.example.com"
        mock_state.get_provider_gateway_api_key.return_value = "test-key"
        assert _should_use_gateway() is True
        
        # API mode
        mock_state.get_llm_integration_mode.return_value = "api"
        assert _should_use_gateway() is False

    @patch("aidefense.runtime.agentsec.patchers.bedrock._state")
    @patch("httpx.Client")
    def test_gateway_mode_sends_native_format(self, mock_httpx_client, mock_state):
        """Test gateway mode sends native Bedrock request to gateway."""
        from aidefense.runtime.agentsec.patchers.bedrock import _handle_bedrock_gateway_call
        
        mock_state.get_llm_mode.return_value = "on_monitor"
        mock_state.get_provider_gateway_url.return_value = "https://gateway.example.com"
        mock_state.get_provider_gateway_api_key.return_value = "test-key"
        mock_state.get_gateway_mode_fail_open_llm.return_value = True
        
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
        
        # Use actual function signature: operation_name and api_params
        result = _handle_bedrock_gateway_call(
            operation_name="Converse",
            api_params={
                "modelId": "anthropic.claude-3-haiku-20240307-v1:0",
                "messages": [{"role": "user", "content": [{"text": "test"}]}]
            }
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
        assert _is_bedrock_operation("Converse", {"modelId": "claude"}) is True
        assert _is_bedrock_operation("ConverseStream", {"modelId": "claude"}) is True
        
        # Non-Bedrock operations
        assert _is_bedrock_operation("ListModels", {}) is False

