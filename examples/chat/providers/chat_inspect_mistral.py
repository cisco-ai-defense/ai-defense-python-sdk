"""
Example: Inspecting a Mistral AI prompt and response using ChatInspectionClient

This script demonstrates:
- Sending a prompt to the Mistral AI API and receiving a response
- Inspecting both the prompt and the response separately
- Inspecting the full conversation (prompt + response) for safety
"""

import os
import requests
from aidefense import ChatInspectionClient
from aidefense.runtime.chat_models import Message, Role

# --- Configuration ---
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "YOUR_MISTRAL_API_KEY")
AIDEFENSE_API_KEY = os.environ.get("AIDEFENSE_API_KEY", "YOUR_AIDEFENSE_API_KEY")
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"

# --- User Prompt ---
user_prompt = "What are the main differences between supervised and unsupervised learning?"

# --- Inspect the user prompt ---
client = ChatInspectionClient(api_key=AIDEFENSE_API_KEY)
prompt_result = client.inspect_prompt(user_prompt)
print("\n----------------Inspect Prompt Result----------------")
print("Prompt is safe?", prompt_result.is_safe)
if not prompt_result.is_safe:
    print(f"Violated policies: {[rule.rule_name.value for rule in prompt_result.rules or []]}")

# --- Call Mistral AI API ---
mistral_headers = {
    "Authorization": f"Bearer {MISTRAL_API_KEY}",
    "Content-Type": "application/json",
}
mistral_payload = {
    "model": "mistral-large-latest",  # Or another available model
    "messages": [{"role": "user", "content": user_prompt}],
    "temperature": 0.7,
    "max_tokens": 500
}

try:
    mistral_response = requests.post(
        MISTRAL_API_URL, headers=mistral_headers, json=mistral_payload
    )
    mistral_response.raise_for_status()
    mistral_data = mistral_response.json()
    ai_response = mistral_data.get("choices", [{}])[0].get("message", {}).get("content", "")
    
    print("\n----------------Mistral AI Response----------------")
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
    print(f"\nError calling Mistral AI API: {e}")
    print("Note: This example requires a valid Mistral AI API key.")
    print("For testing purposes, you can mock the API response as follows:")
    
    # Mock response for testing without actual API call
    ai_response = """Supervised and unsupervised learning are two fundamental approaches in machine learning that differ in how they learn from data:

Supervised Learning:
- Works with labeled data where inputs are paired with correct outputs
- The algorithm learns to map inputs to outputs based on example pairs
- Goal is to predict outputs for new, unseen inputs
- Requires human effort to label training data
- Examples: Classification (spam detection, image recognition) and regression (price prediction, weather forecasting)

Unsupervised Learning:
- Works with unlabeled data with no predefined outputs
- The algorithm finds patterns, structures, or relationships in the data on its own
- Goal is to discover hidden patterns or intrinsic structures in the data
- No need for human-labeled data
- Examples: Clustering (customer segmentation, anomaly detection), dimensionality reduction, and association (market basket analysis)

Key differences:
1. Data: Supervised uses labeled data; unsupervised uses unlabeled data
2. Human involvement: Supervised requires human effort for labeling; unsupervised is more autonomous
3. Complexity: Supervised is conceptually simpler; unsupervised can be more complex
4. Applications: Different use cases depending on available data and objectives
5. Evaluation: Supervised has clear metrics; unsupervised is harder to evaluate"""
    
    print("\n----------------Mocked Mistral AI Response----------------")
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
