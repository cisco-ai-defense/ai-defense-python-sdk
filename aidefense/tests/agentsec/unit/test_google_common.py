"""Tests for Google common helpers."""

import pytest
from unittest.mock import MagicMock

from aidefense.runtime.agentsec.patchers._google_common import (
    normalize_google_messages,
    extract_google_response,
    extract_streaming_chunk_text,
)


class TestNormalizeGoogleMessages:
    """Tests for message normalization."""

    def test_string_input(self):
        """Test normalizing a simple string input."""
        messages = normalize_google_messages("Hello, world!")
        
        assert len(messages) == 1
        assert messages[0] == {"role": "user", "content": "Hello, world!"}

    def test_list_of_dicts_with_parts(self):
        """Test normalizing list of dicts with parts."""
        contents = [
            {"role": "user", "parts": [{"text": "Hello"}]},
            {"role": "model", "parts": [{"text": "Hi there!"}]},
        ]
        
        messages = normalize_google_messages(contents)
        
        assert len(messages) == 2
        assert messages[0] == {"role": "user", "content": "Hello"}
        assert messages[1] == {"role": "assistant", "content": "Hi there!"}  # model -> assistant

    def test_model_role_mapped_to_assistant(self):
        """Test that 'model' role is mapped to 'assistant'."""
        contents = [
            {"role": "model", "parts": [{"text": "I am the model"}]},
        ]
        
        messages = normalize_google_messages(contents)
        
        assert len(messages) == 1
        assert messages[0]["role"] == "assistant"
        assert messages[0]["content"] == "I am the model"

    def test_multiple_parts_concatenated(self):
        """Test that multiple text parts are concatenated."""
        contents = [
            {
                "role": "user",
                "parts": [
                    {"text": "First part"},
                    {"text": "Second part"},
                ]
            },
        ]
        
        messages = normalize_google_messages(contents)
        
        assert len(messages) == 1
        assert "First part" in messages[0]["content"]
        assert "Second part" in messages[0]["content"]

    def test_content_object_with_attributes(self):
        """Test normalizing Content-like objects with attributes."""
        # Mock a Content object
        part = MagicMock()
        part.text = "Hello from object"
        
        content = MagicMock()
        content.role = "user"
        content.parts = [part]
        
        messages = normalize_google_messages([content])
        
        assert len(messages) == 1
        assert messages[0] == {"role": "user", "content": "Hello from object"}

    def test_none_input(self):
        """Test handling None input."""
        messages = normalize_google_messages(None)
        assert messages == []

    def test_empty_list(self):
        """Test handling empty list."""
        messages = normalize_google_messages([])
        assert messages == []


class TestExtractGoogleResponse:
    """Tests for response extraction."""

    def test_extract_from_response_object(self):
        """Test extracting text from response object with candidates."""
        # Mock the response structure
        part = MagicMock()
        part.text = "Hello, I'm the assistant!"
        
        content = MagicMock()
        content.parts = [part]
        
        candidate = MagicMock()
        candidate.content = content
        
        response = MagicMock()
        response.candidates = [candidate]
        
        text = extract_google_response(response)
        
        assert text == "Hello, I'm the assistant!"

    def test_extract_from_dict_response(self):
        """Test extracting text from dict response."""
        response = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "Response from dict"}
                        ]
                    }
                }
            ]
        }
        
        text = extract_google_response(response)
        
        assert text == "Response from dict"

    def test_extract_from_response_with_text_attribute(self):
        """Test extracting from response with direct text attribute."""
        response = MagicMock()
        response.text = "Direct text response"
        response.candidates = None
        
        text = extract_google_response(response)
        
        assert text == "Direct text response"

    def test_extract_from_none(self):
        """Test handling None response."""
        text = extract_google_response(None)
        assert text == ""

    def test_extract_from_empty_candidates(self):
        """Test handling response with empty candidates."""
        response = {"candidates": []}
        text = extract_google_response(response)
        assert text == ""


class TestExtractStreamingChunkText:
    """Tests for streaming chunk extraction."""

    def test_chunk_with_text_attribute(self):
        """Test extracting from chunk with text attribute."""
        chunk = MagicMock()
        chunk.text = "Streaming chunk"
        
        text = extract_streaming_chunk_text(chunk)
        
        assert text == "Streaming chunk"

    def test_chunk_with_candidates(self):
        """Test extracting from chunk with candidates structure."""
        part = MagicMock()
        part.text = "Chunk from candidates"
        
        content = MagicMock()
        content.parts = [part]
        
        candidate = MagicMock()
        candidate.content = content
        
        chunk = MagicMock()
        chunk.text = None  # No direct text
        chunk.candidates = [candidate]
        
        text = extract_streaming_chunk_text(chunk)
        
        assert text == "Chunk from candidates"

    def test_chunk_dict_format(self):
        """Test extracting from dict chunk."""
        chunk = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Dict chunk text"}]
                    }
                }
            ]
        }
        
        text = extract_streaming_chunk_text(chunk)
        
        assert text == "Dict chunk text"

    def test_none_chunk(self):
        """Test handling None chunk."""
        text = extract_streaming_chunk_text(None)
        assert text == ""








