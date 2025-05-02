"""
Example: Inspecting an Anthropic Claude prompt and response using ChatInspectionClient

This script demonstrates:
- Sending a prompt to the Anthropic Claude API and receiving a response
- Inspecting both the prompt and the response separately
- Inspecting the full conversation (prompt + response) for safety
"""

import os
import requests
from aidefense import ChatInspectionClient
from aidefense.runtime.chat_models import Message, Role

# --- Configuration ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "YOUR_ANTHROPIC_API_KEY")
AIDEFENSE_API_KEY = os.environ.get("AIDEFENSE_API_KEY", "YOUR_AIDEFENSE_API_KEY")
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

# --- User Prompt ---
user_prompt = "What are three ways that AI is helping with environmental sustainability?"

# --- Inspect the user prompt ---
client = ChatInspectionClient(api_key=AIDEFENSE_API_KEY)
prompt_result = client.inspect_prompt(user_prompt)
print("\n----------------Inspect Prompt Result----------------")
print("Prompt is safe?", prompt_result.is_safe)
if not prompt_result.is_safe:
    print(f"Violated policies: {[rule.rule_name.value for rule in prompt_result.rules or []]}")

# --- Call Anthropic API ---
anthropic_headers = {
    "x-api-key": ANTHROPIC_API_KEY,
    "anthropic-version": "2023-06-01",
    "Content-Type": "application/json",
}
anthropic_payload = {
    "model": "claude-3-opus-20240229",  # Or another available model
    "messages": [{"role": "user", "content": user_prompt}],
    "max_tokens": 500,
    "temperature": 0.7
}

try:
    anthropic_response = requests.post(
        ANTHROPIC_API_URL, headers=anthropic_headers, json=anthropic_payload
    )
    anthropic_response.raise_for_status()
    anthropic_data = anthropic_response.json()
    ai_response = anthropic_data.get("content", [{}])[0].get("text", "")
    
    print("\n----------------Anthropic Claude Response----------------")
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
    print(f"\nError calling Anthropic API: {e}")
    print("Note: This example requires a valid Anthropic API key.")
    print("For testing purposes, you can mock the API response as follows:")
    
    # Mock response for testing without actual API call
    ai_response = """Here are three significant ways AI is helping with environmental sustainability:

1. Optimizing Energy Systems: AI is improving the efficiency of energy grids by predicting supply and demand patterns, integrating renewable energy sources more effectively, and reducing waste. Smart grid systems use AI to balance loads, predict maintenance needs, and optimize distribution, while AI algorithms help solar and wind farms maximize their output by predicting weather patterns and adjusting operations accordingly.

2. Monitoring and Protecting Biodiversity: AI-powered systems analyze satellite imagery, audio recordings, and camera trap data to monitor deforestation, track endangered species, and detect illegal activities like poaching. For example, platforms like Temboo's Kosmos use machine learning to analyze satellite imagery to detect forest loss in real-time, while organizations like Rainforest Connection use AI to analyze audio recordings to detect illegal logging.

3. Accelerating Climate Science Research: AI is helping climate scientists analyze massive datasets to improve climate models, predict extreme weather events more accurately, and understand complex climate patterns. This enables better preparedness for climate-related disasters and more informed policy decisions. AI has also accelerated materials science research for more sustainable solutions, from better batteries to carbon capture technologies."""
    
    print("\n----------------Mocked Anthropic Claude Response----------------")
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
