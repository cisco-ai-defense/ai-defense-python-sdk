"""Extended tests for the Bedrock patcher.

Covers _should_inspect, _handle_patcher_error, _StreamingBodyWrapper,
_parse_agentcore_payload, _parse_agentcore_response, _parse_bedrock_messages,
_parse_bedrock_response, _parse_converse_messages, _is_agentcore_client,
_is_agentcore_operation, _BedrockFakeStreamWrapper,
_get_inspector, and patch_bedrock.
"""

import json
import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from aidefense.runtime.agentsec.patchers.bedrock import (
    _handle_patcher_error,
    _should_inspect,
    _StreamingBodyWrapper,
    _parse_agentcore_payload,
    _parse_agentcore_response,
    _parse_bedrock_messages,
    _parse_bedrock_response,
    _parse_converse_messages,
    _is_agentcore_client,
    _is_agentcore_operation,
    _BedrockFakeStreamWrapper,
    patch_bedrock,
)
from aidefense.runtime.agentsec.exceptions import SecurityPolicyError
from aidefense.runtime.agentsec import _state
from aidefense.runtime.agentsec._context import clear_inspection_context
from aidefense.runtime.agentsec.patchers import reset_registry


@pytest.fixture(autouse=True)
def reset_state():
    _state.reset()
    reset_registry()
    clear_inspection_context()
    import aidefense.runtime.agentsec.patchers.bedrock as bedrock_module
    bedrock_module._inspector = None
    yield
    _state.reset()
    reset_registry()
    clear_inspection_context()
    bedrock_module._inspector = None


# ===========================================================================
# _should_inspect() — gateway mode tests
# ===========================================================================

class TestShouldInspectGatewayMode:
    def test_true_when_gateway_on(self):
        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            gateway_mode={"llm_mode": "on"},
        )
        clear_inspection_context()
        assert _should_inspect() is True

    def test_false_when_gateway_off(self):
        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            gateway_mode={"llm_mode": "off"},
        )
        clear_inspection_context()
        assert _should_inspect() is False

    def test_gateway_mode_ignores_api_mode_off(self):
        """When integration is gateway and gw_llm_mode is on, api_mode off is irrelevant."""
        _state.set_state(
            initialized=True,
            llm_integration_mode="gateway",
            gateway_mode={"llm_mode": "on"},
            api_mode={"llm": {"mode": "off"}},
        )
        clear_inspection_context()
        assert _should_inspect() is True


# ===========================================================================
# _handle_patcher_error()
# ===========================================================================

class TestHandlePatcherError:
    def test_fail_open_true_returns_allow(self):
        _state.set_state(initialized=True, api_mode={"llm_defaults": {"fail_open": True}})
        d = _handle_patcher_error(RuntimeError("boom"), "test")
        assert d.action == "allow"

    def test_fail_open_false_raises(self):
        _state.set_state(initialized=True, api_mode={"llm_defaults": {"fail_open": False}})
        with pytest.raises(SecurityPolicyError):
            _handle_patcher_error(RuntimeError("boom"), "test")


# ===========================================================================
# _StreamingBodyWrapper
# ===========================================================================

class TestStreamingBodyWrapper:
    def test_read_all(self):
        content = b"hello world"
        wrapper = _StreamingBodyWrapper(content)
        assert wrapper.read() == content

    def test_read_amount(self):
        content = b"hello world"
        wrapper = _StreamingBodyWrapper(content)
        assert wrapper.read(5) == b"hello"
        assert wrapper.read(5) == b" worl"
        assert wrapper.read(5) == b"d"

    def test_iter_lines(self):
        content = b"line1\nline2\nline3"
        wrapper = _StreamingBodyWrapper(content)
        lines = list(wrapper.iter_lines())
        assert lines == [b"line1\n", b"line2\n", b"line3"]

    def test_close(self):
        wrapper = _StreamingBodyWrapper(b"test")
        wrapper.close()  # Should not raise
        with pytest.raises(ValueError, match="closed"):
            wrapper.read()

    def test_iter_yields_chunks(self):
        content = b"abcdefgh"
        wrapper = _StreamingBodyWrapper(content)
        chunks = list(wrapper)
        assert b"".join(chunks) == content

    def test_iter_chunks(self):
        content = b"abcdefghij"
        wrapper = _StreamingBodyWrapper(content)
        chunks = list(wrapper.iter_chunks(chunk_size=3))
        assert chunks == [b"abc", b"def", b"ghi", b"j"]


# ===========================================================================
# _parse_agentcore_payload()
# ===========================================================================

class TestParseAgentcorePayload:
    def test_converse_format_messages_and_system(self):
        payload = json.dumps({
            "messages": [
                {"role": "user", "content": [{"text": "Hello"}]},
                {"role": "assistant", "content": "Hi there"},
            ],
            "system": "You are helpful.",
        }).encode("utf-8")
        result = _parse_agentcore_payload(payload)
        assert len(result) == 3
        assert result[0] == {"role": "system", "content": "You are helpful."}
        assert result[1]["role"] == "user"
        assert "Hello" in result[1]["content"]
        assert result[2]["role"] == "assistant"
        assert result[2]["content"] == "Hi there"

    def test_simple_format_prompt(self):
        payload = json.dumps({"prompt": "What is 2+2?"}).encode("utf-8")
        result = _parse_agentcore_payload(payload)
        assert result == [{"role": "user", "content": "What is 2+2?"}]

    def test_simple_format_query(self):
        payload = json.dumps({"query": "Tell me a joke"}).encode("utf-8")
        result = _parse_agentcore_payload(payload)
        assert result == [{"role": "user", "content": "Tell me a joke"}]

    def test_json_decode_error_plain_text(self):
        payload = b"not valid json"
        result = _parse_agentcore_payload(payload)
        assert result == [{"role": "user", "content": "not valid json"}]

    def test_json_decode_error_empty_returns_empty(self):
        payload = b"   "
        result = _parse_agentcore_payload(payload)
        assert result == []


# ===========================================================================
# _parse_agentcore_response()
# ===========================================================================

class TestParseAgentcoreResponse:
    def test_converse_format_response(self):
        response_body = json.dumps({
            "output": {
                "message": {
                    "content": [
                        {"text": "Hello from assistant"},
                        {"text": " More text"},
                    ]
                }
            }
        }).encode("utf-8")
        result = _parse_agentcore_response(response_body)
        assert "Hello from assistant" in result
        assert "More text" in result

    def test_simple_format_result_key(self):
        response_body = json.dumps({"result": "The answer is 42"}).encode("utf-8")
        result = _parse_agentcore_response(response_body)
        assert result == "The answer is 42"

    def test_bytes_response_non_json_returns_stripped(self):
        response_body = b"plain text content"
        result = _parse_agentcore_response(response_body)
        assert result == "plain text content"

    def test_streaming_body_with_read(self):
        body_content = json.dumps({"result": "from stream"}).encode("utf-8")
        mock_stream = SimpleNamespace(read=lambda: body_content)
        result = _parse_agentcore_response(mock_stream)
        assert result == "from stream"


# ===========================================================================
# _parse_bedrock_messages()
# ===========================================================================

class TestParseBedrockMessages:
    def test_tool_use_blocks(self):
        body = json.dumps({
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "Let me check."},
                        {"type": "tool_use", "name": "weather", "input": {}},
                    ]
                }
            ]
        }).encode("utf-8")
        result = _parse_bedrock_messages(body, "anthropic.claude-3")
        assert len(result) == 1
        assert "[Tool call: weather]" in result[0]["content"]
        assert "Let me check" in result[0]["content"]

    def test_titan_input_text_format(self):
        body = json.dumps({"inputText": "Hello Titan"}).encode("utf-8")
        result = _parse_bedrock_messages(body, "amazon.titan-tg1-large")
        assert result == [{"role": "user", "content": "Hello Titan"}]

    def test_generic_prompt_format(self):
        body = json.dumps({"prompt": "Generic prompt content"}).encode("utf-8")
        result = _parse_bedrock_messages(body, "meta.llama")
        assert result == [{"role": "user", "content": "Generic prompt content"}]

    def test_invalid_json_returns_empty(self):
        body = b"not json"
        result = _parse_bedrock_messages(body, "any-model")
        assert result == []


# ===========================================================================
# _parse_bedrock_response()
# ===========================================================================

class TestParseBedrockResponse:
    def test_titan_results_format(self):
        response_body = json.dumps({
            "results": [
                {"outputText": "First part"},
                {"outputText": " Second part"},
            ]
        }).encode("utf-8")
        result = _parse_bedrock_response(response_body, "amazon.titan")
        assert "First part" in result
        assert "Second part" in result

    def test_completion_format(self):
        response_body = json.dumps({"completion": "Done."}).encode("utf-8")
        result = _parse_bedrock_response(response_body, "meta.llama")
        assert result == "Done."

    def test_generation_format(self):
        response_body = json.dumps({"generation": "Generated text"}).encode("utf-8")
        result = _parse_bedrock_response(response_body, "cohere.model")
        assert result == "Generated text"

    def test_claude_content_format(self):
        response_body = json.dumps({
            "content": [
                {"type": "text", "text": "Claude says hi"},
            ]
        }).encode("utf-8")
        result = _parse_bedrock_response(response_body, "anthropic.claude-3")
        assert result == "Claude says hi"

    def test_invalid_json_returns_empty(self):
        result = _parse_bedrock_response(b"not json", "any-model")
        assert result == ""


# ===========================================================================
# _parse_converse_messages()
# ===========================================================================

class TestParseConverseMessages:
    def test_system_as_string(self):
        api_params = {
            "system": "You are helpful.",
            "messages": [{"role": "user", "content": [{"text": "Hi"}]}],
        }
        result = _parse_converse_messages(api_params)
        assert len(result) == 2
        assert result[0] == {"role": "system", "content": "You are helpful."}
        assert result[1]["content"] == "Hi"

    def test_system_as_list(self):
        api_params = {
            "system": [{"text": "System instruction 1"}, {"text": " System 2"}],
            "messages": [{"role": "user", "content": [{"text": "Hello"}]}],
        }
        result = _parse_converse_messages(api_params)
        assert len(result) == 2
        assert "System instruction 1" in result[0]["content"]
        assert "System 2" in result[0]["content"]

    def test_tool_result_blocks(self):
        api_params = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"toolResult": {"content": [{"text": "Weather is sunny"}]}},
                    ]
                }
            ]
        }
        result = _parse_converse_messages(api_params)
        assert len(result) == 1
        assert "[Tool result:" in result[0]["content"] or "Weather" in result[0]["content"]


# ===========================================================================
# _is_agentcore_client()
# ===========================================================================

class TestIsAgentcoreClient:
    def test_bedrock_agentcore_service(self):
        service_model = SimpleNamespace(service_name="bedrock-agentcore")
        instance = SimpleNamespace(_service_model=service_model)
        assert _is_agentcore_client(instance) is True

    def test_other_service(self):
        service_model = SimpleNamespace(service_name="bedrock-runtime")
        instance = SimpleNamespace(_service_model=service_model)
        assert _is_agentcore_client(instance) is False

    def test_no_service_model(self):
        instance = SimpleNamespace()
        assert _is_agentcore_client(instance) is False

    def test_exception_returns_false(self):
        class BadClient:
            @property
            def _service_model(self):
                raise RuntimeError("boom")

        assert _is_agentcore_client(BadClient()) is False


# ===========================================================================
# _is_agentcore_operation()
# ===========================================================================

class TestIsAgentcoreOperation:
    def test_with_agentcore_client_and_invoke_agent_runtime(self):
        service_model = SimpleNamespace(service_name="bedrock-agentcore")
        instance = SimpleNamespace(_service_model=service_model)
        assert _is_agentcore_operation("InvokeAgentRuntime", instance) is True

    def test_with_agentcore_client_and_invoke_model(self):
        service_model = SimpleNamespace(service_name="bedrock-agentcore")
        instance = SimpleNamespace(_service_model=service_model)
        assert _is_agentcore_operation("InvokeModel", instance) is False

    def test_with_bedrock_runtime_client(self):
        service_model = SimpleNamespace(service_name="bedrock-runtime")
        instance = SimpleNamespace(_service_model=service_model)
        assert _is_agentcore_operation("InvokeAgentRuntime", instance) is False


# ===========================================================================
# _BedrockFakeStreamWrapper
# ===========================================================================

class TestBedrockFakeStreamWrapper:
    def test_sync_iteration_yields_events(self):
        response = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "Hello"}],
                }
            },
            "stopReason": "end_turn",
            "usage": {},
        }
        wrapper = _BedrockFakeStreamWrapper(response)
        events = list(wrapper)
        assert len(events) >= 1
        assert any("messageStart" in e for e in events)
        assert any("contentBlockDelta" in e or "contentBlockStart" in e for e in events)
        assert any("messageStop" in e for e in events)

    def test_close_no_op(self):
        wrapper = _BedrockFakeStreamWrapper({"output": {"message": {"content": []}}})
        wrapper.close()  # Should not raise


# ===========================================================================
# patch_bedrock()
# ===========================================================================

class TestPatchBedrock:
    def test_successful_patch(self):
        with patch("aidefense.runtime.agentsec.patchers.bedrock.safe_import", return_value=MagicMock()), \
             patch("aidefense.runtime.agentsec.patchers.bedrock.is_patched", return_value=False), \
             patch("aidefense.runtime.agentsec.patchers.bedrock.wrapt") as mock_wrapt, \
             patch("aidefense.runtime.agentsec.patchers.bedrock.mark_patched"):
            assert patch_bedrock() is True
            mock_wrapt.wrap_function_wrapper.assert_called()

    def test_patch_failure_returns_false(self):
        with patch("aidefense.runtime.agentsec.patchers.bedrock.safe_import", return_value=MagicMock()), \
             patch("aidefense.runtime.agentsec.patchers.bedrock.is_patched", return_value=False), \
             patch("aidefense.runtime.agentsec.patchers.bedrock.wrapt") as mock_wrapt:
            mock_wrapt.wrap_function_wrapper.side_effect = Exception("fail")
            assert patch_bedrock() is False
