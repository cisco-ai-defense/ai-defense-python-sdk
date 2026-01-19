# Copyright 2025 Cisco Systems, Inc. and its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

"""
Shared utilities for Google AI client patching.

This module provides common helpers used by both google_ai.py (google-generativeai)
and vertexai.py (vertexai) patchers for message normalization and response extraction.
"""

import logging
from typing import Any, Dict, List, Optional, Iterator

logger = logging.getLogger("aidefense.runtime.agentsec.patchers.google_common")


def normalize_google_messages(contents: Any) -> List[Dict[str, Any]]:
    """
    Normalize Google AI message format to standard format.
    
    Google uses:
        - role: "user" or "model"
        - parts: [{"text": "..."}, ...]
    
    We normalize to:
        - role: "user" or "assistant" (model -> assistant)
        - content: "..."
    
    Args:
        contents: Input in various Google formats:
            - str: Single user message
            - list of dicts: [{role, parts}, ...]
            - list of Content objects
            
    Returns:
        List of normalized messages: [{"role": str, "content": str}, ...]
    """
    if contents is None:
        return []
    
    # String input = single user message
    if isinstance(contents, str):
        return [{"role": "user", "content": contents}]
    
    # Not a list - try to handle as single content
    if not isinstance(contents, (list, tuple)):
        # Could be a Content object
        return _normalize_single_content(contents)
    
    messages = []
    for item in contents:
        normalized = _normalize_single_content(item)
        messages.extend(normalized)
    
    return messages


def _normalize_single_content(content: Any) -> List[Dict[str, Any]]:
    """Normalize a single content item."""
    if content is None:
        return []
    
    # String
    if isinstance(content, str):
        return [{"role": "user", "content": content}]
    
    # Dict with role and parts
    if isinstance(content, dict):
        role = content.get("role", "user")
        # Map "model" to "assistant"
        if role == "model":
            role = "assistant"
        
        parts = content.get("parts", [])
        text = _extract_text_from_parts(parts)
        
        if text:
            return [{"role": role, "content": text}]
        return []
    
    # Content object from SDK (has role and parts attributes)
    if hasattr(content, "role") and hasattr(content, "parts"):
        role = content.role
        if role == "model":
            role = "assistant"
        
        text = _extract_text_from_parts(content.parts)
        
        if text:
            return [{"role": role, "content": text}]
        return []
    
    # Unknown format - try str()
    try:
        text = str(content)
        if text:
            return [{"role": "user", "content": text}]
    except Exception as e:
        logger.debug(f"Error converting content to string: {e}")
    
    return []


def _extract_text_from_parts(parts: Any) -> str:
    """Extract text content from parts list."""
    if parts is None:
        return ""
    
    # String parts
    if isinstance(parts, str):
        return parts
    
    # List of parts
    if isinstance(parts, (list, tuple)):
        texts = []
        for part in parts:
            if isinstance(part, str):
                texts.append(part)
            elif isinstance(part, dict):
                # {"text": "..."}
                if "text" in part and part["text"] is not None:
                    texts.append(part["text"])
            elif hasattr(part, "text"):
                # Part object with text attribute - ensure it's not None
                if part.text is not None:
                    texts.append(part.text)
        return " ".join(texts)
    
    # Single part object
    if hasattr(parts, "text"):
        return parts.text
    
    return ""


def extract_google_response(response: Any) -> str:
    """
    Extract text content from a Google GenerateContentResponse.
    
    Response structure:
        response.candidates[0].content.parts[0].text
        
    Args:
        response: GenerateContentResponse object or dict
        
    Returns:
        Extracted text content, or empty string if not found
    """
    if response is None:
        return ""
    
    try:
        # Try object attribute access first (SDK response)
        if hasattr(response, "candidates"):
            candidates = response.candidates
            if candidates and len(candidates) > 0:
                candidate = candidates[0]
                if hasattr(candidate, "content"):
                    content = candidate.content
                    if hasattr(content, "parts"):
                        return _extract_text_from_parts(content.parts)
        
        # Try dict access (raw response)
        if isinstance(response, dict):
            candidates = response.get("candidates", [])
            if candidates:
                candidate = candidates[0]
                content = candidate.get("content", {})
                parts = content.get("parts", [])
                return _extract_text_from_parts(parts)
        
        # Try text attribute directly (some responses)
        if hasattr(response, "text"):
            return response.text
        
    except Exception as e:
        logger.debug(f"Error extracting Google response: {e}")
    
    return ""


def extract_streaming_chunk_text(chunk: Any) -> str:
    """
    Extract text from a streaming response chunk.
    
    Args:
        chunk: A streaming chunk from generate_content(stream=True)
        
    Returns:
        Text content from this chunk
    """
    if chunk is None:
        return ""
    
    try:
        # Object with text attribute - check it's not None
        if hasattr(chunk, "text") and chunk.text is not None:
            return chunk.text or ""
        
        # Object with candidates
        if hasattr(chunk, "candidates") and chunk.candidates:
            candidates = chunk.candidates
            if candidates and len(candidates) > 0:
                candidate = candidates[0]
                if hasattr(candidate, "content"):
                    content = candidate.content
                    if hasattr(content, "parts"):
                        return _extract_text_from_parts(content.parts)
        
        # Dict format
        if isinstance(chunk, dict):
            # Direct text
            if "text" in chunk:
                return chunk["text"]
            
            # Candidates format
            candidates = chunk.get("candidates", [])
            if candidates:
                candidate = candidates[0]
                content = candidate.get("content", {})
                parts = content.get("parts", [])
                return _extract_text_from_parts(parts)
                
    except Exception as e:
        logger.debug(f"Error extracting streaming chunk: {e}")
    
    return ""
