"""
Bedrock/boto3 and AgentCore client autopatching.

This module provides automatic inspection for AWS Bedrock and AgentCore LLM calls
by patching at the botocore level. This covers ALL Bedrock and AgentCore operations:

Bedrock Operations:
- InvokeModel: Direct model invocation
- InvokeModelWithResponseStream: Streaming model invocation
- Converse: Chat-like Converse API
- ConverseStream: Streaming Converse API

AgentCore Operations:
- InvokeAgentRuntime: Agent runtime invocation (supports direct deploy, Lambda, container)

By patching botocore.client.BaseClient._make_api_call, we intercept all Bedrock
and AgentCore operations regardless of which higher-level AWS SDK or wrapper is used.

Gateway Mode Support:
- Bedrock: Uses Bearer token authentication with API key
- AgentCore: Uses AWS Signature V4 authentication (no separate API key needed)

When llm_integration_mode=gateway, calls are routed to the provider-specific
AI Defense Gateway in native format.

Note: This satisfies roadmap item 21 (AWS Bedrock Client Autopatch) as the
botocore-level patching covers all Bedrock and AgentCore client interfaces.
"""

import io
import json
import logging
import threading
from typing import Any, Dict, Iterator, List, Optional

import wrapt

from .. import _state
from .._context import get_inspection_context, set_inspection_context
from ..decision import Decision
from ..exceptions import SecurityPolicyError
from ..inspectors.api_llm import LLMInspector
from . import is_patched, mark_patched
from ._base import safe_import, resolve_gateway_settings

logger = logging.getLogger("aidefense.runtime.agentsec.patchers.bedrock")


def _build_aws_session(gw_settings):
    """Build a boto3 session from per-gateway AWS settings.

    Constructs a ``boto3.Session`` using credentials configured on the
    gateway entry in ``agentsec.yaml``.  The resolution order mirrors the
    standard AWS credential chain but allows each gateway to override it:

    1. Explicit keys (``aws_access_key_id`` + ``aws_secret_access_key``,
       plus optional ``aws_session_token``).
    2. Named profile (``aws_profile`` from ``~/.aws/credentials``).
    3. Default boto3 credential chain (environment variables, instance
       role, etc.).

    If ``aws_role_arn`` is also set, the base credentials from steps 1-3
    are used to call ``sts:AssumeRole`` and the resulting temporary
    credentials replace the session.

    Args:
        gw_settings: A :class:`GatewaySettings` instance with optional
            ``aws_*`` fields.

    Returns:
        A ``(session, credentials, region)`` tuple where *credentials*
        may be ``None`` if no credentials could be resolved.
    """
    import boto3

    # Step 1: Build base session kwargs from per-gateway config
    session_kwargs = {}
    if gw_settings.aws_region:
        session_kwargs["region_name"] = gw_settings.aws_region
    if gw_settings.aws_access_key_id and gw_settings.aws_secret_access_key:
        # Explicit keys take precedence over profile
        session_kwargs["aws_access_key_id"] = gw_settings.aws_access_key_id
        session_kwargs["aws_secret_access_key"] = gw_settings.aws_secret_access_key
        if gw_settings.aws_session_token:
            session_kwargs["aws_session_token"] = gw_settings.aws_session_token
    elif gw_settings.aws_profile:
        session_kwargs["profile_name"] = gw_settings.aws_profile

    try:
        session = boto3.Session(**session_kwargs)
    except Exception:
        # Profile may not exist (e.g., Lambda uses IAM execution role, not profiles).
        # Fall back to the default credential chain without the profile.
        if "profile_name" in session_kwargs:
            logger.debug(
                "[GATEWAY] AWS profile '%s' not found, falling back to default credential chain",
                session_kwargs.pop("profile_name"),
            )
            session = boto3.Session(**session_kwargs)
        else:
            raise

    # Step 2: Assume role if configured (cross-account / least-privilege)
    if gw_settings.aws_role_arn:
        sts = session.client("sts")
        assumed = sts.assume_role(
            RoleArn=gw_settings.aws_role_arn,
            RoleSessionName="agentsec-gateway",
        )
        temp = assumed["Credentials"]
        session = boto3.Session(
            aws_access_key_id=temp["AccessKeyId"],
            aws_secret_access_key=temp["SecretAccessKey"],
            aws_session_token=temp["SessionToken"],
            region_name=gw_settings.aws_region or session.region_name,
        )

    credentials = session.get_credentials()
    region = gw_settings.aws_region or session.region_name or "us-east-1"
    return session, credentials, region


class _StreamingBodyWrapper:
    """
    Wrapper that mimics boto3's StreamingBody interface while wrapping pre-read content.
    
    When inspecting Bedrock responses, we need to read the StreamingBody to get the content.
    This wrapper allows us to provide a replacement that looks like a StreamingBody to
    calling code, ensuring compatibility with code that expects StreamingBody-specific methods.
    
    Supported methods (same as botocore.response.StreamingBody):
    - read(amt=None): Read some or all of the body
    - close(): Close the stream
    - iter_lines(): Iterate over lines
    - iter_chunks(chunk_size): Iterate over chunks
    """
    
    def __init__(self, content: bytes):
        """
        Initialize with pre-read content.
        
        Args:
            content: The bytes content that was read from the original StreamingBody
        """
        self._content = content
        self._stream = io.BytesIO(content)
        self._amount_read = 0
    
    def read(self, amt: Optional[int] = None) -> bytes:
        """
        Read the body content.
        
        Args:
            amt: Number of bytes to read, or None to read all remaining content
            
        Returns:
            The requested bytes
        """
        return self._stream.read(amt)
    
    def readlines(self) -> List[bytes]:
        """Read all lines from the stream."""
        return self._stream.readlines()
    
    def close(self) -> None:
        """Close the underlying stream."""
        self._stream.close()
    
    def iter_lines(self, chunk_size: int = 1024):
        """
        Iterate over lines in the body.
        
        Args:
            chunk_size: Size of chunks to read (for compatibility, not used)
            
        Yields:
            Lines from the body content
        """
        for line in self._stream:
            yield line
    
    def iter_chunks(self, chunk_size: int = 1024):
        """
        Iterate over chunks of the body.
        
        Args:
            chunk_size: Size of each chunk
            
        Yields:
            Chunks of the body content
        """
        while True:
            chunk = self._stream.read(chunk_size)
            if not chunk:
                break
            yield chunk
    
    def __iter__(self):
        """Allow iteration over the stream."""
        return self.iter_chunks()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()

# Bedrock operation names to intercept
BEDROCK_OPERATIONS = {"InvokeModel", "InvokeModelWithResponseStream", "Converse", "ConverseStream"}

# AgentCore operation names to intercept
AGENTCORE_OPERATIONS = {"InvokeAgentRuntime"}

# Global inspector instance with thread-safe initialization
_inspector: Optional[LLMInspector] = None
_inspector_lock = threading.Lock()


def _reset_inspector() -> None:
    """Clear the cached inspector so the next call to _get_inspector() creates a fresh one."""
    global _inspector
    _inspector = None


def _get_inspector() -> LLMInspector:
    """Get or create the LLMInspector instance (thread-safe)."""
    global _inspector
    if _inspector is None:
        with _inspector_lock:
            # Double-check pattern for thread safety
            if _inspector is None:
                if not _state.is_initialized():
                    logger.warning("agentsec.protect() not called, using default config")
                _inspector = LLMInspector(
                    fail_open=_state.get_api_llm_fail_open(),
                    default_rules=_state.get_llm_rules(),
                )
                # Register for cleanup on shutdown
                from ..inspectors import register_inspector_for_cleanup
                register_inspector_for_cleanup(_inspector)
    return _inspector


# =============================================================================
# AgentCore-specific functions
# =============================================================================

def _is_agentcore_client(instance) -> bool:
    """
    Check if the boto client is for the bedrock-agentcore service.
    
    Args:
        instance: The boto client instance
        
    Returns:
        True if this is a bedrock-agentcore client
    """
    try:
        service_model = getattr(instance, '_service_model', None)
        if service_model:
            service_name = getattr(service_model, 'service_name', '')
            return service_name == 'bedrock-agentcore'
    except Exception as e:
        logger.debug(f"Error detecting AgentCore client: {e}")
    return False


def _is_agentcore_operation(operation_name: str, instance) -> bool:
    """Check if this is an AgentCore operation we should intercept."""
    return operation_name in AGENTCORE_OPERATIONS and _is_agentcore_client(instance)


def _parse_agentcore_payload(payload: bytes) -> List[Dict[str, Any]]:
    """
    Parse AgentCore request payload into standard message format.
    
    Handles multiple payload formats:
    1. Bedrock Converse format (messages array)
    2. Simple formats (prompt, query, input, text)
    
    Args:
        payload: The request payload (bytes or string)
        
    Returns:
        List of message dicts with role and content
    """
    if isinstance(payload, bytes):
        try:
            payload = payload.decode('utf-8')
        except UnicodeDecodeError:
            return []
    
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        # If it's not JSON, treat it as plain text
        if payload.strip():
            return [{"role": "user", "content": payload.strip()}]
        return []
    
    messages = []
    
    # Format 1: Bedrock Converse format (messages array)
    if "messages" in data:
        for msg in data.get("messages", []):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if isinstance(content, list):
                # Handle content blocks (Bedrock Converse style)
                text_parts = []
                for c in content:
                    if isinstance(c, dict):
                        if "text" in c:
                            text_parts.append(c.get("text", ""))
                        elif c.get("type") == "text":
                            text_parts.append(c.get("text", ""))
                content = " ".join(text_parts)
            
            if content:
                messages.append({"role": role, "content": content})
        
        # Add system prompt if present
        if "system" in data:
            system_content = data["system"]
            if isinstance(system_content, list):
                text = " ".join(
                    c.get("text", "") for c in system_content if isinstance(c, dict) and "text" in c
                )
                if text:
                    messages.insert(0, {"role": "system", "content": text})
            elif isinstance(system_content, str):
                messages.insert(0, {"role": "system", "content": system_content})
        
        return messages
    
    # Format 2: Simple prompt formats
    for key in ["prompt", "query", "input", "text"]:
        if key in data:
            content = data[key]
            if isinstance(content, str) and content.strip():
                return [{"role": "user", "content": content.strip()}]
    
    return messages


def _parse_agentcore_response(response_payload) -> str:
    """
    Parse AgentCore response payload to extract assistant content.
    
    Handles multiple response formats:
    1. Bedrock Converse format (output.message.content)
    2. Simple formats (response, completion, content, text)
    
    Args:
        response_payload: The response payload (bytes, string, or StreamingBody)
        
    Returns:
        Extracted assistant content as string
    """
    # Handle StreamingBody from boto3
    if hasattr(response_payload, 'read'):
        try:
            response_payload = response_payload.read()
        except Exception:
            return ""
    
    if isinstance(response_payload, bytes):
        try:
            response_payload = response_payload.decode('utf-8')
        except UnicodeDecodeError:
            return ""
    
    try:
        data = json.loads(response_payload)
    except json.JSONDecodeError:
        # If it's not JSON, return as-is if it looks like content
        if response_payload.strip():
            return response_payload.strip()
        return ""
    
    # Format 1: Bedrock Converse format
    if "output" in data:
        output = data["output"]
        if isinstance(output, dict) and "message" in output:
            message = output["message"]
            content = message.get("content", [])
            if isinstance(content, list):
                return " ".join(
                    c.get("text", "") for c in content if isinstance(c, dict) and "text" in c
                )
            elif isinstance(content, str):
                return content
    
    # Format 2: Simple response formats
    for key in ["result", "response", "completion", "content", "text", "output"]:
        if key in data:
            value = data[key]
            if isinstance(value, str):
                return value
            elif isinstance(value, dict) and "text" in value:
                return value["text"]
    
    return ""


def _handle_agentcore_gateway_call(operation_name: str, api_params: Dict, instance, gw_settings) -> Dict:
    """
    Handle AgentCore call via AI Defense Gateway with AWS Signature V4 authentication.
    
    Sends the request to the AI Defense Gateway, which proxies to AgentCore.
    Uses the Bedrock gateway URL with AWS Sig V4 authentication (when auth_mode=aws_sigv4)
    or Bearer token (when auth_mode=api_key).
    
    Args:
        operation_name: AgentCore operation name (InvokeAgentRuntime)
        api_params: AgentCore API parameters
        instance: The boto client instance (used for session/credentials)
        gw_settings: Resolved gateway settings
        
    Returns:
        AgentCore-format response dict
    """
    import httpx
    
    gateway_url = gw_settings.url
    if not gateway_url:
        logger.warning("Gateway mode enabled but Bedrock gateway not configured")
        raise SecurityPolicyError(
            Decision.block(reasons=["Bedrock gateway not configured"]),
            "Gateway mode enabled but Bedrock gateway not configured (check gateway_mode.llm_gateways for a bedrock provider entry in config)"
        )
    
    agent_runtime_arn = api_params.get("agentRuntimeArn", "")
    session_id = api_params.get("runtimeSessionId") or ""
    payload = api_params.get("payload", b"")
    
    # Ensure payload is string for JSON encoding
    if isinstance(payload, bytes):
        payload = payload.decode('utf-8')
    
    logger.debug(f"[GATEWAY] Sending AgentCore request to gateway")
    logger.debug(f"[GATEWAY] Operation: {operation_name}, AgentRuntime: {agent_runtime_arn}")
    
    try:
        # Build request body
        try:
            request_body = json.loads(payload) if payload else {}
        except json.JSONDecodeError:
            request_body = {"payload": payload}
        
        # Add AgentCore-specific fields
        request_body["agentRuntimeArn"] = agent_runtime_arn
        # Always provide a session ID; generate one if the caller omitted it
        import uuid
        request_body["runtimeSessionId"] = session_id if session_id else str(uuid.uuid4())
        
        body_bytes = json.dumps(request_body).encode('utf-8')
        headers = {
            "Content-Type": "application/json",
            "X-AgentCore-Operation": operation_name,
        }
        
        if gw_settings.auth_mode == "aws_sigv4":
            # AWS Sig V4 authentication (per-gateway credentials)
            from botocore.auth import SigV4Auth
            from botocore.awsrequest import AWSRequest
            
            session, credentials, region = _build_aws_session(gw_settings)
            if credentials is None:
                logger.error("[GATEWAY] No AWS credentials available for Sig V4 signing")
                raise SecurityPolicyError(
                    Decision.block(reasons=["AWS credentials not available"]),
                    "AWS credentials required for AgentCore gateway authentication"
                )
            aws_request = AWSRequest(
                method="POST",
                url=gateway_url,
                data=body_bytes,
                headers=headers,
            )
            SigV4Auth(credentials, "bedrock", region).add_auth(aws_request)
            with httpx.Client(timeout=float(gw_settings.timeout)) as client:
                response = client.post(
                    gateway_url,
                    content=body_bytes,
                    headers=dict(aws_request.headers),
                )
                response.raise_for_status()
                response_data = response.json()
        else:
            # api_key (default): Bearer token
            if not gw_settings.api_key:
                raise SecurityPolicyError(
                    Decision.block(reasons=["Gateway API key not configured"]),
                    "AgentCore gateway requires api_key when auth_mode=api_key"
                )
            auth_headers = {
                **headers,
                "Authorization": f"Bearer {gw_settings.api_key}",
            }
            with httpx.Client(timeout=float(gw_settings.timeout)) as client:
                response = client.post(
                    gateway_url,
                    content=body_bytes,
                    headers=auth_headers,
                )
                response.raise_for_status()
                response_data = response.json()
        
        logger.debug(f"[GATEWAY] Received AgentCore response from gateway")
        set_inspection_context(decision=Decision.allow(reasons=["Gateway handled inspection"]), done=True)
        
        return response_data
        
    except httpx.HTTPStatusError as e:
        logger.error(f"[GATEWAY] HTTP error: {e}")
        if gw_settings.fail_open:
            # fail_open=True: allow request to proceed by re-raising original error
            logger.warning(f"[GATEWAY] fail_open=True, re-raising original HTTP error for caller to handle")
            set_inspection_context(decision=Decision.allow(reasons=["Gateway error, fail_open=True"]), done=True)
            raise  # Re-raise original HTTP error, not SecurityPolicyError
        else:
            # fail_open=False: block the request with SecurityPolicyError
            raise SecurityPolicyError(
                Decision.block(reasons=["AgentCore gateway unavailable"]),
                f"Gateway HTTP error: {e}"
            )
    except ImportError as e:
        logger.error(f"[GATEWAY] Missing dependency for AWS Sig V4: {e}")
        raise SecurityPolicyError(
            Decision.block(reasons=["Missing AWS SDK dependencies"]),
            f"boto3/botocore required for AgentCore gateway: {e}"
        )
    except Exception as e:
        logger.error(f"[GATEWAY] Error: {e}")
        if gw_settings.fail_open:
            logger.warning(f"[GATEWAY] fail_open=True, re-raising original error for caller to handle")
            set_inspection_context(decision=Decision.allow(reasons=["Gateway error, fail_open=True"]), done=True)
            raise  # Re-raise original error
        raise


def _handle_agentcore_api_mode(operation_name: str, api_params: Dict, wrapped, args, kwargs) -> Dict:
    """
    Handle AgentCore call in API mode (inspection via AI Defense API).
    
    Args:
        operation_name: AgentCore operation name
        api_params: AgentCore API parameters
        wrapped: Original wrapped function
        args: Original args
        kwargs: Original kwargs
        
    Returns:
        AgentCore response from the original call
    """
    payload = api_params.get("payload", b"")
    agent_runtime_arn = api_params.get("agentRuntimeArn", "")
    
    # Parse messages from payload
    messages = _parse_agentcore_payload(payload)
    
    metadata = get_inspection_context().metadata
    metadata["agent_runtime_arn"] = agent_runtime_arn
    metadata["provider"] = "bedrock"  # AgentCore uses Bedrock as the underlying provider
    
    mode = _state.get_llm_mode()
    integration_mode = _state.get_llm_integration_mode()
    logger.debug(f"╔══════════════════════════════════════════════════════════════")
    logger.debug(f"║ [PATCHED] LLM CALL: AgentCore")
    logger.debug(f"║ Operation: AgentCore.{operation_name} | LLM Mode: {mode} | Integration: {integration_mode}")
    logger.debug(f"║ AgentRuntime: {agent_runtime_arn}")
    logger.debug(f"╚══════════════════════════════════════════════════════════════")
    
    # Pre-call inspection
    if messages:
        try:
            logger.debug(f"[PATCHED CALL] AgentCore.{operation_name} - Request inspection ({len(messages)} messages)")
            inspector = _get_inspector()
            decision = inspector.inspect_conversation(messages, metadata)
            logger.debug(f"[PATCHED CALL] AgentCore.{operation_name} - Request decision: {decision.action}")
            set_inspection_context(decision=decision)
            _enforce_decision(decision)
        except SecurityPolicyError:
            raise
        except Exception as e:
            decision = _handle_patcher_error(e, f"AgentCore.{operation_name} pre-call")
            if decision:
                set_inspection_context(decision=decision)
    
    # Call original
    logger.debug(f"[PATCHED CALL] AgentCore.{operation_name} - calling original method")
    response = wrapped(*args, **kwargs)
    
    # Post-call inspection
    try:
        # AgentCore response can have either "payload" or "response" key
        response_key = "payload" if "payload" in response else "response"
        response_payload = response.get(response_key)
        
        # Read StreamingBody and buffer it for re-use
        response_bytes = b""
        if response_payload is not None:
            if hasattr(response_payload, 'read'):
                response_bytes = response_payload.read()
                # Replace StreamingBody with a wrapper that mimics StreamingBody interface
                response[response_key] = _StreamingBodyWrapper(response_bytes)
            elif isinstance(response_payload, bytes):
                response_bytes = response_payload
            else:
                response_bytes = str(response_payload).encode('utf-8')
        
        assistant_content = _parse_agentcore_response(response_bytes)
        
        if assistant_content and messages:
            logger.debug(f"[PATCHED CALL] AgentCore.{operation_name} - Response inspection (response: {len(assistant_content)} chars)")
            messages_with_response = messages + [
                {"role": "assistant", "content": assistant_content}
            ]
            inspector = _get_inspector()
            decision = inspector.inspect_conversation(messages_with_response, metadata)
            logger.debug(f"[PATCHED CALL] AgentCore.{operation_name} - Response decision: {decision.action}")
            set_inspection_context(decision=decision, done=True)
            _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as e:
        _handle_patcher_error(e, f"AgentCore.{operation_name} post-call")
    
    logger.debug(f"[PATCHED CALL] AgentCore.{operation_name} - complete")
    return response


def _should_inspect() -> bool:
    """Check if we should inspect (not already done, mode is not off, and not skipped).

    When mode is None (not configured), inspection is off by default.
    """
    from .._context import is_llm_skip_active
    if is_llm_skip_active():
        return False
    if _state.get_llm_integration_mode() == "gateway":
        if _state.get_gw_llm_mode() == "off":
            return False
    else:
        mode = _state.get_llm_mode()
        if mode is None or mode == "off":
            return False
    ctx = get_inspection_context()
    return not ctx.done


def _enforce_decision(decision: Decision) -> None:
    """Enforce or log a decision based on the current mode."""
    mode = _state.get_llm_mode()
    if decision.action == "block":
        if mode == "enforce":
            raise SecurityPolicyError(decision)
        elif mode == "monitor":
            logger.warning(
                "[agentsec] Block decision in monitor mode: reasons=%s, severity=%s, classifications=%s",
                decision.reasons, decision.severity, decision.classifications,
            )
            callback = _state.get_on_violation()
            if callback is not None:
                try:
                    callback(decision)
                except Exception:
                    logger.debug("on_violation callback raised an exception", exc_info=True)


def _is_bedrock_operation(operation_name: str) -> bool:
    """Check if this is a Bedrock operation we should intercept."""
    return operation_name in BEDROCK_OPERATIONS


def _parse_bedrock_messages(body: bytes, model_id: str) -> List[Dict[str, Any]]:
    """
    Parse Bedrock request body into standard message format.
    
    Handles different model formats (Claude, Titan, etc.)
    
    AI Defense only supports user/assistant/system roles with text content.
    - Extracts text from content blocks (type: "text")
    - Annotates tool_use blocks (assistant requesting tool calls)
    - Annotates tool_result blocks (tool responses)
    
    TBD: This is a workaround for AI Defense API not supporting Bedrock/Claude tool
    use format (type: "tool_use", "tool_result"). When AI Defense adds support
    for these content types, this normalization should be updated to preserve the
    full message structure for proper inspection of tool calls and responses.
    """
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return []
    
    messages = []
    
    # Claude format
    if "messages" in data:
        for msg in data.get("messages", []):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if isinstance(content, list):
                # Handle content blocks
                text_parts = []
                for c in content:
                    if not isinstance(c, dict):
                        continue
                    block_type = c.get("type", "")
                    
                    if block_type == "text":
                        # Regular text content
                        text_parts.append(c.get("text", ""))
                    elif block_type == "tool_use":
                        # Tool call request - annotate it
                        tool_name = c.get("name", "unknown")
                        text_parts.append(f"[Tool call: {tool_name}]")
                    elif block_type == "tool_result":
                        # Tool result - annotate with truncated content
                        tool_content = c.get("content", "")
                        if isinstance(tool_content, str):
                            preview = tool_content[:100] + "..." if len(tool_content) > 100 else tool_content
                            text_parts.append(f"[Tool result: {preview}]")
                
                content = " ".join(text_parts)
            
            # Only include messages with actual content
            if content:
                messages.append({"role": role, "content": content})
        
        # Add system prompt if present
        if "system" in data:
            messages.insert(0, {"role": "system", "content": data["system"]})
    
    # Titan format
    elif "inputText" in data:
        messages.append({"role": "user", "content": data["inputText"]})
    
    # Generic prompt format
    elif "prompt" in data:
        messages.append({"role": "user", "content": data["prompt"]})
    
    return messages


def _parse_bedrock_response(response_body: bytes, model_id: str) -> str:
    """Parse Bedrock response body to extract assistant content."""
    try:
        data = json.loads(response_body)
    except json.JSONDecodeError:
        return ""
    
    # Claude format
    if "content" in data:
        content = data["content"]
        if isinstance(content, list):
            return " ".join(c.get("text", "") for c in content if c.get("type") == "text")
        return str(content)
    
    # Titan format
    if "results" in data:
        return " ".join(r.get("outputText", "") for r in data["results"])
    
    # Generic completion
    if "completion" in data:
        return data["completion"]
    
    if "generation" in data:
        return data["generation"]
    
    return ""


def _parse_converse_messages(api_params: Dict) -> List[Dict[str, Any]]:
    """
    Parse Converse API parameters into standard message format.
    
    Converse API uses 'messages' directly in api_params, not in body.
    
    AI Defense only supports user/assistant/system roles with text content.
    - Extracts text from content blocks
    - Annotates toolUse blocks (assistant requesting tool calls)
    - Skips toolResult blocks (tool responses) - they don't have inspectable text
    
    TBD: This is a workaround for AI Defense API not supporting Bedrock tool
    use format (toolUse/toolResult content blocks). When AI Defense adds support
    for these content types, this normalization should be updated to preserve the
    full message structure for proper inspection of tool calls and responses.
    """
    messages = []
    
    # Handle system prompt
    if "system" in api_params:
        system_content = api_params["system"]
        if isinstance(system_content, list):
            # System is a list of content blocks
            text = " ".join(
                c.get("text", "") for c in system_content if isinstance(c, dict) and "text" in c
            )
            if text:
                messages.append({"role": "system", "content": text})
        elif isinstance(system_content, str):
            messages.append({"role": "system", "content": system_content})
    
    # Handle messages
    for msg in api_params.get("messages", []):
        role = msg.get("role", "user")
        content = msg.get("content", [])
        
        # Content is a list of content blocks in Converse API
        if isinstance(content, list):
            text_parts = []
            has_tool_result = False
            
            for block in content:
                if isinstance(block, dict):
                    if "text" in block:
                        # Regular text content
                        text_parts.append(block["text"])
                    elif "toolUse" in block:
                        # Assistant requesting a tool call - annotate it
                        tool_use = block["toolUse"]
                        tool_name = tool_use.get("name", "unknown")
                        text_parts.append(f"[Tool call: {tool_name}]")
                    elif "toolResult" in block:
                        # Tool result from previous call - mark for potential skip
                        has_tool_result = True
                        # Extract text from tool result if available
                        tool_result = block["toolResult"]
                        result_content = tool_result.get("content", [])
                        for rc in result_content:
                            if isinstance(rc, dict) and "text" in rc:
                                text_parts.append(f"[Tool result: {rc['text'][:100]}...]" if len(rc.get('text', '')) > 100 else f"[Tool result: {rc.get('text', '')}]")
            
            text = " ".join(text_parts)
        else:
            text = str(content)
        
        # Only include messages with actual content
        if text:
            messages.append({"role": role, "content": text})
    
    return messages


def _handle_patcher_error(error: Exception, operation: str) -> Optional[Decision]:
    """
    Handle errors in patcher inspection calls.
    
    Args:
        error: The exception that occurred
        operation: Name of the operation for logging
        
    Returns:
        Decision.allow() if fail_open=True, raises SecurityPolicyError otherwise
    """
    fail_open = _state.get_api_llm_fail_open()
    
    error_type = type(error).__name__
    logger.warning(f"[{operation}] Inspection error: {error_type}: {error}")
    
    if fail_open:
        logger.warning(f"llm_fail_open=True, allowing request despite inspection error")
        return Decision.allow(reasons=[f"Inspection error ({error_type}), llm_fail_open=True"])
    else:
        logger.error(f"fail_open=False, blocking request due to inspection error")
        decision = Decision.block(reasons=[f"Inspection error: {error_type}: {error}"])
        raise SecurityPolicyError(decision, f"Inspection failed and fail_open=False: {error}")


def _handle_bedrock_gateway_call(operation_name: str, api_params: Dict, gw_settings) -> Dict:
    """
    Handle Bedrock call via AI Defense Gateway with native format.
    
    Sends native Bedrock request directly to the provider-specific gateway.
    The gateway handles the request in native Bedrock format - no conversion needed.
    Uses Bearer token when auth_mode=api_key (default), or AWS SigV4 when auth_mode=aws_sigv4.
    
    Args:
        operation_name: Bedrock operation name (Converse, InvokeModel, etc.)
        api_params: Bedrock API parameters
        gw_settings: Resolved gateway settings
        
    Returns:
        Bedrock-format response dict (native from gateway)
    """
    import httpx
    
    gateway_url = gw_settings.url
    if not gateway_url:
        logger.warning("Gateway mode enabled but Bedrock gateway not configured")
        raise SecurityPolicyError(
            Decision.block(reasons=["Bedrock gateway not configured"]),
            "Gateway mode enabled but Bedrock gateway not configured (check gateway_mode.llm_gateways for a bedrock provider entry in config)"
        )
    if gw_settings.auth_mode != "aws_sigv4" and not gw_settings.api_key:
        logger.warning("Gateway mode enabled but Bedrock gateway API key not configured")
        raise SecurityPolicyError(
            Decision.block(reasons=["Bedrock gateway not configured"]),
            "Gateway mode enabled but Bedrock gateway API key not configured (check gateway_mode.llm_gateways for a bedrock provider entry in config)"
        )
    
    model_id = api_params.get("modelId", "")
    
    # Map Bedrock operation names to REST API URL paths
    operation_path_map = {
        "Converse": "converse",
        "ConverseStream": "converse-stream",
        "InvokeModel": "invoke",
        "InvokeModelWithResponseStream": "invoke-with-response-stream",
    }
    operation_path = operation_path_map.get(operation_name, operation_name.lower())
    
    # Send native Bedrock request to gateway
    logger.debug(f"[GATEWAY] Sending native Bedrock request to gateway")
    logger.debug(f"[GATEWAY] Operation: {operation_name}, Model: {model_id}")
    
    try:
        # Build request body based on operation type
        # Note: modelId goes in the URL path, NOT in the request body
        if operation_name in {"Converse", "ConverseStream"}:
            request_body = {
                "messages": api_params.get("messages", []),
            }
            if api_params.get("system"):
                request_body["system"] = api_params["system"]
            if api_params.get("inferenceConfig"):
                request_body["inferenceConfig"] = api_params["inferenceConfig"]
            if api_params.get("toolConfig"):
                request_body["toolConfig"] = api_params["toolConfig"]
        else:
            # InvokeModel - send body as-is
            body = api_params.get("body", b"")
            if isinstance(body, bytes):
                body = body.decode("utf-8")
            request_body = json.loads(body) if isinstance(body, str) else body
        
        # Build full gateway URL: {gateway_url}/model/{modelId}/{operation-path}
        full_gateway_url = f"{gateway_url}/model/{model_id}/{operation_path}"
        
        # Send to gateway with native format - auth based on gw_settings.auth_mode
        if gw_settings.auth_mode == "aws_sigv4":
            from botocore.auth import SigV4Auth
            from botocore.awsrequest import AWSRequest
            
            body_bytes = json.dumps(request_body).encode('utf-8')
            session, credentials, region = _build_aws_session(gw_settings)
            if credentials is None:
                logger.error("[GATEWAY] No AWS credentials available for Sig V4 signing")
                raise SecurityPolicyError(
                    Decision.block(reasons=["AWS credentials not available"]),
                    "AWS credentials required for Bedrock gateway (auth_mode=aws_sigv4)"
                )
            headers = {
                "Content-Type": "application/json",
                "x-amzn-bedrock-accept-type": "application/json",
            }
            # Sign against the REAL Bedrock endpoint (the gateway forwards
            # the signature to AWS, which validates against the real host)
            bedrock_sign_url = f"https://bedrock-runtime.{region}.amazonaws.com/model/{model_id}/{operation_path}"
            aws_request = AWSRequest(
                method="POST",
                url=bedrock_sign_url,
                data=body_bytes,
                headers=headers,
            )
            SigV4Auth(credentials, "bedrock", region).add_auth(aws_request)
            signed_headers = dict(aws_request.headers)
            logger.debug(f"[GATEWAY] SigV4 signed for: {bedrock_sign_url}")
            logger.debug(f"[GATEWAY] Sending to gateway: {full_gateway_url}")
            with httpx.Client(timeout=float(gw_settings.timeout)) as client:
                response = client.post(
                    full_gateway_url,
                    content=body_bytes,
                    headers=signed_headers,
                )
                response.raise_for_status()
                response_data = response.json()
        else:
            # api_key (default): Bearer token
            with httpx.Client(timeout=float(gw_settings.timeout)) as client:
                response = client.post(
                    full_gateway_url,
                    json=request_body,
                    headers={
                        "Authorization": f"Bearer {gw_settings.api_key}",
                        "Content-Type": "application/json",
                        "x-amzn-bedrock-accept-type": "application/json",
                    },
                )
                response.raise_for_status()
                response_data = response.json()
        
        logger.debug(f"[GATEWAY] Received native Bedrock response from gateway")
        set_inspection_context(decision=Decision.allow(reasons=["Gateway handled inspection"]), done=True)
        
        # Ensure ResponseMetadata is present (boto3 always includes it)
        if "ResponseMetadata" not in response_data:
            response_data["ResponseMetadata"] = {
                "RequestId": "gateway-handled",
                "HTTPStatusCode": 200,
                "HTTPHeaders": {},
                "RetryAttempts": 0,
            }
        
        # For InvokeModel operations, wrap response in boto3 format
        # boto3 InvokeModel returns {"body": <StreamingBody>, "contentType": ..., "ResponseMetadata": ...}
        # but Converse returns a plain dict which is already the correct format
        if operation_name in {"InvokeModel", "InvokeModelWithResponseStream"}:
            wrapped_response = {
                "body": _StreamingBodyWrapper(json.dumps(response_data).encode("utf-8")),
                "contentType": "application/json",
                "ResponseMetadata": response_data["ResponseMetadata"],
            }
            return wrapped_response
        
        return response_data
        
    except httpx.HTTPStatusError as e:
        logger.error(f"[GATEWAY] HTTP error: {e}")
        # Log status code and truncated body for debugging (avoid leaking sensitive data)
        try:
            body_preview = e.response.text[:200] if hasattr(e.response, 'text') else ""
            logger.error(f"[GATEWAY] HTTP {e.response.status_code} — body preview: {body_preview}")
        except Exception:
            pass
        if gw_settings.fail_open:
            # fail_open=True: allow request to proceed by re-raising original error
            logger.warning(f"[GATEWAY] fail_open=True, re-raising original HTTP error for caller to handle")
            set_inspection_context(decision=Decision.allow(reasons=["Gateway error, fail_open=True"]), done=True)
            raise  # Re-raise original HTTP error, not SecurityPolicyError
        else:
            # fail_open=False: block the request with SecurityPolicyError
            raise SecurityPolicyError(
                Decision.block(reasons=["Gateway unavailable"]),
                f"Gateway HTTP error: {e}"
            )
    except Exception as e:
        logger.error(f"[GATEWAY] Error: {e}")
        if gw_settings.fail_open:
            logger.warning(f"[GATEWAY] fail_open=True, re-raising original error for caller to handle")
            set_inspection_context(decision=Decision.allow(reasons=["Gateway error, fail_open=True"]), done=True)
            raise  # Re-raise original error
        raise


def _handle_bedrock_gateway_call_streaming(operation_name: str, api_params: Dict, gw_settings):
    """
    Handle Bedrock streaming call via AI Defense Gateway with native format.
    
    Sends native Bedrock request to the gateway and wraps response for streaming.
    
    Args:
        operation_name: Bedrock operation name (ConverseStream, InvokeModelWithResponseStream)
        api_params: Bedrock API parameters
        gw_settings: Resolved gateway settings
        
    Returns:
        Dict with 'stream' key containing event wrapper
    """
    # Use non-streaming gateway call and wrap result for streaming compatibility
    bedrock_response = _handle_bedrock_gateway_call(operation_name.replace("Stream", ""), api_params, gw_settings)
    
    # Wrap the response in a streaming-like format
    return {"stream": _BedrockFakeStreamWrapper(bedrock_response)}


class _BedrockFakeStreamWrapper:
    """
    Wrapper to make a non-streaming Bedrock response look like a streaming EventStream.
    
    This yields the full response as a series of events that match Bedrock's
    ConverseStream event format.
    """
    
    def __init__(self, bedrock_response: Dict):
        self._response = bedrock_response
        self._events = None
        self._finished = False
    
    def _generate_events(self):
        """Generate Bedrock stream events from the response."""
        message = self._response.get("output", {}).get("message", {})
        role = message.get("role", "assistant")
        content = message.get("content", [])
        stop_reason = self._response.get("stopReason", "end_turn")
        usage = self._response.get("usage", {})
        
        # messageStart
        yield {"messageStart": {"role": role}}
        
        # Process content blocks
        for idx, block in enumerate(content):
            if "text" in block:
                # contentBlockStart for text
                yield {
                    "contentBlockStart": {
                        "contentBlockIndex": idx,
                        "start": {"text": ""},
                    }
                }
                # contentBlockDelta with the text
                yield {
                    "contentBlockDelta": {
                        "contentBlockIndex": idx,
                        "delta": {"text": block["text"]},
                    }
                }
                # contentBlockStop
                yield {"contentBlockStop": {"contentBlockIndex": idx}}
                
            elif "toolUse" in block:
                tool_use = block["toolUse"]
                # contentBlockStart for tool use
                yield {
                    "contentBlockStart": {
                        "contentBlockIndex": idx,
                        "start": {
                            "toolUse": {
                                "toolUseId": tool_use.get("toolUseId", ""),
                                "name": tool_use.get("name", ""),
                            }
                        },
                    }
                }
                # contentBlockDelta with the input
                yield {
                    "contentBlockDelta": {
                        "contentBlockIndex": idx,
                        "delta": {
                            "toolUse": {"input": json.dumps(tool_use.get("input", {}))}
                        },
                    }
                }
                # contentBlockStop
                yield {"contentBlockStop": {"contentBlockIndex": idx}}
        
        # messageStop
        yield {"messageStop": {"stopReason": stop_reason}}
        
        # metadata
        yield {
            "metadata": {
                "usage": usage,
                "metrics": self._response.get("metrics", {"latencyMs": 0}),
            }
        }
    
    def __iter__(self):
        return self
    
    def __next__(self):
        if self._events is None:
            self._events = self._generate_events()
        try:
            return next(self._events)
        except StopIteration:
            raise
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        if self._events is None:
            self._events = self._generate_events()
        try:
            return next(self._events)
        except StopIteration:
            raise StopAsyncIteration
    
    def close(self):
        """Close the stream."""
        pass



# Maximum buffer size for streaming inspection (1MB)
MAX_STREAMING_BUFFER_SIZE = 1_000_000


class _ConverseStreamInspectionWrapper:
    """Wraps a ConverseStream EventStream to accumulate and inspect response text.

    Bedrock ConverseStream yields dict events:
      - messageStart, contentBlockStart, contentBlockDelta, contentBlockStop,
        messageStop, metadata.
    Text arrives in contentBlockDelta events under ``delta.text``.
    This wrapper transparently yields every event while buffering text for
    incremental and final AI Defense inspection.
    """

    def __init__(
        self,
        stream: Iterator,
        messages: List[Dict[str, Any]],
        metadata: Dict[str, Any],
    ):
        self._stream = iter(stream)
        self._messages = messages
        self._metadata = metadata
        self._buffer = ""
        self._inspector = _get_inspector()
        self._chunk_count = 0
        self._inspect_interval = 10
        self._final_inspection_done = False

    def __iter__(self):
        return self

    def __next__(self):
        try:
            event = next(self._stream)
        except StopIteration:
            self._perform_final_inspection()
            raise
        except Exception as e:
            logger.warning(
                "ConverseStream error, performing final inspection on buffered content: %s", e
            )
            self._perform_final_inspection()
            raise

        try:
            delta = (event.get("contentBlockDelta") or {}).get("delta") or {}
            text = delta.get("text")
            if text:
                if len(self._buffer) < MAX_STREAMING_BUFFER_SIZE:
                    remaining = MAX_STREAMING_BUFFER_SIZE - len(self._buffer)
                    self._buffer += text[:remaining]
                self._chunk_count += 1
                if self._chunk_count % self._inspect_interval == 0:
                    self._inspect_buffer()
        except Exception as e:
            logger.warning("Error processing ConverseStream event: %s", e)

        return event

    # Async iteration support (ConverseStream may be consumed asynchronously)
    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            event = next(self._stream)
        except StopIteration:
            self._perform_final_inspection()
            raise StopAsyncIteration
        except Exception as e:
            logger.warning(
                "ConverseStream async error, performing final inspection: %s", e
            )
            self._perform_final_inspection()
            raise

        try:
            delta = (event.get("contentBlockDelta") or {}).get("delta") or {}
            text = delta.get("text")
            if text:
                if len(self._buffer) < MAX_STREAMING_BUFFER_SIZE:
                    remaining = MAX_STREAMING_BUFFER_SIZE - len(self._buffer)
                    self._buffer += text[:remaining]
                self._chunk_count += 1
                if self._chunk_count % self._inspect_interval == 0:
                    self._inspect_buffer()
        except Exception as e:
            logger.warning("Error processing ConverseStream async event: %s", e)

        return event

    def close(self):
        """Close the underlying stream."""
        if hasattr(self._stream, "close"):
            self._stream.close()

    def _perform_final_inspection(self) -> None:
        if self._final_inspection_done:
            return
        self._final_inspection_done = True
        if self._buffer:
            self._inspect_buffer()
        set_inspection_context(done=True)

    def _inspect_buffer(self) -> None:
        if not self._buffer or not _should_inspect():
            return

        buffer_to_inspect = self._buffer[:MAX_STREAMING_BUFFER_SIZE]
        messages_with_response = self._messages + [
            {"role": "assistant", "content": buffer_to_inspect}
        ]
        try:
            decision = self._inspector.inspect_conversation(
                messages_with_response, self._metadata,
            )
            set_inspection_context(decision=decision)
            _enforce_decision(decision)
        except SecurityPolicyError:
            raise
        except Exception as e:
            _handle_patcher_error(e, "Bedrock ConverseStream inspection")


class _InvokeModelStreamInspectionWrapper:
    """Wraps an InvokeModelWithResponseStream body to inspect accumulated chunks.

    The EventStream yields ``{"chunk": {"bytes": b'...'}}`` events.  The bytes
    contain JSON-encoded partial responses whose format depends on the model
    (e.g. Claude returns ``{"type": "content_block_delta", "delta": {"text": "..."}}``,
    Titan returns ``{"outputText": "..."}``).

    This wrapper accumulates text from the decoded chunks, inspects
    periodically, and performs a final inspection when the stream ends.
    """

    def __init__(
        self,
        stream: Iterator,
        messages: List[Dict[str, Any]],
        metadata: Dict[str, Any],
        model_id: str,
    ):
        self._stream = iter(stream)
        self._messages = messages
        self._metadata = metadata
        self._model_id = model_id
        self._buffer = ""
        self._inspector = _get_inspector()
        self._chunk_count = 0
        self._inspect_interval = 10
        self._final_inspection_done = False

    def __iter__(self):
        return self

    def __next__(self):
        try:
            event = next(self._stream)
        except StopIteration:
            self._perform_final_inspection()
            raise
        except Exception as e:
            logger.warning(
                "InvokeModelStream error, performing final inspection: %s", e
            )
            self._perform_final_inspection()
            raise

        self._accumulate(event)
        return event

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            event = next(self._stream)
        except StopIteration:
            self._perform_final_inspection()
            raise StopAsyncIteration
        except Exception as e:
            logger.warning(
                "InvokeModelStream async error, performing final inspection: %s", e
            )
            self._perform_final_inspection()
            raise

        self._accumulate(event)
        return event

    def close(self):
        if hasattr(self._stream, "close"):
            self._stream.close()

    def _accumulate(self, event) -> None:
        try:
            chunk_bytes = (event.get("chunk") or {}).get("bytes")
            if not chunk_bytes:
                return
            data = json.loads(chunk_bytes)
            text = self._extract_text(data)
            if text:
                if len(self._buffer) < MAX_STREAMING_BUFFER_SIZE:
                    remaining = MAX_STREAMING_BUFFER_SIZE - len(self._buffer)
                    self._buffer += text[:remaining]
                self._chunk_count += 1
                if self._chunk_count % self._inspect_interval == 0:
                    self._inspect_buffer()
        except Exception as e:
            logger.warning("Error accumulating InvokeModelStream chunk: %s", e)

    def _extract_text(self, data: dict) -> str:
        """Extract text from a streaming chunk based on model format."""
        # Claude content_block_delta
        delta = data.get("delta", {})
        if delta.get("type") == "text_delta":
            return delta.get("text", "")
        if "text" in delta:
            return delta["text"]
        # Titan
        if "outputText" in data:
            return data["outputText"]
        # Claude completion_delta (older streaming format)
        if "completion" in data:
            return data["completion"]
        return ""

    def _perform_final_inspection(self) -> None:
        if self._final_inspection_done:
            return
        self._final_inspection_done = True
        if self._buffer:
            self._inspect_buffer()
        set_inspection_context(done=True)

    def _inspect_buffer(self) -> None:
        if not self._buffer or not _should_inspect():
            return

        buffer_to_inspect = self._buffer[:MAX_STREAMING_BUFFER_SIZE]
        messages_with_response = self._messages + [
            {"role": "assistant", "content": buffer_to_inspect}
        ]
        try:
            decision = self._inspector.inspect_conversation(
                messages_with_response, self._metadata,
            )
            set_inspection_context(decision=decision)
            _enforce_decision(decision)
        except SecurityPolicyError:
            raise
        except Exception as e:
            _handle_patcher_error(e, "Bedrock InvokeModelStream inspection")


def _handle_agentcore_call(wrapped, instance, args, kwargs, operation_name: str, api_params: Dict):
    """
    Handle AgentCore operations (InvokeAgentRuntime).
    
    Routes to either gateway mode or API mode based on configuration.
    Uses Bedrock gateway configuration for gateway mode.
    
    Args:
        wrapped: Original wrapped function
        instance: The boto client instance
        args: Original args
        kwargs: Original kwargs
        operation_name: AgentCore operation name
        api_params: AgentCore API parameters
        
    Returns:
        AgentCore response
    """
    set_inspection_context(done=False)
    if not _should_inspect():
        logger.debug(f"[PATCHED CALL] AgentCore.{operation_name} - inspection skipped (mode=off or already done)")
        return wrapped(*args, **kwargs)
    
    # Gateway mode: route through AI Defense Gateway (uses Bedrock gateway config)
    gw_settings = resolve_gateway_settings("bedrock")
    if gw_settings:
        logger.debug(f"[PATCHED CALL] AgentCore.{operation_name} - Gateway mode - routing to AI Defense Gateway")
        return _handle_agentcore_gateway_call(operation_name, api_params, instance, gw_settings)
    
    # API mode: use LLMInspector for inspection
    return _handle_agentcore_api_mode(operation_name, api_params, wrapped, args, kwargs)


def _wrap_make_api_call(wrapped, instance, args, kwargs):
    """Wrapper for botocore BaseClient._make_api_call.
    
    Wraps LLM inspection with error handling to ensure LLM calls
    never crash due to inspection errors, respecting llm_fail_open setting.
    
    Supports both API mode (inspection via AI Defense API) and Gateway mode
    (routing through AI Defense Gateway with format conversion).
    
    Handles both Bedrock operations (InvokeModel, Converse, etc.) and
    AgentCore operations (InvokeAgentRuntime).
    """
    operation_name = args[0] if args else kwargs.get("operation_name", "")
    api_params = args[1] if len(args) > 1 else kwargs.get("api_params", {})
    
    # Check for AgentCore operations first (more specific check)
    if _is_agentcore_operation(operation_name, instance):
        return _handle_agentcore_call(wrapped, instance, args, kwargs, operation_name, api_params)
    
    # Only intercept Bedrock operations
    if not _is_bedrock_operation(operation_name):
        return wrapped(*args, **kwargs)
    
    # Reset inspection context for each new API call so successive calls
    # (e.g. bedrock-1 then bedrock-2) are each independently inspected.
    set_inspection_context(done=False)
    
    if not _should_inspect():
        logger.debug(f"[PATCHED CALL] Bedrock.{operation_name} - inspection skipped (mode=off or already done)")
        return wrapped(*args, **kwargs)
    
    # Extract messages based on operation type
    if operation_name in {"Converse", "ConverseStream"}:
        # Converse API uses messages directly in api_params
        model_id = api_params.get("modelId", "")
        messages = _parse_converse_messages(api_params)
    else:
        # InvokeModel uses body
        body = api_params.get("body", b"")
        model_id = api_params.get("modelId", "")
        
        if isinstance(body, str):
            body = body.encode()
        
        messages = _parse_bedrock_messages(body, model_id)
    
    metadata = get_inspection_context().metadata
    metadata["model_id"] = model_id
    
    mode = _state.get_llm_mode()
    integration_mode = _state.get_llm_integration_mode()
    logger.debug(f"╔══════════════════════════════════════════════════════════════")
    logger.debug(f"║ [PATCHED] LLM CALL: {model_id}")
    logger.debug(f"║ Operation: Bedrock.{operation_name} | LLM Mode: {mode} | Integration: {integration_mode}")
    logger.debug(f"╚══════════════════════════════════════════════════════════════")
    
    # Gateway mode: route through AI Defense Gateway with format conversion
    gw_settings = resolve_gateway_settings("bedrock")
    if gw_settings:
        logger.debug(f"[PATCHED CALL] Bedrock.{operation_name} - Gateway mode - routing to AI Defense Gateway")
        if operation_name == "Converse":
            return _handle_bedrock_gateway_call(operation_name, api_params, gw_settings)
        elif operation_name == "ConverseStream":
            return _handle_bedrock_gateway_call_streaming(operation_name, api_params, gw_settings)
        elif operation_name == "InvokeModel":
            return _handle_bedrock_gateway_call(operation_name, api_params, gw_settings)
        elif operation_name == "InvokeModelWithResponseStream":
            return _handle_bedrock_gateway_call_streaming(operation_name, api_params, gw_settings)
        else:
            logger.error(f"[PATCHED CALL] Unknown Bedrock operation in gateway mode: {operation_name}")
            raise SecurityPolicyError(
                Decision.block(reasons=[f"Unknown operation: {operation_name}"]),
                f"Gateway mode: unknown operation {operation_name}"
            )
    
    # API mode (default): use LLMInspector for inspection
    # Pre-call inspection with error handling
    if messages:
        try:
            logger.debug(f"[PATCHED CALL] Bedrock.{operation_name} - Request inspection ({len(messages)} messages)")
            inspector = _get_inspector()
            decision = inspector.inspect_conversation(messages, metadata)
            logger.debug(f"[PATCHED CALL] Bedrock.{operation_name} - Request decision: {decision.action}")
            set_inspection_context(decision=decision)
            _enforce_decision(decision)
        except SecurityPolicyError:
            raise
        except Exception as e:
            decision = _handle_patcher_error(e, f"Bedrock.{operation_name} pre-call")
            if decision:
                set_inspection_context(decision=decision)
    
    # Call original
    logger.debug(f"[PATCHED CALL] Bedrock.{operation_name} - calling original method")
    response = wrapped(*args, **kwargs)
    
    # Post-call inspection for non-streaming with error handling
    if operation_name not in {"InvokeModelWithResponseStream", "ConverseStream"}:
        try:
            assistant_content = ""
            
            if operation_name == "Converse":
                # Converse API returns structured response
                output = response.get("output", {})
                message = output.get("message", {})
                content = message.get("content", [])
                if isinstance(content, list):
                    assistant_content = " ".join(
                        c.get("text", "") for c in content if isinstance(c, dict) and "text" in c
                    )
            else:
                # InvokeModel returns body
                response_body = response.get("body")
                if response_body:
                    if hasattr(response_body, "read"):
                        response_content = response_body.read()
                        # Replace with wrapper that mimics StreamingBody interface
                        response["body"] = _StreamingBodyWrapper(response_content)
                    else:
                        response_content = response_body
                    
                    assistant_content = _parse_bedrock_response(response_content, model_id)
            
            if assistant_content and messages:
                logger.debug(f"[PATCHED CALL] Bedrock.{operation_name} - Response inspection (response: {len(assistant_content)} chars)")
                messages_with_response = messages + [
                    {"role": "assistant", "content": assistant_content}
                ]
                inspector = _get_inspector()
                decision = inspector.inspect_conversation(messages_with_response, metadata)
                logger.debug(f"[PATCHED CALL] Bedrock.{operation_name} - Response decision: {decision.action}")
                set_inspection_context(decision=decision, done=True)
                _enforce_decision(decision)
        except SecurityPolicyError:
            raise
        except Exception as e:
            _handle_patcher_error(e, f"Bedrock.{operation_name} post-call")
    else:
        # Wrap streaming responses for inspection
        if operation_name == "ConverseStream":
            stream = response.get("stream")
            if stream is not None:
                logger.debug(
                    f"[PATCHED CALL] Bedrock.{operation_name} - wrapping stream for inspection"
                )
                response["stream"] = _ConverseStreamInspectionWrapper(
                    stream, messages, metadata
                )
        elif operation_name == "InvokeModelWithResponseStream":
            body = response.get("body")
            if body is not None:
                logger.debug(
                    f"[PATCHED CALL] Bedrock.{operation_name} - wrapping stream for inspection"
                )
                response["body"] = _InvokeModelStreamInspectionWrapper(
                    body, messages, metadata, model_id
                )
    
    logger.debug(f"[PATCHED CALL] Bedrock.{operation_name} - complete")
    return response


def patch_bedrock() -> bool:
    """
    Patch boto3/botocore for automatic Bedrock inspection.
    
    Returns:
        True if patching was successful, False otherwise
    """
    if is_patched("bedrock"):
        logger.debug("Bedrock already patched, skipping")
        return True
    
    botocore = safe_import("botocore")
    if botocore is None:
        return False
    
    try:
        wrapt.wrap_function_wrapper(
            "botocore.client",
            "BaseClient._make_api_call",
            _wrap_make_api_call,
        )
        
        mark_patched("bedrock")
        logger.info("Bedrock/boto3 patched successfully")
        return True
    except Exception as e:
        logger.warning(f"Failed to patch Bedrock: {e}")
        return False


