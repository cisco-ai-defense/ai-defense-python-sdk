import pytest
from unittest.mock import patch, MagicMock
import secrets
from aidefense import ChatInspectionClient
from aidefense.runtime.chat_models import Message, Role


@pytest.fixture
def fake_bedrock_client():
    # Patch ChatInspectionClient methods
    with patch.object(ChatInspectionClient, 'inspect_prompt', return_value=MagicMock(is_safe=True)), \
            patch.object(ChatInspectionClient, 'inspect_response', return_value=MagicMock(is_safe=True)), \
            patch.object(ChatInspectionClient, 'inspect_conversation', return_value=MagicMock(is_safe=True)):
        yield


def test_chat_inspect_bedrock_workflow(fake_bedrock_client, capsys):
    user_prompt = "Explain three key benefits of cloud computing."
    dummy_api_key = secrets.token_hex(32)
    client = ChatInspectionClient(api_key=dummy_api_key)

    # Mock boto3.client and Bedrock API response
    with patch("boto3.client") as mock_boto3_client:
        mock_bedrock = MagicMock()
        mock_boto3_client.return_value = mock_bedrock
        # Simulate Bedrock model response
        mock_response = {
            "body": MagicMock(read=lambda: b'{"completion": "AI response from Bedrock."}')
        }
        mock_bedrock.invoke_model.return_value = mock_response

        # --- Inspect the user prompt ---
        prompt_result = client.inspect_prompt(user_prompt)
        print("\n----------------Inspect Prompt Result----------------")
        print("Prompt is safe?", prompt_result.is_safe)
        if not prompt_result.is_safe:
            print("Violated policies: ...")

        # --- Call Amazon Bedrock API ---
        import boto3
        bedrock_runtime = boto3.client(
            service_name="bedrock-runtime",
            region_name="us-east-1"
        )
        model_id = "anthropic.claude-v2"
        bedrock_payload = {
            "prompt": f"\n\nHuman: {user_prompt}\n\nAssistant:",
            "max_tokens_to_sample": 300,
            "temperature": 0.5,
            "top_p": 0.9,
        }
        bedrock_response = bedrock_runtime.invoke_model(
            modelId=model_id, body='{}'
        )
        response_body = {"completion": "AI response from Bedrock."}
        ai_response = response_body.get("completion", "")

        print("\n----------------Amazon Bedrock Response----------------")
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
    assert "----------------Amazon Bedrock Response----------------" in out
    assert "Response: AI response from Bedrock." in out
    assert "----------------Inspect Response Result----------------" in out
    assert "Response is safe? True" in out
    assert "----------------Inspect Conversation Result----------------" in out
    assert "Conversation is safe? True" in out