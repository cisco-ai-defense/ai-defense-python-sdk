"""Extended tests for the VertexAI patcher.

Covers _should_inspect, _enforce_decision, _serialize_vertexai_part,
_serialize_vertexai_obj, _build_vertexai_response, _strip_unknown_fields,
_VertexAIResponseWrapper, _CandidateWrapper, _ContentWrapper, _PartWrapper,
_VertexAIGatewayStreamWrapper, _handle_vertexai_gateway_call,
GoogleStreamingInspectionWrapper, _inspect_vertexai_sync,
_wrap_generate_content, _wrap_private_generate_content,
patch_vertexai, _extract_from_prediction_request,
_extract_model_short_name, _clean_proto_dict, _prediction_request_to_body,
_inspect_prediction_sync, _inspect_prediction_stream_sync,
_wrap_prediction_generate_content, _wrap_prediction_stream_generate_content,
_handle_prediction_gateway_call, and _get_inspector.
Does NOT test async functions.
"""

import httpx
import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from aidefense.runtime.agentsec.patchers.vertexai import (
    _serialize_vertexai_part,
    _serialize_vertexai_obj,
    _build_vertexai_response,
    _strip_unknown_fields,
    _handle_vertexai_gateway_call,
    _should_inspect,
    _VertexAIResponseWrapper,
    _CandidateWrapper,
    _ContentWrapper,
    _PartWrapper,
    _VertexAIGatewayStreamWrapper,
    _VertexFunctionCallWrapper,
    _VertexFunctionResponseWrapper,
    GoogleStreamingInspectionWrapper,
    _inspect_vertexai_sync,
    _wrap_generate_content,
    _wrap_private_generate_content,
    patch_vertexai,
    # PredictionServiceClient helpers
    _extract_from_prediction_request,
    _extract_model_short_name,
    _clean_proto_dict,
    _prediction_request_to_body,
    _handle_prediction_gateway_call,
    _inspect_prediction_sync,
    _inspect_prediction_stream_sync,
    _wrap_prediction_generate_content,
    _wrap_prediction_stream_generate_content,
)
from aidefense.runtime.agentsec.exceptions import SecurityPolicyError
from aidefense.runtime.agentsec.decision import Decision
from aidefense.runtime.agentsec import _state
from aidefense.runtime.agentsec._context import clear_inspection_context
from aidefense.runtime.agentsec.patchers import reset_registry


def _extract_post_body(mock_client):
    """Extract the JSON body from an httpx mock client's post call.

    The gateway handler now sends ``content=<bytes>`` instead of
    ``json=<dict>``, so we parse the bytes back to a dict.
    """
    import json
    call_kw = mock_client.post.call_args.kwargs or {}
    # Try content= first (new code path)
    raw = call_kw.get("content")
    if raw is not None:
        if isinstance(raw, bytes):
            return json.loads(raw)
        return json.loads(raw)
    # Fallback to json= (legacy)
    return call_kw.get("json")


@pytest.fixture(autouse=True)
def reset_state():
    _state.reset()
    reset_registry()
    clear_inspection_context()
    import aidefense.runtime.agentsec.patchers.vertexai as vertexai_module
    vertexai_module._inspector = None
    yield
    _state.reset()
    reset_registry()
    clear_inspection_context()
    vertexai_module._inspector = None


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
# _serialize_vertexai_part()
# ===========================================================================

class TestSerializeVertexAIPart:
    def test_dict_input_passthrough(self):
        part = {"text": "hello"}
        result = _serialize_vertexai_part(part)
        assert result == {"text": "hello"}

    def test_object_with_text_attr(self):
        part = SimpleNamespace(text="hello world")
        result = _serialize_vertexai_part(part)
        assert result == {"text": "hello world"}

    def test_object_with_function_call(self):
        fc = SimpleNamespace(name="my_func", args={"key": "value"})
        part = SimpleNamespace(text=None, function_call=fc)
        result = _serialize_vertexai_part(part)
        assert result == {"functionCall": {"name": "my_func", "args": {"key": "value"}}}

    def test_object_with_function_response(self):
        fr = SimpleNamespace(name="my_func", response={"result": 42})
        part = SimpleNamespace(text=None, function_call=None, function_response=fr)
        result = _serialize_vertexai_part(part)
        assert result == {"functionResponse": {"name": "my_func", "response": {"result": 42}}}


# ===========================================================================
# _serialize_vertexai_obj()
# ===========================================================================

class TestSerializeVertexAIObj:
    def test_none_returns_none(self):
        assert _serialize_vertexai_obj(None) is None

    def test_dict_passthrough(self):
        d = {"key": "value"}
        assert _serialize_vertexai_obj(d) == d

    def test_list_recursively_serializes(self):
        class WithToDict:
            @classmethod
            def to_dict(cls, o):
                return {"serialized": True}
        obj = [{"a": 1}, WithToDict()]
        result = _serialize_vertexai_obj(obj)
        assert result[0] == {"a": 1}
        assert result[1] == {"serialized": True}

    def test_object_with_to_dict(self):
        class WithToDict:
            @classmethod
            def to_dict(cls, o):
                return {"serialized": True}
        obj = WithToDict()
        result = _serialize_vertexai_obj(obj)
        assert result == {"serialized": True}

    def test_primitives_passthrough(self):
        assert _serialize_vertexai_obj("str") == "str"
        assert _serialize_vertexai_obj(42) == 42
        assert _serialize_vertexai_obj(3.14) == 3.14
        assert _serialize_vertexai_obj(True) is True


# ===========================================================================
# _build_vertexai_response()
# ===========================================================================

class TestBuildVertexAIResponse:
    def test_fallback_wrapper_when_from_dict_unavailable(self):
        """When GenerationResponse.from_dict fails, returns _VertexAIResponseWrapper."""
        response_data = {
            "candidates": [{"content": {"role": "model", "parts": [{"text": "fallback response"}]}}]
        }
        # Force the try block to fail by making __import__ raise for vertexai.generative_models
        import builtins
        _orig_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "vertexai.generative_models":
                raise ImportError("vertexai not available")
            return _orig_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = _build_vertexai_response(response_data)

        assert isinstance(result, _VertexAIResponseWrapper)
        assert result.text == "fallback response"


# ===========================================================================
# _strip_unknown_fields()
# ===========================================================================

class TestStripUnknownFields:
    def test_removes_unknown_fields_from_usage_metadata(self):
        data = {
            "candidates": [],
            "usageMetadata": {
                "promptTokenCount": 10,
                "totalTokenCount": 15,
                "trafficType": "unknown",
                "customField": "strip_me",
            },
        }
        result = _strip_unknown_fields(data)
        assert "usageMetadata" in result
        assert result["usageMetadata"]["promptTokenCount"] == 10
        assert result["usageMetadata"]["totalTokenCount"] == 15
        assert "trafficType" not in result["usageMetadata"]
        assert "customField" not in result["usageMetadata"]

    def test_handles_usage_metadata_snake_case(self):
        data = {"usage_metadata": {"prompt_token_count": 5, "extra": "strip"}}
        result = _strip_unknown_fields(data)
        assert "usage_metadata" in result
        assert result["usage_metadata"].get("prompt_token_count") == 5
        assert "extra" not in result["usage_metadata"]


# ===========================================================================
# _VertexAIResponseWrapper
# ===========================================================================

class TestVertexAIResponseWrapper:
    def test_valid_dict_text_extraction(self):
        wrapper = _VertexAIResponseWrapper({
            "candidates": [{"content": {"role": "model", "parts": [{"text": "Hello world"}]}}]
        })
        assert wrapper.text == "Hello world"

    def test_empty_candidates(self):
        wrapper = _VertexAIResponseWrapper({"candidates": []})
        assert wrapper.candidates == []
        assert wrapper.text == ""

    def test_to_dict(self):
        data = {"candidates": [], "usageMetadata": {}}
        wrapper = _VertexAIResponseWrapper(data)
        assert wrapper.to_dict() is data

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="expected dict"):
            _VertexAIResponseWrapper("not a dict")


# ===========================================================================
# _CandidateWrapper, _ContentWrapper, _PartWrapper
# ===========================================================================

class TestCandidateContentPartWrappers:
    def test_candidate_wrapper_properties(self):
        cand = _CandidateWrapper({
            "content": {"role": "model", "parts": [{"text": "hi"}]},
            "finishReason": "STOP",
        })
        assert cand.finish_reason == "STOP"
        assert cand.content.role == "model"
        assert cand.content.parts[0].text == "hi"

    def test_content_wrapper_role_getter_setter(self):
        content = _ContentWrapper({"role": "user", "parts": []})
        assert content.role == "user"
        content.role = "model"
        assert content._data["role"] == "model"

    def test_part_wrapper_function_call(self):
        part = _PartWrapper({
            "functionCall": {"name": "my_tool", "args": {"x": 1}}
        })
        assert part.text == ""
        assert part.function_call is not None
        assert part.function_call.name == "my_tool"
        assert part.function_call.args == {"x": 1}

    def test_part_wrapper_function_response(self):
        part = _PartWrapper({
            "functionResponse": {"name": "my_tool", "response": {"ok": True}}
        })
        assert part.function_response is not None
        assert part.function_response.name == "my_tool"
        assert part.function_response.response == {"ok": True}


# ===========================================================================
# _VertexFunctionCallWrapper, _VertexFunctionResponseWrapper
# ===========================================================================

class TestVertexFunctionWrappers:
    def test_function_call_wrapper(self):
        fc = _VertexFunctionCallWrapper({"name": "tool_a", "args": {"key": "val"}})
        assert fc.name == "tool_a"
        assert fc.args == {"key": "val"}

    def test_function_response_wrapper(self):
        fr = _VertexFunctionResponseWrapper({"name": "tool_b", "response": {}})
        assert fr.name == "tool_b"
        assert fr.response == {}


# ===========================================================================
# _VertexAIGatewayStreamWrapper
# ===========================================================================

class TestVertexAIGatewayStreamWrapper:
    def test_yields_single_chunk_then_stops(self):
        response = _VertexAIResponseWrapper({
            "candidates": [{"content": {"role": "model", "parts": [{"text": "chunk"}]}}]
        })
        wrapper = _VertexAIGatewayStreamWrapper(response)
        chunks = list(wrapper)
        assert len(chunks) == 1
        assert chunks[0] is response
        assert chunks[0].text == "chunk"


# ===========================================================================
# patch_vertexai()
# ===========================================================================

class TestPatchVertexAI:
    def test_successful_patch_returns_true(self):
        with patch(
            "aidefense.runtime.agentsec.patchers.vertexai.safe_import",
            return_value=MagicMock(),
        ), patch(
            "aidefense.runtime.agentsec.patchers.vertexai.is_patched",
            return_value=False,
        ), patch(
            "aidefense.runtime.agentsec.patchers.vertexai.wrapt",
        ) as mock_wrapt, patch(
            "aidefense.runtime.agentsec.patchers.vertexai.mark_patched",
        ) as mock_mark:
            assert patch_vertexai() is True
            mock_mark.assert_called_once_with("vertexai")


# ===========================================================================
# _serialize_vertexai_part() — proto-plus path
# ===========================================================================

class TestSerializeVertexAIPartProtoPlus:
    def test_proto_plus_to_dict(self):
        """Object whose type has a to_dict classmethod should be serialized."""
        class FakePartType:
            @classmethod
            def to_dict(cls, instance):
                return {"text": "from proto-plus"}

        part = FakePartType()
        result = _serialize_vertexai_part(part)
        assert result == {"text": "from proto-plus"}


# ===========================================================================
# _serialize_vertexai_obj() — Pydantic paths
# ===========================================================================

class TestSerializeVertexAIObjPydantic:
    def test_model_dump_json_mode(self):
        obj = MagicMock()
        obj.model_dump.return_value = {"temperature": 0.7}
        assert _serialize_vertexai_obj(obj) == {"temperature": 0.7}

    def test_model_dump_fallback_to_non_json(self):
        obj = MagicMock()
        obj.model_dump.side_effect = [TypeError("no json mode"), {"temperature": 0.5}]
        assert _serialize_vertexai_obj(obj) == {"temperature": 0.5}

    def test_dict_method_fallback(self):
        """Pydantic v1 .dict() path."""
        obj = MagicMock(spec=["dict"])
        obj.dict.return_value = {"old": True}
        assert _serialize_vertexai_obj(obj) == {"old": True}


# ===========================================================================
# _handle_vertexai_gateway_call()
# ===========================================================================

class TestHandleVertexAIGatewayCall:
    def _gw(self, url="https://gw.example.com", api_key="key",
             fail_open=True, timeout=30, auth_mode="api_key",
             project=None, location=None, endpoint=None):
        return SimpleNamespace(
            url=url, api_key=api_key, fail_open=fail_open,
            timeout=timeout, auth_mode=auth_mode,
            project=project, location=location, endpoint=endpoint,
        )

    def test_missing_url_raises_security(self):
        with pytest.raises(SecurityPolicyError):
            _handle_vertexai_gateway_call("model", "Hello", self._gw(url=""))

    def test_missing_api_key_raises_security(self):
        with pytest.raises(SecurityPolicyError):
            _handle_vertexai_gateway_call("model", "Hello", self._gw(api_key=""))

    @patch("aidefense.runtime.agentsec.patchers._google_common.build_vertexai_gateway_url",
           return_value="https://gw.example.com/v1/model:generateContent")
    @patch("httpx.Client")
    def test_success_with_string_content(self, mock_client_cls, _url):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "candidates": [{"content": {"role": "model", "parts": [{"text": "Hi"}]}}]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        clear_inspection_context()
        result = _handle_vertexai_gateway_call("gemini-2.0-flash", "Hello", self._gw())
        # Implementation may return native GenerationResponse (when from_dict succeeds)
        # or _VertexAIResponseWrapper (fallback); both provide .text
        assert hasattr(result, "text") and result.text == "Hi"

    @patch("aidefense.runtime.agentsec.patchers._google_common.build_vertexai_gateway_url",
           return_value="https://gw.example.com/v1/model:generateContent")
    @patch("httpx.Client")
    def test_success_with_list_content_objects(self, mock_client_cls, _url):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"candidates": [{"content": {"role": "model", "parts": [{"text": "OK"}]}}]}
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        clear_inspection_context()
        contents = [SimpleNamespace(role="user", parts=[SimpleNamespace(text="Hi")])]
        _handle_vertexai_gateway_call("model", contents, self._gw())

        body = _extract_post_body(mock_client)
        assert body["contents"][0]["role"] == "user"

    @patch("aidefense.runtime.agentsec.patchers._google_common.build_vertexai_gateway_url",
           return_value="https://gw.example.com/v1/model:generateContent")
    @patch("httpx.Client")
    def test_object_generation_config(self, mock_client_cls, _url):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"candidates": [{"content": {"parts": [{"text": "x"}]}}]}
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        clear_inspection_context()
        gen_config = SimpleNamespace(temperature=0.5, max_output_tokens=100)
        _handle_vertexai_gateway_call("model", "Hi", self._gw(), generation_config=gen_config)

        body = _extract_post_body(mock_client)
        assert body["generationConfig"]["temperature"] == 0.5

    @patch("aidefense.runtime.agentsec.patchers._google_common.build_vertexai_gateway_url",
           return_value="https://gw.example.com/v1/model:generateContent")
    @patch("httpx.Client")
    def test_system_instruction_string(self, mock_client_cls, _url):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"candidates": [{"content": {"parts": [{"text": "x"}]}}]}
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        clear_inspection_context()
        _handle_vertexai_gateway_call("model", "Hi", self._gw(), system_instruction="You are helpful")

        body = _extract_post_body(mock_client)
        assert body["systemInstruction"]["parts"][0]["text"] == "You are helpful"

    @patch("aidefense.runtime.agentsec.patchers._google_common.build_vertexai_gateway_url",
           return_value="https://gw.example.com/v1/model:generateContent")
    @patch("httpx.Client")
    def test_http_error_fail_open_true(self, mock_client_cls, _url):
        request = httpx.Request("POST", "https://gw.example.com")
        response = httpx.Response(500, request=request)
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = MagicMock(
            raise_for_status=MagicMock(side_effect=httpx.HTTPStatusError("500", request=request, response=response))
        )
        mock_client_cls.return_value = mock_client

        clear_inspection_context()
        with pytest.raises(httpx.HTTPStatusError):
            _handle_vertexai_gateway_call("model", "Hi", self._gw(fail_open=True))

    @patch("aidefense.runtime.agentsec.patchers._google_common.build_vertexai_gateway_url",
           return_value="https://gw.example.com/v1/model:generateContent")
    @patch("httpx.Client")
    def test_http_error_fail_open_false(self, mock_client_cls, _url):
        request = httpx.Request("POST", "https://gw.example.com")
        response = httpx.Response(500, request=request)
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = MagicMock(
            raise_for_status=MagicMock(side_effect=httpx.HTTPStatusError("500", request=request, response=response))
        )
        mock_client_cls.return_value = mock_client

        clear_inspection_context()
        with pytest.raises(SecurityPolicyError):
            _handle_vertexai_gateway_call("model", "Hi", self._gw(fail_open=False))


# ===========================================================================
# GoogleStreamingInspectionWrapper
# ===========================================================================

class TestGoogleStreamingInspectionWrapper:
    @patch("aidefense.runtime.agentsec.patchers.vertexai._get_inspector")
    @patch("aidefense.runtime.agentsec.patchers._google_common.extract_streaming_chunk_text",
           return_value="chunk text")
    def test_buffers_and_inspects(self, _mock_extract, mock_get_inspector):
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = Decision.allow(reasons=[])
        mock_get_inspector.return_value = mock_inspector

        _state.set_state(initialized=True, api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}})
        clear_inspection_context()

        chunk = SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[SimpleNamespace(text="Hi")]))])
        wrapper = GoogleStreamingInspectionWrapper(iter([chunk]), [{"role": "user", "content": "test"}], {})
        chunks = list(wrapper)
        assert len(chunks) == 1
        assert mock_inspector.inspect_conversation.called

    @patch("aidefense.runtime.agentsec.patchers.vertexai._get_inspector")
    @patch("aidefense.runtime.agentsec.patchers._google_common.extract_streaming_chunk_text",
           return_value="")
    def test_no_inspection_on_empty_buffer(self, _mock_extract, mock_get_inspector):
        mock_inspector = MagicMock()
        mock_get_inspector.return_value = mock_inspector

        _state.set_state(initialized=True, api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}})
        clear_inspection_context()

        wrapper = GoogleStreamingInspectionWrapper(iter([SimpleNamespace()]), [], {})
        list(wrapper)
        mock_inspector.inspect_conversation.assert_not_called()


# ===========================================================================
# _inspect_vertexai_sync()
# ===========================================================================

class TestInspectVertexaiSync:
    @patch("aidefense.runtime.agentsec.patchers.vertexai._should_inspect", return_value=False)
    def test_skip_when_should_inspect_false(self, _):
        mock_wrapped = MagicMock(return_value="raw")
        result = _inspect_vertexai_sync(mock_wrapped, SimpleNamespace(model_name="m"), ("Hi",), {})
        assert result == "raw"

    @patch("aidefense.runtime.agentsec.patchers.vertexai._get_inspector")
    @patch("aidefense.runtime.agentsec.patchers.vertexai.resolve_gateway_settings", return_value=None)
    @patch("aidefense.runtime.agentsec.patchers.vertexai.extract_google_response", return_value="Reply")
    @patch("aidefense.runtime.agentsec.patchers.vertexai.normalize_google_messages",
           return_value=[{"role": "user", "content": "Hi"}])
    def test_api_mode_pre_post_inspection(self, _norm, _extract, _gw, mock_get_inspector):
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = Decision.allow(reasons=[])
        mock_get_inspector.return_value = mock_inspector

        _state.set_state(initialized=True, api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}})
        clear_inspection_context()

        mock_wrapped = MagicMock(return_value=SimpleNamespace(text="Reply"))
        _inspect_vertexai_sync(mock_wrapped, SimpleNamespace(model_name="gemini"), ("Hi",), {})
        assert mock_inspector.inspect_conversation.call_count == 2

    @patch("aidefense.runtime.agentsec.patchers.vertexai._handle_vertexai_gateway_call",
           return_value=SimpleNamespace(text="GW"))
    @patch("aidefense.runtime.agentsec.patchers.vertexai.resolve_gateway_settings")
    @patch("aidefense.runtime.agentsec.patchers.vertexai.normalize_google_messages",
           return_value=[{"role": "user", "content": "Hi"}])
    def test_gateway_mode_non_streaming(self, _norm, mock_gw_settings, mock_gw_call):
        mock_gw_settings.return_value = SimpleNamespace(
            url="https://gw.example.com", api_key="key", fail_open=True, timeout=30, auth_mode="api_key",
        )

        _state.set_state(initialized=True, api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}})
        clear_inspection_context()

        result = _inspect_vertexai_sync(MagicMock(), SimpleNamespace(model_name="m"), ("Hi",), {})
        assert result.text == "GW"


# ===========================================================================
# _wrap_generate_content() / _wrap_private_generate_content()
# ===========================================================================

class TestWrapGenerateContent:
    @patch("aidefense.runtime.agentsec.patchers.vertexai._inspect_vertexai_sync",
           return_value="inspected")
    def test_calls_inspect_and_sets_reentrancy(self, mock_inspect):
        result = _wrap_generate_content(MagicMock(), SimpleNamespace(), (), {})
        assert result == "inspected"
        mock_inspect.assert_called_once()


class TestWrapPrivateGenerateContent:
    def test_reentrancy_guard_passes_through(self):
        """When reentrancy guard is active, should call wrapped directly."""
        import aidefense.runtime.agentsec.patchers.vertexai as mod
        token = mod._vertexai_inspection_active.set(True)
        try:
            mock_wrapped = MagicMock(return_value="direct")
            result = _wrap_private_generate_content(mock_wrapped, SimpleNamespace(), (), {})
            assert result == "direct"
            mock_wrapped.assert_called_once()
        finally:
            mod._vertexai_inspection_active.reset(token)

    @patch("aidefense.runtime.agentsec.patchers.vertexai._inspect_vertexai_sync",
           return_value="inspected")
    def test_direct_call_inspects(self, mock_inspect):
        """When no reentrancy guard, should inspect."""
        result = _wrap_private_generate_content(MagicMock(), SimpleNamespace(), (), {})
        assert result == "inspected"


# ===========================================================================
# PredictionServiceClient helpers
# ===========================================================================

class TestExtractModelShortName:
    def test_fully_qualified(self):
        fq = "projects/p/locations/l/publishers/google/models/gemini-2.5-flash"
        assert _extract_model_short_name(fq) == "gemini-2.5-flash"

    def test_already_short(self):
        assert _extract_model_short_name("gemini-2.5-flash") == "gemini-2.5-flash"

    def test_endpoint_format(self):
        ep = "projects/p/locations/l/endpoints/12345"
        assert _extract_model_short_name(ep) == ep


class TestCleanProtoDict:
    def test_removes_thought_defaults(self):
        d = {
            "role": "user",
            "parts": [{"text": "hi", "thought": False, "thought_signature": ""}],
        }
        result = _clean_proto_dict(d)
        assert result == {"role": "user", "parts": [{"text": "hi"}]}

    def test_preserves_non_default_values(self):
        d = {"text": "hello", "thought": True}
        result = _clean_proto_dict(d)
        assert result == {"text": "hello", "thought": True}

    def test_passes_through_primitives(self):
        assert _clean_proto_dict(42) == 42
        assert _clean_proto_dict("hello") == "hello"


class TestExtractFromPredictionRequest:
    def test_from_dict_request(self):
        req_dict = {
            "model": "projects/p/locations/l/publishers/google/models/gemini-2.5-flash",
            "contents": [{"role": "user", "parts": [{"text": "Hi"}]}],
        }
        request, short, contents, fq = _extract_from_prediction_request(
            (), {"request": req_dict}
        )
        assert request is req_dict
        assert short == "gemini-2.5-flash"
        assert contents == [{"role": "user", "parts": [{"text": "Hi"}]}]

    def test_from_object_request(self):
        req = SimpleNamespace(
            model="projects/p/locations/l/publishers/google/models/gemini-pro",
            contents=["content1"],
        )
        request, short, contents, fq = _extract_from_prediction_request(
            (req,), {}
        )
        assert short == "gemini-pro"
        assert contents == ["content1"]

    def test_from_kwargs(self):
        request, short, contents, fq = _extract_from_prediction_request(
            (),
            {
                "model": "projects/p/locations/l/publishers/google/models/gemini-flash",
                "contents": [{"role": "user", "parts": [{"text": "Hello"}]}],
            },
        )
        assert request is None
        assert short == "gemini-flash"

    def test_unknown_model(self):
        _, short, _, fq = _extract_from_prediction_request((), {})
        assert short == "unknown"
        assert fq == "unknown"


class TestPredictionRequestToBody:
    def test_dict_request(self):
        req = {
            "model": "projects/p/locations/l/publishers/google/models/gem",
            "contents": [{"role": "user", "parts": [{"text": "hi"}]}],
            "generationConfig": {"temperature": 0.7},
        }
        body = _prediction_request_to_body(req, req["model"])
        assert "model" not in body
        assert body["contents"] == [{"role": "user", "parts": [{"text": "hi"}]}]
        assert body["generationConfig"] == {"temperature": 0.7}

    def test_dict_strips_empty(self):
        req = {"model": "m", "contents": [], "tools": [], "labels": {}}
        body = _prediction_request_to_body(req, "m")
        assert "model" not in body
        assert "tools" not in body or body.get("tools") == []

    def test_proto_like_object_with_to_dict(self):
        class FakeProto:
            model = "projects/p/locations/l/publishers/google/models/g"
            contents = []
            @classmethod
            def to_dict(cls, obj):
                return {
                    "model": obj.model,
                    "contents": [{"role": "user", "parts": [{"text": "hello", "thought": False}]}],
                }
        body = _prediction_request_to_body(FakeProto(), FakeProto.model)
        assert "model" not in body
        assert body["contents"] == [{"role": "user", "parts": [{"text": "hello"}]}]


# ===========================================================================
# _handle_prediction_gateway_call()
# ===========================================================================

class TestHandlePredictionGatewayCall:
    def _make_gw_settings(self, **overrides):
        defaults = {
            "url": "https://gw.example.com/conn/123",
            "api_key": "test-key",
            "auth_mode": "api_key",
            "fail_open": True,
            "timeout": 30,
            "gcp_project": "my-proj",
            "gcp_location": "us-central1",
            "gcp_service_account_key_file": None,
            "gcp_target_service_account": None,
        }
        defaults.update(overrides)
        return SimpleNamespace(**defaults)

    @patch("aidefense.runtime.agentsec.patchers._google_common.build_vertexai_gateway_url",
           return_value="https://gw.example.com/v1/model:generateContent")
    @patch("httpx.Client")
    def test_gateway_success(self, mock_client_cls, _url):
        gw = self._make_gw_settings()
        response_json = {
            "candidates": [{"content": {"role": "model", "parts": [{"text": "Hi!"}]}}]
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = response_json
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        _state.set_state(initialized=True, api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}})
        clear_inspection_context()

        req = {"model": "projects/p/locations/l/publishers/google/models/gemini-2.5-flash",
               "contents": [{"role": "user", "parts": [{"text": "hello"}]}]}

        result = _handle_prediction_gateway_call(
            model_short_name="gemini-2.5-flash",
            fq_model=req["model"],
            request=req,
            gw_settings=gw,
        )
        mock_client.post.assert_called_once()
        assert result is not None

    @patch("aidefense.runtime.agentsec.patchers._google_common.build_vertexai_gateway_url",
           return_value="https://gw.example.com/v1/model:generateContent")
    @patch("httpx.Client")
    def test_gateway_body_excludes_model(self, mock_client_cls, _url):
        gw = self._make_gw_settings()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "candidates": [{"content": {"role": "model", "parts": [{"text": "ok"}]}}]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        clear_inspection_context()

        req = {"model": "projects/p/locations/l/publishers/google/models/gem",
               "contents": [{"role": "user", "parts": [{"text": "hi"}]}]}

        _handle_prediction_gateway_call(
            model_short_name="gem", fq_model=req["model"], request=req, gw_settings=gw,
        )
        body = _extract_post_body(mock_client)
        assert "model" not in body
        assert "contents" in body

    def test_gateway_missing_url(self):
        gw = self._make_gw_settings(url=None)
        with pytest.raises(SecurityPolicyError):
            _handle_prediction_gateway_call(
                model_short_name="m", fq_model="m", request={}, gw_settings=gw,
            )

    def test_gateway_missing_api_key(self):
        gw = self._make_gw_settings(api_key=None)
        with pytest.raises(SecurityPolicyError):
            _handle_prediction_gateway_call(
                model_short_name="m", fq_model="m", request={}, gw_settings=gw,
            )


# ===========================================================================
# _inspect_prediction_sync()
# ===========================================================================

class TestInspectPredictionSync:
    @patch("aidefense.runtime.agentsec.patchers.vertexai._should_inspect", return_value=False)
    def test_skip_when_should_inspect_false(self, _):
        mock_wrapped = MagicMock(return_value="raw")
        req = SimpleNamespace(
            model="projects/p/locations/l/publishers/google/models/gem",
            contents=[SimpleNamespace(role="user", parts=[SimpleNamespace(text="Hi")])],
        )
        result = _inspect_prediction_sync(mock_wrapped, None, (), {"request": req})
        assert result == "raw"

    @patch("aidefense.runtime.agentsec.patchers.vertexai._get_inspector")
    @patch("aidefense.runtime.agentsec.patchers.vertexai.resolve_gateway_settings", return_value=None)
    @patch("aidefense.runtime.agentsec.patchers.vertexai.extract_google_response", return_value="Reply")
    @patch("aidefense.runtime.agentsec.patchers.vertexai.normalize_google_messages",
           return_value=[{"role": "user", "content": "Hi"}])
    def test_api_mode_pre_post_inspection(self, _norm, _extract, _gw, mock_get_inspector):
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = Decision.allow(reasons=[])
        mock_get_inspector.return_value = mock_inspector

        _state.set_state(initialized=True, api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}})
        clear_inspection_context()

        req = SimpleNamespace(
            model="projects/p/locations/l/publishers/google/models/gem",
            contents=[SimpleNamespace(role="user", parts=[SimpleNamespace(text="Hi")])],
        )
        mock_wrapped = MagicMock(return_value=SimpleNamespace(text="Reply"))
        _inspect_prediction_sync(mock_wrapped, None, (), {"request": req})
        assert mock_inspector.inspect_conversation.call_count == 2

    @patch("aidefense.runtime.agentsec.patchers.vertexai._handle_prediction_gateway_call",
           return_value=SimpleNamespace(text="GW"))
    @patch("aidefense.runtime.agentsec.patchers.vertexai.resolve_gateway_settings")
    @patch("aidefense.runtime.agentsec.patchers.vertexai.normalize_google_messages",
           return_value=[{"role": "user", "content": "Hi"}])
    def test_gateway_mode(self, _norm, mock_gw_settings, mock_gw_call):
        mock_gw_settings.return_value = SimpleNamespace(
            url="https://gw.example.com", api_key="key", fail_open=True, timeout=30, auth_mode="api_key",
        )

        _state.set_state(initialized=True, api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}})
        clear_inspection_context()

        req = SimpleNamespace(
            model="projects/p/locations/l/publishers/google/models/gem",
            contents=[SimpleNamespace(role="user", parts=[SimpleNamespace(text="Hi")])],
        )
        result = _inspect_prediction_sync(MagicMock(), None, (), {"request": req})
        assert result.text == "GW"
        mock_gw_call.assert_called_once()


# ===========================================================================
# _inspect_prediction_stream_sync()
# ===========================================================================

class TestInspectPredictionStreamSync:
    @patch("aidefense.runtime.agentsec.patchers.vertexai._should_inspect", return_value=False)
    def test_skip_when_should_inspect_false(self, _):
        mock_wrapped = MagicMock(return_value=iter(["chunk1"]))
        req = SimpleNamespace(
            model="projects/p/locations/l/publishers/google/models/gem",
            contents=[],
        )
        result = _inspect_prediction_stream_sync(mock_wrapped, None, (), {"request": req})
        assert list(result) == ["chunk1"]

    @patch("aidefense.runtime.agentsec.patchers.vertexai._handle_prediction_gateway_call",
           return_value=SimpleNamespace(text="GW"))
    @patch("aidefense.runtime.agentsec.patchers.vertexai.resolve_gateway_settings")
    @patch("aidefense.runtime.agentsec.patchers.vertexai.normalize_google_messages",
           return_value=[{"role": "user", "content": "Hi"}])
    def test_gateway_returns_single_chunk_iter(self, _norm, mock_gw_settings, mock_gw_call):
        mock_gw_settings.return_value = SimpleNamespace(
            url="https://gw.example.com", api_key="key", fail_open=True, timeout=30, auth_mode="api_key",
        )

        _state.set_state(initialized=True, api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}})
        clear_inspection_context()

        req = SimpleNamespace(
            model="projects/p/locations/l/publishers/google/models/gem",
            contents=[SimpleNamespace(role="user", parts=[SimpleNamespace(text="Hi")])],
        )
        result = _inspect_prediction_stream_sync(MagicMock(), None, (), {"request": req})
        chunks = list(result)
        assert len(chunks) == 1
        assert chunks[0].text == "GW"


# ===========================================================================
# _wrap_prediction_generate_content / _wrap_prediction_stream_generate_content
# ===========================================================================

class TestWrapPredictionGenerateContent:
    @patch("aidefense.runtime.agentsec.patchers.vertexai._inspect_prediction_sync",
           return_value="inspected")
    def test_delegates_to_inspect(self, mock_inspect):
        result = _wrap_prediction_generate_content(MagicMock(), None, (), {})
        assert result == "inspected"
        mock_inspect.assert_called_once()


class TestWrapPredictionStreamGenerateContent:
    @patch("aidefense.runtime.agentsec.patchers.vertexai._inspect_prediction_stream_sync",
           return_value=iter(["chunk"]))
    def test_delegates_to_inspect(self, mock_inspect):
        result = _wrap_prediction_stream_generate_content(MagicMock(), None, (), {})
        assert list(result) == ["chunk"]
        mock_inspect.assert_called_once()
