import pytest
from unittest.mock import patch, MagicMock
import secrets
from aidefense import ChatInspectionClient, Config
from aidefense.runtime import Message, Role


@pytest.fixture
def fake_chat_client():
    dummy_api_key = secrets.token_hex(32)  # 32 bytes = 64 hex chars
    with patch.object(ChatInspectionClient, 'inspect_prompt',
                      return_value=MagicMock(is_safe=True, __str__=lambda self: "fake_result")) as mock_prompt, \
            patch.object(ChatInspectionClient, 'inspect_conversation',
                         return_value=MagicMock(is_safe=True, __str__=lambda self: "fake_result")) as mock_conv, \
            patch.object(ChatInspectionClient, 'inspect_response',
                         return_value=MagicMock(is_safe=True, __str__=lambda self: "fake_result")) as mock_resp:
        yield ChatInspectionClient(api_key=dummy_api_key)


def test_chat_inspect_prompt(fake_chat_client):
    result = fake_chat_client.inspect_prompt("How to make a bomb?")
    assert result.is_safe
    assert str(result) == "fake_result"


def test_chat_inspect_conversation(fake_chat_client):
    conversation = [
        Message(role=Role.USER, content="Hi, can you help me with my account?"),
        Message(role=Role.ASSISTANT, content="Sure, what do you need help with?"),
    ]
    result = fake_chat_client.inspect_conversation(conversation)
    assert result.is_safe
    assert str(result) == "fake_result"


def test_chat_inspect_response(fake_chat_client):
    result = fake_chat_client.inspect_response("Here is some code ...")
    assert result.is_safe
    assert str(result) == "fake_result"


def test_chat_inspect_multiple_clients():
    config = Config(logger_params={"level": "DEBUG"})
    dummy_api_key_1 = secrets.token_hex(32)
    dummy_api_key_2 = secrets.token_hex(32)

    with patch.object(ChatInspectionClient, 'inspect_prompt', return_value=MagicMock(is_safe=True)), \
            patch.object(ChatInspectionClient, 'inspect_conversation', return_value=MagicMock(is_safe=True)):
        client1 = ChatInspectionClient(api_key=dummy_api_key_1, config=config)
        client2 = ChatInspectionClient(api_key=dummy_api_key_2, config=config)
        result1 = client1.inspect_prompt("Is this a safe prompt?")
        assert result1.is_safe
        conversation = [
            Message(role=Role.USER, content="Hi, can you help?"),
            Message(role=Role.ASSISTANT, content="Sure, what do you need?"),
        ]
        result2 = client2.inspect_conversation(conversation)
        assert result2.is_safe
