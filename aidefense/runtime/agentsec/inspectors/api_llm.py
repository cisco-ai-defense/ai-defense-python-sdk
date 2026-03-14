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

"""LLM Inspector for Cisco AI Defense Chat Inspection API.

Uses ChatInspectionClient (sync) and AsyncChatInspectionClient (async) from the runtime.
"""

import asyncio
import logging
import threading
import time
from typing import Any, Dict, List, Optional

import aiohttp
import httpx
import requests

from ..decision import Decision
from ..exceptions import (
    ConfigurationError,
    SecurityPolicyError,
    InspectionTimeoutError,
    InspectionNetworkError,
)
from aidefense.config import Config, AsyncConfig
from aidefense.runtime.chat_inspect import ChatInspectionClient, AsyncChatInspectionClient
from aidefense.runtime.chat_models import Message, Role
from aidefense.runtime.models import Metadata, InspectResponse, InspectionConfig, Rule, RuleName

logger = logging.getLogger("aidefense.runtime.agentsec.inspectors.llm")


def _inspect_response_to_decision(resp: InspectResponse) -> Decision:
    """Map runtime InspectResponse to agentsec Decision."""
    reasons = [c.value for c in resp.classifications] if resp.classifications else []
    if resp.explanation and resp.explanation not in reasons:
        reasons.append(resp.explanation)
    if not reasons and resp.rules:
        for rule in resp.rules:
            rn = getattr(rule, "rule_name", None) or (rule.get("rule_name") if isinstance(rule, dict) else None)
            cl = getattr(rule, "classification", None) or (rule.get("classification") if isinstance(rule, dict) else None)
            if cl and str(cl) not in ("NONE_VIOLATION", "NONE_SEVERITY"):
                reasons.append(f"{rn}: {cl}")
    severity_str = resp.severity.value if resp.severity else None
    rules_list = [getattr(r, "__dict__", r) if not isinstance(r, dict) else r for r in (resp.rules or [])]
    if resp.action.name == "BLOCK" or not resp.is_safe:
        return Decision.block(
            reasons=reasons,
            raw_response=resp,
            severity=severity_str,
            classifications=[c.value for c in resp.classifications] if resp.classifications else None,
            rules=rules_list,
            explanation=resp.explanation,
            event_id=resp.event_id,
        )
    return Decision.allow(
        reasons=reasons,
        raw_response=resp,
        severity=severity_str,
        classifications=[c.value for c in resp.classifications] if resp.classifications else None,
        rules=rules_list,
        explanation=resp.explanation,
        event_id=resp.event_id,
    )


class _AgentSecConfig(Config):
    """Per-inspector config for ChatInspectionClient; __new__ bypasses singleton."""

    def __new__(cls, *args, **kwargs):
        return object.__new__(cls)

    def _initialize(
        self,
        runtime_base_url: str = None,
        timeout_sec: float = None,
        logger_instance: logging.Logger = None,
        **kwargs,
    ):
        timeout_int = max(1, int(timeout_sec)) if timeout_sec is not None else None
        Config._initialize(
            self,
            region="us-west-2",
            runtime_base_url=runtime_base_url,
            timeout=timeout_int,
            logger=logger_instance,
        )
        if runtime_base_url:
            self.runtime_base_url = runtime_base_url.rstrip("/")


class _AgentSecAsyncConfig(AsyncConfig):
    """Per-inspector config for AsyncChatInspectionClient; __new__ bypasses singleton."""

    def __new__(cls, *args, **kwargs):
        return object.__new__(cls)

    def _initialize(
        self,
        runtime_base_url: str = None,
        timeout_sec: float = None,
        logger_instance: logging.Logger = None,
        **kwargs,
    ):
        timeout_int = max(1, int(timeout_sec)) if timeout_sec is not None else None
        AsyncConfig._initialize(
            self,
            region="us-west-2",
            runtime_base_url=runtime_base_url,
            timeout=timeout_int,
            logger=logger_instance,
        )
        if runtime_base_url:
            self.runtime_base_url = runtime_base_url.rstrip("/")


def _messages_to_runtime(messages: List[Dict[str, Any]]) -> List[Message]:
    """Convert agentsec message dicts to runtime Message list."""
    out = []
    valid_roles = {r.value for r in Role}
    for m in messages:
        role_str = (m.get("role") or "user").lower() if isinstance(m.get("role"), str) else "user"
        if role_str not in valid_roles:
            role_str = "user"
        content = m.get("content") or ""
        if not isinstance(content, str):
            content = str(content)
        out.append(Message(role=Role(role_str), content=content))
    return out


def _metadata_to_runtime(metadata: Dict[str, Any]) -> Optional[Metadata]:
    """Convert agentsec metadata dict to runtime Metadata if present."""
    if not metadata or not isinstance(metadata, dict):
        return None
    known = {"user", "created_at", "src_app", "dst_app", "sni", "dst_ip", "src_ip", "dst_host", "user_agent", "client_transaction_id"}
    kwargs = {k: metadata[k] for k in known if k in metadata and metadata[k] is not None}
    return Metadata(**kwargs) if kwargs else None


def _normalize_rule_name(name: str) -> Optional[RuleName]:
    """Try to match a rule name string to a RuleName enum value.
    
    Attempts exact match first, then case-insensitive match with
    underscore/hyphen normalization (e.g. "prompt_injection" -> "Prompt Injection").
    
    Returns None if no matching RuleName is found.
    """
    # Exact match
    try:
        return RuleName(name)
    except ValueError:
        pass
    # Normalize: lowercase, replace underscores/hyphens with spaces
    normalized = name.lower().replace("_", " ").replace("-", " ").strip()
    for rule_name in RuleName:
        if rule_name.value.lower() == normalized:
            return rule_name
    return None


def _inspection_config_from_inspector(
    default_rules: Optional[List[Any]],
    entity_types: Optional[List[str]],
) -> Optional[InspectionConfig]:
    """Build runtime InspectionConfig from LLMInspector default_rules and entity_types."""
    if not default_rules and not entity_types:
        return None
    rules = []
    for rule in default_rules or []:
        if isinstance(rule, dict):
            rule_dict = dict(rule)
        elif isinstance(rule, Rule):
            rule_dict = {"rule_name": rule.rule_name, "entity_types": getattr(rule, "entity_types", None)}
        else:
            rule_dict = {"rule_name": rule}
        if entity_types and rule_dict.get("entity_types") is None:
            rule_dict["entity_types"] = entity_types
        rn = rule_dict.get("rule_name")
        if rn:
            matched = _normalize_rule_name(str(rn))
            if matched is not None:
                rule_name = matched
            else:
                # Preserve the original string for custom/server-side rule names
                # (e.g. "jailbreak") instead of silently falling back to PII
                rule_name = str(rn)
                logger.debug(f"Rule name '{rn}' not in RuleName enum, passing through as-is")
        else:
            rule_name = RuleName.PII
        rules.append(Rule(rule_name=rule_name, entity_types=rule_dict.get("entity_types")))
    if not rules and entity_types:
        rules = [Rule(rule_name=RuleName.PII, entity_types=entity_types)]
    return InspectionConfig(enabled_rules=rules) if rules else None


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
        retry_total: Total number of retry attempts (default 1 = no retry)
        retry_backoff: Exponential backoff factor in seconds (default 0 = no backoff)
        retry_status_codes: HTTP status codes to retry on
        fail_open: Whether to allow requests when API is unreachable
        entity_types: Entity types to filter for (e.g., ["EMAIL", "PHONE_NUMBER"])
    """
    
    # Maximum backoff delay to prevent runaway waits
    MAX_BACKOFF_DELAY = 30.0
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        default_rules: Optional[List[Any]] = None,
        entity_types: Optional[List[str]] = None,
        timeout_ms: Optional[int] = None,
        retry_attempts: Optional[int] = None,  # Deprecated, use retry_total
        retry_total: Optional[int] = None,
        retry_backoff: Optional[float] = None,
        retry_status_codes: Optional[List[int]] = None,
        pool_max_connections: Optional[int] = None,
        pool_max_keepalive: Optional[int] = None,
        fail_open: bool = True,
    ):
        """
        Initialize the LLM Inspector.
        
        Args:
            api_key: API key for Cisco AI Defense (or from AI_DEFENSE_API_MODE_LLM_API_KEY env)
            endpoint: Base URL for the AI Defense API (or from AI_DEFENSE_API_MODE_LLM_ENDPOINT env)
            default_rules: Default rules for inspection
            entity_types: Entity types to filter for (e.g., ["EMAIL", "PHONE_NUMBER"])
            timeout_ms: Request timeout in milliseconds (if omitted, SDK config default is used)
            retry_attempts: Deprecated, use retry_total instead
            retry_total: Total number of retry attempts (default 1, no retry)
            retry_backoff: Exponential backoff factor in seconds (default 0, no backoff)
            retry_status_codes: HTTP status codes to retry on (default [500, 502, 503, 504])
            pool_max_connections: Maximum connections in the pool (default 100)
            pool_max_keepalive: Maximum keepalive connections (default 20)
            fail_open: Whether to allow requests when API is unreachable (default True)
        """
        import os
        from .. import _state
        
        # Priority: explicit param > state > env var
        self.api_key = api_key or _state.get_api_mode_llm_api_key() or os.environ.get("AI_DEFENSE_API_MODE_LLM_API_KEY")
        self.endpoint = endpoint or _state.get_api_mode_llm_endpoint() or os.environ.get("AI_DEFENSE_API_MODE_LLM_ENDPOINT")
        self.default_rules = default_rules or []
        self.entity_types = entity_types or _state.get_llm_entity_types()
        self.fail_open = fail_open
        
        # Timeout: explicit param > state; if neither set, leave None so SDK uses its default.
        # A value of 0 or negative is treated as "not set" (use SDK default).
        if timeout_ms is not None and timeout_ms > 0:
            self.timeout_ms = timeout_ms
        else:
            state_timeout = _state.get_api_llm_timeout()
            self.timeout_ms = (state_timeout * 1000) if state_timeout and state_timeout > 0 else None
        
        # Retry configuration: explicit param > state > default
        # Handle deprecated retry_attempts parameter
        if retry_total is not None:
            self.retry_total = max(1, retry_total)
        elif retry_attempts is not None:
            # Deprecated parameter - use it but log warning
            logger.debug("retry_attempts is deprecated, use retry_total instead")
            self.retry_total = max(1, retry_attempts)
        else:
            state_retry = _state.get_api_llm_retry_total()
            self.retry_total = max(1, state_retry) if state_retry is not None else 1
        
        if retry_backoff is not None:
            self.retry_backoff = max(0.0, retry_backoff)
        else:
            state_backoff = _state.get_api_llm_retry_backoff()
            self.retry_backoff = max(0.0, state_backoff) if state_backoff is not None else 0.0
        
        if retry_status_codes is not None:
            self.retry_status_codes = retry_status_codes
        else:
            state_codes = _state.get_api_llm_retry_status_codes()
            self.retry_status_codes = state_codes if state_codes is not None else [500, 502, 503, 504]
        
        # Keep retry_attempts as alias for backward compatibility
        self.retry_attempts = self.retry_total
        
        # Connection pool configuration: explicit param > state > default
        if pool_max_connections is not None:
            self.pool_max_connections = pool_max_connections
        else:
            state_pool = _state.get_pool_max_connections()
            self.pool_max_connections = state_pool if state_pool is not None else 100
        
        if pool_max_keepalive is not None:
            self.pool_max_keepalive = pool_max_keepalive
        else:
            state_keepalive = _state.get_pool_max_keepalive()
            self.pool_max_keepalive = state_keepalive if state_keepalive is not None else 20
        
        # ChatInspectionClient is created lazily via _get_chat_client()
        self._chat_client: Optional[ChatInspectionClient] = None
        self._chat_client_lock = threading.Lock()
        # AsyncChatInspectionClient is created lazily per event loop via _get_async_chat_client()
        self._async_chat_client: Optional[AsyncChatInspectionClient] = None
        self._async_chat_client_lock = threading.Lock()
        self._async_loop_id: Optional[int] = None
    
    def _get_chat_client(self) -> ChatInspectionClient:
        """Get or create the ChatInspectionClient (thread-safe)."""
        if self._chat_client is not None:
            return self._chat_client
        with self._chat_client_lock:
            if self._chat_client is not None:
                return self._chat_client
            runtime_base_url = (self.endpoint or "").rstrip("/").removesuffix("/api")
            if not runtime_base_url:
                runtime_base_url = "https://us.api.inspect.aidefense.security.cisco.com"
            cfg = _AgentSecConfig(
                runtime_base_url=runtime_base_url,
                timeout_sec=(self.timeout_ms / 1000.0) if self.timeout_ms is not None else None,
                logger_instance=logger,
            )
            self._chat_client = ChatInspectionClient(api_key=self.api_key, config=cfg)
            return self._chat_client
    
    async def _get_async_chat_client(self) -> AsyncChatInspectionClient:
        """Get or create AsyncChatInspectionClient for the current event loop (thread-safe)."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        loop_id = id(loop) if loop else None
        if self._async_chat_client is not None and self._async_loop_id == loop_id:
            return self._async_chat_client
        with self._async_chat_client_lock:
            if self._async_chat_client is not None and self._async_loop_id == loop_id:
                return self._async_chat_client
            runtime_base_url = (self.endpoint or "").rstrip("/").removesuffix("/api")
            if not runtime_base_url:
                runtime_base_url = "https://us.api.inspect.aidefense.security.cisco.com"
            cfg = _AgentSecAsyncConfig(
                runtime_base_url=runtime_base_url,
                timeout_sec=(self.timeout_ms / 1000.0) if self.timeout_ms is not None else None,
                logger_instance=logger,
            )
            client = AsyncChatInspectionClient(api_key=self.api_key, config=cfg)
            await client._request_handler.ensure_session()
            self._async_chat_client = client
            self._async_loop_id = loop_id
            return self._async_chat_client
    
    def _get_backoff_delay(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay for a retry attempt.
        
        Args:
            attempt: The attempt number (0-indexed)
            
        Returns:
            Delay in seconds, capped at MAX_BACKOFF_DELAY
        """
        if self.retry_backoff <= 0:
            return 0.0
        
        # Exponential backoff: backoff_factor * (2 ** attempt)
        delay = self.retry_backoff * (2 ** attempt)
        
        # Cap the delay to prevent runaway waits
        return min(delay, self.MAX_BACKOFF_DELAY)
    
    def _should_retry(self, error: Exception, status_code: Optional[int] = None) -> bool:
        """
        Determine if a request should be retried based on the error.
        
        Args:
            error: The exception that occurred
            status_code: Optional HTTP status code from the response
            
        Returns:
            True if the request should be retried
        """
        import json
        from aidefense.exceptions import ApiError as SDKApiError
        
        # Never retry on JSON decode errors (response is malformed, not transient)
        if isinstance(error, json.JSONDecodeError):
            logger.warning(f"JSON decode error (not retryable): {error}")
            return False
        
        # Always retry on timeout or network errors (httpx, requests, aiohttp, asyncio)
        if isinstance(error, (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError)):
            return True
        if isinstance(error, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
            return True
        if isinstance(error, (asyncio.TimeoutError, aiohttp.ClientError)):
            return True
        
        # Retry on configured status codes (httpx / requests native exceptions)
        if isinstance(error, httpx.HTTPStatusError):
            return error.response.status_code in self.retry_status_codes
        if isinstance(error, requests.exceptions.HTTPError) and getattr(error, "response", None):
            return getattr(error.response, "status_code", 0) in self.retry_status_codes
        
        # Retry on SDK ApiError with retryable status code
        if isinstance(error, SDKApiError) and getattr(error, "status_code", None):
            return error.status_code in self.retry_status_codes
        
        # Don't retry on other errors
        return False
    
    def _handle_error(
        self,
        error: Exception,
        context: Optional[str] = None,
        message_count: int = 0,
    ) -> Decision:
        """
        Handle API errors based on fail_open config.
        
        Centralizes error handling for all API-related errors. Logs with context
        and respects fail_open setting. When fail_open=False, raises typed
        exceptions (InspectionTimeoutError, InspectionNetworkError) to allow
        callers to handle specific error types.
        
        Args:
            error: The exception that occurred
            context: Optional context string (e.g., "inspect_conversation")
            message_count: Number of messages in the request for logging
            
        Returns:
            Decision.allow() if fail_open
            
        Raises:
            InspectionTimeoutError: If fail_open=False and error is a timeout
            InspectionNetworkError: If fail_open=False and error is a network error
            SecurityPolicyError: If fail_open=False for other errors
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
            
            # Raise typed exceptions based on error type
            if isinstance(error, (httpx.TimeoutException, requests.exceptions.Timeout, asyncio.TimeoutError)):
                raise InspectionTimeoutError(
                    f"Inspection timed out: {error_msg}",
                    timeout_ms=self.timeout_ms,
                ) from error
            
            if isinstance(error, (httpx.ConnectError, httpx.NetworkError, requests.exceptions.ConnectionError, aiohttp.ClientError)):
                raise InspectionNetworkError(
                    f"Failed to connect to inspection API: {error_msg}"
                ) from error
            
            # ValueError from urllib3 timeout validation (timeout <= 0) is a timeout issue
            if isinstance(error, ValueError) and "timeout" in error_msg.lower():
                raise InspectionTimeoutError(
                    f"Inspection timeout configuration error: {error_msg}",
                    timeout_ms=self.timeout_ms,
                ) from error
            
            # ValueError from API key format validation is a configuration issue
            if isinstance(error, ValueError) and "api key" in error_msg.lower():
                raise ConfigurationError(
                    f"Invalid API key configuration: {error_msg}"
                ) from error
            
            # For other errors, raise SecurityPolicyError
            decision = Decision.block(reasons=[f"API error: {error_type}: {error_msg}"])
            raise SecurityPolicyError(decision, f"AI Defense API unavailable and fail_open=False: {error_msg}") from error
    
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
            InspectionTimeoutError: If fail_open=False and request times out
            InspectionNetworkError: If fail_open=False and network error occurs
            SecurityPolicyError: If fail_open=False and other API errors occur
        """
        if not self.endpoint or not self.api_key:
            logger.debug("No API endpoint/key configured, allowing by default")
            return Decision.allow()
        
        logger.info(f"Request inspection: {len(messages)} messages")
        runtime_messages = _messages_to_runtime(messages)
        runtime_metadata = _metadata_to_runtime(metadata or {})
        config = _inspection_config_from_inspector(self.default_rules, self.entity_types)
        last_error: Optional[Exception] = None
        
        for attempt in range(self.retry_total):
            try:
                client = self._get_chat_client()
                resp = client.inspect_conversation(
                    messages=runtime_messages,
                    metadata=runtime_metadata,
                    config=config,
                    timeout=(max(1, int(self.timeout_ms / 1000)) if self.timeout_ms is not None else None),
                )
                decision = _inspect_response_to_decision(resp)
                logger.info(f"Request decision: {decision.action}")
                return decision
            except Exception as e:
                last_error = e
                logger.debug(f"Attempt {attempt + 1}/{self.retry_total} failed: {e}")
                is_last_attempt = attempt >= self.retry_total - 1
                if is_last_attempt or not self._should_retry(e):
                    break
                delay = self._get_backoff_delay(attempt)
                if delay > 0:
                    logger.debug(f"Retrying in {delay:.2f}s...")
                    time.sleep(delay)
        
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
        Uses AsyncChatInspectionClient for native async I/O.
        
        Args:
            messages: List of conversation messages with role and content
            metadata: Additional metadata (user, src_app, transaction_id, etc.)
            
        Returns:
            Decision indicating whether to allow, block, or sanitize
            
        Raises:
            InspectionTimeoutError: If fail_open=False and request times out
            InspectionNetworkError: If fail_open=False and network error occurs
            SecurityPolicyError: If fail_open=False and other API errors occur
        """
        if not self.endpoint or not self.api_key:
            logger.debug("No API endpoint/key configured, allowing by default")
            return Decision.allow()
        
        logger.info(f"Request inspection: {len(messages)} messages")
        runtime_messages = _messages_to_runtime(messages)
        runtime_metadata = _metadata_to_runtime(metadata or {})
        config = _inspection_config_from_inspector(self.default_rules, self.entity_types)
        last_error: Optional[Exception] = None
        timeout_sec = (max(1, int(self.timeout_ms / 1000)) if self.timeout_ms is not None else None)
        
        for attempt in range(self.retry_total):
            try:
                client = await self._get_async_chat_client()
                resp = await client.inspect_conversation(
                    messages=runtime_messages,
                    metadata=runtime_metadata,
                    config=config,
                    timeout=timeout_sec,
                )
                decision = _inspect_response_to_decision(resp)
                logger.info(f"Request decision: {decision.action}")
                return decision
            except Exception as e:
                last_error = e
                logger.debug(f"Attempt {attempt + 1}/{self.retry_total} failed: {e}")
                is_last_attempt = attempt >= self.retry_total - 1
                if is_last_attempt or not self._should_retry(e):
                    break
                delay = self._get_backoff_delay(attempt)
                if delay > 0:
                    logger.debug(f"Retrying in {delay:.2f}s...")
                    await asyncio.sleep(delay)
        
        return self._handle_error(
            last_error,  # type: ignore
            context="ainspect_conversation",
            message_count=len(messages),
        )
    
    def close(self) -> None:
        """Release clients and close any open aiohttp sessions.
        
        This properly closes the async client's aiohttp session to prevent
        'Unclosed client session' warnings during interpreter shutdown.
        """
        with self._chat_client_lock:
            if self._chat_client is not None:
                self._chat_client = None
        async_client = None
        with self._async_chat_client_lock:
            if self._async_chat_client is not None:
                async_client = self._async_chat_client
                self._async_chat_client = None
                self._async_loop_id = None
        if async_client is not None:
            self._close_async_client_sync(async_client)
    
    def _close_async_client_sync(self, async_client) -> None:
        """Close an async chat client's aiohttp session and connector from a synchronous context."""
        try:
            handler = getattr(async_client, '_request_handler', None)
            if handler is None:
                return
            session = getattr(handler, '_session', None)
            connector = getattr(handler, '_connector', None)

            async def _close_all():
                """Close both the session and the shared connector."""
                if session is not None and not session.closed:
                    await session.close()
                if connector is not None and not connector.closed:
                    await connector.close()

            # Try to run the async close in an event loop
            try:
                # Check if there's already a running loop (Python 3.10+)
                loop = asyncio.get_running_loop()
                # If we're inside a running loop, we can't use run_until_complete
                # The resources will be cleaned up when the loop closes
            except RuntimeError:
                # No running loop — create a new one to run cleanup
                try:
                    new_loop = asyncio.new_event_loop()
                    new_loop.run_until_complete(_close_all())
                    new_loop.close()
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Could not close async session synchronously: {e}")
    
    async def aclose(self) -> None:
        """Release the AsyncChatInspectionClient session and clear cached clients."""
        client_to_close = None
        with self._async_chat_client_lock:
            if self._async_chat_client is not None:
                client_to_close = self._async_chat_client
                self._async_chat_client = None
                self._async_loop_id = None
        if client_to_close is not None:
            try:
                await client_to_close._request_handler.close()
            except Exception as e:
                logger.debug(f"Error closing async chat client session: {e}")
        self.close()
