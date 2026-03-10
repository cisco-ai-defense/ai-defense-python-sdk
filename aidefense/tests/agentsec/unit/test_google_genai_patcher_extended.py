"""Extended tests for the google-genai SDK patcher.

Covers _should_inspect, _enforce_decision, _serialize_part, _serialize_sdk_object,
_extract_model_name, _extract_genai_response, response wrappers, _get_inspector,
_wrap_generate_content, GoogleGenAIStreamingWrapper, and patch_google_genai.
No async functions tested.
"""

import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from aidefense.runtime.agentsec.patchers.google_genai import (
    _serialize_part,
    _serialize_sdk_object,
    _extract_model_name,
    _extract_genai_response,
    _should_inspect,
    _GoogleGenAIResponseWrapper,
    _PromptFeedbackWrapper,
    _UsageMetadataWrapper,
    _CandidateWrapper,
    _ContentWrapper,
    _PartWrapper,
    _FunctionCallWrapper,
    _FunctionResponseWrapper,
    GoogleGenAIStreamingWrapper,
    _wrap_generate_content,
    patch_google_genai,
)
from aidefense.runtime.agentsec.decision import Decision
from aidefense.runtime.agentsec import _state
from aidefense.runtime.agentsec._context import clear_inspection_context
from aidefense.runtime.agentsec.patchers import reset_registry


@pytest.fixture(autouse=True)
def reset_state():
    _state.reset()
    reset_registry()
    clear_inspection_context()
    import aidefense.runtime.agentsec.patchers.google_genai as google_genai_module
    google_genai_module._inspector = None
    yield
    _state.reset()
    reset_registry()
    clear_inspection_context()
    google_genai_module._inspector = None


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
# _serialize_part()
# ===========================================================================

class TestSerializePart:
    def test_dict_input_returns_as_is(self):
        part = {"text": "hello"}
        assert _serialize_part(part) == {"text": "hello"}

    def test_object_with_text_attr(self):
        part = SimpleNamespace(text="foo bar")
        assert _serialize_part(part) == {"text": "foo bar"}

    def test_object_with_function_call(self):
        fc = SimpleNamespace(name="get_weather", args={"location": "NYC"})
        part = SimpleNamespace(text=None, function_call=fc, function_response=None)
        result = _serialize_part(part)
        assert result == {"functionCall": {"name": "get_weather", "args": {"location": "NYC"}}}

    def test_object_with_function_response(self):
        fr = SimpleNamespace(name="get_weather", response={"temp": 72})
        part = SimpleNamespace(text=None, function_call=None, function_response=fr)
        result = _serialize_part(part)
        assert result == {"functionResponse": {"name": "get_weather", "response": {"temp": 72}}}

    def test_pydantic_model_dump(self):
        part = MagicMock()
        part.model_dump.return_value = {"text": "pydantic"}
        part.text = None
        part.function_call = None
        part.function_response = None
        result = _serialize_part(part)
        assert result == {"text": "pydantic"}


# ===========================================================================
# _serialize_sdk_object()
# ===========================================================================

class TestSerializeSdkObject:
    def test_none_returns_none(self):
        assert _serialize_sdk_object(None) is None

    def test_str_returns_as_is(self):
        assert _serialize_sdk_object("hello") == "hello"

    def test_dict_returns_as_is(self):
        d = {"key": "value"}
        assert _serialize_sdk_object(d) == d

    def test_list_recursively_serializes(self):
        obj = MagicMock()
        obj.model_dump.return_value = {"x": 1}
        result = _serialize_sdk_object([obj])
        assert result == [{"x": 1}]

    def test_object_with_model_dump(self):
        obj = MagicMock()
        obj.model_dump.return_value = {"declarations": []}
        assert _serialize_sdk_object(obj) == {"declarations": []}

    def test_object_with_dict_method(self):
        obj = MagicMock(spec=["dict"])
        obj.dict.return_value = {"old": "pydantic v1"}
        assert _serialize_sdk_object(obj) == {"old": "pydantic v1"}

    def test_object_with_to_dict_proto_plus(self):
        # Proto-plus uses type(obj).to_dict(obj)
        def to_dict(inst):
            return {"proto": "serialized"}

        cls = type("ProtoObj", (), {"to_dict": staticmethod(to_dict)})
        obj = cls()
        assert _serialize_sdk_object(obj) == {"proto": "serialized"}


# ===========================================================================
# _extract_model_name()
# ===========================================================================

class TestExtractModelName:
    def test_str_returns_as_is(self):
        assert _extract_model_name("gemini-2.0-flash") == "gemini-2.0-flash"

    def test_object_with_name_attribute(self):
        model = SimpleNamespace(name="gemini-1.5-pro")
        assert _extract_model_name(model) == "gemini-1.5-pro"

    def test_object_with_model_name_attribute(self):
        model = SimpleNamespace(model_name="gemini-1.0-pro")
        assert _extract_model_name(model) == "gemini-1.0-pro"

    def test_none_returns_unknown(self):
        assert _extract_model_name(None) == "unknown"


# ===========================================================================
# _extract_genai_response()
# ===========================================================================

class TestExtractGenaiResponse:
    def test_exception_path_returns_empty_string(self):
        class BadResponse:
            @property
            def text(self):
                raise ValueError("no text")

        result = _extract_genai_response(BadResponse())
        assert result == ""


# ===========================================================================
# _GoogleGenAIResponseWrapper
# ===========================================================================

class TestGoogleGenAIResponseWrapper:
    def test_valid_dict(self):
        data = {
            "candidates": [{
                "content": {"role": "model", "parts": [{"text": "Hello!"}]},
                "finishReason": "STOP",
            }],
        }
        wrapper = _GoogleGenAIResponseWrapper(data)
        assert wrapper.text == "Hello!"
        assert wrapper.to_dict() == data

    def test_invalid_non_dict_raises_value_error(self):
        with pytest.raises(ValueError, match="expected dict"):
            _GoogleGenAIResponseWrapper("not a dict")

    def test_text_property_from_candidates(self):
        data = {
            "candidates": [{
                "content": {"role": "model", "parts": [{"text": "Response text"}]},
            }],
        }
        wrapper = _GoogleGenAIResponseWrapper(data)
        assert wrapper.text == "Response text"

    def test_candidates_property(self):
        data = {
            "candidates": [
                {"content": {"parts": [{"text": "First"}]}},
                {"content": {"parts": [{"text": "Second"}]}},
            ],
        }
        wrapper = _GoogleGenAIResponseWrapper(data)
        assert len(wrapper.candidates) == 2
        assert wrapper.candidates[0].content.parts[0].text == "First"
        assert wrapper.candidates[1].content.parts[0].text == "Second"


# ===========================================================================
# _PromptFeedbackWrapper
# ===========================================================================

class TestPromptFeedbackWrapper:
    def test_block_reason(self):
        wrapper = _PromptFeedbackWrapper({"blockReason": 1})
        assert wrapper.block_reason == 1

    def test_block_reason_snake_case(self):
        wrapper = _PromptFeedbackWrapper({"block_reason": 2})
        assert wrapper.block_reason == 2

    def test_bool_false_when_no_block(self):
        wrapper = _PromptFeedbackWrapper({})
        assert bool(wrapper) is False

    def test_bool_true_when_blocked(self):
        wrapper = _PromptFeedbackWrapper({"blockReason": 1})
        assert bool(wrapper) is True


# ===========================================================================
# _UsageMetadataWrapper
# ===========================================================================

class TestUsageMetadataWrapper:
    def test_token_counts_camel_case(self):
        wrapper = _UsageMetadataWrapper({
            "promptTokenCount": 10,
            "candidatesTokenCount": 5,
            "totalTokenCount": 15,
        })
        assert wrapper.prompt_token_count == 10
        assert wrapper.candidates_token_count == 5
        assert wrapper.total_token_count == 15

    def test_token_counts_snake_case(self):
        wrapper = _UsageMetadataWrapper({
            "prompt_token_count": 20,
            "candidates_token_count": 10,
            "total_token_count": 30,
        })
        assert wrapper.prompt_token_count == 20
        assert wrapper.candidates_token_count == 10
        assert wrapper.total_token_count == 30

    def test_empty_returns_zero(self):
        wrapper = _UsageMetadataWrapper({})
        assert wrapper.prompt_token_count == 0
        assert wrapper.total_token_count == 0


# ===========================================================================
# _CandidateWrapper, _ContentWrapper, _PartWrapper
# ===========================================================================

class TestCandidateWrapper:
    def test_content_property(self):
        data = {"content": {"role": "model", "parts": [{"text": "x"}]}}
        c = _CandidateWrapper(data)
        assert c.content.role == "model"
        assert c.content.parts[0].text == "x"

    def test_finish_reason(self):
        c = _CandidateWrapper({"finishReason": "STOP"})
        assert c.finish_reason == "STOP"


class TestContentWrapper:
    def test_role_default_model(self):
        c = _ContentWrapper({})
        assert c.role == "model"

    def test_role_setter(self):
        c = _ContentWrapper({})
        c.role = "user"
        assert c._data["role"] == "user"

    def test_parts_property(self):
        c = _ContentWrapper({"parts": [{"text": "a"}, {"text": "b"}]})
        assert len(c.parts) == 2
        assert c.parts[0].text == "a"
        assert c.parts[1].text == "b"


class TestPartWrapper:
    def test_text_property(self):
        p = _PartWrapper({"text": "hello"})
        assert p.text == "hello"

    def test_function_call_property(self):
        p = _PartWrapper({"functionCall": {"name": "foo", "args": {"x": 1}}})
        fc = p.function_call
        assert fc is not None
        assert fc.name == "foo"
        assert fc.args == {"x": 1}

    def test_function_response_property(self):
        p = _PartWrapper({"functionResponse": {"name": "foo", "response": {"result": "ok"}}})
        fr = p.function_response
        assert fr is not None
        assert fr.name == "foo"
        assert fr.response == {"result": "ok"}


# ===========================================================================
# _FunctionCallWrapper, _FunctionResponseWrapper
# ===========================================================================

class TestFunctionCallWrapper:
    def test_name_and_args(self):
        fc = _FunctionCallWrapper({"name": "my_func", "args": {"arg1": 42}})
        assert fc.name == "my_func"
        assert fc.args == {"arg1": 42}


class TestFunctionResponseWrapper:
    def test_name_and_response(self):
        fr = _FunctionResponseWrapper({"name": "my_func", "response": {"output": "done"}})
        assert fr.name == "my_func"
        assert fr.response == {"output": "done"}


# ===========================================================================
# patch_google_genai()
# ===========================================================================

class TestPatchGoogleGenai:
    def test_successful_patch(self):
        with (
            patch("aidefense.runtime.agentsec.patchers.google_genai.safe_import", return_value=MagicMock()),
            patch("aidefense.runtime.agentsec.patchers.google_genai.is_patched", return_value=False),
            patch("aidefense.runtime.agentsec.patchers.google_genai.wrapt") as mock_wrapt,
            patch("aidefense.runtime.agentsec.patchers.google_genai.mark_patched"),
        ):
            assert patch_google_genai() is True
            assert mock_wrapt.wrap_function_wrapper.call_count >= 1

    def test_patch_failure_returns_false(self):
        with (
            patch("aidefense.runtime.agentsec.patchers.google_genai.safe_import", return_value=MagicMock()),
            patch("aidefense.runtime.agentsec.patchers.google_genai.is_patched", return_value=False),
            patch("aidefense.runtime.agentsec.patchers.google_genai.wrapt") as mock_wrapt,
        ):
            mock_wrapt.wrap_function_wrapper.side_effect = Exception("fail")
            assert patch_google_genai() is False


# ===========================================================================
# _serialize_part() — deeper branches
# ===========================================================================

class TestSerializePartDeeper:
    def test_function_call_with_map_composite_args(self):
        """When args has .items() (MapComposite), should convert via dict()."""
        class MapLike:
            def items(self):
                return [("k", "v")]
            def keys(self):
                return ["k"]
            def __getitem__(self, key):
                return {"k": "v"}[key]
            def __iter__(self):
                return iter(["k"])
            def __len__(self):
                return 1
        fc = SimpleNamespace(name="tool", args=MapLike())
        part = SimpleNamespace(text=None, function_call=fc, function_response=None)
        result = _serialize_part(part)
        assert result["functionCall"]["args"] == {"k": "v"}

    def test_function_response_with_map_composite(self):
        class MapLike:
            def items(self):
                return [("status", "ok")]
            def keys(self):
                return ["status"]
            def __getitem__(self, key):
                return {"status": "ok"}[key]
            def __iter__(self):
                return iter(["status"])
            def __len__(self):
                return 1
        fr = SimpleNamespace(name="tool", response=MapLike())
        part = SimpleNamespace(text=None, function_call=None, function_response=fr)
        result = _serialize_part(part)
        assert result["functionResponse"]["response"] == {"status": "ok"}

    def test_function_response_non_dict_fallback(self):
        fr = SimpleNamespace(name="tool", response="plain result")
        part = SimpleNamespace(text=None, function_call=None, function_response=fr)
        result = _serialize_part(part)
        assert result["functionResponse"]["response"] == {"result": "plain result"}

    def test_pydantic_model_dump_fallback_to_non_json(self):
        """When model_dump(mode='json') raises, should fall back to model_dump(by_alias=True)."""
        part = MagicMock()
        part.model_dump.side_effect = [TypeError("no json"), {"text": "v2 fallback"}]
        part.text = None
        part.function_call = None
        part.function_response = None
        result = _serialize_part(part)
        assert result == {"text": "v2 fallback"}

    def test_empty_part_returns_none(self):
        part = SimpleNamespace()
        result = _serialize_part(part)
        assert result is None


# ===========================================================================
# _CandidateWrapper — extra properties
# ===========================================================================

class TestCandidateWrapperExtended:
    def test_safety_ratings(self):
        data = {"safetyRatings": [{"category": "HARM", "probability": "LOW"}]}
        c = _CandidateWrapper(data)
        assert len(c.safety_ratings) == 1

    def test_index_property(self):
        c = _CandidateWrapper({"index": 2})
        assert c.index == 2

    def test_citation_metadata(self):
        c = _CandidateWrapper({"citationMetadata": {"sources": []}})
        assert c.citation_metadata == {"sources": []}

    def test_grounding_metadata(self):
        c = _CandidateWrapper({"groundingMetadata": {"info": True}})
        assert c.grounding_metadata == {"info": True}


# ===========================================================================
# _PartWrapper — stub attributes for framework compatibility
# ===========================================================================

class TestPartWrapperStubs:
    def test_inline_data_returns_none(self):
        p = _PartWrapper({})
        assert p.inline_data is None

    def test_executable_code_returns_none(self):
        p = _PartWrapper({})
        assert p.executable_code is None

    def test_code_execution_result_returns_none(self):
        p = _PartWrapper({})
        assert p.code_execution_result is None

    def test_file_data_returns_none(self):
        p = _PartWrapper({})
        assert p.file_data is None

    def test_video_metadata_returns_none(self):
        p = _PartWrapper({})
        assert p.video_metadata is None

    def test_thought_returns_none(self):
        p = _PartWrapper({})
        assert p.thought is None


# ===========================================================================
# _FunctionCallWrapper — __repr__
# ===========================================================================

class TestFunctionCallWrapperRepr:
    def test_repr(self):
        fc = _FunctionCallWrapper({"name": "foo", "args": {"x": 1}})
        assert "foo" in repr(fc)


# ===========================================================================
# _GoogleGenAIResponseWrapper — extra properties
# ===========================================================================

class TestGoogleGenAIResponseWrapperExtended:
    def test_prompt_feedback_property(self):
        data = {"promptFeedback": {"blockReason": 1}, "candidates": []}
        wrapper = _GoogleGenAIResponseWrapper(data)
        assert wrapper.prompt_feedback.block_reason == 1

    def test_usage_metadata_property(self):
        data = {"usageMetadata": {"totalTokenCount": 50}, "candidates": []}
        wrapper = _GoogleGenAIResponseWrapper(data)
        assert wrapper.usage_metadata.total_token_count == 50

    def test_model_version_property(self):
        data = {"modelVersion": "gemini-2.0", "candidates": []}
        wrapper = _GoogleGenAIResponseWrapper(data)
        assert wrapper.model_version == "gemini-2.0"

    def test_response_id_property(self):
        data = {"responseId": "resp-123", "candidates": []}
        wrapper = _GoogleGenAIResponseWrapper(data)
        assert wrapper.response_id == "resp-123"


# ===========================================================================
# GoogleGenAIStreamingWrapper — sync iteration
# ===========================================================================

class TestGoogleGenAIStreamingWrapper:
    @patch("aidefense.runtime.agentsec.patchers.google_genai._get_inspector")
    @patch("aidefense.runtime.agentsec.patchers.google_genai._extract_genai_response",
           return_value="streamed text")
    def test_buffers_and_inspects(self, _mock_extract, mock_get_inspector):
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = Decision.allow(reasons=[])
        mock_get_inspector.return_value = mock_inspector

        _state.set_state(initialized=True, api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}})
        clear_inspection_context()

        chunk = SimpleNamespace()
        wrapper = GoogleGenAIStreamingWrapper(iter([chunk]), [{"role": "user", "content": "Q"}], {})
        chunks = list(wrapper)
        assert len(chunks) == 1
        assert mock_inspector.inspect_conversation.called

    @patch("aidefense.runtime.agentsec.patchers.google_genai._get_inspector")
    @patch("aidefense.runtime.agentsec.patchers.google_genai._extract_genai_response",
           return_value="")
    def test_no_inspection_on_empty_stream(self, _mock_extract, mock_get_inspector):
        mock_inspector = MagicMock()
        mock_get_inspector.return_value = mock_inspector

        _state.set_state(initialized=True, api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}})
        clear_inspection_context()

        wrapper = GoogleGenAIStreamingWrapper(iter([SimpleNamespace()]), [], {})
        list(wrapper)
        mock_inspector.inspect_conversation.assert_not_called()


# ===========================================================================
# _wrap_generate_content() — sync
# ===========================================================================

class TestWrapGenerateContent:
    @patch("aidefense.runtime.agentsec.patchers.google_genai._should_inspect", return_value=False)
    def test_passthrough_when_skip(self, _):
        mock_wrapped = MagicMock(return_value="raw")
        result = _wrap_generate_content(mock_wrapped, None, (), {"model": "gemini", "contents": "Hi"})
        assert result == "raw"

    @patch("aidefense.runtime.agentsec.patchers.google_genai._get_inspector")
    @patch("aidefense.runtime.agentsec.patchers.google_genai.resolve_gateway_settings", return_value=None)
    @patch("aidefense.runtime.agentsec.patchers.google_genai.extract_google_response", return_value="Reply")
    @patch("aidefense.runtime.agentsec.patchers.google_genai.normalize_google_messages",
           return_value=[{"role": "user", "content": "Hi"}])
    def test_api_mode_pre_post_inspection(self, _norm, _extract, _gw, mock_get_inspector):
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = Decision.allow(reasons=[])
        mock_get_inspector.return_value = mock_inspector

        _state.set_state(initialized=True, api_mode={"llm_defaults": {"fail_open": True}, "llm": {"mode": "monitor"}})
        clear_inspection_context()

        mock_wrapped = MagicMock(return_value=SimpleNamespace(text="Reply"))
        _wrap_generate_content(mock_wrapped, None, (), {"model": "gemini", "contents": "Hi"})
        assert mock_inspector.inspect_conversation.call_count >= 1
