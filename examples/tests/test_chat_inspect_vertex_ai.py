import pytest
from unittest.mock import patch, MagicMock
import secrets
from aidefense import ChatInspectionClient
from aidefense.runtime.chat_models import Message, Role

def test_chat_inspect_vertex_ai_workflow(capsys):
    user_prompt = "Explain the theory of relativity in simple terms."
    dummy_api_key = secrets.token_hex(32)
    client = ChatInspectionClient(api_key=dummy_api_key)

    # Mock the Vertex AI API response
    fake_vertex_response = MagicMock()
    fake_vertex_response.json.return_value = {
        "predictions": [
            {"content": "Relativity explains how time and space are linked for objects moving at a constant speed."}
        ]
    }
    fake_vertex_response.raise_for_status.return_value = None

    # Mock google.auth.default and credentials
    fake_credentials = MagicMock()
    fake_credentials.token = "fake-google-token"
    fake_credentials.refresh.return_value = None
    fake_auth_default = (fake_credentials, "fake-project")

    with patch.object(ChatInspectionClient, 'inspect_prompt', return_value=MagicMock(is_safe=True)), \
         patch.object(ChatInspectionClient, 'inspect_response', return_value=MagicMock(is_safe=True)), \
         patch.object(ChatInspectionClient, 'inspect_conversation', return_value=MagicMock(is_safe=True)), \
         patch("requests.post", return_value=fake_vertex_response), \
         patch("google.auth.default", return_value=fake_auth_default), \
         patch("google.auth.transport.requests.Request"):

        # --- Inspect the user prompt ---
        prompt_result = client.inspect_prompt(user_prompt)
        print("\n----------------Inspect Prompt Result----------------")
        print("Prompt is safe?", prompt_result.is_safe)
        if not prompt_result.is_safe:
            print("Violated policies: ...")

        # --- Call Vertex AI API (mocked) ---
        import requests
        import google.auth
        import google.auth.transport.requests
        VERTEX_API_URL = "https://us-central1-aiplatform.googleapis.com/v1/projects/fake-project/locations/us-central1/publishers/google/models/gemini-1.0-pro:predict"
        vertex_headers = {
            "Authorization": f"Bearer {fake_credentials.token}",
            "Content-Type": "application/json",
        }
        vertex_payload = {
            "instances": [{"content": user_prompt}],
            "parameters": {
                "temperature": 0.2,
                "maxOutputTokens": 256,
                "topK": 40,
                "topP": 0.95,
            },
        }
        vertex_response = requests.post(
            VERTEX_API_URL, headers=vertex_headers, json=vertex_payload
        )
        vertex_response.raise_for_status()
        vertex_data = vertex_response.json()
        ai_response = vertex_data.get("predictions", [{}])[0].get("content", "")

        print("\n----------------Vertex AI Response----------------")
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
    assert "----------------Vertex AI Response----------------" in out
    assert "Response: Relativity explains how time and space are linked for objects moving at a constant speed." in out
    assert "----------------Inspect Response Result----------------" in out
    assert "Response is safe? True" in out
    assert "----------------Inspect Conversation Result----------------" in out
    assert "Conversation is safe? True" in out
