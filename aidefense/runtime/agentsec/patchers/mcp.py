"""MCP client autopatching.

This module provides automatic inspection for MCP (Model Context Protocol) operations.

Patched methods:
- ClientSession.call_tool(): Tool execution inspection
- ClientSession.get_prompt(): Prompt retrieval inspection  
- ClientSession.read_resource(): Resource access inspection

Supports two integration modes:
- "api" (default): Use MCPInspector to inspect calls via AI Defense API
- "gateway": Use MCPGatewayInspector to redirect connections through AI Defense Gateway

In gateway mode, the MCP client connects directly to the gateway URL using MCP protocol.
The gateway acts as an MCP server that proxies to the actual MCP server after inspection.
"""

import logging
import threading
from typing import Any, Dict, Optional, Union

import httpx
import wrapt

from .. import _state
from ..gateway_settings import GatewaySettings
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
_gateway_pass_through_inspector: Optional[MCPGatewayInspector] = None
_inspector_lock = threading.Lock()

# Track gateway mode state for URL redirection (log only once)
_gateway_mode_logged: bool = False


def _reset_inspector() -> None:
    """Clear cached inspectors so the next access creates fresh ones."""
    global _api_inspector, _gateway_pass_through_inspector
    _api_inspector = None
    _gateway_pass_through_inspector = None


def _get_api_inspector() -> MCPInspector:
    """Get or create the MCPInspector instance for API mode (thread-safe)."""
    global _api_inspector
    if _api_inspector is None:
        with _inspector_lock:
            if _api_inspector is None:
                if not _state.is_initialized():
                    logger.warning("agentsec.protect() not called, using default config")
                _api_inspector = MCPInspector(
                    fail_open=_state.get_api_mcp_fail_open(),
                )
                # Register for cleanup on shutdown
                from ..inspectors import register_inspector_for_cleanup
                register_inspector_for_cleanup(_api_inspector)
    return _api_inspector


def _get_gateway_settings_for_url(original_url: str) -> Optional[GatewaySettings]:
    """Resolve MCP gateway settings for a given MCP server URL.

    Looks up the gateway configuration keyed by the exact MCP server URL.
    Returns None if no gateway is configured for this URL.
    """
    config = _state.get_mcp_gateway_for_url(original_url)
    if config is None:
        return None
    return _state.resolve_mcp_gateway_settings(config)


def _get_gateway_pass_through_inspector() -> MCPGatewayInspector:
    """Get pass-through inspector for gateway mode (used when URL redirect happens at transport level)."""
    global _gateway_pass_through_inspector
    if _gateway_pass_through_inspector is None:
        with _inspector_lock:
            if _gateway_pass_through_inspector is None:
                _gateway_pass_through_inspector = MCPGatewayInspector(
                    gateway_url=None,
                    api_key=None,
                    fail_open=_state.get_gw_mcp_fail_open(),
                )
    return _gateway_pass_through_inspector


def _get_inspector() -> Union[MCPInspector, MCPGatewayInspector]:
    """Get the appropriate inspector based on integration mode."""
    if _should_use_gateway():
        return _get_gateway_pass_through_inspector()
    return _get_api_inspector()


def _should_use_gateway() -> bool:
    """Check if we should use gateway mode for MCP (not skipped, not off)."""
    from .._context import is_mcp_skip_active
    if _state.get_mcp_integration_mode() != "gateway":
        return False
    if _state.get_gw_mcp_mode() == "off":
        return False
    if is_mcp_skip_active():
        return False
    return True


def _should_inspect() -> bool:
    """Check if we should inspect (applies to API mode, and not skipped).

    When mode is None (not configured), inspection is off by default.
    """
    from .._context import is_mcp_skip_active
    if is_mcp_skip_active():
        return False
    mode = _state.get_mcp_mode()
    if mode is None or mode == "off":
        return False
    return True


def _enforce_decision(decision: Decision) -> None:
    """Enforce or log a decision based on the current mode."""
    mode = _state.get_mcp_mode()
    if decision.action == "block":
        if mode == "enforce":
            raise SecurityPolicyError(decision)
        elif mode == "monitor":
            logger.warning(
                "[agentsec] Block decision in monitor mode (MCP): reasons=%s, severity=%s, classifications=%s",
                decision.reasons, decision.severity, decision.classifications,
            )
            callback = _state.get_on_violation()
            if callback is not None:
                try:
                    callback(decision)
                except Exception:
                    logger.debug("on_violation callback raised an exception", exc_info=True)


def _patch_mcp_handle_get_stream_405() -> None:
    """Patch MCP StreamableHTTPTransport.handle_get_stream to skip retries on 405.

    Some MCP servers (e.g. remote.mcpservers.org, AI Defense gateway) return 405
    Method Not Allowed when the client tries to reconnect the GET SSE stream after
    a disconnect. Retrying is futile and produces noisy logs. Tool calls still
    succeed via the POST path. This patch detects 405 and exits early.
    """
    try:
        from mcp.client import streamable_http as _sh
    except ImportError:
        return

    _LAST_EVENT_ID = getattr(_sh, "LAST_EVENT_ID", "last-event-id")
    _DEFAULT_RECONNECTION_DELAY_MS = getattr(_sh, "DEFAULT_RECONNECTION_DELAY_MS", 1000)
    _MAX_RECONNECTION_ATTEMPTS = getattr(_sh, "MAX_RECONNECTION_ATTEMPTS", 2)
    _mcp_logger = getattr(_sh, "logger", logger)

    async def _patched_handle_get_stream(self, client, read_stream_writer):
        import anyio
        from httpx_sse import aconnect_sse

        last_event_id = None
        retry_interval_ms = None
        attempt = 0

        while attempt < _MAX_RECONNECTION_ATTEMPTS:
            try:
                if not self.session_id:
                    return
                headers = self._prepare_headers()
                if last_event_id:
                    headers[_LAST_EVENT_ID] = last_event_id

                async with aconnect_sse(client, "GET", self.url, headers=headers) as event_source:
                    event_source.response.raise_for_status()
                    _mcp_logger.debug("GET SSE connection established")

                    async for sse in event_source.aiter_sse():
                        if sse.id:
                            last_event_id = sse.id
                        if sse.retry is not None:
                            retry_interval_ms = sse.retry
                        await self._handle_sse_event(sse, read_stream_writer)

                attempt = 0
            except Exception as exc:
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 405:
                    logger.debug(
                        "MCP GET stream reconnection returned 405 (Method Not Allowed); "
                        "server does not support stream reconnect, skipping retries"
                    )
                    return
                _mcp_logger.debug("GET stream error", exc_info=True)
                attempt += 1

            if attempt >= _MAX_RECONNECTION_ATTEMPTS:
                _mcp_logger.debug(
                    f"GET stream max reconnection attempts ({_MAX_RECONNECTION_ATTEMPTS}) exceeded"
                )
                return

            delay_ms = retry_interval_ms if retry_interval_ms is not None else _DEFAULT_RECONNECTION_DELAY_MS
            _mcp_logger.info(f"GET stream disconnected, reconnecting in {delay_ms}ms...")
            await anyio.sleep(delay_ms / 1000.0)

    _sh.StreamableHTTPTransport.handle_get_stream = _patched_handle_get_stream


def _wrap_streamablehttp_client(wrapped, instance, args, kwargs):
    """
    Wrapper for streamablehttp_client to redirect URL to gateway in gateway mode.

    Uses URL-based resolution: looks up gateway for the original MCP server URL,
    then swaps URL and injects auth headers.
    """
    global _gateway_mode_logged

    if not _should_use_gateway():
        return wrapped(*args, **kwargs)

    # Extract the original MCP server URL
    original_url = kwargs.get('url') or (args[0] if args else None)
    if not original_url:
        return wrapped(*args, **kwargs)

    # Resolve gateway config for this URL
    gw_settings = _get_gateway_settings_for_url(original_url)
    if gw_settings is None:
        # Gateway mode is active but no gateway configured for this MCP URL.
        # Raise rather than silently connecting directly (no inspection).
        raise SecurityPolicyError(
            Decision.block(
                reasons=[
                    f"MCP gateway mode enabled but no gateway configured "
                    f"for URL '{original_url}'"
                ]
            ),
            f"MCP gateway mode is active but no gateway configuration "
            f"found for URL '{original_url}'. Configure a gateway for "
            f"this URL in gateway_mode.mcp_gateways or switch to api "
            f"integration mode.",
        )

    if not gw_settings.url:
        # Gateway entry exists but has no URL — treat as misconfiguration.
        raise SecurityPolicyError(
            Decision.block(
                reasons=[
                    f"MCP gateway configured for URL '{original_url}' "
                    f"but gateway URL is empty"
                ]
            ),
            f"MCP gateway entry found for '{original_url}' but gateway "
            f"URL is not set. Check gateway_mode.mcp_gateways configuration.",
        )

    if not _gateway_mode_logged:
        logger.info("[MCP GATEWAY] Redirecting MCP connections to gateway")
        logger.debug(f"[MCP GATEWAY] Original URL: {original_url}")
        logger.debug(f"[MCP GATEWAY] Gateway URL: {gw_settings.url}")
        _gateway_mode_logged = True

    # Copy kwargs to avoid mutating the caller's dict
    kwargs = dict(kwargs)
    # Replace URL with gateway URL
    if 'url' in kwargs:
        kwargs['url'] = gw_settings.url
    elif args:
        args = (gw_settings.url,) + args[1:]

    # Inject auth headers based on auth_mode
    if gw_settings.auth_mode == "client":
        # Forward whatever auth headers the client already set (no gateway auth injected).
        # The gateway proxies the client's credentials to the actual MCP server.
        logger.debug("[MCP GATEWAY] auth_mode=client — forwarding client-provided headers")

    elif gw_settings.auth_mode == "api_key" and gw_settings.api_key:
        headers = kwargs.get('headers', {})
        if headers is None:
            headers = {}
        headers = dict(headers)
        header_name = gw_settings.api_key_header or "api-key"
        headers[header_name] = gw_settings.api_key
        kwargs['headers'] = headers

    elif gw_settings.auth_mode == "oauth2_client_credentials":
        from .._oauth2 import get_oauth2_token

        token = get_oauth2_token(
            token_url=gw_settings.oauth2_token_url,
            client_id=gw_settings.oauth2_client_id,
            client_secret=gw_settings.oauth2_client_secret,
            scopes=gw_settings.oauth2_scopes,
        )
        headers = kwargs.get('headers', {})
        if headers is None:
            headers = {}
        headers = dict(headers)
        headers['Authorization'] = f'Bearer {token}'
        kwargs['headers'] = headers

    # auth_mode == "none" — no headers injected

    return wrapped(*args, **kwargs)


async def _wrap_call_tool(wrapped, instance, args, kwargs):
    """Async wrapper for ClientSession.call_tool.
    
    Routes to appropriate inspector based on integration mode:
    - API mode: MCPInspector (makes API calls for inspection)
    - Gateway mode: MCPGatewayInspector (pass-through, gateway handles inspection)
    """
    # Reset inspection context for this new call
    set_inspection_context(done=False)
    # Extract tool info
    tool_name = args[0] if args else kwargs.get("name", "")
    arguments = args[1] if len(args) > 1 else kwargs.get("arguments", {})
    
    integration_mode = _state.get_mcp_integration_mode()
    use_gateway = _should_use_gateway()
    
    # Log the call
    if use_gateway:
        logger.debug(f"╔══════════════════════════════════════════════════════════════")
        logger.debug(f"║ [PATCHED] MCP TOOL CALL: {tool_name}")
        logger.debug(f"║ Arguments: {arguments}")
        logger.debug(f"║ Integration: gateway (gateway handles inspection)")
        logger.debug(f"╚══════════════════════════════════════════════════════════════")
    else:
        mode = _state.get_mcp_mode()
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
        fail_open = getattr(inspector, 'fail_open', _state.get_api_mcp_fail_open())
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
        fail_open = getattr(inspector, 'fail_open', _state.get_api_mcp_fail_open())
        if not fail_open:
            decision = Decision.block(reasons=[f"MCP response inspection error: {e}"])
            raise SecurityPolicyError(decision, f"MCP response inspection failed and fail_open=False: {e}")
        set_inspection_context(decision=Decision.allow(reasons=[f"MCP response inspection error: {e}"]), done=True)
    
    logger.debug(f"[PATCHED CALL] MCP.call_tool({tool_name}) - complete")
    return result


async def _wrap_get_prompt(wrapped, instance, args, kwargs):
    """Async wrapper for ClientSession.get_prompt.
    
    Routes to appropriate inspector based on integration mode:
    - API mode: MCPInspector (makes API calls for inspection)
    - Gateway mode: MCPGatewayInspector (pass-through, gateway handles inspection)
    """
    # Reset inspection context for this new call
    set_inspection_context(done=False)
    # Extract prompt info
    prompt_name = args[0] if args else kwargs.get("name", "")
    arguments = args[1] if len(args) > 1 else kwargs.get("arguments", {})
    
    integration_mode = _state.get_mcp_integration_mode()
    use_gateway = _should_use_gateway()
    
    # Log the call
    if use_gateway:
        logger.debug(f"╔══════════════════════════════════════════════════════════════")
        logger.debug(f"║ [PATCHED] MCP GET PROMPT: {prompt_name}")
        logger.debug(f"║ Arguments: {arguments}")
        logger.debug(f"║ Integration: gateway (gateway handles inspection)")
        logger.debug(f"╚══════════════════════════════════════════════════════════════")
    else:
        mode = _state.get_mcp_mode()
        logger.debug(f"╔══════════════════════════════════════════════════════════════")
        logger.debug(f"║ [PATCHED] MCP GET PROMPT: {prompt_name}")
        logger.debug(f"║ Arguments: {arguments}")
        logger.debug(f"║ MCP Mode: {mode} | Integration: {integration_mode}")
        logger.debug(f"╚══════════════════════════════════════════════════════════════")
    
    # Check if inspection is enabled (API mode only)
    if not use_gateway and not _should_inspect():
        logger.debug(f"[PATCHED CALL] MCP.get_prompt({prompt_name}) - inspection skipped (mode=off)")
        return await wrapped(*args, **kwargs)
    
    metadata = get_inspection_context().metadata
    inspector = _get_inspector()
    
    # Pre-call inspection
    try:
        logger.debug(f"[PATCHED CALL] MCP.get_prompt({prompt_name}) - Request inspection")
        decision = await inspector.ainspect_request(prompt_name, arguments or {}, metadata, method="prompts/get")
        logger.debug(f"[PATCHED CALL] MCP.get_prompt({prompt_name}) - Request decision: {decision.action}")
        set_inspection_context(decision=decision)
        _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as e:
        logger.warning(f"[PATCHED CALL] MCP.get_prompt({prompt_name}) - Request inspection error: {e}")
        # Use inspector's fail_open setting for consistency
        fail_open = getattr(inspector, 'fail_open', _state.get_api_mcp_fail_open())
        if not fail_open:
            decision = Decision.block(reasons=[f"MCP inspection error: {e}"])
            raise SecurityPolicyError(decision, f"MCP inspection failed: {e}")
        logger.warning(f"fail_open=True, proceeding despite inspection error")
    
    # Call original
    logger.debug(f"[PATCHED CALL] MCP.get_prompt({prompt_name}) - calling original method")
    result = await wrapped(*args, **kwargs)
    
    # Post-call inspection
    try:
        logger.debug(f"[PATCHED CALL] MCP.get_prompt({prompt_name}) - Response inspection")
        decision = await inspector.ainspect_response(prompt_name, arguments or {}, result, metadata, method="prompts/get")
        logger.debug(f"[PATCHED CALL] MCP.get_prompt({prompt_name}) - Response decision: {decision.action}")
        set_inspection_context(decision=decision, done=True)
        _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as e:
        logger.warning(f"[PATCHED CALL] MCP.get_prompt({prompt_name}) - Response inspection error: {e}")
        fail_open = getattr(inspector, 'fail_open', _state.get_api_mcp_fail_open())
        if not fail_open:
            decision = Decision.block(reasons=[f"MCP response inspection error: {e}"])
            raise SecurityPolicyError(decision, f"MCP response inspection failed and fail_open=False: {e}")
        set_inspection_context(decision=Decision.allow(reasons=[f"MCP response inspection error: {e}"]), done=True)
    
    logger.debug(f"[PATCHED CALL] MCP.get_prompt({prompt_name}) - complete")
    return result


async def _wrap_read_resource(wrapped, instance, args, kwargs):
    """Async wrapper for ClientSession.read_resource.
    
    Routes to appropriate inspector based on integration mode:
    - API mode: MCPInspector (makes API calls for inspection)
    - Gateway mode: MCPGatewayInspector (pass-through, gateway handles inspection)
    """
    # Reset inspection context for this new call
    set_inspection_context(done=False)
    # Extract resource info - read_resource takes a URI
    resource_uri = args[0] if args else kwargs.get("uri", "")
    
    integration_mode = _state.get_mcp_integration_mode()
    use_gateway = _should_use_gateway()
    
    # Log the call
    if use_gateway:
        logger.debug(f"╔══════════════════════════════════════════════════════════════")
        logger.debug(f"║ [PATCHED] MCP READ RESOURCE: {resource_uri}")
        logger.debug(f"║ Integration: gateway (gateway handles inspection)")
        logger.debug(f"╚══════════════════════════════════════════════════════════════")
    else:
        mode = _state.get_mcp_mode()
        logger.debug(f"╔══════════════════════════════════════════════════════════════")
        logger.debug(f"║ [PATCHED] MCP READ RESOURCE: {resource_uri}")
        logger.debug(f"║ MCP Mode: {mode} | Integration: {integration_mode}")
        logger.debug(f"╚══════════════════════════════════════════════════════════════")
    
    # Check if inspection is enabled (API mode only)
    if not use_gateway and not _should_inspect():
        logger.debug(f"[PATCHED CALL] MCP.read_resource({resource_uri}) - inspection skipped (mode=off)")
        return await wrapped(*args, **kwargs)
    
    metadata = get_inspection_context().metadata
    inspector = _get_inspector()
    
    # Pre-call inspection
    try:
        logger.debug(f"[PATCHED CALL] MCP.read_resource({resource_uri}) - Request inspection")
        decision = await inspector.ainspect_request(resource_uri, {}, metadata, method="resources/read")
        logger.debug(f"[PATCHED CALL] MCP.read_resource({resource_uri}) - Request decision: {decision.action}")
        set_inspection_context(decision=decision)
        _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as e:
        logger.warning(f"[PATCHED CALL] MCP.read_resource({resource_uri}) - Request inspection error: {e}")
        # Use inspector's fail_open setting for consistency
        fail_open = getattr(inspector, 'fail_open', _state.get_api_mcp_fail_open())
        if not fail_open:
            decision = Decision.block(reasons=[f"MCP inspection error: {e}"])
            raise SecurityPolicyError(decision, f"MCP inspection failed: {e}")
        logger.warning(f"fail_open=True, proceeding despite inspection error")
    
    # Call original
    logger.debug(f"[PATCHED CALL] MCP.read_resource({resource_uri}) - calling original method")
    result = await wrapped(*args, **kwargs)
    
    # Post-call inspection
    try:
        logger.debug(f"[PATCHED CALL] MCP.read_resource({resource_uri}) - Response inspection")
        decision = await inspector.ainspect_response(resource_uri, {}, result, metadata, method="resources/read")
        logger.debug(f"[PATCHED CALL] MCP.read_resource({resource_uri}) - Response decision: {decision.action}")
        set_inspection_context(decision=decision, done=True)
        _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as e:
        logger.warning(f"[PATCHED CALL] MCP.read_resource({resource_uri}) - Response inspection error: {e}")
        fail_open = getattr(inspector, 'fail_open', _state.get_api_mcp_fail_open())
        if not fail_open:
            decision = Decision.block(reasons=[f"MCP response inspection error: {e}"])
            raise SecurityPolicyError(decision, f"MCP response inspection failed and fail_open=False: {e}")
        set_inspection_context(decision=Decision.allow(reasons=[f"MCP response inspection error: {e}"]), done=True)
    
    logger.debug(f"[PATCHED CALL] MCP.read_resource({resource_uri}) - complete")
    return result


def patch_mcp() -> bool:
    """
    Patch MCP client for automatic inspection.
    
    Patches the following MCP ClientSession methods:
    - call_tool: Tool execution inspection
    - get_prompt: Prompt retrieval inspection
    - read_resource: Resource access inspection
    
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
        logger.debug("MCP ClientSession.call_tool patched")
        
        # Patch get_prompt for inspection
        get_prompt_patched = False
        try:
            wrapt.wrap_function_wrapper(
                "mcp.client.session",
                "ClientSession.get_prompt",
                _wrap_get_prompt,
            )
            logger.debug("MCP ClientSession.get_prompt patched")
            get_prompt_patched = True
        except Exception as e:
            logger.warning(f"Could not patch MCP get_prompt - prompt retrieval will NOT be inspected: {e}")
        
        # Patch read_resource for inspection
        read_resource_patched = False
        try:
            wrapt.wrap_function_wrapper(
                "mcp.client.session",
                "ClientSession.read_resource",
                _wrap_read_resource,
            )
            logger.debug("MCP ClientSession.read_resource patched")
            read_resource_patched = True
        except Exception as e:
            logger.warning(f"Could not patch MCP read_resource - resource reads will NOT be inspected: {e}")
        
        # Patch streamablehttp_client for gateway URL redirection
        try:
            wrapt.wrap_function_wrapper(
                "mcp.client.streamable_http",
                "streamablehttp_client",
                _wrap_streamablehttp_client,
            )
            logger.debug("MCP streamablehttp_client patched for gateway mode")
        except Exception as e:
            # This is less critical - only needed for gateway mode URL redirection
            logger.debug(f"Could not patch streamablehttp_client (gateway mode): {e}")

        # Patch handle_get_stream to suppress 405 retries (server doesn't support GET reconnection)
        try:
            _patch_mcp_handle_get_stream_405()
            logger.debug("MCP handle_get_stream patched for 405 reconnection handling")
        except Exception as e:
            logger.debug(f"Could not patch MCP handle_get_stream (405 mitigation): {e}")

        mark_patched("mcp")
        # Build list of patched methods for logging
        patched_methods = ["call_tool"]
        if get_prompt_patched:
            patched_methods.append("get_prompt")
        if read_resource_patched:
            patched_methods.append("read_resource")
        logger.info(f"MCP client patched successfully ({', '.join(patched_methods)})")
        return True
    except Exception as e:
        logger.warning(f"Failed to patch MCP: {e}")
        return False
