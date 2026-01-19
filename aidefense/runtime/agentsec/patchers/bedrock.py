"""
Bedrock/boto3 client autopatching.

This module provides automatic inspection for AWS Bedrock LLM calls by patching
at the botocore level. This covers ALL Bedrock operations including:

- InvokeModel: Direct model invocation
- InvokeModelWithResponseStream: Streaming model invocation
- Converse: Chat-like Converse API
- ConverseStream: Streaming Converse API

By patching botocore.client.BaseClient._make_api_call, we intercept all Bedrock
operations regardless of which higher-level AWS SDK or wrapper is used.

Gateway Mode Support:
When AGENTSEC_LLM_INTEGRATION_MODE=gateway, Bedrock calls are sent directly
to the provider-specific AI Defense Gateway in native format.

Note: This satisfies roadmap item 21 (AWS Bedrock Client Autopatch) as the
botocore-level patching covers all Bedrock client interfaces.
"""

import json
import logging
import threading
from typing import Any, Dict, List, Optional

import wrapt

from .. import _state
from .._context import get_inspection_context, set_inspection_context
from ..decision import Decision
from ..exceptions import SecurityPolicyError
from ..inspectors.api_llm import LLMInspector
from . import is_patched, mark_patched
from ._base import safe_import

logger = logging.getLogger("aidefense.runtime.agentsec.patchers.bedrock")

# Bedrock operation names to intercept
BEDROCK_OPERATIONS = {"InvokeModel", "InvokeModelWithResponseStream", "Converse", "ConverseStream"}

# Global inspector instance with thread-safe initialization
_inspector: Optional[LLMInspector] = None
_inspector_lock = threading.Lock()


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
                    fail_open=_state.get_api_mode_fail_open_llm(),
                    default_rules=_state.get_llm_rules(),
                )
    return _inspector


def _is_gateway_mode() -> bool:
    """Check if LLM integration mode is 'gateway'."""
    return _state.get_llm_integration_mode() == "gateway"


def _should_use_gateway() -> bool:
    """Check if we should use gateway mode (gateway mode enabled, configured, and not skipped)."""
    from .._context import is_llm_skip_active
    if is_llm_skip_active():
        return False
    if not _is_gateway_mode():
        return False
    # Check if Bedrock gateway is properly configured
    gateway_url = _state.get_provider_gateway_url("bedrock")
    gateway_api_key = _state.get_provider_gateway_api_key("bedrock")
    return bool(gateway_url and gateway_api_key)


def _should_inspect() -> bool:
    """Check if we should inspect (not already done, mode is not off, and not skipped)."""
    from .._context import is_llm_skip_active
    if is_llm_skip_active():
        return False
    mode = _state.get_llm_mode()
    if mode == "off":
        return False
    ctx = get_inspection_context()
    return not ctx.done


def _enforce_decision(decision: Decision) -> None:
    """Enforce a decision if in enforce mode."""
    mode = _state.get_llm_mode()
    if mode == "on_enforce" and decision.action == "block":
        raise SecurityPolicyError(decision)


def _is_bedrock_operation(operation_name: str, api_params: Dict) -> bool:
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
    fail_open = _state.get_api_mode_fail_open_llm()
    
    error_type = type(error).__name__
    logger.warning(f"[{operation}] Inspection error: {error_type}: {error}")
    
    if fail_open:
        logger.warning(f"fail_open=True, allowing request despite inspection error")
        return Decision.allow(reasons=[f"Inspection error ({error_type}), fail_open=True"])
    else:
        logger.error(f"fail_open=False, blocking request due to inspection error")
        decision = Decision.block(reasons=[f"Inspection error: {error_type}: {error}"])
        raise SecurityPolicyError(decision, f"Inspection failed and fail_open=False: {error}")


def _handle_bedrock_gateway_call(operation_name: str, api_params: Dict) -> Dict:
    """
    Handle Bedrock call via AI Defense Gateway with native format.
    
    Sends native Bedrock request directly to the provider-specific gateway.
    The gateway handles the request in native Bedrock format - no conversion needed.
    
    Args:
        operation_name: Bedrock operation name (Converse, InvokeModel, etc.)
        api_params: Bedrock API parameters
        
    Returns:
        Bedrock-format response dict (native from gateway)
    """
    import httpx
    
    gateway_url = _state.get_provider_gateway_url("bedrock")
    gateway_api_key = _state.get_provider_gateway_api_key("bedrock")
    
    if not gateway_url or not gateway_api_key:
        logger.warning("Gateway mode enabled but Bedrock gateway not configured")
        raise SecurityPolicyError(
            Decision.block(reasons=["Bedrock gateway not configured"]),
            "Gateway mode enabled but AGENTSEC_BEDROCK_GATEWAY_URL not set"
        )
    
    model_id = api_params.get("modelId", "")
    
    # Send native Bedrock request to gateway
    logger.debug(f"[GATEWAY] Sending native Bedrock request to gateway")
    logger.debug(f"[GATEWAY] Operation: {operation_name}, Model: {model_id}")
    
    try:
        # Build request body based on operation type
        if operation_name in {"Converse", "ConverseStream"}:
            request_body = {
                "modelId": model_id,
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
            request_body["modelId"] = model_id
        
        # Send to gateway with native format
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                gateway_url,
                json=request_body,
                headers={
                    "Authorization": f"Bearer {gateway_api_key}",
                    "Content-Type": "application/json",
                    "X-Bedrock-Operation": operation_name,
                },
            )
            response.raise_for_status()
            response_data = response.json()
        
        logger.debug(f"[GATEWAY] Received native Bedrock response from gateway")
        set_inspection_context(decision=Decision.allow(reasons=["Gateway handled inspection"]), done=True)
        
        return response_data
        
    except httpx.HTTPStatusError as e:
        logger.error(f"[GATEWAY] HTTP error: {e}")
        if _state.get_gateway_mode_fail_open_llm():
            set_inspection_context(decision=Decision.allow(reasons=["Gateway error, fail_open=True"]), done=True)
            raise SecurityPolicyError(
                Decision.block(reasons=["Gateway unavailable"]),
                f"Gateway HTTP error: {e}"
            )
        raise
    except Exception as e:
        logger.error(f"[GATEWAY] Error: {e}")
        raise


def _handle_bedrock_gateway_call_streaming(operation_name: str, api_params: Dict):
    """
    Handle Bedrock streaming call via AI Defense Gateway with native format.
    
    Sends native Bedrock request to the gateway and wraps response for streaming.
    
    Args:
        operation_name: Bedrock operation name (ConverseStream, InvokeModelWithResponseStream)
        api_params: Bedrock API parameters
        
    Returns:
        Dict with 'stream' key containing event wrapper
    """
    # Use non-streaming gateway call and wrap result for streaming compatibility
    bedrock_response = _handle_bedrock_gateway_call(operation_name.replace("Stream", ""), api_params)
    
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


class _BedrockEventStreamWrapper:
    """
    Wrapper to make our generator look like a Bedrock EventStream.
    
    Bedrock streaming responses have a 'stream' attribute that is iterable
    and yields event dicts. Some SDKs also expect __iter__ to work.
    """
    
    def __init__(self, event_generator):
        self._generator = event_generator
        self._events = None
    
    def __iter__(self):
        return self
    
    def __next__(self):
        if self._events is None:
            self._events = iter(self._generator)
        return next(self._events)
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        if self._events is None:
            self._events = iter(self._generator)
        try:
            return next(self._events)
        except StopIteration:
            raise StopAsyncIteration
    
    def close(self):
        """Close the stream."""
        pass


def _wrap_make_api_call(wrapped, instance, args, kwargs):
    """Wrapper for botocore BaseClient._make_api_call.
    
    Wraps LLM inspection with error handling to ensure LLM calls
    never crash due to inspection errors, respecting llm_fail_open setting.
    
    Supports both API mode (inspection via AI Defense API) and Gateway mode
    (routing through AI Defense Gateway with format conversion).
    """
    operation_name = args[0] if args else kwargs.get("operation_name", "")
    api_params = args[1] if len(args) > 1 else kwargs.get("api_params", {})
    
    # Only intercept Bedrock operations
    if not _is_bedrock_operation(operation_name, api_params):
        return wrapped(*args, **kwargs)
    
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
    logger.debug(f"")
    logger.debug(f"╔══════════════════════════════════════════════════════════════")
    logger.debug(f"║ [PATCHED] LLM CALL: {model_id}")
    logger.debug(f"║ Operation: Bedrock.{operation_name} | LLM Mode: {mode} | Integration: {integration_mode}")
    logger.debug(f"╚══════════════════════════════════════════════════════════════")
    
    # Gateway mode: route through AI Defense Gateway with format conversion
    if _should_use_gateway():
        logger.debug(f"[PATCHED CALL] Bedrock.{operation_name} - Gateway mode - routing to AI Defense Gateway")
        if operation_name == "Converse":
            return _handle_bedrock_gateway_call(operation_name, api_params)
        elif operation_name == "ConverseStream":
            return _handle_bedrock_gateway_call_streaming(operation_name, api_params)
        elif operation_name == "InvokeModel":
            return _handle_bedrock_gateway_call(operation_name, api_params)
        elif operation_name == "InvokeModelWithResponseStream":
            return _handle_bedrock_gateway_call_streaming(operation_name, api_params)
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
                        # Reset stream for caller
                        import io
                        response["body"] = io.BytesIO(response_content)
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
            logger.warning(f"[Bedrock.{operation_name} post-call] Inspection error: {e}")
    else:
        logger.debug(f"[PATCHED CALL] Bedrock.{operation_name} - streaming response, Response inspection deferred")
    
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
