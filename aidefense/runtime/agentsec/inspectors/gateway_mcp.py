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

"""MCP Gateway inspector for Cisco AI Defense Gateway mode.

This module provides an inspector for MCP Gateway mode that works by
redirecting MCP connections to the AI Defense Gateway URL.

In MCP Gateway mode:
- MCP connections are redirected to the gateway URL at the transport level
- The MCP client library connects to the gateway using MCP protocol (not HTTP POST)
- Gateway acts as an MCP server that proxies to the actual MCP server after inspection
- Uses `api-key` header for authentication

The inspector methods (inspect_request, inspect_response) are pass-through
since the gateway handles all inspection internally.
"""

import logging
from typing import Any, Dict, Optional

from ..decision import Decision

logger = logging.getLogger("aidefense.runtime.agentsec.inspectors.gateway_mcp")


class MCPGatewayInspector:
    """
    Inspector for MCP Gateway mode.
    
    Unlike MCPInspector (API mode) which makes HTTP calls to inspect each tool call,
    MCPGatewayInspector redirects the MCP transport URL to the gateway. The gateway
    then handles inspection internally using MCP protocol.
    
    The inspect_request and inspect_response methods are pass-through since
    inspection happens at the transport level (gateway handles it).
    
    Attributes:
        gateway_url: Full gateway MCP URL for transport redirection
        api_key: Optional API key for gateway authentication
        fail_open: Whether to allow connections when gateway is unavailable
    """
    
    def __init__(
        self,
        gateway_url: Optional[str] = None,
        api_key: Optional[str] = None,
        fail_open: bool = True,
    ):
        """
        Initialize MCP Gateway Inspector.
        
        Args:
            gateway_url: Full gateway URL for MCP connections
            api_key: Optional API key for gateway authentication (used in `api-key` header)
            fail_open: Whether to allow connections when gateway fails (default True)
        """
        self.gateway_url = gateway_url
        self.api_key = api_key
        self.fail_open = fail_open
        
        if gateway_url:
            logger.debug(f"MCPGatewayInspector initialized with URL: {gateway_url}")
        else:
            logger.debug("MCPGatewayInspector initialized without gateway URL")
    
    @property
    def is_configured(self) -> bool:
        """Check if gateway is properly configured."""
        return bool(self.gateway_url)
    
    def get_redirect_url(self) -> Optional[str]:
        """
        Get the gateway URL to redirect MCP connections to.
        
        Returns:
            The gateway URL, or None if not configured
        """
        return self.gateway_url
    
    def get_headers(self) -> Dict[str, str]:
        """
        Get headers to add to MCP transport connections.
        
        Returns:
            Headers dict with api-key if configured, empty dict otherwise
        """
        if self.api_key:
            return {"api-key": self.api_key}
        return {}
    
    def inspect_request(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Decision:
        """
        Inspect an MCP tool request (pass-through in gateway mode).
        
        In gateway mode, inspection happens at the transport level when
        the MCP client connects to the gateway. This method is a pass-through.
        
        Args:
            tool_name: Name of the MCP tool being called
            arguments: Arguments passed to the tool
            metadata: Optional metadata for context
            
        Returns:
            Decision.allow() - gateway handles actual inspection
        """
        logger.debug(f"[MCP GATEWAY] inspect_request({tool_name}) - pass-through (gateway handles)")
        return Decision.allow(reasons=["Gateway handles inspection at transport level"])
    
    def inspect_response(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Decision:
        """
        Inspect an MCP tool response (pass-through in gateway mode).
        
        In gateway mode, inspection happens at the transport level.
        This method is a pass-through.
        
        Args:
            tool_name: Name of the MCP tool that was called
            arguments: Arguments that were passed to the tool
            result: Result returned by the tool
            metadata: Optional metadata for context
            
        Returns:
            Decision.allow() - gateway handles actual inspection
        """
        logger.debug(f"[MCP GATEWAY] inspect_response({tool_name}) - pass-through (gateway handles)")
        return Decision.allow(reasons=["Gateway handles inspection at transport level"])
    
    async def ainspect_request(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Decision:
        """Async version of inspect_request (pass-through in gateway mode)."""
        return self.inspect_request(tool_name, arguments, metadata)
    
    async def ainspect_response(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Decision:
        """Async version of inspect_response (pass-through in gateway mode)."""
        return self.inspect_response(tool_name, arguments, result, metadata)
    
    def __repr__(self) -> str:
        return f"MCPGatewayInspector(gateway_url={self.gateway_url!r}, api_key={'*****' if self.api_key else None})"
