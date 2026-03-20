# Copyright 2026 Cisco Systems, Inc. and its affiliates
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

"""MCP Inspector for tool, prompt, and resource inspection using Cisco AI Defense MCP Inspection API.

Uses MCPInspectionClient from the runtime; no direct HTTP implementation.
"""

import itertools
import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

import httpx
import requests

from ..decision import Decision
from ..exceptions import (
    ConfigurationError,
    SecurityPolicyError,
    InspectionTimeoutError,
    InspectionNetworkError,
)
from aidefense.config import Config
from aidefense.runtime.mcp_inspect import MCPInspectionClient
from aidefense.runtime.mcp_models import MCPMessage, MCPInspectResponse

logger = logging.getLogger("aidefense.runtime.agentsec.inspectors.mcp")


def _mcp_inspect_response_to_decision(mcp_resp: MCPInspectResponse) -> Decision:
    """Map MCPInspectResponse to agentsec Decision."""
    if mcp_resp.error:
        return Decision.block(
            reasons=[f"MCP inspection error: {mcp_resp.error.message}"],
            raw_response=mcp_resp,
        )
    if not mcp_resp.result:
        return Decision.allow(raw_response=mcp_resp)
    resp = mcp_resp.result
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
    kwargs = dict(
        reasons=reasons,
        raw_response=mcp_resp,
        severity=severity_str,
        classifications=[c.value for c in resp.classifications] if resp.classifications else None,
        rules=rules_list,
        explanation=resp.explanation,
        event_id=resp.event_id,
    )
    if resp.action.name == "BLOCK" or not resp.is_safe:
        return Decision.block(**kwargs)
    return Decision.allow(**kwargs)


def _result_to_content_dict(result: Any) -> Dict[str, Any]:
    """Build MCP result_data for inspect_response. Passes content as-is when already in MCP shape."""
    if isinstance(result, dict) and "content" in result:
        return result
    if isinstance(result, list):
        return {"content": result}
    if isinstance(result, dict):
        return {"content": [result]}
    if isinstance(result, str):
        return {"content": [{"type": "text", "text": result}]}
    return {"content": [{"type": "text", "text": str(result)}]}


def _request_params_for_method(method: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Build params dict for MCP inspect_response from method and request context."""
    if method == "resources/read":
        return {"uri": tool_name}
    if method == "prompts/get":
        return {"name": tool_name, "arguments": arguments or {}}
    return {"name": tool_name, "arguments": arguments or {}}


class _AgentSecMCPConfig(Config):
    """Per-inspector config for MCPInspectionClient; __new__ bypasses singleton."""

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


class MCPInspector:
    """
    Inspector for MCP (Model Context Protocol) operations using Cisco AI Defense.
    
    This class integrates with the Cisco AI Defense MCP Inspection API to
    inspect MCP tool calls, prompt retrievals, and resource reads for security
    policy violations.
    
    Supported MCP methods:
    - tools/call: Tool execution inspection
    - prompts/get: Prompt retrieval inspection
    - resources/read: Resource access inspection
    
    The API expects raw MCP JSON-RPC 2.0 messages and returns inspection results
    with is_safe boolean and action (Allow/Block).
    
    Attributes:
        api_key: API key for Cisco AI Defense MCP inspection
        endpoint: Base URL for the AI Defense MCP API
        timeout_ms: Request timeout in milliseconds
        retry_total: Total number of retry attempts (default 1 = no retry)
        retry_backoff: Exponential backoff factor in seconds (default 0 = no backoff)
        retry_status_codes: HTTP status codes to retry on
        fail_open: Whether to allow operations when API is unreachable
    """
    
    # Maximum backoff delay to prevent runaway waits
    MAX_BACKOFF_DELAY = 30.0
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        timeout_ms: Optional[int] = None,
        retry_attempts: Optional[int] = None,  # Deprecated, use retry_total
        retry_total: Optional[int] = None,
        retry_backoff: Optional[float] = None,
        retry_status_codes: Optional[List[int]] = None,
        pool_max_connections: Optional[int] = None,
        pool_max_keepalive: Optional[int] = None,
        fail_open: bool = True,
    ) -> None:
        """
        Initialize the MCP Inspector.
        
        Args:
            api_key: API key for Cisco AI Defense MCP inspection.
                     Falls back to AI_DEFENSE_API_MODE_MCP_API_KEY env var.
            endpoint: Base URL for the AI Defense MCP API.
                      Falls back to AI_DEFENSE_API_MODE_MCP_ENDPOINT env var.
            timeout_ms: Request timeout in milliseconds (if omitted, SDK config default is used)
            retry_attempts: Deprecated, use retry_total instead
            retry_total: Total number of retry attempts (default 1, no retry)
            retry_backoff: Exponential backoff factor in seconds (default 0, no backoff)
            retry_status_codes: HTTP status codes to retry on (default [500, 502, 503, 504])
            pool_max_connections: Maximum connections in the pool (default 100)
            pool_max_keepalive: Maximum keepalive connections (default 20)
            fail_open: If True, allow tool calls on API errors (default True)
        """
        from .. import _state
        
        # API key: explicit > state > MCP-specific env (no LLM fallback)
        self.api_key = (
            api_key 
            or _state.get_api_mode_mcp_api_key() 
            or os.environ.get("AI_DEFENSE_API_MODE_MCP_API_KEY")
        )
        
        # Endpoint: explicit > state > MCP-specific env (no LLM fallback)
        raw_endpoint = (
            endpoint 
            or _state.get_api_mode_mcp_endpoint() 
            or os.environ.get("AI_DEFENSE_API_MODE_MCP_ENDPOINT")
        )
        
        # Store base endpoint (strip any trailing /api/v1/inspect/mcp path)
        if raw_endpoint:
            self.endpoint = raw_endpoint.rstrip("/").removesuffix("/api/v1/inspect/mcp").removesuffix("/api")
        else:
            self.endpoint = None
        
        self.fail_open = fail_open
        
        # Timeout: explicit param > state; if neither set, leave None so SDK uses its default.
        # A value of 0 or negative is treated as "not set" (use SDK default).
        if timeout_ms is not None and timeout_ms > 0:
            self.timeout_ms = timeout_ms
        else:
            state_timeout = _state.get_api_mcp_timeout()
            self.timeout_ms = (state_timeout * 1000) if state_timeout and state_timeout > 0 else None
        
        # Retry configuration: explicit param > state > default
        if retry_total is not None:
            self.retry_total = max(1, retry_total)
        elif retry_attempts is not None:
            logger.debug("retry_attempts is deprecated, use retry_total instead")
            self.retry_total = max(1, retry_attempts)
        else:
            state_retry = _state.get_api_mcp_retry_total()
            self.retry_total = max(1, state_retry) if state_retry is not None else 1
        
        if retry_backoff is not None:
            self.retry_backoff = max(0.0, retry_backoff)
        else:
            state_backoff = _state.get_api_mcp_retry_backoff()
            self.retry_backoff = max(0.0, state_backoff) if state_backoff is not None else 0.0
        
        if retry_status_codes is not None:
            self.retry_status_codes = retry_status_codes
        else:
            state_codes = _state.get_api_mcp_retry_status_codes()
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
        
        # Thread-safe counter for JSON-RPC message IDs using itertools.count()
        self._request_id_counter = itertools.count(1)
        
        # MCPInspectionClient is created lazily via _get_mcp_client()
        self._mcp_client: Optional[MCPInspectionClient] = None
        self._mcp_client_lock = threading.Lock()
    
    def _get_next_id(self) -> int:
        """Get the next request ID for JSON-RPC messages (thread-safe)."""
        return next(self._request_id_counter)
    
    def _get_mcp_client(self) -> MCPInspectionClient:
        """Get or create the MCPInspectionClient (thread-safe)."""
        if self._mcp_client is not None:
            return self._mcp_client
        with self._mcp_client_lock:
            if self._mcp_client is not None:
                return self._mcp_client
            runtime_base_url = (self.endpoint or "").rstrip("/")
            if not runtime_base_url:
                runtime_base_url = "https://us.api.inspect.aidefense.security.cisco.com"
            cfg = _AgentSecMCPConfig(
                runtime_base_url=runtime_base_url,
                timeout_sec=(self.timeout_ms / 1000.0) if self.timeout_ms is not None else None,
                logger_instance=logger,
            )
            self._mcp_client = MCPInspectionClient(api_key=self.api_key, config=cfg)
            return self._mcp_client
    
    def _get_backoff_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay for a retry attempt."""
        if self.retry_backoff <= 0:
            return 0.0
        delay = self.retry_backoff * (2 ** attempt)
        return min(delay, self.MAX_BACKOFF_DELAY)
    
    def _should_retry(self, error: Exception) -> bool:
        """Determine if a request should be retried based on the error."""
        import json
        from aidefense.exceptions import ApiError as SDKApiError
        
        if isinstance(error, json.JSONDecodeError):
            logger.warning(f"JSON decode error (not retryable): {error}")
            return False
        if isinstance(error, (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError)):
            return True
        if isinstance(error, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
            return True
        if isinstance(error, httpx.HTTPStatusError):
            return error.response.status_code in self.retry_status_codes
        if isinstance(error, requests.exceptions.HTTPError) and getattr(error, "response", None):
            return getattr(error.response, "status_code", 0) in self.retry_status_codes
        if isinstance(error, SDKApiError) and getattr(error, "status_code", None):
            return error.status_code in self.retry_status_codes
        return False
    
    def _handle_error(
        self,
        error: Exception,
        tool_name: str,
        context: Optional[str] = None,
    ) -> Decision:
        """
        Handle API errors based on fail_open config.
        
        Args:
            error: The exception that occurred
            tool_name: Name of the tool being inspected
            context: Optional context string (e.g., "inspect_request")
            
        Returns:
            Decision.allow() if fail_open
            
        Raises:
            InspectionTimeoutError: If fail_open=False and error is a timeout
            InspectionNetworkError: If fail_open=False and error is a network error
            SecurityPolicyError: If fail_open=False for other errors
        """
        error_type = type(error).__name__
        error_msg = str(error)
        
        ctx_str = f" [{context}]" if context else ""
        logger.warning(f"MCP inspection error for tool={tool_name}{ctx_str}: {error_type}: {error_msg}")
        logger.debug(f"Error details: {error}", exc_info=True)
        
        if self.fail_open:
            logger.warning(f"mcp_fail_open=True, allowing tool call '{tool_name}' despite error")
            return Decision.allow(reasons=[f"MCP inspection error ({error_type}), fail_open=True"])
        else:
            logger.error(f"mcp_fail_open=False, blocking tool call '{tool_name}' due to error")
            
            # Raise typed exceptions based on error type
            if isinstance(error, (httpx.TimeoutException, requests.exceptions.Timeout)):
                raise InspectionTimeoutError(
                    f"MCP inspection timed out: {error_msg}",
                    timeout_ms=self.timeout_ms,
                ) from error
            
            if isinstance(error, (httpx.ConnectError, httpx.NetworkError, requests.exceptions.ConnectionError)):
                raise InspectionNetworkError(
                    f"Failed to connect to MCP inspection API: {error_msg}"
                ) from error
            
            if isinstance(error, ValueError) and "timeout" in error_msg.lower():
                raise InspectionTimeoutError(
                    f"MCP inspection timeout configuration error: {error_msg}",
                    timeout_ms=self.timeout_ms,
                ) from error
            
            # ValueError from API key format validation is a configuration issue
            if isinstance(error, ValueError) and "api key" in error_msg.lower():
                raise ConfigurationError(
                    f"Invalid API key configuration: {error_msg}"
                ) from error
            
            decision = Decision.block(reasons=[f"MCP inspection error: {error_type}: {error_msg}"])
            raise SecurityPolicyError(decision, f"MCP inspection failed and fail_open=False: {error_msg}") from error
    
    def inspect_request(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        metadata: Dict[str, Any],
        method: str = "tools/call",
    ) -> Decision:
        """
        Inspect an MCP request before execution (sync).
        
        Sends the request to Cisco AI Defense MCP Inspection API for
        security analysis before execution.
        
        Args:
            tool_name: Name of the tool/prompt/resource being accessed
            arguments: Arguments passed to the operation
            metadata: Additional metadata about the request (not sent to API)
            method: MCP method (tools/call, prompts/get, resources/read)
            
        Returns:
            Decision indicating whether to allow or block the request
            
        Raises:
            SecurityPolicyError: If fail_open=False and API is unreachable
        """
        if not self.endpoint or not self.api_key:
            logger.debug(f"MCP request intercepted: {method}={tool_name}, allowing by default (no API configured)")
            return Decision.allow()
        
        logger.debug(f"MCP inspection request: {method}={tool_name}")
        last_error: Optional[Exception] = None
        timeout_sec = (max(1, int(self.timeout_ms / 1000)) if self.timeout_ms is not None else None)
        
        for attempt in range(self.retry_total):
            try:
                client = self._get_mcp_client()
                if method == "tools/call":
                    mcp_resp = client.inspect_tool_call(
                        tool_name=tool_name,
                        arguments=arguments,
                        message_id=self._get_next_id(),
                        timeout=timeout_sec,
                    )
                elif method == "resources/read":
                    mcp_resp = client.inspect_resource_read(
                        uri=tool_name,
                        message_id=self._get_next_id(),
                        timeout=timeout_sec,
                    )
                else:
                    # prompts/get or other: build MCPMessage and inspect
                    params = {"name": tool_name, "arguments": arguments or {}}
                    msg = MCPMessage(
                        jsonrpc="2.0",
                        method=method,
                        params=params,
                        id=self._get_next_id(),
                    )
                    mcp_resp = client.inspect(msg, timeout=timeout_sec)
                return _mcp_inspect_response_to_decision(mcp_resp)
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
        
        return self._handle_error(last_error, tool_name, context="inspect_request")  # type: ignore
    
    def inspect_response(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Any,
        metadata: Dict[str, Any],
        method: str = "tools/call",
    ) -> Decision:
        """
        Inspect an MCP response after execution (sync).
        
        Sends the response to Cisco AI Defense MCP Inspection API for
        security analysis after execution.
        
        Args:
            tool_name: Name of the tool/prompt/resource that was accessed
            arguments: Arguments that were passed to the operation
            result: The result returned by the operation
            metadata: Additional metadata about the request (not sent to API)
            method: MCP method (tools/call, prompts/get, resources/read)
            
        Returns:
            Decision indicating whether to allow or block the response
            
        Raises:
            SecurityPolicyError: If fail_open=False and API is unreachable
        """
        if not self.endpoint or not self.api_key:
            logger.debug(f"MCP response intercepted: {method}={tool_name}, allowing by default (no API configured)")
            return Decision.allow()
        
        logger.debug(f"MCP inspection response: {method}={tool_name}")
        result_data = _result_to_content_dict(result)
        params = _request_params_for_method(method, tool_name, arguments)
        last_error: Optional[Exception] = None
        timeout_sec = (max(1, int(self.timeout_ms / 1000)) if self.timeout_ms is not None else None)
        
        for attempt in range(self.retry_total):
            try:
                client = self._get_mcp_client()
                mcp_resp = client.inspect_response(
                    result_data=result_data,
                    method=method,
                    params=params,
                    message_id=self._get_next_id(),
                    timeout=timeout_sec,
                )
                return _mcp_inspect_response_to_decision(mcp_resp)
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
        
        return self._handle_error(last_error, tool_name, context="inspect_response")  # type: ignore
    
    async def ainspect_request(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        metadata: Dict[str, Any],
        method: str = "tools/call",
    ) -> Decision:
        """Inspect an MCP request before execution (async). Delegates to sync inspect_request."""
        import asyncio
        if not self.endpoint or not self.api_key:
            logger.debug(f"MCP request intercepted: {method}={tool_name}, allowing by default (no API configured)")
            return Decision.allow()
        return await asyncio.to_thread(
            self.inspect_request,
            tool_name,
            arguments,
            metadata or {},
            method,
        )
    
    async def ainspect_response(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Any,
        metadata: Dict[str, Any],
        method: str = "tools/call",
    ) -> Decision:
        """Inspect an MCP response after execution (async). Delegates to sync inspect_response."""
        import asyncio
        if not self.endpoint or not self.api_key:
            logger.debug(f"MCP response intercepted: {method}={tool_name}, allowing by default (no API configured)")
            return Decision.allow()
        return await asyncio.to_thread(
            self.inspect_response,
            tool_name,
            arguments,
            result,
            metadata or {},
            method,
        )
    
    def close(self) -> None:
        """Release the MCPInspectionClient so it can be garbage collected."""
        with self._mcp_client_lock:
            self._mcp_client = None
    
    async def aclose(self) -> None:
        """Release the MCPInspectionClient (same as close; client is sync)."""
        self.close()
