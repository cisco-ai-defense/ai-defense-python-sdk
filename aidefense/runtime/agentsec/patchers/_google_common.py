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

This module provides common helpers used by both google_genai.py (google-genai)
and vertexai.py (vertexai) patchers for message normalization and response extraction.
"""

import logging
import time
from typing import Any, Dict, List, Optional

import httpx

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


def _should_retry_gateway_error(error: Exception, retry_status_codes: List[int]) -> bool:
    """Return True if the error is retryable (HTTP status in retry list, timeout, connect error)."""
    if isinstance(error, httpx.TimeoutException):
        return True
    if isinstance(error, httpx.ConnectError):
        return True
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code in retry_status_codes
    return False


def vertexai_gateway_post(
    url: str,
    content: bytes,
    headers: Dict[str, str],
    gw_settings: Any,
) -> httpx.Response:
    """
    POST to Vertex AI gateway with retry on retryable errors.

    Uses gw_settings.retry_total, retry_backoff, retry_status_codes.
    Applies exponential backoff between retries.
    """
    retry_total = getattr(gw_settings, "retry_total", 3)
    retry_backoff = getattr(gw_settings, "retry_backoff", 0.5)
    retry_status_codes = getattr(gw_settings, "retry_status_codes", [429, 500, 502, 503, 504])
    timeout = float(getattr(gw_settings, "timeout", 60))

    last_error: Optional[Exception] = None
    for attempt in range(max(1, retry_total)):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, content=content, headers=headers)
                response.raise_for_status()
                return response
        except Exception as e:
            last_error = e
            is_last = attempt >= max(1, retry_total) - 1
            if is_last or not _should_retry_gateway_error(e, retry_status_codes):
                raise
            delay = retry_backoff * (2 ** attempt) if retry_backoff > 0 else 0
            if delay > 0:
                logger.debug(f"[GATEWAY] Retry attempt {attempt + 1}/{retry_total} failed: {e}. Retrying in {delay:.2f}s...")
                time.sleep(min(delay, 30.0))

    if last_error:
        raise last_error
    raise RuntimeError("vertexai_gateway_post: unreachable")  # type: ignore


async def vertexai_gateway_post_async(
    url: str,
    content: bytes,
    headers: Dict[str, str],
    gw_settings: Any,
) -> httpx.Response:
    """Async variant of vertexai_gateway_post."""
    import asyncio

    retry_total = getattr(gw_settings, "retry_total", 3)
    retry_backoff = getattr(gw_settings, "retry_backoff", 0.5)
    retry_status_codes = getattr(gw_settings, "retry_status_codes", [429, 500, 502, 503, 504])
    timeout = float(getattr(gw_settings, "timeout", 60))

    last_error: Optional[Exception] = None
    for attempt in range(max(1, retry_total)):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, content=content, headers=headers)
                response.raise_for_status()
                return response
        except Exception as e:
            last_error = e
            is_last = attempt >= max(1, retry_total) - 1
            if is_last or not _should_retry_gateway_error(e, retry_status_codes):
                raise
            delay = retry_backoff * (2 ** attempt) if retry_backoff > 0 else 0
            if delay > 0:
                logger.debug(f"[GATEWAY] Async retry attempt {attempt + 1}/{retry_total} failed: {e}. Retrying in {delay:.2f}s...")
                await asyncio.sleep(min(delay, 30.0))

    if last_error:
        raise last_error
    raise RuntimeError("vertexai_gateway_post_async: unreachable")  # type: ignore


def _has_multi_turn_contents(contents_list: List[Dict]) -> bool:
    """Return True if contents has more than one message (multi-turn)."""
    return len(contents_list) > 1


def build_vertexai_gateway_url(
    gateway_base_url: str,
    model_name: str,
    gw_settings: Any,
    streaming: bool = False,
) -> str:
    """Build the full Vertex AI gateway URL with the REST API path.

    The Vertex AI gateway expects requests at:
        ``{base}/v1/projects/{project}/locations/{location}/publishers/google/models/{model}:{method}``

    Args:
        gateway_base_url: The base gateway URL from ``agentsec.yaml``
            (e.g. ``https://gateway.../connections/...``).
        model_name: The model identifier (e.g. ``gemini-2.5-flash-lite``).
            Prefixes like ``models/``, ``publishers/google/models/``, or
            ``vertex_ai/`` are stripped automatically.
        gw_settings: A :class:`GatewaySettings` with ``gcp_project`` and
            ``gcp_location`` fields.
        streaming: If *True*, use ``streamGenerateContent``; otherwise
            ``generateContent``.

    Returns:
        The fully-qualified gateway URL.

    Raises:
        ValueError: If ``gcp_project`` or ``gcp_location`` are not
            configured on the gateway settings.
    """
    project = getattr(gw_settings, "gcp_project", None)
    location = getattr(gw_settings, "gcp_location", None)

    if not project or not location:
        raise ValueError(
            "Vertex AI gateway mode requires gcp_project and gcp_location "
            "in the gateway configuration (agentsec.yaml).  "
            f"Got gcp_project={project!r}, gcp_location={location!r}"
        )

    # Strip common model name prefixes
    clean_model = model_name
    for prefix in ("publishers/google/models/", "models/", "vertex_ai/"):
        if clean_model.startswith(prefix):
            clean_model = clean_model[len(prefix):]
            break

    method = "streamGenerateContent" if streaming else "generateContent"

    base = gateway_base_url.rstrip("/")
    return (
        f"{base}/v1/projects/{project}/locations/{location}"
        f"/publishers/google/models/{clean_model}:{method}"
    )


def _build_google_auth_header(gw_settings):
    """Build an Authorization header from per-gateway GCP settings.

    Constructs Google OAuth2 credentials using the configuration on
    the gateway entry in ``agentsec.yaml``.  The resolution order is:

    1. Explicit service account key file (``gcp_service_account_key_file``).
    2. Default Application Default Credentials (``google.auth.default()``).

    If ``gcp_target_service_account`` is also set, the base credentials
    from steps 1-2 are used to impersonate that service account
    (analogous to AWS ``aws_role_arn`` / STS assume-role).

    Finally the credentials are refreshed and the resulting OAuth2 access
    token is returned as a ``Bearer`` authorization header dict.

    Args:
        gw_settings: A :class:`GatewaySettings` instance with optional
            ``gcp_*`` fields.

    Returns:
        A dict ``{"Authorization": "Bearer <token>"}`` ready to merge
        into HTTP request headers.
    """
    import google.auth
    import google.auth.transport.requests

    scopes = ["https://www.googleapis.com/auth/cloud-platform"]

    # Step 1: Build base credentials
    if gw_settings.gcp_service_account_key_file:
        from google.oauth2 import service_account

        credentials = service_account.Credentials.from_service_account_file(
            gw_settings.gcp_service_account_key_file,
            scopes=scopes,
        )
    else:
        credentials, _ = google.auth.default(scopes=scopes)

    # Step 2: Impersonate target service account if configured
    if gw_settings.gcp_target_service_account:
        from google.auth import impersonated_credentials

        credentials = impersonated_credentials.Credentials(
            source_credentials=credentials,
            target_principal=gw_settings.gcp_target_service_account,
            target_scopes=scopes,
        )

    # Refresh to obtain a valid access token
    credentials.refresh(google.auth.transport.requests.Request())
    return {"Authorization": f"Bearer {credentials.token}"}
