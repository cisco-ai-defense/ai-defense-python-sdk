"""
OpenAI client autopatching.

This module provides automatic inspection for OpenAI SDK calls by patching
the resource classes shared by both OpenAI and AzureOpenAI clients:

- chat.completions.create() and acreate()
- responses.create() and acreate() (if available)

Coverage includes:
- OpenAI: Standard OpenAI client
- AzureOpenAI: Azure OpenAI Service client (uses same resource classes)

Both clients share the same underlying Completions resource, so patching
at that level covers all client variants automatically.

Note: This satisfies roadmap item 23 (Azure OpenAI Autopatch) as the
patch covers AzureOpenAI without requiring separate handling.
"""

import logging
import threading
from typing import Any, Dict, Iterator, List, Optional

import wrapt

from .. import _state
from .._context import clear_inspection_context, get_inspection_context, set_inspection_context
from ..decision import Decision
from ..exceptions import SecurityPolicyError
from ..inspectors.api_llm import LLMInspector
from ..inspectors.gateway_llm import GatewayClient
from . import is_patched, mark_patched
from ._base import safe_import

logger = logging.getLogger("aidefense.runtime.agentsec.patchers.openai")

# Global inspector instance with thread-safe initialization
_inspector: Optional[LLMInspector] = None
_inspector_lock = threading.Lock()

# Global gateway client instance
_gateway_client: Optional[GatewayClient] = None
_gateway_lock = threading.Lock()


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


def _detect_provider(instance) -> str:
    """
    Detect whether the client is OpenAI or AzureOpenAI.
    
    Args:
        instance: The Completions instance (from chat.completions)
        
    Returns:
        "azure_openai" if Azure client, otherwise "openai"
    """
    try:
        client = getattr(instance, '_client', None)
        if client is not None:
            client_type = type(client).__name__
            if client_type == 'AzureOpenAI':
                return "azure_openai"
            # Also check base_url for Azure
            base_url = str(getattr(client, 'base_url', ''))
            if 'azure' in base_url.lower():
                return "azure_openai"
    except Exception:
        pass
    return "openai"


def _get_azure_api_version(instance) -> Optional[str]:
    """
    Extract the API version from an Azure OpenAI client.
    
    The api_version can be stored in different places depending on how the client was created:
    - AzureOpenAI SDK: client._api_version
    - LangChain: client._api_version  
    - Strands/OpenAI with default_query: client._default_query["api-version"]
    
    Args:
        instance: The Completions instance (from chat.completions)
        
    Returns:
        API version string or None if not available
    """
    try:
        client = getattr(instance, '_client', None)
        if client is not None:
            # AzureOpenAI client stores api_version in _api_version
            api_version = getattr(client, '_api_version', None)
            if api_version:
                return str(api_version)
            # Also try api_version directly
            api_version = getattr(client, 'api_version', None)
            if api_version:
                return str(api_version)
            # Check default_query (Strands/OpenAI with client_args)
            # Try _default_query, default_query, and _custom_query (OpenAI v1)
            for query_attr in ['_default_query', 'default_query', '_custom_query']:
                query_params = getattr(client, query_attr, None)
                if query_params and isinstance(query_params, dict):
                    api_version = query_params.get('api-version')
                    if api_version:
                        return str(api_version)
    except Exception:
        pass
    return None


def _get_azure_deployment_name(instance, kwargs: Dict[str, Any]) -> Optional[str]:
    """
    Extract the Azure deployment name from the client or kwargs.
    
    For Azure OpenAI, the deployment name can come from:
    1. kwargs["model"] - standard way
    2. The client's base_url which contains /deployments/{name}/
    3. The client's _azure_deployment attribute (LangChain sets this)
    
    Args:
        instance: The Completions instance (from chat.completions)
        kwargs: Call kwargs that may contain "model"
        
    Returns:
        Deployment name string or None if not available
    """
    import re
    
    # First try kwargs["model"] - this is the standard way
    model = kwargs.get("model")
    if model:
        return str(model)
    
    try:
        client = getattr(instance, '_client', None)
        if client is not None:
            # Try _azure_deployment (LangChain/some SDKs set this)
            deployment = getattr(client, '_azure_deployment', None)
            if deployment:
                return str(deployment)
            
            # Try azure_deployment 
            deployment = getattr(client, 'azure_deployment', None)
            if deployment:
                return str(deployment)
            
            # Extract from base_url: .../deployments/{name}/...
            base_url = str(getattr(client, 'base_url', ''))
            match = re.search(r'/deployments/([^/]+)', base_url)
            if match:
                return match.group(1)
    except Exception:
        pass
    
    return None


def _should_use_gateway(provider: str = "openai") -> bool:
    """
    Check if we should use gateway mode (gateway mode enabled, configured, and not skipped).
    
    Args:
        provider: Provider name - "openai" or "azure_openai"
    """
    from .._context import is_llm_skip_active
    if is_llm_skip_active():
        return False
    if not _is_gateway_mode():
        return False
    # Check if gateway is properly configured for this provider
    gateway_url = _state.get_provider_gateway_url(provider)
    gateway_api_key = _state.get_provider_gateway_api_key(provider)
    return bool(gateway_url and gateway_api_key)


def _normalize_messages(messages: Any) -> List[Dict[str, Any]]:
    """
    Normalize messages to standard format for AI Defense API.
    
    AI Defense only supports user/assistant/system roles.
    - Skips 'tool' role messages (tool results)
    - Skips 'function' role messages (legacy function results)
    - Converts assistant messages with tool_calls to include tool request info
    
    TBD: This is a workaround for AI Defense API not supporting OpenAI function
    calling format (role: "tool", tool_calls array). When AI Defense adds support
    for these message types, this normalization should be updated to preserve the
    full message structure for proper inspection of tool calls and responses.
    See: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/400
    """
    if not isinstance(messages, list):
        return []
    
    result = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content") or ""
        
        # Handle content that's a list of content blocks (OpenAI/Strands format)
        # Convert to string for AI Defense API compatibility
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    # Handle {"type": "text", "text": "..."} format
                    if block.get("type") == "text" and "text" in block:
                        text_parts.append(block["text"])
                    # Handle {"text": "..."} format
                    elif "text" in block:
                        text_parts.append(block["text"])
                elif isinstance(block, str):
                    text_parts.append(block)
            content = "\n".join(text_parts)
        
        # Skip tool/function response messages - AI Defense doesn't support these roles
        if role in ("tool", "function"):
            continue
        
        # Handle assistant messages that triggered tool calls
        if role == "assistant" and m.get("tool_calls"):
            # Include info about what tool was called
            tool_names = [tc.get("function", {}).get("name", "unknown") 
                         for tc in m.get("tool_calls", [])]
            tool_info = f"[Called tools: {', '.join(tool_names)}]"
            content = f"{content} {tool_info}" if content else tool_info
        
        # Only include messages with actual content
        if content:
            result.append({"role": role, "content": content})
    
    return result


def _extract_assistant_content(response: Any) -> str:
    """Extract assistant content from OpenAI response."""
    try:
        if hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            if hasattr(choice, "message"):
                return choice.message.content or ""
            elif hasattr(choice, "text"):
                return choice.text or ""
    except Exception as e:
        logger.debug(f"Error extracting assistant content: {e}")
    return ""


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


class StreamingInspectionWrapper:
    """Wrapper for streaming responses with incremental inspection."""
    
    def __init__(self, stream: Iterator, messages: List[Dict[str, Any]], metadata: Dict[str, Any]):
        self._stream = stream
        self._messages = messages
        self._metadata = metadata
        self._buffer = ""
        self._inspector = _get_inspector()
        self._chunk_count = 0
        self._inspect_interval = 10  # Inspect every N chunks
    
    def __iter__(self):
        return self
    
    def __next__(self):
        chunk = next(self._stream)
        
        # Extract content from chunk
        try:
            if hasattr(chunk, "choices") and chunk.choices:
                delta = chunk.choices[0].delta
                if hasattr(delta, "content") and delta.content:
                    self._buffer += delta.content
                    self._chunk_count += 1
                    
                    # Incremental inspection
                    if self._chunk_count % self._inspect_interval == 0:
                        self._inspect_buffer()
        except Exception as e:
            logger.debug(f"Error processing streaming chunk: {e}")
        
        return chunk
    
    def _inspect_buffer(self) -> None:
        """Inspect the buffered content."""
        if not self._buffer or not _should_inspect():
            return
        
        messages_with_response = self._messages + [
            {"role": "assistant", "content": self._buffer}
        ]
        
        try:
            decision = self._inspector.inspect_conversation(
                messages_with_response,
                self._metadata,
            )
            set_inspection_context(decision=decision, done=True)
            _enforce_decision(decision)
        except SecurityPolicyError:
            raise
        except Exception as e:
            logger.warning(f"Streaming inspection error: {e}")


class AsyncStreamingInspectionWrapper:
    """Async wrapper for streaming responses with incremental inspection."""
    
    def __init__(self, stream: Any, messages: List[Dict[str, Any]], metadata: Dict[str, Any]):
        self._stream = stream
        self._messages = messages
        self._metadata = metadata
        self._buffer = ""
        self._inspector = _get_inspector()
        self._chunk_count = 0
        self._inspect_interval = 10
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        chunk = await self._stream.__anext__()
        
        try:
            if hasattr(chunk, "choices") and chunk.choices:
                delta = chunk.choices[0].delta
                if hasattr(delta, "content") and delta.content:
                    self._buffer += delta.content
                    self._chunk_count += 1
                    
                    if self._chunk_count % self._inspect_interval == 0:
                        await self._inspect_buffer()
        except StopAsyncIteration:
            raise
        except Exception as e:
            logger.debug(f"Error processing async streaming chunk: {e}")
        
        return chunk
    
    async def _inspect_buffer(self) -> None:
        """Inspect the buffered content asynchronously."""
        if not self._buffer or not _should_inspect():
            return
        
        messages_with_response = self._messages + [
            {"role": "assistant", "content": self._buffer}
        ]
        
        try:
            decision = await self._inspector.ainspect_conversation(
                messages_with_response,
                self._metadata,
            )
            set_inspection_context(decision=decision, done=True)
            _enforce_decision(decision)
        except SecurityPolicyError:
            raise
        except Exception as e:
            logger.warning(f"Async streaming inspection error: {e}")


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
        logger.warning(f"llm_fail_open=True, allowing request despite inspection error")
        return Decision.allow(reasons=[f"Inspection error ({error_type}), fail_open=True"])
    else:
        logger.error(f"llm_fail_open=False, blocking request due to inspection error")
        decision = Decision.block(reasons=[f"Inspection error: {error_type}: {error}"])
        raise SecurityPolicyError(decision, f"Inspection failed and fail_open=False: {error}")


def _wrap_chat_completions_create(wrapped, instance, args, kwargs):
    """Wrapper for chat.completions.create.
    
    Wraps LLM inspection with error handling to ensure LLM calls
    never crash due to inspection errors, respecting llm_fail_open setting.
    
    Supports two integration modes:
    - "api" (default): Use LLMInspector to inspect, then call original method
    - "gateway": Route request through AI Defense Gateway (gateway handles inspection)
    """
    model = kwargs.get("model", "unknown")
    
    if not _should_inspect():
        logger.debug(f"[PATCHED CALL] OpenAI.chat.completions.create - inspection skipped (mode=off or already done)")
        return wrapped(*args, **kwargs)
    
    # Detect provider (OpenAI vs Azure OpenAI)
    provider = _detect_provider(instance)
    
    # Extract Azure-specific info if using Azure OpenAI
    azure_api_version = None
    azure_deployment_name = None
    if provider == "azure_openai":
        azure_api_version = _get_azure_api_version(instance)
        azure_deployment_name = _get_azure_deployment_name(instance, kwargs)
    
    messages = kwargs.get("messages", [])
    normalized = _normalize_messages(messages)
    metadata = get_inspection_context().metadata
    stream = kwargs.get("stream", False)
    
    mode = _state.get_llm_mode()
    integration_mode = _state.get_llm_integration_mode()
    logger.debug(f"")
    logger.debug(f"╔══════════════════════════════════════════════════════════════")
    logger.debug(f"║ [PATCHED] LLM CALL: {model}")
    logger.debug(f"║ Operation: OpenAI.chat.completions.create | LLM Mode: {mode} | Integration: {integration_mode} | Provider: {provider}")
    logger.debug(f"╚══════════════════════════════════════════════════════════════")
    
    # Gateway mode: route through AI Defense Gateway
    if _should_use_gateway(provider):
        logger.debug(f"[PATCHED CALL] Gateway mode ({provider}) - routing to AI Defense Gateway")
        return _handle_gateway_call_sync(kwargs, stream, normalized, metadata, provider, azure_api_version, azure_deployment_name)
    
    # API mode (default): use LLMInspector for inspection
    # Pre-call inspection with error handling
    try:
        logger.debug(f"[PATCHED CALL] OpenAI.chat.completions.create - Request inspection ({len(normalized)} messages)")
        inspector = _get_inspector()
        decision = inspector.inspect_conversation(normalized, metadata)
        logger.debug(f"[PATCHED CALL] OpenAI.chat.completions.create - Request decision: {decision.action}")
        set_inspection_context(decision=decision)
        _enforce_decision(decision)
    except SecurityPolicyError:
        # Re-raise SecurityPolicyError (expected in enforce mode or from fail_open=False)
        raise
    except Exception as e:
        # Unexpected error during inspection - handle based on fail_open
        decision = _handle_patcher_error(e, "OpenAI.chat.completions.create pre-call")
        if decision:
            set_inspection_context(decision=decision)
    
    # Call the original
    logger.debug(f"[PATCHED CALL] OpenAI.chat.completions.create - calling original method")
    response = wrapped(*args, **kwargs)
    
    # Handle streaming vs non-streaming
    if stream:
        logger.debug(f"[PATCHED CALL] OpenAI.chat.completions.create - streaming response, wrapping for inspection")
        return StreamingInspectionWrapper(response, normalized, metadata)
    
    # Post-call inspection for non-streaming with error handling
    try:
        assistant_content = _extract_assistant_content(response)
        if assistant_content:
            logger.debug(f"[PATCHED CALL] OpenAI.chat.completions.create - Response inspection (response: {len(assistant_content)} chars)")
            messages_with_response = normalized + [
                {"role": "assistant", "content": assistant_content}
            ]
            inspector = _get_inspector()
            decision = inspector.inspect_conversation(messages_with_response, metadata)
            logger.debug(f"[PATCHED CALL] OpenAI.chat.completions.create - Response decision: {decision.action}")
            set_inspection_context(decision=decision, done=True)
            _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as e:
        # Log post-call errors but don't block - we've already made the call
        logger.warning(f"[OpenAI.chat.completions.create post-call] Inspection error: {e}")
    
    logger.debug(f"[PATCHED CALL] OpenAI.chat.completions.create - complete")
    return response


def _handle_gateway_call_sync(kwargs: Dict[str, Any], stream: bool, normalized: List[Dict], metadata: Dict, provider: str = "openai", azure_api_version: Optional[str] = None, azure_deployment_name: Optional[str] = None) -> Any:
    """
    Handle synchronous gateway call.
    
    Routes the request through provider-specific AI Defense Gateway, which handles 
    inspection and proxying to the actual LLM provider.
    
    Args:
        kwargs: Original call kwargs (model, messages, etc.)
        stream: Whether streaming is requested
        normalized: Normalized messages for context
        metadata: Inspection metadata
        provider: Provider name - "openai" or "azure_openai"
        azure_api_version: Azure OpenAI API version (only for azure_openai provider)
        azure_deployment_name: Azure deployment name (only for azure_openai provider)
        
    Returns:
        Response from gateway (same format as OpenAI response)
    """
    import httpx
    
    gateway_url = _state.get_provider_gateway_url(provider)
    gateway_api_key = _state.get_provider_gateway_api_key(provider)
    
    if not gateway_url or not gateway_api_key:
        logger.warning(f"Gateway mode enabled but {provider} gateway not configured")
        set_inspection_context(decision=Decision.allow(reasons=[f"{provider} gateway not configured"]), done=True)
        raise SecurityPolicyError(
            Decision.block(reasons=[f"{provider} gateway not configured"]),
            f"Gateway mode enabled but AGENTSEC_{provider.upper()}_GATEWAY_URL not set"
        )
    
    # Build request body (OpenAI-compatible format)
    request_body = {
        "model": kwargs.get("model"),
        "messages": kwargs.get("messages", []),
    }
    
    # Copy optional parameters
    for param in ["temperature", "max_tokens", "top_p", "n", "stop", "presence_penalty", 
                  "frequency_penalty", "logit_bias", "user", "tools", "tool_choice",
                  "response_format", "seed"]:
        if param in kwargs:
            request_body[param] = kwargs[param]
    
    # Note: Gateway mode does NOT support streaming yet - always use non-streaming
    # The gateway returns JSON response, not SSE stream
    if stream:
        logger.debug(f"[GATEWAY] Streaming requested but gateway returns JSON - will convert response")
    
    try:
        # Construct full URL based on provider
        full_url = gateway_url.rstrip('/')
        
        if provider == "azure_openai":
            # Azure OpenAI gateway URL format:
            # {gateway_base}/openai/deployments/{deployment_name}/chat/completions[?api-version={api_version}]
            # Use azure_deployment_name (extracted from client) or fall back to kwargs["model"]
            deployment_name = azure_deployment_name or kwargs.get("model", "")
            if 'chat/completions' not in full_url:
                full_url = f"{full_url}/openai/deployments/{deployment_name}/chat/completions"
                if azure_api_version:
                    full_url = f"{full_url}?api-version={azure_api_version}"
        else:
            # OpenAI gateway URL format: {gateway_base}/v1/chat/completions
            if 'chat/completions' not in full_url:
                full_url = full_url + '/v1/chat/completions'
        
        logger.debug(f"[GATEWAY] Sending request to {provider} gateway: {full_url}")
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                full_url,
                json=request_body,
                headers={
                    "Authorization": f"Bearer {gateway_api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            response_data = response.json()
        
        logger.debug(f"[GATEWAY] Received response from {provider} gateway")
        set_inspection_context(decision=Decision.allow(reasons=["Gateway handled inspection"]), done=True)
        
        # Convert dict response to OpenAI-like object
        response_obj = _dict_to_openai_response(response_data)
        
        # If streaming was requested, wrap in iterable
        if stream:
            return _FakeStreamWrapper(response_obj)
        
        return response_obj
        
    except httpx.HTTPStatusError as e:
        logger.error(f"[GATEWAY] HTTP error: {e}")
        if _state.get_gateway_mode_fail_open_llm():
            set_inspection_context(decision=Decision.allow(reasons=["Gateway error, fail_open=True"]), done=True)
            raise SecurityPolicyError(
                Decision.block(reasons=["Gateway unavailable"]),
                f"Gateway HTTP error: {e}"
            )
        raise
    except SecurityPolicyError:
        raise
    except Exception as e:
        logger.error(f"[GATEWAY] Error: {e}")
        raise


class _FakeStreamWrapper:
    """Wraps a complete response as a sync iterator for streaming compatibility.
    
    When gateway mode returns a non-streaming response but the caller expects
    streaming, this wrapper yields the response as a single chunk with proper
    streaming format.
    """
    
    def __init__(self, response):
        self.response = response
        self._yielded = False
    
    def __iter__(self):
        return self
    
    def __next__(self):
        if self._yielded:
            raise StopIteration
        self._yielded = True
        
        # Convert complete response to streaming chunk format
        chunk = _create_stream_chunk_from_response(self.response)
        return chunk


def _dict_to_openai_response(data: Dict[str, Any]) -> Any:
    """
    Convert dictionary response to OpenAI-like response object.
    
    Creates a simple object that mimics OpenAI's ChatCompletion response structure
    so that calling code can access response.choices[0].message.content etc.
    """
    class ToolCall:
        def __init__(self, tool_call_data):
            self.id = tool_call_data.get("id")
            self.index = tool_call_data.get("index", 0)
            self.type = tool_call_data.get("type", "function")
            function_data = tool_call_data.get("function", {})
            self.function = type("Function", (), {
                "name": function_data.get("name"),
                "arguments": function_data.get("arguments"),
            })()
    
    class Message:
        def __init__(self, message_data):
            self._data = message_data  # Store original data for dict conversion
            self.role = message_data.get("role", "assistant")
            self.content = message_data.get("content")
            self.function_call = message_data.get("function_call")
            self.refusal = message_data.get("refusal")
            # Convert tool_calls dicts to objects
            raw_tool_calls = message_data.get("tool_calls")
            if raw_tool_calls:
                self.tool_calls = [ToolCall(tc) for tc in raw_tool_calls]
            else:
                self.tool_calls = None
        
        # Support dict(message) for AutoGen compatibility
        def keys(self):
            return self._data.keys()
        
        def __getitem__(self, key):
            return self._data[key]
        
        def __iter__(self):
            return iter(self._data)
        
        def get(self, key, default=None):
            return self._data.get(key, default)
    
    class Choice:
        def __init__(self, choice_data):
            self.index = choice_data.get("index", 0)
            self.finish_reason = choice_data.get("finish_reason")
            message_data = choice_data.get("message", {})
            self.message = Message(message_data)
    
    class Usage:
        def __init__(self, usage_data):
            self.prompt_tokens = usage_data.get("prompt_tokens", 0)
            self.completion_tokens = usage_data.get("completion_tokens", 0)
            self.total_tokens = usage_data.get("total_tokens", 0)
    
    class ChatCompletion:
        def __init__(self, response_data):
            self._data = response_data  # Store original data
            self.id = response_data.get("id")
            self.object = response_data.get("object", "chat.completion")
            self.created = response_data.get("created")
            self.model = response_data.get("model")
            self.choices = [Choice(c) for c in response_data.get("choices", [])]
            usage_data = response_data.get("usage", {})
            self.usage = Usage(usage_data) if usage_data else None
            self.system_fingerprint = response_data.get("system_fingerprint")
        
        def parse(self):
            """Return self for LangChain compatibility.
            
            LangChain calls response.parse() expecting the parsed response.
            For our use case, the response is already parsed, so we return self.
            """
            return self
        
        def model_dump(self):
            """Return the response data as a dictionary."""
            return self._data
    
    return ChatCompletion(data)


async def _wrap_chat_completions_create_async(wrapped, instance, args, kwargs):
    """Async wrapper for chat.completions.create.
    
    Wraps LLM inspection with error handling to ensure LLM calls
    never crash due to inspection errors, respecting llm_fail_open setting.
    
    Supports two integration modes:
    - "api" (default): Use LLMInspector to inspect, then call original method
    - "gateway": Route request through AI Defense Gateway (gateway handles inspection)
    """
    model = kwargs.get("model", "unknown")
    
    if not _should_inspect():
        logger.debug(f"[PATCHED CALL] OpenAI.async.chat.completions.create - inspection skipped")
        return await wrapped(*args, **kwargs)
    
    # Detect provider (OpenAI vs Azure OpenAI)
    provider = _detect_provider(instance)
    
    # Extract Azure-specific info if using Azure OpenAI
    azure_api_version = None
    azure_deployment_name = None
    if provider == "azure_openai":
        azure_api_version = _get_azure_api_version(instance)
        azure_deployment_name = _get_azure_deployment_name(instance, kwargs)
    
    messages = kwargs.get("messages", [])
    normalized = _normalize_messages(messages)
    metadata = get_inspection_context().metadata
    stream = kwargs.get("stream", False)
    
    mode = _state.get_llm_mode()
    integration_mode = _state.get_llm_integration_mode()
    logger.debug(f"")
    logger.debug(f"╔══════════════════════════════════════════════════════════════")
    logger.debug(f"║ [PATCHED] LLM CALL (async): {model}")
    logger.debug(f"║ Operation: OpenAI.async.chat.completions.create | LLM Mode: {mode} | Integration: {integration_mode} | Provider: {provider}")
    logger.debug(f"╚══════════════════════════════════════════════════════════════")
    
    # Gateway mode: route through AI Defense Gateway
    if _should_use_gateway(provider):
        logger.debug(f"[PATCHED CALL] Gateway mode (async, {provider}) - routing to AI Defense Gateway")
        return await _handle_gateway_call_async(kwargs, stream, normalized, metadata, provider, azure_api_version, azure_deployment_name)
    
    # API mode (default): use LLMInspector for inspection
    # Pre-call inspection with error handling
    try:
        logger.debug(f"[PATCHED CALL] OpenAI.async - Request inspection ({len(normalized)} messages)")
        inspector = _get_inspector()
        decision = await inspector.ainspect_conversation(normalized, metadata)
        logger.debug(f"[PATCHED CALL] OpenAI.async - Request decision: {decision.action}")
        set_inspection_context(decision=decision)
        _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as e:
        decision = _handle_patcher_error(e, "OpenAI.async pre-call")
        if decision:
            set_inspection_context(decision=decision)
    
    # Call the original
    logger.debug(f"[PATCHED CALL] OpenAI.async - calling original method")
    response = await wrapped(*args, **kwargs)
    
    # Handle streaming
    if stream:
        logger.debug(f"[PATCHED CALL] OpenAI.async - streaming response, wrapping for inspection")
        return AsyncStreamingInspectionWrapper(response, normalized, metadata)
    
    # Post-call inspection with error handling
    try:
        assistant_content = _extract_assistant_content(response)
        if assistant_content:
            logger.debug(f"[PATCHED CALL] OpenAI.async - Response inspection")
            messages_with_response = normalized + [
                {"role": "assistant", "content": assistant_content}
            ]
            inspector = _get_inspector()
            decision = await inspector.ainspect_conversation(messages_with_response, metadata)
            logger.debug(f"[PATCHED CALL] OpenAI.async - Response decision: {decision.action}")
            set_inspection_context(decision=decision, done=True)
            _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as e:
        logger.warning(f"[OpenAI.async post-call] Inspection error: {e}")
    
    logger.debug(f"[PATCHED CALL] OpenAI.async - complete")
    return response


async def _handle_gateway_call_async(kwargs: Dict[str, Any], stream: bool, normalized: List[Dict], metadata: Dict, provider: str = "openai", azure_api_version: Optional[str] = None, azure_deployment_name: Optional[str] = None) -> Any:
    """
    Handle asynchronous gateway call.
    
    Routes the request through provider-specific AI Defense Gateway, which handles 
    inspection and proxying to the actual LLM provider.
    
    Args:
        kwargs: Original call kwargs (model, messages, etc.)
        stream: Whether streaming is requested
        normalized: Normalized messages for context
        metadata: Inspection metadata
        provider: Provider name - "openai" or "azure_openai"
        azure_api_version: Azure OpenAI API version (only for azure_openai provider)
        azure_deployment_name: Azure deployment name (only for azure_openai provider)
        
    Returns:
        Response from gateway (same format as OpenAI response)
    """
    import httpx
    
    gateway_url = _state.get_provider_gateway_url(provider)
    gateway_api_key = _state.get_provider_gateway_api_key(provider)
    
    if not gateway_url or not gateway_api_key:
        logger.warning(f"Gateway mode enabled but {provider} gateway not configured")
        raise SecurityPolicyError(
            Decision.block(reasons=[f"{provider} gateway not configured"]),
            f"Gateway mode enabled but AGENTSEC_{provider.upper()}_GATEWAY_URL not set"
        )
    
    # Build request body (OpenAI-compatible format)
    request_body = {
        "model": kwargs.get("model"),
        "messages": kwargs.get("messages", []),
    }
    
    # Copy optional parameters
    for param in ["temperature", "max_tokens", "top_p", "n", "stop", "presence_penalty", 
                  "frequency_penalty", "logit_bias", "user", "tools", "tool_choice",
                  "response_format", "seed"]:
        if param in kwargs:
            request_body[param] = kwargs[param]
    
    # Note: Gateway mode does NOT support streaming yet - always use non-streaming
    # The gateway returns JSON response, not SSE stream
    if stream:
        logger.debug(f"[GATEWAY] Streaming requested but gateway returns JSON - will convert response")
    
    try:
        # Construct full URL based on provider
        full_url = gateway_url.rstrip('/')
        
        if provider == "azure_openai":
            # Azure OpenAI gateway URL format:
            # {gateway_base}/openai/deployments/{deployment_name}/chat/completions[?api-version={api_version}]
            # Use azure_deployment_name (extracted from client) or fall back to kwargs["model"]
            deployment_name = azure_deployment_name or kwargs.get("model", "")
            if 'chat/completions' not in full_url:
                full_url = f"{full_url}/openai/deployments/{deployment_name}/chat/completions"
                if azure_api_version:
                    full_url = f"{full_url}?api-version={azure_api_version}"
        else:
            # OpenAI gateway URL format: {gateway_base}/v1/chat/completions
            if 'chat/completions' not in full_url:
                full_url = full_url + '/v1/chat/completions'
        
        logger.debug(f"[GATEWAY] Sending async request to {provider} gateway: {full_url}")
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                full_url,
                json=request_body,
                headers={
                    "Authorization": f"Bearer {gateway_api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            response_data = response.json()
        
        logger.debug(f"[GATEWAY] Received async response from {provider} gateway")
        set_inspection_context(decision=Decision.allow(reasons=["Gateway handled inspection"]), done=True)
        
        # Convert dict response to OpenAI-like object
        response_obj = _dict_to_openai_response(response_data)
        
        # If streaming was requested, wrap the complete response as a fake stream
        if stream:
            logger.debug(f"[GATEWAY] Wrapping response as fake async stream for compatibility")
            return _AsyncFakeStreamWrapper(response_obj)
        
        return response_obj
        
    except httpx.HTTPStatusError as e:
        logger.error(f"[GATEWAY] HTTP error: {e}")
        if _state.get_gateway_mode_fail_open_llm():
            set_inspection_context(decision=Decision.allow(reasons=["Gateway error, fail_open=True"]), done=True)
            raise SecurityPolicyError(
                Decision.block(reasons=["Gateway unavailable"]),
                f"Gateway HTTP error: {e}"
            )
        raise
    except SecurityPolicyError:
        raise
    except Exception as e:
        logger.error(f"[GATEWAY] Async error: {e}")
        raise


class _AsyncFakeStreamWrapper:
    """Wraps a complete response as an async iterator for streaming compatibility.
    
    When gateway mode returns a non-streaming response but the caller expects
    streaming, this wrapper yields the response as a single chunk with proper
    streaming format.
    """
    
    def __init__(self, response):
        self.response = response
        self._yielded = False
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        if self._yielded:
            raise StopAsyncIteration
        self._yielded = True
        
        # Convert complete response to streaming chunk format
        chunk = _create_stream_chunk_from_response(self.response)
        return chunk


def _create_stream_chunk_from_response(response):
    """Convert a complete ChatCompletion response to a streaming chunk format."""
    from types import SimpleNamespace
    
    # Extract content from the response
    content = ""
    tool_calls = None
    finish_reason = "stop"
    
    if hasattr(response, 'choices') and response.choices:
        choice = response.choices[0]
        if hasattr(choice, 'message'):
            if hasattr(choice.message, 'content') and choice.message.content:
                content = choice.message.content
            if hasattr(choice.message, 'tool_calls') and choice.message.tool_calls:
                # Tool calls are already converted to objects in _dict_to_openai_response
                tool_calls = choice.message.tool_calls
        if hasattr(choice, 'finish_reason'):
            finish_reason = choice.finish_reason
    
    # Create delta object for streaming chunk
    delta = SimpleNamespace(
        content=content,
        role="assistant",
        tool_calls=tool_calls,
    )
    
    chunk_choice = SimpleNamespace(
        index=0,
        delta=delta,
        finish_reason=finish_reason,
    )
    
    chunk = SimpleNamespace(
        id=getattr(response, 'id', 'gateway-response'),
        object="chat.completion.chunk",
        created=getattr(response, 'created', 0),
        model=getattr(response, 'model', 'gateway'),
        choices=[chunk_choice],
    )
    
    return chunk


def _wrap_responses_create(wrapped, instance, args, kwargs):
    """Wrapper for responses.create (newer API).
    
    Wraps LLM inspection with error handling to ensure LLM calls
    never crash due to inspection errors, respecting llm_fail_open setting.
    """
    if not _should_inspect():
        return wrapped(*args, **kwargs)
    
    # Extract input messages
    input_data = kwargs.get("input", args[0] if args else None)
    messages = []
    if isinstance(input_data, str):
        messages = [{"role": "user", "content": input_data}]
    elif isinstance(input_data, list):
        messages = _normalize_messages(input_data)
    
    metadata = get_inspection_context().metadata
    
    # Pre-call inspection with error handling
    try:
        inspector = _get_inspector()
        decision = inspector.inspect_conversation(messages, metadata)
        set_inspection_context(decision=decision)
        _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as e:
        decision = _handle_patcher_error(e, "OpenAI.responses.create pre-call")
        if decision:
            set_inspection_context(decision=decision)
    
    # Call original
    response = wrapped(*args, **kwargs)
    
    # Post-call inspection with error handling
    try:
        if hasattr(response, "output_text"):
            messages_with_response = messages + [
                {"role": "assistant", "content": response.output_text}
            ]
            inspector = _get_inspector()
            decision = inspector.inspect_conversation(messages_with_response, metadata)
            set_inspection_context(decision=decision, done=True)
            _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as e:
        logger.warning(f"[OpenAI.responses.create post-call] Inspection error: {e}")
    
    return response


async def _wrap_responses_create_async(wrapped, instance, args, kwargs):
    """Async wrapper for responses.create.
    
    Wraps LLM inspection with error handling to ensure LLM calls
    never crash due to inspection errors, respecting llm_fail_open setting.
    """
    if not _should_inspect():
        return await wrapped(*args, **kwargs)
    
    input_data = kwargs.get("input", args[0] if args else None)
    messages = []
    if isinstance(input_data, str):
        messages = [{"role": "user", "content": input_data}]
    elif isinstance(input_data, list):
        messages = _normalize_messages(input_data)
    
    metadata = get_inspection_context().metadata
    
    # Pre-call inspection with error handling
    try:
        inspector = _get_inspector()
        decision = await inspector.ainspect_conversation(messages, metadata)
        set_inspection_context(decision=decision)
        _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as e:
        decision = _handle_patcher_error(e, "OpenAI.async.responses.create pre-call")
        if decision:
            set_inspection_context(decision=decision)
    
    # Call original
    response = await wrapped(*args, **kwargs)
    
    # Post-call inspection with error handling
    try:
        if hasattr(response, "output_text"):
            messages_with_response = messages + [
                {"role": "assistant", "content": response.output_text}
            ]
            inspector = _get_inspector()
            decision = await inspector.ainspect_conversation(messages_with_response, metadata)
            set_inspection_context(decision=decision, done=True)
            _enforce_decision(decision)
    except SecurityPolicyError:
        raise
    except Exception as e:
        logger.warning(f"[OpenAI.async.responses.create post-call] Inspection error: {e}")
    
    return response


def patch_openai() -> bool:
    """
    Patch OpenAI client for automatic inspection.
    
    Returns:
        True if patching was successful, False otherwise
    """
    if is_patched("openai"):
        logger.debug("OpenAI already patched, skipping")
        return True
    
    openai = safe_import("openai")
    if openai is None:
        return False
    
    try:
        # Patch chat.completions.create
        wrapt.wrap_function_wrapper(
            "openai.resources.chat.completions",
            "Completions.create",
            _wrap_chat_completions_create,
        )
        
        # Patch async version
        wrapt.wrap_function_wrapper(
            "openai.resources.chat.completions",
            "AsyncCompletions.create",
            _wrap_chat_completions_create_async,
        )
        
        # Try to patch responses.create if available (newer API)
        try:
            wrapt.wrap_function_wrapper(
                "openai.resources.responses",
                "Responses.create",
                _wrap_responses_create,
            )
            wrapt.wrap_function_wrapper(
                "openai.resources.responses",
                "AsyncResponses.create",
                _wrap_responses_create_async,
            )
        except Exception:
            logger.debug("responses.create not available, skipping")
        
        mark_patched("openai")
        logger.info("OpenAI client patched successfully")
        return True
    except Exception as e:
        logger.warning(f"Failed to patch OpenAI: {e}")
        return False
