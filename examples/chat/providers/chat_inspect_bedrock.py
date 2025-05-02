"""
Example: Inspecting an Amazon Bedrock prompt and response using ChatInspectionClient

This script demonstrates:
- Sending a prompt to the Amazon Bedrock API and receiving a response
- Inspecting both the prompt and the response separately
- Inspecting the full conversation (prompt + response) for safety
"""

import os
import json
from aidefense import ChatInspectionClient
from aidefense.runtime.chat_models import Message, Role

# --- Configuration ---
AIDEFENSE_API_KEY = os.environ.get("AIDEFENSE_API_KEY", "YOUR_AIDEFENSE_API_KEY")

# --- User Prompt ---
user_prompt = "Explain three key benefits of cloud computing."

# --- Inspect the user prompt ---
client = ChatInspectionClient(api_key=AIDEFENSE_API_KEY)
prompt_result = client.inspect_prompt(user_prompt)
print("\n----------------Inspect Prompt Result----------------")
print("Prompt is safe?", prompt_result.is_safe)
if not prompt_result.is_safe:
    print(f"Violated policies: {[rule.rule_name.value for rule in prompt_result.rules or []]}")

# --- Call Amazon Bedrock API ---
try:
    # Note: In a real application, you would use the boto3 client
    # This example shows the pattern but requires AWS credentials
    import boto3
    
    bedrock_runtime = boto3.client(
        service_name='bedrock-runtime',
        region_name='us-east-1'  # Adjust to your preferred region
    )
    
    # Using Claude model from Anthropic on Amazon Bedrock
    model_id = "anthropic.claude-v2"
    
    bedrock_payload = {
        "prompt": f"\n\nHuman: {user_prompt}\n\nAssistant:",
        "max_tokens_to_sample": 300,
        "temperature": 0.5,
        "top_p": 0.9
    }
    
    bedrock_response = bedrock_runtime.invoke_model(
        modelId=model_id,
        body=json.dumps(bedrock_payload)
    )
    
    response_body = json.loads(bedrock_response['body'].read())
    ai_response = response_body.get('completion', '')
    
    print("\n----------------Amazon Bedrock Response----------------")
    print("Response:", ai_response)
    
    # --- Inspect the AI response ---
    response_result = client.inspect_response(ai_response)
    print("\n----------------Inspect Response Result----------------")
    print("Response is safe?", response_result.is_safe)
    if not response_result.is_safe:
        print(f"Violated policies: {[rule.rule_name.value for rule in response_result.rules or []]}")
    
    # --- Inspect the full conversation ---
    conversation = [
        Message(role=Role.USER, content=user_prompt),
        Message(role=Role.ASSISTANT, content=ai_response),
    ]
    conversation_result = client.inspect_conversation(conversation)
    print("\n----------------Inspect Conversation Result----------------")
    print("Conversation is safe?", conversation_result.is_safe)
    if not conversation_result.is_safe:
        print(f"Violated policies: {[rule.rule_name.value for rule in conversation_result.rules or []]}")

except Exception as e:
    print(f"\nError calling Amazon Bedrock API: {e}")
    print("Note: This example requires AWS credentials and permissions to access Bedrock.")
    print("For testing purposes, you can mock the API response as follows:")
    
    # Mock response for testing without actual API call
    ai_response = """Here are three key benefits of cloud computing:

1. Scalability: Cloud services allow businesses to easily scale resources up or down based on demand, without investing in physical infrastructure. This means you can quickly adapt to changing business needs without significant capital expenditure.

2. Cost Efficiency: With cloud computing, you pay only for what you use, converting capital expenses to operational expenses. This eliminates the need for expensive hardware purchases, maintenance costs, and reduces the need for large IT staffs.

3. Accessibility and Collaboration: Cloud services enable access to data and applications from anywhere with an internet connection, facilitating remote work and global collaboration. Teams can work on the same documents in real-time, regardless of their physical location."""
    
    print("\n----------------Mocked Amazon Bedrock Response----------------")
    print("Response:", ai_response)
    
    # Continue with inspection as before
    response_result = client.inspect_response(ai_response)
    print("\n----------------Inspect Response Result----------------")
    print("Response is safe?", response_result.is_safe)
    
    conversation = [
        Message(role=Role.USER, content=user_prompt),
        Message(role=Role.ASSISTANT, content=ai_response),
    ]
    conversation_result = client.inspect_conversation(conversation)
    print("\n----------------Inspect Conversation Result----------------")
    print("Conversation is safe?", conversation_result.is_safe)
