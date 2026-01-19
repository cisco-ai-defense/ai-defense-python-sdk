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

"""LLM Inspector for Cisco AI Defense Chat Inspection API."""

import logging
from typing import Any, Dict, List, Optional

import httpx

from ..decision import Decision
from ..exceptions import SecurityPolicyError

logger = logging.getLogger("aidefense.runtime.agentsec.inspectors.llm")


class LLMInspector:
    """
    Inspector for LLM conversations using Cisco AI Defense Chat Inspection API.
    
    This class integrates with the Cisco AI Defense Chat Inspection API to
    inspect LLM requests and responses for security policy violations.
    
    See: https://developer.cisco.com/docs/ai-defense/overview/
    
    Attributes:
        api_key: API key for Cisco AI Defense
        endpoint: Base URL for the AI Defense API
        timeout_ms: Request timeout in milliseconds
        retry_attempts: Number of retry attempts (default 1 = no retry)
        fail_open: Whether to allow requests when API is unreachable
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        default_rules: Optional[List[Any]] = None,
        timeout_ms: int = 1000,
        retry_attempts: int = 1,
        fail_open: bool = True,
    ):
        """
        Initialize the LLM Inspector.
        
        Args:
            api_key: API key for Cisco AI Defense (or from AI_DEFENSE_API_MODE_LLM_API_KEY env)
            endpoint: Base URL for the AI Defense API (or from AI_DEFENSE_API_MODE_LLM_ENDPOINT env)
            default_rules: Default rules for inspection
            timeout_ms: Request timeout in milliseconds (default 1000)
            retry_attempts: Number of attempts (default 1, no retry)
            fail_open: Whether to allow requests when API is unreachable (default True)
        """
        import os
        from .. import _state
        
        # Priority: explicit param > state > env var
        self.api_key = api_key or _state.get_api_mode_llm_api_key() or os.environ.get("AI_DEFENSE_API_MODE_LLM_API_KEY")
        self.endpoint = endpoint or _state.get_api_mode_llm_endpoint() or os.environ.get("AI_DEFENSE_API_MODE_LLM_ENDPOINT")
        self.default_rules = default_rules or []
        self.timeout_ms = timeout_ms
        self.retry_attempts = max(1, retry_attempts)
        self.fail_open = fail_open
        
        # Create sync HTTP client (use HTTP/1.1 - AI Defense API doesn't support HTTP/2)
        # Note: Async client is created per-request in ainspect_conversation() to avoid
        # "attached to different event loop" errors with frameworks like Strands
        timeout = httpx.Timeout(timeout_ms / 1000.0)
        self._sync_client = httpx.Client(timeout=timeout, http2=False)
    
    def _build_request_payload(
        self,
        messages: List[Dict[str, Any]],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Build the Chat Inspection API request payload.
        
        Args:
            messages: List of conversation messages with role and content
            metadata: Additional metadata (user, src_app, transaction_id, etc.)
            
        Returns:
            Request payload dict for the API
        """
        payload = {
            "messages": messages,
            "metadata": metadata,
        }
        # Only include rules if they're configured
        if self.default_rules:
            payload["rules"] = self.default_rules
        return payload
    
    def _parse_response(self, response_data: Dict[str, Any]) -> Decision:
        """
        Parse the API response into a Decision.
        
        Args:
            response_data: JSON response from the API
            
        Returns:
            Decision based on API response
        """
        # The API returns action capitalized (Allow, Block, etc.) - normalize to lowercase
        action = response_data.get("action", "allow").lower()
        reasons = response_data.get("reasons", [])
        sanitized_content = response_data.get("sanitized_content")
        
        # Log full response for debugging block decisions
        if action == "block":
            logger.debug(f"AI Defense BLOCK response: {response_data}")
        
        # Extract reasons from "rules" field (primary source of violations)
        if not reasons and "rules" in response_data:
            for rule in response_data.get("rules", []):
                classification = rule.get("classification")
                if classification and classification not in ("NONE_VIOLATION", "NONE_SEVERITY"):
                    reasons.append(f"{rule.get('rule_name')}: {classification}")
        
        # Also check processed_rules as fallback
        if not reasons and "processed_rules" in response_data:
            for rule in response_data.get("processed_rules", []):
                if rule.get("classification") not in ("NONE_VIOLATION", None):
                    reasons.append(f"{rule.get('rule_name')}: {rule.get('classification')}")
        
        # Map API action to Decision
        if action == "block":
            return Decision.block(reasons=reasons, raw_response=response_data)
        elif action == "sanitize":
            return Decision.sanitize(
                reasons=reasons,
                sanitized_content=sanitized_content,
                raw_response=response_data,
            )
        elif action == "monitor_only":
            return Decision.monitor_only(reasons=reasons, raw_response=response_data)
        else:
            return Decision.allow(reasons=reasons, raw_response=response_data)
    
    def _handle_error(
        self,
        error: Exception,
        context: Optional[str] = None,
        message_count: int = 0,
    ) -> Decision:
        """
        Handle API errors based on fail_open config.
        
        Centralizes error handling for all API-related errors. Logs with context
        and respects fail_open setting.
        
        Args:
            error: The exception that occurred
            context: Optional context string (e.g., "inspect_conversation")
            message_count: Number of messages in the request for logging
            
        Returns:
            Decision.allow() if fail_open, raises SecurityPolicyError otherwise
        """
        # Classify the error type for better logging
        error_type = type(error).__name__
        error_msg = str(error)
        
        # Build context string for logging
        ctx_parts = []
        if context:
            ctx_parts.append(f"operation={context}")
        if message_count > 0:
            ctx_parts.append(f"messages={message_count}")
        ctx_str = f" [{', '.join(ctx_parts)}]" if ctx_parts else ""
        
        # Log at WARNING level (will be upgraded to ERROR if fail_open=False)
        logger.warning(f"AI Defense API error{ctx_str}: {error_type}: {error_msg}")
        
        # Log stack trace at DEBUG level only
        logger.debug(f"Error details: {error}", exc_info=True)
        
        if self.fail_open:
            logger.warning("fail_open=True, allowing request despite API error")
            return Decision.allow(reasons=[f"API error ({error_type}), fail_open=True"])
        else:
            logger.error("fail_open=False, blocking request due to API error")
            decision = Decision.block(reasons=[f"API error: {error_type}: {error_msg}"])
            raise SecurityPolicyError(decision, f"AI Defense API unavailable and fail_open=False: {error_msg}")
    
    def inspect_conversation(
        self,
        messages: List[Dict[str, Any]],
        metadata: Dict[str, Any],
    ) -> Decision:
        """
        Inspect an LLM conversation for security violations (sync).
        
        Args:
            messages: List of conversation messages with role and content
            metadata: Additional metadata (user, src_app, transaction_id, etc.)
            
        Returns:
            Decision indicating whether to allow, block, or sanitize
            
        Raises:
            SecurityPolicyError: If fail_open=False and API is unreachable
        """
        if not self.endpoint or not self.api_key:
            logger.debug("No API endpoint/key configured, allowing by default")
            return Decision.allow()
        
        payload = self._build_request_payload(messages, metadata)
        logger.debug(f"AI Defense request: {len(messages)} messages, metadata={list(metadata.keys())}")
        logger.debug(f"AI Defense request payload: {payload}")
        headers = {
            "X-Cisco-AI-Defense-API-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        last_error: Optional[Exception] = None
        
        for attempt in range(self.retry_attempts):
            try:
                response = self._sync_client.post(
                    f"{self.endpoint}/v1/inspect/chat",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                response_json = response.json()
                logger.debug(f"AI Defense response: {response_json}")
                return self._parse_response(response_json)
            except Exception as e:
                last_error = e
                logger.debug(f"Attempt {attempt + 1}/{self.retry_attempts} failed: {e}")
        
        return self._handle_error(
            last_error,  # type: ignore
            context="inspect_conversation",
            message_count=len(messages),
        )
    
    async def ainspect_conversation(
        self,
        messages: List[Dict[str, Any]],
        metadata: Dict[str, Any],
    ) -> Decision:
        """
        Inspect an LLM conversation for security violations (async).
        
        Args:
            messages: List of conversation messages with role and content
            metadata: Additional metadata (user, src_app, transaction_id, etc.)
            
        Returns:
            Decision indicating whether to allow, block, or sanitize
            
        Raises:
            SecurityPolicyError: If fail_open=False and API is unreachable
        """
        if not self.endpoint or not self.api_key:
            logger.debug("No API endpoint/key configured, allowing by default")
            return Decision.allow()
        
        payload = self._build_request_payload(messages, metadata)
        logger.debug(f"AI Defense async request: {len(messages)} messages, metadata={list(metadata.keys())}")
        logger.debug(f"AI Defense async request payload: {payload}")
        headers = {
            "X-Cisco-AI-Defense-API-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        last_error: Optional[Exception] = None
        
        # Create fresh async client per request to avoid event loop issues
        # (Strands and other frameworks may run async code in different event loops)
        timeout = httpx.Timeout(self.timeout_ms / 1000.0)
        async with httpx.AsyncClient(timeout=timeout, http2=False) as client:
            for attempt in range(self.retry_attempts):
                try:
                    response = await client.post(
                        f"{self.endpoint}/v1/inspect/chat",
                        json=payload,
                        headers=headers,
                    )
                    if response.status_code != 200:
                        logger.debug(f"AI Defense async response error: {response.status_code} - {response.text[:500]}")
                    response.raise_for_status()
                    response_json = response.json()
                    logger.debug(f"AI Defense async response: {response_json}")
                    return self._parse_response(response_json)
                except Exception as e:
                    last_error = e
                    logger.debug(f"Attempt {attempt + 1}/{self.retry_attempts} failed: {e}")
        
        return self._handle_error(
            last_error,  # type: ignore
            context="ainspect_conversation",
            message_count=len(messages),
        )
    
    def close(self) -> None:
        """Close HTTP client."""
        self._sync_client.close()
    
    async def aclose(self) -> None:
        """Close async resources.
        
        Note: This is a no-op because async clients are created per-request
        in ainspect_conversation() to avoid event loop issues.
        """
        pass
