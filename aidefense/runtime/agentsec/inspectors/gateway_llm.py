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
from typing import Any, Dict, Optional

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
    
    Attributes:
        gateway_url: Full gateway URL (user-provided, includes tenant-id, connection-id, etc.)
        api_key: API key for gateway authentication
        timeout_ms: Request timeout in milliseconds
        retry_attempts: Number of retry attempts (default 1 = no retry)
        fail_open: Whether to allow requests when gateway is unreachable
    """
    
    def __init__(
        self,
        gateway_url: str,
        api_key: str,
        timeout_ms: int = 30000,
        retry_attempts: int = 1,
        fail_open: bool = True,
    ):
        """
        Initialize the Gateway Client.
        
        Args:
            gateway_url: Full gateway URL (user provides complete URL)
            api_key: API key for gateway authentication (used in `api-key` header)
            timeout_ms: Request timeout in milliseconds (default 30000 for LLM calls)
            retry_attempts: Number of attempts (default 1, no retry)
            fail_open: Whether to allow requests when gateway is unreachable (default True)
        """
        self.gateway_url = gateway_url
        self.api_key = api_key
        self.timeout_ms = timeout_ms
        self.retry_attempts = max(1, retry_attempts)
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
        logger.debug(f"Gateway request payload: {request_body}")
        
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
                logger.debug(f"Gateway response: {response_json}")
                return response_json
            except Exception as e:
                last_error = e
                logger.debug(f"Gateway attempt {attempt + 1}/{self.retry_attempts} failed: {e}")
        
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
        logger.debug(f"Gateway async request payload: {request_body}")
        
        last_error: Optional[Exception] = None
        
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
                    logger.debug(f"Gateway async response: {response_json}")
                    return response_json
                except Exception as e:
                    last_error = e
                    logger.debug(f"Gateway async attempt {attempt + 1}/{self.retry_attempts} failed: {e}")
        
        return self._handle_error(last_error, context="gateway_acall")  # type: ignore
    
    def call_streaming(
        self,
        request_body: Dict[str, Any],
        extra_headers: Optional[Dict[str, str]] = None,
    ):
        """
        Make a synchronous streaming call to the gateway.
        
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
            error_result = self._handle_error(e, context="gateway_streaming")
            if error_result:  # fail_open=True case
                return
    
    async def acall_streaming(
        self,
        request_body: Dict[str, Any],
        extra_headers: Optional[Dict[str, str]] = None,
    ):
        """
        Make an asynchronous streaming call to the gateway.
        
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
            error_result = self._handle_error(e, context="gateway_async_streaming")
            if error_result:  # fail_open=True case
                return
    
    def close(self) -> None:
        """Close the HTTP client."""
        if self._sync_client is not None:
            self._sync_client.close()
            self._sync_client = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()
