import pytest
from unittest.mock import patch, MagicMock
import secrets
from aidefense import ChatInspectionClient
from aidefense.runtime.chat_models import Message, Role

def test_chat_inspect_cohere_workflow(capsys):
    user_prompt = "Tell me a fun fact about space."
    dummy_api_key = secrets.token_hex(32)
    client = ChatInspectionClient(api_key=dummy_api_key)

    # Mock the Cohere API response
    fake_cohere_response = MagicMock()
    fake_cohere_response.json.return_value = {"text": "Space is completely silent."}
    fake_cohere_response.raise_for_status.return_value = None

    with patch.object(ChatInspectionClient, 'inspect_prompt', return_value=MagicMock(is_safe=True)), \
         patch.object(ChatInspectionClient, 'inspect_response', return_value=MagicMock(is_safe=True)), \
         patch.object(ChatInspectionClient, 'inspect_conversation', return_value=MagicMock(is_safe=True)), \
         patch("requests.post", return_value=fake_cohere_response):

        # --- Inspect the user prompt ---
        prompt_result = client.inspect_prompt(user_prompt)
        print("Prompt is safe?", prompt_result.is_safe)

        # --- Call Cohere API (mocked) ---
        import requests
        COHERE_API_URL = "https://api.cohere.com/v1/chat"
        cohere_headers = {
            "Authorization": f"Bearer fake-key",
            "Content-Type": "application/json",
        }
        cohere_payload = {"message": user_prompt}
        cohere_response = requests.post(
            COHERE_API_URL, headers=cohere_headers, json=cohere_payload
        )
        cohere_response.raise_for_status()
        cohere_data = cohere_response.json()
        ai_response = (
            cohere_data.get("text")
            or cohere_data.get("reply")
            or cohere_data.get("response")
            or ""
        )

        print("Cohere AI Response:", ai_response)

        # 2. Inspect the AI response
        response_result = client.inspect_response(ai_response)
        print("Response is safe?", response_result.is_safe)

        # 3. Inspect the full conversation
        conversation = [
            Message(role=Role.USER, content=user_prompt),
            Message(role=Role.ASSISTANT, content=ai_response),
        ]
        conversation_result = client.inspect_conversation(conversation)
        print("Conversation is safe?", conversation_result.is_safe)

    out = capsys.readouterr().out
    assert "Prompt is safe? True" in out
    assert "Cohere AI Response: Space is completely silent." in out
    assert "Response is safe? True" in out
    assert "Conversation is safe? True" in out