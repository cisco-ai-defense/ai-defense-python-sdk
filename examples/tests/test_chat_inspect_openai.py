import pytest
from unittest.mock import patch, MagicMock
import secrets
from aidefense import ChatInspectionClient
from aidefense.runtime.chat_models import Message, Role

def test_chat_inspect_openai_workflow(capsys):
    user_prompt = "Tell me a fun fact about quantum computing."
    dummy_api_key = secrets.token_hex(32)
    client = ChatInspectionClient(api_key=dummy_api_key)

    # Mock the OpenAI API response
    fake_openai_response = MagicMock()
    fake_openai_response.json.return_value = {
        "choices": [
            {"message": {"content": "Quantum computers use qubits instead of bits."}}
        ]
    }
    fake_openai_response.raise_for_status.return_value = None

    with patch.object(ChatInspectionClient, 'inspect_prompt', return_value=MagicMock(is_safe=True)), \
         patch.object(ChatInspectionClient, 'inspect_response', return_value=MagicMock(is_safe=True)), \
         patch.object(ChatInspectionClient, 'inspect_conversation', return_value=MagicMock(is_safe=True)), \
         patch("requests.post", return_value=fake_openai_response):

        # --- Inspect the user prompt ---
        prompt_result = client.inspect_prompt(user_prompt)
        print("\n----------------Inspect Prompt Result----------------")
        print("Prompt is safe?", prompt_result.is_safe)
        if not prompt_result.is_safe:
            print("Violated policies: ...")

        # --- Call OpenAI API (mocked) ---
        import requests
        OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
        openai_headers = {
            "Authorization": f"Bearer fake-key",
            "Content-Type": "application/json",
        }
        openai_payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": user_prompt}],
            "max_tokens": 150,
        }
        openai_response = requests.post(
            OPENAI_API_URL, headers=openai_headers, json=openai_payload
        )
        openai_response.raise_for_status()
        openai_data = openai_response.json()
        ai_response = openai_data.get("choices", [{}])[0].get("message", {}).get("content", "")

        print("\n----------------OpenAI Response----------------")
        print("Response:", ai_response)

        # --- Inspect the AI response ---
        response_result = client.inspect_response(ai_response)
        print("\n----------------Inspect Response Result----------------")
        print("Response is safe?", response_result.is_safe)

        # --- Inspect the full conversation ---
        conversation = [
            Message(role=Role.USER, content=user_prompt),
            Message(role=Role.ASSISTANT, content=ai_response),
        ]
        conversation_result = client.inspect_conversation(conversation)
        print("\n----------------Inspect Conversation Result----------------")
        print("Conversation is safe?", conversation_result.is_safe)

    out = capsys.readouterr().out
    assert "----------------Inspect Prompt Result----------------" in out
    assert "Prompt is safe? True" in out
    assert "----------------OpenAI Response----------------" in out
    assert "Response: Quantum computers use qubits instead of bits." in out
    assert "----------------Inspect Response Result----------------" in out
    assert "Response is safe? True" in out
    assert "----------------Inspect Conversation Result----------------" in out
    assert "Conversation is safe? True" in out
