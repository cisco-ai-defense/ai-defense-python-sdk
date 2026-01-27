"""MCP Inspector for tool, prompt, and resource inspection using Cisco AI Defense MCP Inspection API."""

import json
import logging
import os
from typing import Any, Dict, Optional

import httpx

from ..decision import Decision
from ..exceptions import SecurityPolicyError

logger = logging.getLogger("aidefense.runtime.agentsec.inspectors.mcp")


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
        retry_attempts: Number of retry attempts (default 1 = no retry)
        fail_open: Whether to allow operations when API is unreachable
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        timeout_ms: int = 1000,
        retry_attempts: int = 1,
        fail_open: bool = True,
    ) -> None:
        """
        Initialize the MCP Inspector.
        
        Args:
            api_key: API key for Cisco AI Defense MCP inspection.
                     Falls back to AI_DEFENSE_API_MODE_MCP_API_KEY, then AI_DEFENSE_API_MODE_LLM_API_KEY env vars.
            endpoint: Base URL for the AI Defense MCP API.
                      Falls back to AI_DEFENSE_API_MODE_MCP_ENDPOINT, then AI_DEFENSE_API_MODE_LLM_ENDPOINT env vars.
            timeout_ms: Request timeout in milliseconds (default 1000)
            retry_attempts: Number of attempts (default 1, no retry)
            fail_open: If True, allow tool calls on API errors (default True)
        """
        from .. import _state
        
        # API key: explicit > state > MCP-specific env > general env
        self.api_key = (
            api_key 
            or _state.get_api_mode_mcp_api_key() 
            or os.environ.get("AI_DEFENSE_API_MODE_MCP_API_KEY") 
            or os.environ.get("AI_DEFENSE_API_MODE_LLM_API_KEY")
        )
        
        # Endpoint: explicit > state > MCP-specific env > general env
        raw_endpoint = (
            endpoint 
            or _state.get_api_mode_mcp_endpoint() 
            or os.environ.get("AI_DEFENSE_API_MODE_MCP_ENDPOINT") 
            or os.environ.get("AI_DEFENSE_API_MODE_LLM_ENDPOINT")
        )
        
        # Store base endpoint (strip any trailing /api/v1/inspect/mcp path)
        if raw_endpoint:
            self.endpoint = raw_endpoint.rstrip("/").removesuffix("/api/v1/inspect/mcp").removesuffix("/api")
        else:
            self.endpoint = None
        
        self.timeout_ms = timeout_ms
        self.retry_attempts = max(1, retry_attempts)
        self.fail_open = fail_open
        
        # Counter for JSON-RPC message IDs
        self._request_id_counter = 0
        
        # Create HTTP client (use HTTP/1.1 - AI Defense API doesn't support HTTP/2)
        timeout = httpx.Timeout(timeout_ms / 1000.0)
        self._sync_client = httpx.Client(timeout=timeout, http2=False)
    
    def _get_next_id(self) -> int:
        """Get the next request ID for JSON-RPC messages."""
        self._request_id_counter += 1
        return self._request_id_counter
    
    def _build_request_message(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        method: str = "tools/call",
    ) -> Dict[str, Any]:
        """
        Build a JSON-RPC 2.0 request message for MCP inspection.
        
        Args:
            tool_name: Name of the tool/prompt/resource being accessed
            arguments: Arguments passed to the operation
            method: MCP method (tools/call, prompts/get, resources/read)
            
        Returns:
            JSON-RPC 2.0 request message dict
        """
        if method == "prompts/get":
            return {
                "jsonrpc": "2.0",
                "method": method,
                "params": {
                    "name": tool_name,
                    "arguments": arguments,
                },
                "id": self._get_next_id(),
            }
        elif method == "resources/read":
            return {
                "jsonrpc": "2.0",
                "method": method,
                "params": {
                    "uri": tool_name,  # For resources, the "name" is the URI
                },
                "id": self._get_next_id(),
            }
        else:
            # Default: tools/call
            return {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments,
                },
                "id": self._get_next_id(),
            }
    
    def _build_response_message(
        self,
        result: Any,
    ) -> Dict[str, Any]:
        """
        Build a JSON-RPC 2.0 response message for MCP tool response inspection.
        
        Args:
            result: The result returned by the tool
            
        Returns:
            JSON-RPC 2.0 response message dict
        """
        # Convert result to text content format expected by MCP
        if isinstance(result, str):
            text_content = result
        elif isinstance(result, (dict, list)):
            text_content = json.dumps(result)
        else:
            text_content = str(result)
        
        return {
            "jsonrpc": "2.0",
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": text_content,
                    }
                ]
            },
            "id": self._get_next_id(),
        }
    
    def _parse_mcp_response(self, response_data: Dict[str, Any]) -> Decision:
        """
        Parse the MCP Inspection API response into a Decision.
        
        The API returns a JSON-RPC 2.0 response with result containing:
        - is_safe: boolean (primary decision flag)
        - action: "Allow" or "Block"
        - severity: NONE_SEVERITY, LOW, MEDIUM, HIGH, CRITICAL
        - rules: list of rules that triggered
        - classifications: list of violation types
        - explanation: human-readable explanation
        - event_id: unique inspection event ID
        
        Args:
            response_data: JSON response from the API
            
        Returns:
            Decision based on API response
        """
        # Extract the result object from JSON-RPC response
        result = response_data.get("result", response_data)
        
        # Primary decision: action field (Allow/Block)
        action = result.get("action", "Allow")
        is_safe = result.get("is_safe", True)
        
        # Build reasons from rules that triggered
        reasons = []
        for rule in result.get("rules", []):
            classification = rule.get("classification")
            if classification and classification != "NONE_VIOLATION":
                rule_name = rule.get("rule_name", "Unknown")
                reasons.append(f"{rule_name}: {classification}")
        
        # If no specific rules triggered but is_safe is false, add generic reason
        if not reasons and not is_safe:
            severity = result.get("severity", "UNKNOWN")
            attack_technique = result.get("attack_technique", "")
            explanation = result.get("explanation", "")
            if explanation:
                reasons.append(explanation)
            elif attack_technique and attack_technique != "NONE_ATTACK_TECHNIQUE":
                reasons.append(f"Attack technique: {attack_technique}")
            else:
                reasons.append(f"Unsafe content detected (severity: {severity})")
        
        # Log block decisions for debugging
        if action == "Block" or not is_safe:
            logger.debug(f"MCP Inspection BLOCK response: {response_data}")
        
        # Decision based on action OR is_safe
        if action == "Block" or not is_safe:
            return Decision.block(reasons=reasons, raw_response=response_data)
        else:
            return Decision.allow(reasons=reasons, raw_response=response_data)
    
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
            Decision.allow() if fail_open, raises SecurityPolicyError otherwise
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
            decision = Decision.block(reasons=[f"MCP inspection error: {error_type}: {error_msg}"])
            raise SecurityPolicyError(decision, f"MCP inspection failed and fail_open=False: {error_msg}")
    
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
        # If no API configured, allow by default (backward compatible)
        if not self.endpoint or not self.api_key:
            logger.debug(f"MCP request intercepted: {method}={tool_name}, allowing by default (no API configured)")
            return Decision.allow()
        
        # Build JSON-RPC request message
        mcp_message = self._build_request_message(tool_name, arguments, method)
        logger.debug(f"MCP inspection request: {method}={tool_name}")
        
        headers = {
            "X-Cisco-AI-Defense-API-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        last_error: Optional[Exception] = None
        
        for attempt in range(self.retry_attempts):
            try:
                response = self._sync_client.post(
                    f"{self.endpoint}/api/v1/inspect/mcp",
                    json=mcp_message,
                    headers=headers,
                )
                response.raise_for_status()
                return self._parse_mcp_response(response.json())
            except Exception as e:
                last_error = e
                logger.debug(f"Attempt {attempt + 1}/{self.retry_attempts} failed: {e}")
        
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
        # If no API configured, allow by default (backward compatible)
        if not self.endpoint or not self.api_key:
            logger.debug(f"MCP response intercepted: {method}={tool_name}, allowing by default (no API configured)")
            return Decision.allow()
        
        # Build JSON-RPC response message
        mcp_message = self._build_response_message(result)
        logger.debug(f"MCP inspection response: {method}={tool_name}")
        
        headers = {
            "X-Cisco-AI-Defense-API-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        last_error: Optional[Exception] = None
        
        for attempt in range(self.retry_attempts):
            try:
                response = self._sync_client.post(
                    f"{self.endpoint}/api/v1/inspect/mcp",
                    json=mcp_message,
                    headers=headers,
                )
                response.raise_for_status()
                return self._parse_mcp_response(response.json())
            except Exception as e:
                last_error = e
                logger.debug(f"Attempt {attempt + 1}/{self.retry_attempts} failed: {e}")
        
        return self._handle_error(last_error, tool_name, context="inspect_response")  # type: ignore
    
    async def ainspect_request(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        metadata: Dict[str, Any],
        method: str = "tools/call",
    ) -> Decision:
        """
        Inspect an MCP request before execution (async).
        
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
        # If no API configured, allow by default (backward compatible)
        if not self.endpoint or not self.api_key:
            logger.debug(f"MCP request intercepted: {method}={tool_name}, allowing by default (no API configured)")
            return Decision.allow()
        
        # Build JSON-RPC request message
        mcp_message = self._build_request_message(tool_name, arguments, method)
        logger.debug(f"MCP async inspection request: {method}={tool_name}")
        
        headers = {
            "X-Cisco-AI-Defense-API-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        last_error: Optional[Exception] = None
        
        # Create fresh async client per request to avoid event loop issues
        timeout = httpx.Timeout(self.timeout_ms / 1000.0)
        async with httpx.AsyncClient(timeout=timeout, http2=False) as client:
            for attempt in range(self.retry_attempts):
                try:
                    response = await client.post(
                        f"{self.endpoint}/api/v1/inspect/mcp",
                        json=mcp_message,
                        headers=headers,
                    )
                    response.raise_for_status()
                    return self._parse_mcp_response(response.json())
                except Exception as e:
                    last_error = e
                    logger.debug(f"Attempt {attempt + 1}/{self.retry_attempts} failed: {e}")
        
        return self._handle_error(last_error, tool_name, context="ainspect_request")  # type: ignore
    
    async def ainspect_response(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Any,
        metadata: Dict[str, Any],
        method: str = "tools/call",
    ) -> Decision:
        """
        Inspect an MCP response after execution (async).
        
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
        # If no API configured, allow by default (backward compatible)
        if not self.endpoint or not self.api_key:
            logger.debug(f"MCP response intercepted: {method}={tool_name}, allowing by default (no API configured)")
            return Decision.allow()
        
        # Build JSON-RPC response message
        mcp_message = self._build_response_message(result)
        logger.debug(f"MCP async inspection response: {method}={tool_name}")
        
        headers = {
            "X-Cisco-AI-Defense-API-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        last_error: Optional[Exception] = None
        
        # Create fresh async client per request to avoid event loop issues
        timeout = httpx.Timeout(self.timeout_ms / 1000.0)
        async with httpx.AsyncClient(timeout=timeout, http2=False) as client:
            for attempt in range(self.retry_attempts):
                try:
                    response = await client.post(
                        f"{self.endpoint}/api/v1/inspect/mcp",
                        json=mcp_message,
                        headers=headers,
                    )
                    response.raise_for_status()
                    return self._parse_mcp_response(response.json())
                except Exception as e:
                    last_error = e
                    logger.debug(f"Attempt {attempt + 1}/{self.retry_attempts} failed: {e}")
        
        return self._handle_error(last_error, tool_name, context="ainspect_response")  # type: ignore
    
    def close(self) -> None:
        """Close HTTP client."""
        self._sync_client.close()
    
    async def aclose(self) -> None:
        """Close resources (no-op as async client is created per request)."""
        pass
