# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Unit tests for the native Anthropic Messages API patcher."""

import asyncio

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from aidefense.runtime.agentsec import _state
from aidefense.runtime.agentsec._context import clear_inspection_context
from aidefense.runtime.agentsec.decision import Decision
from aidefense.runtime.agentsec.exceptions import SecurityPolicyError
from aidefense.runtime.agentsec.patchers import reset_registry
from aidefense.runtime.agentsec.patchers.anthropic import (
    _AnthropicAsyncStreamManagerProxy,
    _AnthropicStreamManagerProxy,
    _extract_assistant_content,
    _gateway_request_body,
    _gateway_url,
    _normalize_kwargs,
    _normalize_messages,
    _wrap_create,
    _wrap_create_async,
    _wrap_stream,
    _wrap_stream_async,
    patch_anthropic,
)


@pytest.fixture(autouse=True)
def reset_state():
    _state.reset()
    reset_registry()
    clear_inspection_context()
    import aidefense.runtime.agentsec.patchers.anthropic as anthropic_module

    anthropic_module._inspector = None
    yield
    _state.reset()
    reset_registry()
    clear_inspection_context()
    anthropic_module._inspector = None


def _enable_api(mode="monitor", fail_open=True):
    _state.set_state(
        initialized=True,
        llm_rules=None,
        api_mode={"llm_defaults": {"fail_open": fail_open}, "llm": {"mode": mode}},
    )


class _FakeMessageStream:
    """Mimics Anthropic 0.71.0: the body cannot be read after the manager closes it."""

    def __init__(self, final_message, error=None):
        self.closed = False
        self.final_message_calls = 0
        self._final_message = final_message
        self._error = error

    def _read_final_message(self):
        self.final_message_calls += 1
        if self.closed:
            raise RuntimeError(
                "Attempted to read or stream content, but the stream has been closed."
            )
        if self._error is not None:
            raise self._error
        return self._final_message

    def get_final_message(self):
        return self._read_final_message()


class _FakeAsyncMessageStream(_FakeMessageStream):
    async def get_final_message(self):
        return self._read_final_message()


class _FakeStreamManager:
    def __init__(self, stream):
        self.stream = stream

    def __enter__(self):
        return self.stream

    def __exit__(self, exc_type, exc, exc_tb):
        self.stream.closed = True
        return False

    async def __aenter__(self):
        return self.stream

    async def __aexit__(self, exc_type, exc, exc_tb):
        self.stream.closed = True
        return False


def _stream_kwargs():
    return {"model": "claude-sonnet", "messages": [{"role": "user", "content": "Hi"}]}


_SSN_REPLY = {"content": [{"type": "text", "text": "123-45-6789"}]}


class TestAnthropicNormalization:
    def test_normalizes_system_and_native_content_blocks(self):
        messages = _normalize_messages(
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Run the tool"},
                        {"type": "image", "source": {"media_type": "image/png"}},
                    ],
                },
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "lookup",
                            "input": {"query": "secret"},
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "tool-1",
                            "content": "result",
                        }
                    ],
                },
            ],
            system="You are a secure assistant.",
        )

        assert messages[0] == {
            "role": "system",
            "content": "You are a secure assistant.",
        }
        assert "Run the tool" in messages[1]["content"]
        assert "[image image/png]" in messages[1]["content"]
        assert "tool_use name=lookup" in messages[2]["content"]
        assert "tool_result id=tool-1" in messages[3]["content"]

    def test_extracts_text_and_tool_use_response_blocks(self):
        response = {
            "content": [
                {"type": "text", "text": "I will look that up."},
                {"type": "tool_use", "name": "lookup", "input": {"id": 1}},
            ]
        }
        content = _extract_assistant_content(response)
        assert "I will look that up." in content
        assert "tool_use name=lookup" in content

    def test_normalizes_tool_definitions(self):
        messages = _normalize_kwargs(
            {
                "messages": [{"role": "user", "content": "Use lookup"}],
                "tools": [{"name": "lookup", "description": "Look up a value"}],
            }
        )
        assert messages[-1]["role"] == "system"
        assert "tool_definitions" in messages[-1]["content"]

    def test_materializes_iterable_messages_for_inspection(self):
        prompt = {"role": "user", "content": "My social security number is 123-45-6789"}
        kwargs = {"messages": (m for m in [prompt])}

        messages = _normalize_kwargs(kwargs)

        assert kwargs["messages"] == [prompt]
        assert messages[-1]["role"] == "user"
        assert "123-45-6789" in messages[-1]["content"]

    def test_gateway_uses_native_messages_endpoint_and_payload(self):
        settings = SimpleNamespace(url="https://gateway.example.com/tenant/connection")
        assert _gateway_url(settings) == "https://gateway.example.com/tenant/connection/v1/messages"
        body = _gateway_request_body(
            {
                "model": "claude-sonnet",
                "max_tokens": 100,
                "system": "Be concise",
                "messages": [{"role": "user", "content": "Hi"}],
                "stream": True,
            },
            False,
        )
        assert body["system"] == "Be concise"
        assert body["messages"][0]["role"] == "user"
        assert "stream" not in body


class TestAnthropicInspection:
    @patch("aidefense.runtime.agentsec.patchers.anthropic._get_inspector")
    def test_sync_create_inspects_request_and_response(self, get_inspector):
        _enable_api()
        inspector = MagicMock()
        inspector.inspect_conversation.return_value = Decision.allow()
        get_inspector.return_value = inspector

        response = {"content": [{"type": "text", "text": "Hello"}]}
        wrapped = MagicMock(return_value=response)
        result = _wrap_create(
            wrapped,
            MagicMock(),
            (),
            {
                "model": "claude-sonnet",
                "max_tokens": 100,
                "system": "Be concise",
                "messages": [{"role": "user", "content": "Hi"}],
            },
        )

        assert result == response
        assert inspector.inspect_conversation.call_count == 2
        wrapped.assert_called_once()
        inspected_request = inspector.inspect_conversation.call_args_list[0].args[0]
        assert inspected_request[0]["role"] == "system"
        assert inspected_request[1]["content"] == "Hi"

    @patch("aidefense.runtime.agentsec.patchers.anthropic._get_inspector")
    def test_enforce_mode_blocks_before_provider_call(self, get_inspector):
        _enable_api(mode="enforce")
        inspector = MagicMock()
        inspector.inspect_conversation.return_value = Decision.block(reasons=["blocked"])
        get_inspector.return_value = inspector
        wrapped = MagicMock()

        with pytest.raises(SecurityPolicyError):
            _wrap_create(
                wrapped,
                MagicMock(),
                (),
                {"model": "claude-sonnet", "messages": [{"role": "user", "content": "Hi"}]},
            )

        wrapped.assert_not_called()

    @patch("aidefense.runtime.agentsec.patchers.anthropic._get_inspector")
    def test_iterable_messages_are_inspected_before_provider_call(self, get_inspector):
        _enable_api(mode="enforce")
        inspector = MagicMock()
        inspector.inspect_conversation.return_value = Decision.block(reasons=["pii"])
        get_inspector.return_value = inspector
        wrapped = MagicMock()

        class MessageIterable:
            def __iter__(self):
                yield {
                    "role": "user",
                    "content": "My social security number is 123-45-6789",
                }

        with pytest.raises(SecurityPolicyError):
            _wrap_create(
                wrapped,
                MagicMock(),
                (),
                {"model": "claude-sonnet", "messages": MessageIterable()},
            )

        wrapped.assert_not_called()
        request_messages = inspector.inspect_conversation.call_args.args[0]
        assert "123-45-6789" in request_messages[-1]["content"]

    @patch("aidefense.runtime.agentsec.patchers.anthropic._get_inspector")
    def test_sync_stream_inspects_accumulated_text(self, get_inspector):
        _enable_api()
        inspector = MagicMock()
        inspector.inspect_conversation.return_value = Decision.allow()
        get_inspector.return_value = inspector
        events = [
            SimpleNamespace(
                type="content_block_delta",
                delta=SimpleNamespace(type="text_delta", text="hello"),
            ),
            SimpleNamespace(type="message_stop"),
        ]
        wrapped = MagicMock(return_value=iter(events))

        result = _wrap_create(
            wrapped,
            MagicMock(),
            (),
            {
                "model": "claude-sonnet",
                "max_tokens": 100,
                "messages": [{"role": "user", "content": "Hi"}],
                "stream": True,
            },
        )
        assert list(result) == events
        assert inspector.inspect_conversation.call_count == 2
        final_request = inspector.inspect_conversation.call_args_list[-1].args[0]
        assert final_request[-1] == {"role": "assistant", "content": "hello"}

    @pytest.mark.asyncio
    @patch("aidefense.runtime.agentsec.patchers.anthropic._get_inspector")
    async def test_async_create_inspects_request_and_response(self, get_inspector):
        _enable_api()
        inspector = MagicMock()
        inspector.ainspect_conversation = AsyncMock(return_value=Decision.allow())
        get_inspector.return_value = inspector
        response = {"content": [{"type": "text", "text": "Hello"}]}
        wrapped = AsyncMock(return_value=response)

        result = await _wrap_create_async(
            wrapped,
            MagicMock(),
            (),
            {"model": "claude-sonnet", "max_tokens": 100, "messages": [{"role": "user", "content": "Hi"}]},
        )

        assert result == response
        assert inspector.ainspect_conversation.call_count == 2
        wrapped.assert_awaited_once()

    @patch("aidefense.runtime.agentsec.patchers.anthropic._get_inspector")
    def test_sync_stream_manager_preserves_text_stream_and_inspects_final_message(self, get_inspector):
        _enable_api()
        inspector = MagicMock()
        inspector.inspect_conversation.return_value = Decision.allow()
        get_inspector.return_value = inspector

        final_message = {"content": [{"type": "text", "text": "done"}]}

        class FakeStream:
            def __init__(self):
                self._events = iter(
                    [
                        SimpleNamespace(
                            type="content_block_delta",
                            delta=SimpleNamespace(type="text_delta", text="done"),
                        )
                    ]
                )

            def __iter__(self):
                return self

            def __next__(self):
                return next(self._events)

            def get_final_message(self):
                return final_message

        class FakeManager:
            def __enter__(self):
                return FakeStream()

            def __exit__(self, exc_type, exc, exc_tb):
                return False

        manager = _wrap_stream(
            MagicMock(return_value=FakeManager()),
            MagicMock(),
            (),
            {"model": "claude-sonnet", "messages": [{"role": "user", "content": "Hi"}]},
        )

        assert isinstance(manager, _AnthropicStreamManagerProxy)
        with manager as stream:
            assert list(stream.text_stream) == ["done"]
        assert inspector.inspect_conversation.call_count == 2

    @pytest.mark.asyncio
    @patch("aidefense.runtime.agentsec.patchers.anthropic._get_inspector")
    async def test_async_stream_manager_preserves_text_stream_and_inspects_final_message(self, get_inspector):
        _enable_api()
        inspector = MagicMock()
        inspector.ainspect_conversation = AsyncMock(return_value=Decision.allow())
        get_inspector.return_value = inspector

        final_message = {"content": [{"type": "text", "text": "done"}]}

        class FakeStream:
            def __init__(self):
                self._events = iter(
                    [
                        SimpleNamespace(
                            type="content_block_delta",
                            delta=SimpleNamespace(type="text_delta", text="done"),
                        )
                    ]
                )

            def __aiter__(self):
                return self

            async def __anext__(self):
                try:
                    return next(self._events)
                except StopIteration:
                    raise StopAsyncIteration

            async def get_final_message(self):
                return final_message

        class FakeManager:
            async def __aenter__(self):
                return FakeStream()

            async def __aexit__(self, exc_type, exc, exc_tb):
                return False

        manager = _wrap_stream_async(
            MagicMock(return_value=FakeManager()),
            MagicMock(),
            (),
            {"model": "claude-sonnet", "messages": [{"role": "user", "content": "Hi"}]},
        )

        assert isinstance(manager, _AnthropicAsyncStreamManagerProxy)
        async with manager as stream:
            chunks = []
            async for chunk in stream.text_stream:
                chunks.append(chunk)
            assert chunks == ["done"]
        assert inspector.ainspect_conversation.call_count == 2

    @patch("aidefense.runtime.agentsec.patchers.anthropic._get_inspector")
    def test_sync_unread_stream_is_inspected_before_close(self, get_inspector):
        _enable_api()
        inspector = MagicMock()
        inspector.inspect_conversation.return_value = Decision.allow()
        get_inspector.return_value = inspector
        fake_manager = _FakeStreamManager(_FakeMessageStream(_SSN_REPLY))
        manager = _wrap_stream(MagicMock(return_value=fake_manager), MagicMock(), (), _stream_kwargs())

        with manager:
            pass

        assert fake_manager.stream.closed is True
        assert inspector.inspect_conversation.call_count == 2
        response_messages = inspector.inspect_conversation.call_args_list[1].args[0]
        assert "123-45-6789" in response_messages[-1]["content"]

    @patch("aidefense.runtime.agentsec.patchers.anthropic._get_inspector")
    def test_sync_unread_stream_block_raises_and_still_closes(self, get_inspector):
        _enable_api(mode="enforce")
        inspector = MagicMock()
        inspector.inspect_conversation.side_effect = [
            Decision.allow(),
            Decision.block(reasons=["pii"]),
        ]
        get_inspector.return_value = inspector
        fake_manager = _FakeStreamManager(_FakeMessageStream(_SSN_REPLY))
        manager = _wrap_stream(MagicMock(return_value=fake_manager), MagicMock(), (), _stream_kwargs())

        with pytest.raises(SecurityPolicyError):
            with manager:
                pass

        assert fake_manager.stream.closed is True
        assert inspector.inspect_conversation.call_count == 2

    @patch("aidefense.runtime.agentsec.patchers.anthropic._get_inspector")
    def test_sync_body_exception_skips_drain_and_keeps_original_error(self, get_inspector):
        _enable_api(mode="enforce", fail_open=False)
        inspector = MagicMock()
        inspector.inspect_conversation.return_value = Decision.allow()
        get_inspector.return_value = inspector
        stream = _FakeMessageStream(_SSN_REPLY, error=RuntimeError("broken stream"))
        fake_manager = _FakeStreamManager(stream)
        manager = _wrap_stream(MagicMock(return_value=fake_manager), MagicMock(), (), _stream_kwargs())

        with pytest.raises(ValueError, match="caller error"):
            with manager:
                raise ValueError("caller error")

        assert stream.closed is True
        assert stream.final_message_calls == 0
        assert inspector.inspect_conversation.call_count == 1

    @pytest.mark.asyncio
    @patch("aidefense.runtime.agentsec.patchers.anthropic._get_inspector")
    async def test_async_unread_stream_is_inspected_before_close(self, get_inspector):
        _enable_api()
        inspector = MagicMock()
        inspector.ainspect_conversation = AsyncMock(return_value=Decision.allow())
        get_inspector.return_value = inspector
        fake_manager = _FakeStreamManager(_FakeAsyncMessageStream(_SSN_REPLY))
        manager = _wrap_stream_async(
            MagicMock(return_value=fake_manager), MagicMock(), (), _stream_kwargs()
        )

        async with manager:
            pass

        assert fake_manager.stream.closed is True
        assert inspector.ainspect_conversation.call_count == 2
        response_messages = inspector.ainspect_conversation.call_args_list[1].args[0]
        assert "123-45-6789" in response_messages[-1]["content"]

    @pytest.mark.asyncio
    @patch("aidefense.runtime.agentsec.patchers.anthropic._get_inspector")
    async def test_async_unread_stream_block_raises_and_still_closes(self, get_inspector):
        _enable_api(mode="enforce")
        inspector = MagicMock()
        inspector.ainspect_conversation = AsyncMock(
            side_effect=[Decision.allow(), Decision.block(reasons=["pii"])]
        )
        get_inspector.return_value = inspector
        fake_manager = _FakeStreamManager(_FakeAsyncMessageStream(_SSN_REPLY))
        manager = _wrap_stream_async(
            MagicMock(return_value=fake_manager), MagicMock(), (), _stream_kwargs()
        )

        with pytest.raises(SecurityPolicyError):
            async with manager:
                pass

        assert fake_manager.stream.closed is True
        assert inspector.ainspect_conversation.call_count == 2

    @pytest.mark.asyncio
    @patch("aidefense.runtime.agentsec.patchers.anthropic._get_inspector")
    async def test_async_body_exception_skips_drain_and_keeps_original_error(self, get_inspector):
        _enable_api(mode="enforce", fail_open=False)
        inspector = MagicMock()
        inspector.ainspect_conversation = AsyncMock(return_value=Decision.allow())
        get_inspector.return_value = inspector
        stream = _FakeAsyncMessageStream(_SSN_REPLY, error=RuntimeError("broken stream"))
        fake_manager = _FakeStreamManager(stream)
        manager = _wrap_stream_async(
            MagicMock(return_value=fake_manager), MagicMock(), (), _stream_kwargs()
        )

        with pytest.raises(ValueError, match="caller error"):
            async with manager:
                raise ValueError("caller error")

        assert stream.closed is True
        assert stream.final_message_calls == 0
        assert inspector.ainspect_conversation.call_count == 1

    @pytest.mark.asyncio
    @patch("aidefense.runtime.agentsec.patchers.anthropic._get_inspector")
    async def test_async_cancellation_skips_drain_and_closes(self, get_inspector):
        _enable_api(mode="enforce", fail_open=False)
        inspector = MagicMock()
        inspector.ainspect_conversation = AsyncMock(return_value=Decision.allow())
        get_inspector.return_value = inspector
        stream = _FakeAsyncMessageStream(_SSN_REPLY)
        fake_manager = _FakeStreamManager(stream)
        manager = _wrap_stream_async(
            MagicMock(return_value=fake_manager), MagicMock(), (), _stream_kwargs()
        )

        with pytest.raises(asyncio.CancelledError):
            async with manager:
                raise asyncio.CancelledError()

        assert stream.closed is True
        assert stream.final_message_calls == 0
        assert inspector.ainspect_conversation.call_count == 1


class TestAnthropicPatchApply:
    def test_returns_false_when_anthropic_is_not_installed(self):
        with patch(
            "aidefense.runtime.agentsec.patchers.anthropic.safe_import",
            return_value=None,
        ):
            assert patch_anthropic() is False

    def test_patches_sync_and_async_message_methods(self):
        with patch(
            "aidefense.runtime.agentsec.patchers.anthropic.safe_import",
            return_value=MagicMock(),
        ), patch("aidefense.runtime.agentsec.patchers.anthropic.wrapt") as wrapt_mock:
            assert patch_anthropic() is True
            assert wrapt_mock.wrap_function_wrapper.call_count >= 4
