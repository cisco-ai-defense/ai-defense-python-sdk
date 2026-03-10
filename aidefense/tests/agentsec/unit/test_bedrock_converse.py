"""Tests for Bedrock Converse API coverage."""

import json
import pytest
from unittest.mock import MagicMock, patch

from aidefense.runtime.agentsec.patchers.bedrock import (
    _parse_bedrock_messages,
    _parse_bedrock_response,
    BEDROCK_OPERATIONS,
)


class TestBedrockOperationsCoverage:
    """Verify all Bedrock operations are covered."""

    def test_converse_operation_in_coverage(self):
        """Test that Converse operation is in the coverage set."""
        assert "Converse" in BEDROCK_OPERATIONS

    def test_converse_stream_operation_in_coverage(self):
        """Test that ConverseStream operation is in the coverage set."""
        assert "ConverseStream" in BEDROCK_OPERATIONS

    def test_invoke_model_operation_in_coverage(self):
        """Test that InvokeModel operation is in the coverage set."""
        assert "InvokeModel" in BEDROCK_OPERATIONS

    def test_invoke_model_stream_operation_in_coverage(self):
        """Test that InvokeModelWithResponseStream operation is in the coverage set."""
        assert "InvokeModelWithResponseStream" in BEDROCK_OPERATIONS


class TestConverseMessageNormalization:
    """Test message normalization for Converse API format."""

    def test_converse_messages_format(self):
        """Test parsing Converse API message format."""
        # Converse API uses same format as Claude messages
        body = json.dumps({
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
                {"role": "user", "content": "How are you?"},
            ]
        }).encode()

        messages = _parse_bedrock_messages(body, "anthropic.claude-3-sonnet")
        
        assert len(messages) == 3
        assert messages[0] == {"role": "user", "content": "Hello"}
        assert messages[1] == {"role": "assistant", "content": "Hi there!"}
        assert messages[2] == {"role": "user", "content": "How are you?"}

    def test_converse_with_system_prompt(self):
        """Test Converse API with system prompt."""
        body = json.dumps({
            "system": "You are a helpful assistant.",
            "messages": [
                {"role": "user", "content": "Hello"},
            ]
        }).encode()

        messages = _parse_bedrock_messages(body, "anthropic.claude-3-sonnet")
        
        assert len(messages) == 2
        assert messages[0] == {"role": "system", "content": "You are a helpful assistant."}
        assert messages[1] == {"role": "user", "content": "Hello"}

    def test_converse_content_blocks_format(self):
        """Test Converse API with content blocks (multi-part messages)."""
        body = json.dumps({
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "First part"},
                        {"type": "text", "text": "Second part"},
                    ]
                },
            ]
        }).encode()

        messages = _parse_bedrock_messages(body, "anthropic.claude-3-sonnet")
        
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert "First part" in messages[0]["content"]
        assert "Second part" in messages[0]["content"]

    def test_converse_response_parsing(self):
        """Test parsing Converse API response format."""
        # Converse returns Claude-style response
        response_body = json.dumps({
            "content": [
                {"type": "text", "text": "Hello! How can I help you today?"}
            ]
        }).encode()

        content = _parse_bedrock_response(response_body, "anthropic.claude-3-sonnet")
        
        assert content == "Hello! How can I help you today?"

