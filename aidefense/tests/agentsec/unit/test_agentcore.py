"""Tests for AgentCore patcher functionality."""

import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from aidefense.runtime.agentsec.decision import Decision
from aidefense.runtime.agentsec.exceptions import SecurityPolicyError


class TestAgentCoreServiceDetection:
    """Test AgentCore service detection functions."""

    def test_is_agentcore_client_true(self):
        """Test _is_agentcore_client returns True for agentcore service."""
        from aidefense.runtime.agentsec.patchers.bedrock import _is_agentcore_client
        
        mock_instance = MagicMock()
        mock_service_model = MagicMock()
        mock_service_model.service_name = 'bedrock-agentcore'
        mock_instance._service_model = mock_service_model
        
        assert _is_agentcore_client(mock_instance) is True

    def test_is_agentcore_client_false_for_bedrock(self):
        """Test _is_agentcore_client returns False for bedrock-runtime service."""
        from aidefense.runtime.agentsec.patchers.bedrock import _is_agentcore_client
        
        mock_instance = MagicMock()
        mock_service_model = MagicMock()
        mock_service_model.service_name = 'bedrock-runtime'
        mock_instance._service_model = mock_service_model
        
        assert _is_agentcore_client(mock_instance) is False

    def test_is_agentcore_client_false_for_other_service(self):
        """Test _is_agentcore_client returns False for other services."""
        from aidefense.runtime.agentsec.patchers.bedrock import _is_agentcore_client
        
        mock_instance = MagicMock()
        mock_service_model = MagicMock()
        mock_service_model.service_name = 's3'
        mock_instance._service_model = mock_service_model
        
        assert _is_agentcore_client(mock_instance) is False

    def test_is_agentcore_client_handles_missing_service_model(self):
        """Test _is_agentcore_client handles missing service model gracefully."""
        from aidefense.runtime.agentsec.patchers.bedrock import _is_agentcore_client
        
        mock_instance = MagicMock(spec=[])  # No _service_model attribute
        
        assert _is_agentcore_client(mock_instance) is False

    def test_is_agentcore_operation_true(self):
        """Test _is_agentcore_operation returns True for InvokeAgentRuntime."""
        from aidefense.runtime.agentsec.patchers.bedrock import _is_agentcore_operation
        
        mock_instance = MagicMock()
        mock_service_model = MagicMock()
        mock_service_model.service_name = 'bedrock-agentcore'
        mock_instance._service_model = mock_service_model
        
        assert _is_agentcore_operation("InvokeAgentRuntime", mock_instance) is True

    def test_is_agentcore_operation_false_for_wrong_operation(self):
        """Test _is_agentcore_operation returns False for non-AgentCore operations."""
        from aidefense.runtime.agentsec.patchers.bedrock import _is_agentcore_operation
        
        mock_instance = MagicMock()
        mock_service_model = MagicMock()
        mock_service_model.service_name = 'bedrock-agentcore'
        mock_instance._service_model = mock_service_model
        
        assert _is_agentcore_operation("Converse", mock_instance) is False

    def test_is_agentcore_operation_false_for_wrong_service(self):
        """Test _is_agentcore_operation returns False for wrong service."""
        from aidefense.runtime.agentsec.patchers.bedrock import _is_agentcore_operation
        
        mock_instance = MagicMock()
        mock_service_model = MagicMock()
        mock_service_model.service_name = 'bedrock-runtime'
        mock_instance._service_model = mock_service_model
        
        assert _is_agentcore_operation("InvokeAgentRuntime", mock_instance) is False


class TestAgentCorePayloadParsing:
    """Test AgentCore payload parsing functions."""

    def test_parse_converse_format_messages(self):
        """Test parsing Bedrock Converse format payload."""
        from aidefense.runtime.agentsec.patchers.bedrock import _parse_agentcore_payload
        
        payload = json.dumps({
            "messages": [
                {"role": "user", "content": [{"text": "Hello"}]},
                {"role": "assistant", "content": [{"text": "Hi there"}]},
            ]
        }).encode()
        
        result = _parse_agentcore_payload(payload)
        
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello"
        assert result[1]["role"] == "assistant"
        assert result[1]["content"] == "Hi there"

    def test_parse_converse_format_with_system(self):
        """Test parsing Converse format with system prompt."""
        from aidefense.runtime.agentsec.patchers.bedrock import _parse_agentcore_payload
        
        payload = json.dumps({
            "messages": [
                {"role": "user", "content": [{"text": "Hello"}]},
            ],
            "system": [{"text": "You are a helpful assistant"}]
        }).encode()
        
        result = _parse_agentcore_payload(payload)
        
        assert len(result) == 2
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "You are a helpful assistant"
        assert result[1]["role"] == "user"

    def test_parse_simple_prompt_format(self):
        """Test parsing simple prompt format."""
        from aidefense.runtime.agentsec.patchers.bedrock import _parse_agentcore_payload
        
        payload = json.dumps({"prompt": "What is the weather?"}).encode()
        
        result = _parse_agentcore_payload(payload)
        
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "What is the weather?"

    def test_parse_query_format(self):
        """Test parsing query format."""
        from aidefense.runtime.agentsec.patchers.bedrock import _parse_agentcore_payload
        
        payload = json.dumps({"query": "Search for documents"}).encode()
        
        result = _parse_agentcore_payload(payload)
        
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Search for documents"

    def test_parse_input_format(self):
        """Test parsing input format."""
        from aidefense.runtime.agentsec.patchers.bedrock import _parse_agentcore_payload
        
        payload = json.dumps({"input": "Process this data"}).encode()
        
        result = _parse_agentcore_payload(payload)
        
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Process this data"

    def test_parse_text_format(self):
        """Test parsing text format."""
        from aidefense.runtime.agentsec.patchers.bedrock import _parse_agentcore_payload
        
        payload = json.dumps({"text": "Analyze this"}).encode()
        
        result = _parse_agentcore_payload(payload)
        
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Analyze this"

    def test_parse_plain_text_payload(self):
        """Test parsing non-JSON plain text payload."""
        from aidefense.runtime.agentsec.patchers.bedrock import _parse_agentcore_payload
        
        payload = b"This is just plain text"
        
        result = _parse_agentcore_payload(payload)
        
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "This is just plain text"

    def test_parse_empty_payload(self):
        """Test parsing empty payload."""
        from aidefense.runtime.agentsec.patchers.bedrock import _parse_agentcore_payload
        
        result = _parse_agentcore_payload(b"")
        
        assert result == []

    def test_parse_string_payload(self):
        """Test parsing string (not bytes) payload."""
        from aidefense.runtime.agentsec.patchers.bedrock import _parse_agentcore_payload
        
        payload = json.dumps({"prompt": "Hello"})
        
        result = _parse_agentcore_payload(payload)
        
        assert len(result) == 1
        assert result[0]["content"] == "Hello"


class TestAgentCoreResponseParsing:
    """Test AgentCore response parsing functions."""

    def test_parse_converse_format_response(self):
        """Test parsing Bedrock Converse format response."""
        from aidefense.runtime.agentsec.patchers.bedrock import _parse_agentcore_response
        
        response = json.dumps({
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "Hello! How can I help?"}]
                }
            }
        }).encode()
        
        result = _parse_agentcore_response(response)
        
        assert result == "Hello! How can I help?"

    def test_parse_simple_response_format(self):
        """Test parsing simple response format."""
        from aidefense.runtime.agentsec.patchers.bedrock import _parse_agentcore_response
        
        response = json.dumps({"response": "This is the response"}).encode()
        
        result = _parse_agentcore_response(response)
        
        assert result == "This is the response"

    def test_parse_completion_format(self):
        """Test parsing completion format."""
        from aidefense.runtime.agentsec.patchers.bedrock import _parse_agentcore_response
        
        response = json.dumps({"completion": "Generated completion"}).encode()
        
        result = _parse_agentcore_response(response)
        
        assert result == "Generated completion"

    def test_parse_content_format(self):
        """Test parsing content format."""
        from aidefense.runtime.agentsec.patchers.bedrock import _parse_agentcore_response
        
        response = json.dumps({"content": "Content here"}).encode()
        
        result = _parse_agentcore_response(response)
        
        assert result == "Content here"

    def test_parse_text_response_format(self):
        """Test parsing text response format."""
        from aidefense.runtime.agentsec.patchers.bedrock import _parse_agentcore_response
        
        response = json.dumps({"text": "Text response"}).encode()
        
        result = _parse_agentcore_response(response)
        
        assert result == "Text response"

    def test_parse_output_string_format(self):
        """Test parsing output as string format."""
        from aidefense.runtime.agentsec.patchers.bedrock import _parse_agentcore_response
        
        response = json.dumps({"output": "Direct output string"}).encode()
        
        result = _parse_agentcore_response(response)
        
        assert result == "Direct output string"

    def test_parse_result_format(self):
        """Test parsing result format (used by AgentCore agents)."""
        from aidefense.runtime.agentsec.patchers.bedrock import _parse_agentcore_response
        
        response = json.dumps({"result": "The answer is 42"}).encode()
        
        result = _parse_agentcore_response(response)
        
        assert result == "The answer is 42"

    def test_parse_plain_text_response(self):
        """Test parsing non-JSON plain text response."""
        from aidefense.runtime.agentsec.patchers.bedrock import _parse_agentcore_response
        
        response = b"Plain text response"
        
        result = _parse_agentcore_response(response)
        
        assert result == "Plain text response"

    def test_parse_empty_response(self):
        """Test parsing empty response."""
        from aidefense.runtime.agentsec.patchers.bedrock import _parse_agentcore_response
        
        result = _parse_agentcore_response(b"")
        
        assert result == ""

    def test_parse_string_response(self):
        """Test parsing string (not bytes) response."""
        from aidefense.runtime.agentsec.patchers.bedrock import _parse_agentcore_response
        
        response = json.dumps({"response": "Hello"})
        
        result = _parse_agentcore_response(response)
        
        assert result == "Hello"

    def test_parse_streaming_body_response(self):
        """Test parsing StreamingBody-like response (has read method)."""
        from aidefense.runtime.agentsec.patchers.bedrock import _parse_agentcore_response
        import io
        
        # Create a StreamingBody-like object
        class MockStreamingBody:
            def __init__(self, content):
                self._content = content
            def read(self):
                return self._content
        
        response = MockStreamingBody(json.dumps({"result": "Streamed result"}).encode())
        
        result = _parse_agentcore_response(response)
        
        assert result == "Streamed result"

    def test_parse_bytesio_response(self):
        """Test parsing BytesIO response."""
        from aidefense.runtime.agentsec.patchers.bedrock import _parse_agentcore_response
        import io
        
        response = io.BytesIO(json.dumps({"result": "BytesIO result"}).encode())
        
        result = _parse_agentcore_response(response)
        
        assert result == "BytesIO result"


class TestAgentCoreGatewayMode:
    """Test AgentCore gateway mode functionality."""

    @patch("aidefense.runtime.agentsec.patchers.bedrock._state")
    def test_should_use_agentcore_gateway_checks_config(self, mock_state):
        """Test _should_use_agentcore_gateway checks gateway URL."""
        from aidefense.runtime.agentsec.patchers.bedrock import _should_use_agentcore_gateway
        
        # Gateway mode but no URL
        mock_state.get_llm_integration_mode.return_value = "gateway"
        mock_state.get_provider_gateway_url.return_value = None
        assert _should_use_agentcore_gateway() is False
        
        # Gateway mode with URL (no API key needed for Sig V4)
        mock_state.get_provider_gateway_url.return_value = "https://gateway.example.com"
        assert _should_use_agentcore_gateway() is True
        
        # API mode
        mock_state.get_llm_integration_mode.return_value = "api"
        assert _should_use_agentcore_gateway() is False

    @patch("aidefense.runtime.agentsec.patchers.bedrock._state")
    @patch("boto3.Session")
    @patch("httpx.Client")
    def test_gateway_mode_uses_sig_v4(self, mock_httpx_client, mock_boto3_session, mock_state):
        """Test gateway mode uses AWS Sig V4 authentication."""
        from aidefense.runtime.agentsec.patchers.bedrock import _handle_agentcore_gateway_call
        
        mock_state.get_provider_gateway_url.return_value = "https://gateway.example.com"
        mock_state.get_gateway_mode_fail_open_llm.return_value = True
        
        # Mock boto3 session and credentials
        mock_session = MagicMock()
        mock_credentials = MagicMock()
        mock_credentials.access_key = "test-access-key"
        mock_credentials.secret_key = "test-secret-key"
        mock_credentials.token = None
        mock_session.get_credentials.return_value = mock_credentials
        mock_session.region_name = "us-east-1"
        mock_boto3_session.return_value = mock_session
        
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "payload": json.dumps({"response": "Hello"})
        }
        mock_client_instance = MagicMock()
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_client_instance.post.return_value = mock_response
        mock_httpx_client.return_value = mock_client_instance
        
        mock_instance = MagicMock()
        
        with patch("botocore.auth.SigV4Auth") as mock_sig_v4:
            result = _handle_agentcore_gateway_call(
                operation_name="InvokeAgentRuntime",
                api_params={
                    "agentRuntimeArn": "arn:aws:bedrock:us-east-1:123:agent-runtime/test",
                    "runtimeSessionId": "session-123",
                    "payload": json.dumps({"prompt": "Hello"})
                },
                instance=mock_instance
            )
        
        # Verify Sig V4 was called
        mock_sig_v4.assert_called_once()
        # Verify HTTP call was made
        mock_client_instance.post.assert_called_once()

    @patch("aidefense.runtime.agentsec.patchers.bedrock._state")
    def test_gateway_mode_raises_when_not_configured(self, mock_state):
        """Test gateway mode raises error when not configured."""
        from aidefense.runtime.agentsec.patchers.bedrock import _handle_agentcore_gateway_call
        
        mock_state.get_provider_gateway_url.return_value = None
        
        mock_instance = MagicMock()
        
        with pytest.raises(SecurityPolicyError) as exc_info:
            _handle_agentcore_gateway_call(
                operation_name="InvokeAgentRuntime",
                api_params={
                    "agentRuntimeArn": "arn:aws:bedrock:us-east-1:123:agent-runtime/test",
                    "payload": b"{}"
                },
                instance=mock_instance
            )
        
        assert "AGENTSEC_AGENTCORE_GATEWAY_URL" in str(exc_info.value)


class TestAgentCoreApiMode:
    """Test AgentCore API mode functionality."""

    @patch("aidefense.runtime.agentsec.patchers.bedrock._state")
    @patch("aidefense.runtime.agentsec.patchers.bedrock._get_inspector")
    @patch("aidefense.runtime.agentsec.patchers.bedrock.get_inspection_context")
    @patch("aidefense.runtime.agentsec.patchers.bedrock.set_inspection_context")
    def test_api_mode_inspects_request(self, mock_set_ctx, mock_get_ctx, mock_get_inspector, mock_state):
        """Test API mode inspects request before calling."""
        from aidefense.runtime.agentsec.patchers.bedrock import _handle_agentcore_api_mode
        
        mock_state.get_llm_mode.return_value = "on_monitor"
        mock_state.get_llm_integration_mode.return_value = "api"
        
        mock_ctx = MagicMock()
        mock_ctx.metadata = {}
        mock_get_ctx.return_value = mock_ctx
        
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = Decision.allow()
        mock_get_inspector.return_value = mock_inspector
        
        mock_wrapped = MagicMock()
        mock_wrapped.return_value = {"payload": json.dumps({"response": "Hello"})}
        
        result = _handle_agentcore_api_mode(
            operation_name="InvokeAgentRuntime",
            api_params={
                "agentRuntimeArn": "arn:aws:bedrock:us-east-1:123:agent-runtime/test",
                "payload": json.dumps({"prompt": "Hello"})
            },
            wrapped=mock_wrapped,
            args=(),
            kwargs={}
        )
        
        # Verify inspection was called
        assert mock_inspector.inspect_conversation.call_count >= 1

    @patch("aidefense.runtime.agentsec.patchers.bedrock._state")
    @patch("aidefense.runtime.agentsec.patchers.bedrock._get_inspector")
    @patch("aidefense.runtime.agentsec.patchers.bedrock.get_inspection_context")
    def test_api_mode_enforces_block_decision(self, mock_get_ctx, mock_get_inspector, mock_state):
        """Test API mode enforces block decision in enforce mode."""
        from aidefense.runtime.agentsec.patchers.bedrock import _handle_agentcore_api_mode
        
        mock_state.get_llm_mode.return_value = "on_enforce"
        mock_state.get_llm_integration_mode.return_value = "api"
        
        mock_ctx = MagicMock()
        mock_ctx.metadata = {}
        mock_get_ctx.return_value = mock_ctx
        
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = Decision.block(reasons=["policy_violation"])
        mock_get_inspector.return_value = mock_inspector
        
        mock_wrapped = MagicMock()
        
        with pytest.raises(SecurityPolicyError):
            _handle_agentcore_api_mode(
                operation_name="InvokeAgentRuntime",
                api_params={
                    "agentRuntimeArn": "arn:aws:bedrock:us-east-1:123:agent-runtime/test",
                    "payload": json.dumps({"prompt": "malicious content"})
                },
                wrapped=mock_wrapped,
                args=(),
                kwargs={}
            )


class TestAgentCoreOperationsConstant:
    """Test AgentCore operations constant."""

    def test_agentcore_operations_contains_invoke_agent_runtime(self):
        """Test AGENTCORE_OPERATIONS contains InvokeAgentRuntime."""
        from aidefense.runtime.agentsec.patchers.bedrock import AGENTCORE_OPERATIONS
        
        assert "InvokeAgentRuntime" in AGENTCORE_OPERATIONS

    def test_agentcore_operations_does_not_contain_bedrock_ops(self):
        """Test AGENTCORE_OPERATIONS does not contain Bedrock operations."""
        from aidefense.runtime.agentsec.patchers.bedrock import AGENTCORE_OPERATIONS, BEDROCK_OPERATIONS
        
        for op in BEDROCK_OPERATIONS:
            assert op not in AGENTCORE_OPERATIONS


class TestAgentCoreStateConfig:
    """Test AgentCore state configuration."""

    def test_agentcore_in_supported_providers(self):
        """Test agentcore is in SUPPORTED_PROVIDERS."""
        from aidefense.runtime.agentsec._state import SUPPORTED_PROVIDERS
        
        assert "agentcore" in SUPPORTED_PROVIDERS

    def test_agentcore_in_provider_gateway_config(self):
        """Test agentcore is in provider gateway config."""
        from aidefense.runtime.agentsec._state import _provider_gateway_config
        
        assert "agentcore" in _provider_gateway_config

    def test_agentcore_in_provider_api_config(self):
        """Test agentcore is in provider API config."""
        from aidefense.runtime.agentsec._state import _provider_api_config
        
        assert "agentcore" in _provider_api_config
