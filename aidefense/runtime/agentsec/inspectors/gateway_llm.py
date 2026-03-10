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

"""Gateway client for Cisco AI Defense Gateway mode.

This module provides HTTP client functionality for routing LLM and MCP calls
through the Cisco AI Defense Gateway instead of using the inspection APIs.

In Gateway mode:
- LLM calls are redirected to the gateway URL, which handles inspection and proxying
- The gateway uses `api-key` header (not `X-Cisco-AI-Defense-API-Key`)
- Request body format is standard OpenAI-compatible format
"""

import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from ..decision import Decision
from ..exceptions import SecurityPolicyError

logger = logging.getLogger("aidefense.runtime.agentsec.inspectors.gateway")


class GatewayClient:
    """
    HTTP client for Cisco AI Defense Gateway.
    
    This client routes LLM/MCP calls through the AI Defense Gateway,
    which handles inspection internally and proxies to the actual provider.
    
    The Gateway uses a different authentication header format than the
    inspection API: `api-key: {key}` instead of `X-Cisco-AI-Defense-API-Key`.
    
    .. todo::
        The individual LLM patchers (openai.py, bedrock.py, etc.) currently
        create raw ``httpx.Client`` / ``httpx.AsyncClient`` instances per
        gateway request instead of delegating to this class.  This duplicates
        retry, backoff, and error-handling logic and creates a new connection
        pool on every call.  Refactoring patchers to use ``GatewayClient``
        would improve performance (connection reuse) and reduce code
        duplication across all 8 patchers.
    
    Attributes:
        gateway_url: Full gateway URL (user-provided, includes tenant-id, connection-id, etc.)
        api_key: API key for gateway authentication
        timeout_ms: Request timeout in milliseconds
        retry_attempts: Number of retry attempts (default 1 = no retry)
        retry_backoff: Exponential backoff factor in seconds (default 0.5)
        retry_status_codes: HTTP status codes to retry on
        fail_open: Whether to allow requests when gateway is unreachable
    """
    
    # Maximum backoff delay to prevent runaway waits
    MAX_BACKOFF_DELAY = 30.0
    
    # Default retryable status codes (server errors and rate limiting)
    DEFAULT_RETRY_STATUS_CODES = [429, 500, 502, 503, 504]
    
    def __init__(
        self,
        gateway_url: str,
        api_key: str,
        timeout_ms: int = 30000,
        retry_attempts: int = 1,
        retry_backoff: float = 0.5,
        retry_status_codes: Optional[List[int]] = None,
        fail_open: bool = True,
    ):
        """
        Initialize the Gateway Client.
        
        Args:
            gateway_url: Full gateway URL (user provides complete URL)
            api_key: API key for gateway authentication (used in `api-key` header)
            timeout_ms: Request timeout in milliseconds (default 30000 for LLM calls)
            retry_attempts: Number of attempts (default 1, no retry)
            retry_backoff: Exponential backoff factor in seconds (default 0.5)
            retry_status_codes: HTTP status codes to retry on (default [429, 500, 502, 503, 504])
            fail_open: Whether to allow requests when gateway is unreachable (default True)
        """
        self.gateway_url = gateway_url
        self.api_key = api_key
        self.timeout_ms = timeout_ms
        self.retry_attempts = max(1, retry_attempts)
        self.retry_backoff = max(0.0, retry_backoff)
        self.retry_status_codes = retry_status_codes or self.DEFAULT_RETRY_STATUS_CODES
        self.fail_open = fail_open
        
        # Lazy initialization for HTTP client (created on first use)
        self._sync_client: Optional[httpx.Client] = None
    
    def _get_sync_client(self) -> httpx.Client:
        """Get or create the sync HTTP client (lazy initialization)."""
        if self._sync_client is None:
            timeout = httpx.Timeout(self.timeout_ms / 1000.0)
            self._sync_client = httpx.Client(timeout=timeout, http2=False)
        return self._sync_client
    
    def _build_headers(self, extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        Build headers for gateway request.
        
        Gateway uses `api-key` header format (NOT `X-Cisco-AI-Defense-API-Key`).
        
        Args:
            extra_headers: Additional headers to include
            
        Returns:
            Headers dict for the request
        """
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)
        return headers
    
    def _get_backoff_delay(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay for retry attempts.
        
        Uses exponential backoff: delay = backoff_factor * (2 ** attempt)
        Capped at MAX_BACKOFF_DELAY to prevent runaway waits.
        
        Args:
            attempt: Current attempt number (0-indexed)
            
        Returns:
            Delay in seconds before next retry
        """
        if self.retry_backoff <= 0:
            return 0
        
        delay = self.retry_backoff * (2 ** attempt)
        return min(delay, self.MAX_BACKOFF_DELAY)
    
    def _should_retry(self, error: Exception) -> bool:
        """
        Determine if an error is retryable.
        
        Args:
            error: The exception that occurred
            
        Returns:
            True if the error should trigger a retry, False otherwise
        """
        import json
        
        # Never retry on JSON decode errors (response is malformed, not transient)
        if isinstance(error, json.JSONDecodeError):
            logger.warning(f"JSON decode error (not retryable): {error}")
            return False
        
        # Timeout errors are retryable
        if isinstance(error, httpx.TimeoutException):
            return True
        
        # Connection errors are retryable
        if isinstance(error, httpx.ConnectError):
            return True
        
        # HTTP status errors - check if status code is in retry list
        if isinstance(error, httpx.HTTPStatusError):
            return error.response.status_code in self.retry_status_codes
        
        # Unknown errors are not retryable by default
        return False
    
    def _handle_error(
        self,
        error: Exception,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Handle gateway errors based on fail_open config.
        
        Args:
            error: The exception that occurred
            context: Optional context string for logging
            
        Returns:
            Empty dict if fail_open=True (caller should handle gracefully)
            
        Raises:
            SecurityPolicyError: If fail_open=False
        """
        error_type = type(error).__name__
        error_msg = str(error)
        
        ctx_str = f" [{context}]" if context else ""
        logger.warning(f"Gateway error{ctx_str}: {error_type}: {error_msg}")
        logger.debug(f"Gateway error details: {error}", exc_info=True)
        
        if self.fail_open:
            logger.warning("fail_open=True, caller should handle gateway failure gracefully")
            return {"error": f"Gateway error ({error_type})", "fail_open": True}
        else:
            logger.error("fail_open=False, blocking request due to gateway error")
            decision = Decision.block(reasons=[f"Gateway error: {error_type}: {error_msg}"])
            raise SecurityPolicyError(decision, f"Gateway unavailable and fail_open=False: {error_msg}")
    
    def call(
        self,
        request_body: Dict[str, Any],
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Make a synchronous call to the gateway.
        
        Args:
            request_body: Request payload (OpenAI-compatible format)
            extra_headers: Additional headers to include
            
        Returns:
            Response from gateway (OpenAI-compatible format)
            
        Raises:
            SecurityPolicyError: If fail_open=False and gateway is unreachable
        """
        headers = self._build_headers(extra_headers)
        
        logger.debug(f"Gateway request to {self.gateway_url}")
        logger.debug(f"Gateway request payload keys: {list(request_body.keys()) if isinstance(request_body, dict) else type(request_body).__name__}")
        
        last_error: Optional[Exception] = None
        
        client = self._get_sync_client()
        for attempt in range(self.retry_attempts):
            try:
                response = client.post(
                    self.gateway_url,
                    json=request_body,
                    headers=headers,
                )
                response.raise_for_status()
                response_json = response.json()
                logger.debug(f"Gateway response: status={response.status_code}, keys={list(response_json.keys()) if isinstance(response_json, dict) else type(response_json).__name__}")
                return response_json
            except Exception as e:
                last_error = e
                logger.debug(f"Gateway attempt {attempt + 1}/{self.retry_attempts} failed: {e}")
                
                # Check if we should retry
                is_last_attempt = attempt >= self.retry_attempts - 1
                if is_last_attempt or not self._should_retry(e):
                    break
                
                # Apply exponential backoff before next retry
                delay = self._get_backoff_delay(attempt)
                if delay > 0:
                    logger.debug(f"Retrying in {delay:.2f}s...")
                    time.sleep(delay)
        
        return self._handle_error(last_error, context="gateway_call")  # type: ignore
    
    async def acall(
        self,
        request_body: Dict[str, Any],
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Make an asynchronous call to the gateway.
        
        Args:
            request_body: Request payload (OpenAI-compatible format)
            extra_headers: Additional headers to include
            
        Returns:
            Response from gateway (OpenAI-compatible format)
            
        Raises:
            SecurityPolicyError: If fail_open=False and gateway is unreachable
        """
        headers = self._build_headers(extra_headers)
        
        logger.debug(f"Gateway async request to {self.gateway_url}")
        logger.debug(f"Gateway async request payload keys: {list(request_body.keys()) if isinstance(request_body, dict) else type(request_body).__name__}")
        
        last_error: Optional[Exception] = None
        
        import asyncio
        
        # Create fresh async client per request to avoid event loop issues
        timeout = httpx.Timeout(self.timeout_ms / 1000.0)
        async with httpx.AsyncClient(timeout=timeout, http2=False) as client:
            for attempt in range(self.retry_attempts):
                try:
                    response = await client.post(
                        self.gateway_url,
                        json=request_body,
                        headers=headers,
                    )
                    response.raise_for_status()
                    response_json = response.json()
                    logger.debug(f"Gateway async response: status={response.status_code}, keys={list(response_json.keys()) if isinstance(response_json, dict) else type(response_json).__name__}")
                    return response_json
                except Exception as e:
                    last_error = e
                    logger.debug(f"Gateway async attempt {attempt + 1}/{self.retry_attempts} failed: {e}")
                    
                    # Check if we should retry
                    is_last_attempt = attempt >= self.retry_attempts - 1
                    if is_last_attempt or not self._should_retry(e):
                        break
                    
                    # Apply exponential backoff before next retry (async sleep)
                    delay = self._get_backoff_delay(attempt)
                    if delay > 0:
                        logger.debug(f"Retrying in {delay:.2f}s...")
                        await asyncio.sleep(delay)
        
        return self._handle_error(last_error, context="gateway_acall")  # type: ignore
    
    def call_streaming(
        self,
        request_body: Dict[str, Any],
        extra_headers: Optional[Dict[str, str]] = None,
    ):
        """
        Make a synchronous streaming call to the gateway.
        
        Note: Streaming calls do not support retry as streams cannot be resumed.
        
        Args:
            request_body: Request payload (should include stream=True)
            extra_headers: Additional headers to include
            
        Yields:
            Response chunks from gateway (SSE format)
            
        Raises:
            SecurityPolicyError: If fail_open=False and gateway is unreachable
        """
        headers = self._build_headers(extra_headers)
        
        logger.debug(f"Gateway streaming request to {self.gateway_url}")
        
        client = self._get_sync_client()
        try:
            with client.stream(
                "POST",
                self.gateway_url,
                json=request_body,
                headers=headers,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        yield line
        except Exception as e:
            # Handle error - raises SecurityPolicyError if fail_open=False
            self._handle_error(e, context="gateway_streaming")
            # If we reach here, fail_open=True - caller should handle empty response
    
    async def acall_streaming(
        self,
        request_body: Dict[str, Any],
        extra_headers: Optional[Dict[str, str]] = None,
    ):
        """
        Make an asynchronous streaming call to the gateway.
        
        Note: Streaming calls do not support retry as streams cannot be resumed.
        
        Args:
            request_body: Request payload (should include stream=True)
            extra_headers: Additional headers to include
            
        Yields:
            Response chunks from gateway (SSE format)
            
        Raises:
            SecurityPolicyError: If fail_open=False and gateway is unreachable
        """
        headers = self._build_headers(extra_headers)
        
        logger.debug(f"Gateway async streaming request to {self.gateway_url}")
        
        timeout = httpx.Timeout(self.timeout_ms / 1000.0)
        try:
            async with httpx.AsyncClient(timeout=timeout, http2=False) as client:
                async with client.stream(
                    "POST",
                    self.gateway_url,
                    json=request_body,
                    headers=headers,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line:
                            yield line
        except Exception as e:
            # Handle error - raises SecurityPolicyError if fail_open=False
            self._handle_error(e, context="gateway_async_streaming")
            # If we reach here, fail_open=True - caller should handle empty response
    
    def close(self) -> None:
        """Close the HTTP client."""
        if self._sync_client is not None:
            self._sync_client.close()
            self._sync_client = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()
