"""MCP client autopatching.

This module provides automatic inspection for MCP (Model Context Protocol) tool calls.

Supports two integration modes:
- "api" (default): Use MCPInspector to inspect tool calls via AI Defense API
- "gateway": Use MCPGatewayInspector to redirect connections through AI Defense Gateway

In gateway mode, the MCP client connects directly to the gateway URL using MCP protocol.
The gateway acts as an MCP server that proxies to the actual MCP server after inspection.
"""

import logging
import threading
from typing import Any, Dict, Optional, Union

import wrapt

from .. import _state
from .._context import get_inspection_context, set_inspection_context
from ..decision import Decision
from ..exceptions import SecurityPolicyError
from ..inspectors.api_mcp import MCPInspector
from ..inspectors.gateway_mcp import MCPGatewayInspector
from . import is_patched, mark_patched
from ._base import safe_import

logger = logging.getLogger("aidefense.runtime.agentsec.patchers.mcp")

# Global inspector instances with thread-safe initialization
_api_inspector: Optional[MCPInspector] = None
_gateway_inspector: Optional[MCPGatewayInspector] = None
_inspector_lock = threading.Lock()

# Track gateway mode state for URL redirection (log only once)
_gateway_mode_logged: bool = False


def _get_api_inspector() -> MCPInspector:
    """Get or create the MCPInspector instance for API mode (thread-safe)."""
    global _api_inspector
    if _api_inspector is None:
        with _inspector_lock:
            if _api_inspector is None:
                if not _state.is_initialized():
                    logger.warning("agentsec.protect() not called, using default config")
                _api_inspector = MCPInspector(
                    fail_open=_state.get_api_mode_fail_open_mcp(),
                )
    return _api_inspector


def _get_gateway_inspector() -> MCPGatewayInspector:
    """Get or create the MCPGatewayInspector instance for gateway mode (thread-safe)."""
    global _gateway_inspector
    if _gateway_inspector is None:
        with _inspector_lock:
            if _gateway_inspector is None:
                gateway_url = _state.get_mcp_gateway_url()
                gateway_api_key = _state.get_mcp_gateway_api_key()
                
                _gateway_inspector = MCPGatewayInspector(
                    gateway_url=gateway_url,
                    api_key=gateway_api_key,
                    fail_open=_state.get_gateway_mode_fail_open_mcp(),
                )
    return _gateway_inspector


def _get_inspector() -> Union[MCPInspector, MCPGatewayInspector]:
    """Get the appropriate inspector based on integration mode."""
    if _should_use_gateway():
        return _get_gateway_inspector()
    return _get_api_inspector()


def _is_gateway_mode() -> bool:
    """Check if MCP integration mode is 'gateway'."""
    return _state.get_mcp_integration_mode() == "gateway"


def _get_gateway_mode_setting() -> str:
    """Get the gateway mode setting (off/on)."""
    return _state.get_mcp_gateway_mode()


def _should_use_gateway() -> bool:
    """Check if we should use gateway mode for MCP (not skipped)."""
    from .._context import is_mcp_skip_active
    if is_mcp_skip_active():
        return False
    if not _is_gateway_mode():
        return False
    if _get_gateway_mode_setting() == "off":
        return False
    gateway_inspector = _get_gateway_inspector()
    return gateway_inspector.is_configured


def _should_inspect() -> bool:
    """Check if we should inspect (applies to API mode, and not skipped)."""
    from .._context import is_mcp_skip_active
    if is_mcp_skip_active():
        return False
    mode = _state.get_mcp_mode()
    if mode == "off":
        return False
    return True


def _enforce_decision(decision: Decision) -> None:
    """Enforce a decision if in enforce mode."""
    mode = _state.get_mcp_mode()
    if mode == "on_enforce" and decision.action == "block":
        raise SecurityPolicyError(decision)


def _wrap_streamablehttp_client(wrapped, instance, args, kwargs):
    """
    Wrapper for streamablehttp_client to redirect URL to gateway in gateway mode.
    
    In gateway mode, this intercepts the MCP transport creation and redirects
    the connection to the AI Defense Gateway URL. The gateway then handles
    inspection and proxies to the actual MCP server.
    """
    global _gateway_mode_logged
    
    if _should_use_gateway():
        gateway_inspector = _get_gateway_inspector()
        redirect_url = gateway_inspector.get_redirect_url()
        
        if redirect_url:
            # Get the original URL for logging
            original_url = kwargs.get('url') or (args[0] if args else None)
            
            if not _gateway_mode_logged:
                logger.info(f"[MCP GATEWAY] Redirecting MCP connections to gateway")
                logger.debug(f"[MCP GATEWAY] Original URL: {original_url}")
                logger.debug(f"[MCP GATEWAY] Gateway URL: {redirect_url}")
                _gateway_mode_logged = True
            
            # Replace URL with gateway URL
            if 'url' in kwargs:
                kwargs['url'] = redirect_url
            elif args:
                args = (redirect_url,) + args[1:]
            
            # Add gateway headers
            gateway_headers = gateway_inspector.get_headers()
            if gateway_headers:
                headers = kwargs.get('headers', {})
                if headers is None:
                    headers = {}
                headers.update(gateway_headers)
                kwargs['headers'] = headers
    
    return wrapped(*args, **kwargs)


async def _wrap_call_tool(wrapped, instance, args, kwargs):
    """Async wrapper for ClientSession.call_tool.
    
    Routes to appropriate inspector based on integration mode:
    - API mode: MCPInspector (makes API calls for inspection)
    - Gateway mode: MCPGatewayInspector (pass-through, gateway handles inspection)
    """
    # Extract tool info
    tool_name = args[0] if args else kwargs.get("name", "")
    arguments = args[1] if len(args) > 1 else kwargs.get("arguments", {})
    
    integration_mode = _state.get_mcp_integration_mode()
    use_gateway = _should_use_gateway()
    
    # Log the call
    if use_gateway:
        logger.debug(f"")
        logger.debug(f"╔══════════════════════════════════════════════════════════════")
        logger.debug(f"║ [PATCHED] MCP TOOL CALL: {tool_name}")
        logger.debug(f"║ Arguments: {arguments}")
        logger.debug(f"║ Integration: gateway (gateway handles inspection)")
        logger.debug(f"╚══════════════════════════════════════════════════════════════")
    else:
        mode = _state.get_mcp_mode()
        logger.debug(f"")
        logger.debug(f"╔══════════════════════════════════════════════════════════════")
        logger.debug(f"║ [PATCHED] MCP TOOL CALL: {tool_name}")
        logger.debug(f"║ Arguments: {arguments}")
        logger.debug(f"║ MCP Mode: {mode} | Integration: {integration_mode}")
        logger.debug(f"╚══════════════════════════════════════════════════════════════")
    
    # Check if inspection is enabled (API mode only)
    if not use_gateway and not _should_inspect():
        logger.debug(f"[PATCHED CALL] MCP.call_tool({tool_name}) - inspection skipped (mode=off)")
        return await wrapped(*args, **kwargs)
    
    metadata = get_inspection_context().metadata
    inspector = _get_inspector()
    
    # Pre-call inspection
    try:
        logger.debug(f"[PATCHED CALL] MCP.call_tool({tool_name}) - Request inspection")
        decision = await inspector.ainspect_request(tool_name, arguments, metadata)
        logger.debug(f"[PATCHED CALL] MCP.call_tool({tool_name}) - Request decision: {decision.action}")
        set_inspection_context(decision=decision)
        _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as e:
        logger.warning(f"[PATCHED CALL] MCP.call_tool({tool_name}) - Request inspection error: {e}")
        # Use inspector's fail_open setting for consistency
        fail_open = getattr(inspector, 'fail_open', _state.get_api_mode_fail_open_mcp())
        if not fail_open:
            decision = Decision.block(reasons=[f"MCP inspection error: {e}"])
            raise SecurityPolicyError(decision, f"MCP inspection failed: {e}")
        logger.warning(f"fail_open=True, proceeding despite inspection error")
    
    # Call original
    logger.debug(f"[PATCHED CALL] MCP.call_tool({tool_name}) - calling original method")
    result = await wrapped(*args, **kwargs)
    
    # Post-call inspection
    try:
        logger.debug(f"[PATCHED CALL] MCP.call_tool({tool_name}) - Response inspection")
        decision = await inspector.ainspect_response(tool_name, arguments, result, metadata)
        logger.debug(f"[PATCHED CALL] MCP.call_tool({tool_name}) - Response decision: {decision.action}")
        set_inspection_context(decision=decision, done=True)
        _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as e:
        logger.warning(f"[PATCHED CALL] MCP.call_tool({tool_name}) - Response inspection error: {e}")
    
    logger.debug(f"[PATCHED CALL] MCP.call_tool({tool_name}) - complete")
    return result


def patch_mcp() -> bool:
    """
    Patch MCP client for automatic inspection.
    
    Returns:
        True if patching was successful, False otherwise
    """
    if is_patched("mcp"):
        logger.debug("MCP already patched, skipping")
        return True
    
    mcp = safe_import("mcp")
    if mcp is None:
        return False
    
    try:
        # Patch call_tool for inspection
        wrapt.wrap_function_wrapper(
            "mcp.client.session",
            "ClientSession.call_tool",
            _wrap_call_tool,
        )
        
        # Patch streamablehttp_client for gateway URL redirection
        try:
            wrapt.wrap_function_wrapper(
                "mcp.client.streamable_http",
                "streamablehttp_client",
                _wrap_streamablehttp_client,
            )
            logger.debug("MCP streamablehttp_client patched for gateway mode")
        except Exception as e:
            logger.debug(f"Could not patch streamablehttp_client: {e}")
        
        mark_patched("mcp")
        logger.info("MCP client patched successfully")
        return True
    except Exception as e:
        logger.warning(f"Failed to patch MCP: {e}")
        return False
