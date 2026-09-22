# Copyright 2026 Cisco Systems, Inc. and its affiliates
# SPDX-License-Identifier: Apache-2.0

"""Small, fail-closed bidirectional gRPC inspection client."""

from __future__ import annotations

import asyncio
import logging
import uuid
from urllib.parse import urlsplit
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)

from aidefense.pydantic.runtime.ai_defense.inspection.v1 import (
    inspection_pydantic as runtime_chat,
)
from aidefense.config import BaseConfig, Config
from aidefense.runtime.models import InspectionConfig

from ._dependencies import require_grpc, require_wire_dependencies
from ._session import _StreamSession
from .adapters import EventStreamAdapter
from .exceptions import (
    EventStreamError,
    StreamBackpressureError,
    StreamCancelledError,
    StreamConfigurationError,
    StreamConnectionError,
    StreamProtocolError,
    StreamSourceError,
    StreamTimeoutError,
)
from .models import (
    CanonicalMessage,
    EventStreamConfig,
    StreamContext,
    StreamDecision,
    StreamDirection,
    StreamEvent,
    StreamInspectionResult,
)
from .observability import ReasonCode, StreamObserver

RequestContent = Union[
    str,
    Sequence[CanonicalMessage],
    Sequence[Dict[str, Any]],
]


def _request_messages(request: RequestContent) -> Tuple[CanonicalMessage, ...]:
    """Normalize SDK input without requiring protobuf construction."""

    if isinstance(request, str):
        if not request:
            raise StreamProtocolError("request must not be empty")
        return (
            CanonicalMessage(
                role=runtime_chat.Role.user,
                content=runtime_chat.MessageContent(text=request),
            ),
        )
    if not isinstance(request, Sequence) or isinstance(request, (bytes, bytearray)):
        raise StreamProtocolError(
            "request must be text or a sequence of canonical messages"
        )
    if not request:
        raise StreamProtocolError("request conversation must not be empty")

    messages = []
    for value in request:
        try:
            if isinstance(value, CanonicalMessage):
                message = value.model_copy(deep=True)
            elif isinstance(value, dict):
                data = dict(value)
                if isinstance(data.get("content"), str):
                    data["content"] = {"text": data["content"]}
                message = CanonicalMessage.model_validate(data)
            else:
                raise TypeError
        except (TypeError, ValueError) as exc:
            raise StreamProtocolError(
                "request contains an invalid canonical message"
            ) from exc
        if message.role in (None, runtime_chat.Role.invalid_role):
            raise StreamProtocolError("request messages must have a valid role")
        messages.append(message)
    return tuple(messages)


class EventStreamClient:
    """Send canonical events and release application events after inspection.

    The client is reusable and intentionally keeps no per-call mutable state.
    Every :meth:`inspect` invocation creates an isolated ``_StreamSession`` and
    gRPC channel, which permits concurrent calls from tasks and threads.

    The SDK sends exactly one ``InspectionEvent`` per input ``StreamEvent``. It
    does not group content, split tokens, or create overlap. The service may
    acknowledge a set of sent events in one result; exactly those local events
    are decided, while application content is released in sequence order.
    """

    def __init__(
        self,
        api_key: Optional[Union[str, EventStreamConfig]] = None,
        config: Optional[Union[BaseConfig, EventStreamConfig]] = None,
        *,
        observer: Optional[StreamObserver] = None,
        on_decision: Optional[Callable[[StreamInspectionResult], Any]] = None,
        channel_factory: Optional[Callable[..., Any]] = None,
        stub_factory: Optional[Callable[[Any], Any]] = None,
    ) -> None:
        # A shared Config gives streaming callers the same API-key/config shape,
        # logger, debug level, tracer, and metrics hooks used elsewhere in the
        # SDK. An explicit StreamObserver remains available for advanced users.
        runtime_config = config if isinstance(config, BaseConfig) else None
        self.observer = observer or StreamObserver(
            logger=getattr(runtime_config, "logger", None),
            tracer=getattr(runtime_config, "tracer", None),
            metrics=getattr(runtime_config, "metrics", None),
        )
        try:
            resolved_config = self._resolve_config(api_key, config)
            resolved_config.validate()
        except StreamConfigurationError:
            self.observer.event(ReasonCode.CONFIGURATION_INVALID, level=logging.ERROR)
            raise
        self.config = resolved_config
        self._on_decision = on_decision
        self._channel_factory = channel_factory
        self._stub_factory = stub_factory
        self.observer.debug(
            ReasonCode.STREAM_CONFIGURED,
            attributes={
                "tls": self.config.tls,
                "tls_mode": self._tls_mode(self.config),
                "tls_server_name_override": bool(self.config.tls_server_name),
                "metadata_count": len(self.config.metadata),
                "idle_timeout_seconds": self.config.idle_timeout,
                "absolute_timeout_seconds": self.config.absolute_timeout,
                "max_pending_events": self.config.max_pending_events,
                "max_stream_events": self.config.max_stream_events,
                "max_stream_bytes": self.config.max_stream_bytes,
            },
        )

    def _make_stub(self, channel: Any) -> Any:
        """Create the generated stub without importing it during SDK startup."""

        if self._stub_factory is not None:
            return self._stub_factory(channel)
        from ._grpc import InspectionServiceStub

        return InspectionServiceStub(channel)

    @classmethod
    def from_env(
        cls,
        *,
        observer: Optional[StreamObserver] = None,
        on_decision: Optional[Callable[[StreamInspectionResult], Any]] = None,
        **overrides: Any,
    ) -> "EventStreamClient":
        """Build a client from secure runtime environment configuration."""

        resolved_observer = observer or StreamObserver()
        try:
            config = EventStreamConfig.from_env(**overrides)
        except StreamConfigurationError:
            resolved_observer.event(
                ReasonCode.CONFIGURATION_INVALID, level=logging.ERROR
            )
            raise
        return cls(
            config,
            observer=resolved_observer,
            on_decision=on_decision,
        )

    @staticmethod
    def _resolve_config(
        api_key: Optional[Union[str, EventStreamConfig]],
        config: Optional[Union[BaseConfig, EventStreamConfig]],
    ) -> EventStreamConfig:
        """Accept ChatInspect-style credentials or the advanced stream config.

        Most callers should pass ``api_key`` plus the shared ``Config``. The
        transport-specific ``EventStreamConfig`` form remains useful for a
        custom CA, custom gRPC metadata, and server-limit tuning.
        """

        if isinstance(api_key, EventStreamConfig):
            if config is not None:
                raise StreamConfigurationError(
                    "config must not be provided with EventStreamConfig"
                )
            return api_key
        if isinstance(config, EventStreamConfig):
            if api_key is not None:
                raise StreamConfigurationError(
                    "api_key is already part of EventStreamConfig"
                )
            return config
        if not isinstance(api_key, str) or not api_key.strip():
            raise StreamConfigurationError("api_key must not be empty")

        runtime_config = config or Config()
        if not isinstance(runtime_config, BaseConfig):
            raise StreamConfigurationError(
                "config must be a Config, AsyncConfig, or EventStreamConfig object"
            )
        return EventStreamClient._config_from_runtime(api_key, runtime_config)

    @staticmethod
    def _config_from_runtime(
        api_key: str, runtime_config: BaseConfig
    ) -> EventStreamConfig:
        """Convert the shared HTTP runtime URL into a gRPC channel target.

        ``Config`` remains the convenient ChatInspect-style entry point. The
        URL path is intentionally rejected because gRPC routes by service and
        method name rather than an HTTP API path.
        """

        try:
            parsed = urlsplit(runtime_config.runtime_base_url)
            port = parsed.port
        except (TypeError, ValueError) as exc:
            raise StreamConfigurationError("runtime_base_url is invalid") from exc
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise StreamConfigurationError(
                "runtime_base_url must be an http:// or https:// URL"
            )
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise StreamConfigurationError(
                "runtime_base_url must not contain credentials, query, or fragment"
            )
        if parsed.path not in {"", "/"}:
            raise StreamConfigurationError(
                "runtime_base_url must not contain an API path"
            )

        host = parsed.hostname
        if ":" in host:
            host = f"[{host}]"
        endpoint = f"{host}:{port or (443 if parsed.scheme == 'https' else 80)}"
        absolute_timeout = float(runtime_config.timeout)
        return EventStreamConfig(
            endpoint=endpoint,
            api_key=api_key,
            tls=parsed.scheme == "https",
            idle_timeout=min(30.0, absolute_timeout),
            absolute_timeout=absolute_timeout,
        )

    async def inspect(
        self,
        events: Any,
        *,
        context: StreamContext,
        source: Optional[str] = None,
        request: Optional[RequestContent] = None,
        adapter: Optional[EventStreamAdapter] = None,
        message_id: Optional[str] = None,
        inspection_config: Optional[InspectionConfig] = None,
    ) -> AsyncIterator[Any]:
        """Inspect native adapter events or caller-created ``StreamEvent`` values.

        With ``adapter``, ``request`` becomes one request event and native
        response events are converted lazily after that request is safe. Passing
        ``events`` as a callable is recommended because the callable is not
        invoked until prompt inspection has allowed model execution.

        Without ``adapter``, ``events`` must contain the canonical request and
        response sequence. One response event is retained only to mark the
        actual final event; content is never grouped. Only application events
        covered by a non-blocking server decision are yielded.

        The returned async generator owns an RPC. Consumers that stop before
        exhaustion must call ``aclose()`` (normally in ``finally``) so transport
        and source cleanup runs immediately.
        """

        context.validate()
        if adapter is not None:
            if request is None:
                raise StreamProtocolError(
                    "request is required when an adapter is provided"
                )
            request_messages = _request_messages(request)
            identifier = message_id or str(uuid.uuid4())
            resolved_source = source or adapter.source
            native_events = events

            async def canonical_events() -> AsyncIterator[StreamEvent]:
                yield StreamEvent(
                    application_event=None,
                    messages=request_messages,
                    direction=StreamDirection.REQUEST,
                    message_id=identifier,
                )
                adapted_events = adapter.adapt(
                    native_events,
                    message_id=identifier,
                    direction=StreamDirection.RESPONSE,
                )
                try:
                    async for converted in adapted_events:
                        yield converted
                except EventStreamError:
                    raise
                except Exception as exc:
                    # Provider/framework failures happen inside the writer
                    # worker. Preserve that boundary instead of reporting an
                    # unrelated gRPC connection failure to the application.
                    raise StreamSourceError(
                        f"{resolved_source} event source failed "
                        f"({type(exc).__name__})",
                        cause=exc,
                    ) from exc
                finally:
                    close = getattr(adapted_events, "aclose", None)
                    if close is not None:
                        await close()

            events = canonical_events()
        else:
            if request is not None or message_id is not None:
                raise StreamProtocolError("request and message_id require an adapter")
            resolved_source = source or ""
        if not isinstance(resolved_source, str) or not resolved_source.strip():
            raise StreamProtocolError("source must not be empty")

        # A private session owns all mutable state for this invocation. The
        # client and adapter remain reusable across concurrent tasks or threads.
        session = _StreamSession(
            client=self,
            events=events,
            context=context,
            source=resolved_source,
            inspection_config=inspection_config,
        )
        async for approved_event in session.run():
            yield approved_event

    @staticmethod
    def _validate_event(event: Any) -> None:
        if not isinstance(event, StreamEvent):
            raise StreamProtocolError("inspect accepts only StreamEvent values")
        if not event.messages:
            raise StreamProtocolError("StreamEvent.messages must not be empty")
        if not isinstance(event.message_id, str) or not event.message_id.strip():
            raise StreamProtocolError("StreamEvent.message_id must not be empty")
        if not isinstance(event.direction, StreamDirection):
            raise StreamProtocolError("StreamEvent.direction is invalid")

    def _open_channel(self) -> Any:
        """Create one channel per inspection call using the selected TLS mode.

        ``root_certificates=None`` asks gRPC to use its default public trust
        roots. A custom root bundle changes server trust. Supplying both client
        fields additionally enables mTLS; neither secret is logged or retained
        by the reusable client beyond its immutable configuration.
        """

        if self._channel_factory is not None:
            return self._channel_factory(self.config)
        grpc = require_grpc()
        options: List[Tuple[str, Any]] = [
            ("grpc.max_send_message_length", self.config.max_stream_bytes),
            ("grpc.max_receive_message_length", self.config.max_stream_bytes),
        ]
        if self.config.tls_server_name:
            options.extend(
                [
                    ("grpc.ssl_target_name_override", self.config.tls_server_name),
                    ("grpc.default_authority", self.config.tls_server_name),
                ]
            )
        if self.config.tls:
            credentials = grpc.ssl_channel_credentials(
                root_certificates=self.config.root_certificates,
                private_key=self.config.client_private_key,
                certificate_chain=self.config.client_certificate,
            )
            return grpc.aio.secure_channel(
                self.config.endpoint, credentials, options=tuple(options)
            )
        return grpc.aio.insecure_channel(self.config.endpoint, options=tuple(options))

    @staticmethod
    def _tls_mode(config: EventStreamConfig) -> str:
        """Return a non-secret transport mode suitable for diagnostics."""

        if not config.tls:
            return "insecure"
        if config.client_certificate is not None:
            return "mutual_tls"
        if config.root_certificates is not None:
            return "custom_ca"
        return "default_tls"

    @staticmethod
    def _start_frame(context: StreamContext, config: Optional[InspectionConfig]) -> Any:
        _, _, stream_api, runtime_stream = require_wire_dependencies()
        start = runtime_stream.InspectStreamStart(
            context=runtime_stream.InspectionContext(
                session_id=context.session_id,
                request_id=context.request_id,
                conversation_id=context.conversation_id,
                actor_id=context.actor_id,
            )
        )
        if config is not None:
            start.inspection_config = _inspection_config(config)
        return _to_wire(
            runtime_stream.InspectStreamRequest(start=start),
            stream_api.InspectStreamRequest(),
        )

    @staticmethod
    def _event_frame(
        event: StreamEvent,
        sequence: int,
        source: str,
        is_final: bool,
    ) -> Any:
        _, _, stream_api, runtime_stream = require_wire_dependencies()
        direction = (
            runtime_stream.Direction.DIRECTION_REQUEST
            if event.direction is StreamDirection.REQUEST
            else runtime_stream.Direction.DIRECTION_RESPONSE
        )
        runtime_event = runtime_stream.InspectionEvent(
            message_id=event.message_id,
            sequence=sequence,
            source=source,
            direction=direction,
            is_final=is_final,
            conversation=runtime_stream.ConversationPayload(
                messages=list(event.messages)
            ),
        )
        return _to_wire(runtime_event, stream_api.InspectionEvent())

    @staticmethod
    def _decision(response: runtime_chat.InspectResponse) -> StreamDecision:
        return StreamDecision(
            is_safe=response.is_safe,
            action=str(response.action or runtime_chat.Action.ActionUnspecified),
            event_id=response.event_id,
            classifications=tuple(str(value) for value in response.classifications),
            rules=tuple(rule.rule_name for rule in response.rules),
            redacted_content=response.redacted_content,
        )

    @staticmethod
    def _map_error(exc: BaseException) -> EventStreamError:
        if isinstance(exc, EventStreamError):
            return exc
        if isinstance(exc, asyncio.CancelledError):
            return StreamCancelledError("event stream was cancelled", cause=exc)
        if isinstance(exc, asyncio.TimeoutError):
            return StreamTimeoutError("event stream timed out", cause=exc)
        try:
            grpc = require_grpc()
        except ImportError:
            return StreamConnectionError("event stream connection failed", cause=exc)
        if isinstance(exc, grpc.aio.AioRpcError):
            code = exc.code()
            details = " ".join((exc.details() or "").split())
            if len(details) > 512:
                details = f"{details[:509]}..."
            if code == grpc.StatusCode.CANCELLED:
                return StreamCancelledError(
                    "server cancelled the event stream", cause=exc
                )
            if code == grpc.StatusCode.DEADLINE_EXCEEDED:
                return StreamTimeoutError("server deadline expired", cause=exc)
            if code in (
                grpc.StatusCode.INVALID_ARGUMENT,
                grpc.StatusCode.FAILED_PRECONDITION,
            ):
                message = f"event stream request was rejected with {code.name}"
                if details:
                    message = f"{message}: {details}"
                return StreamProtocolError(message, cause=exc)
            if code == grpc.StatusCode.RESOURCE_EXHAUSTED:
                message = "event stream exceeded a server capacity limit"
                if details:
                    message = f"{message}: {details}"
                return StreamBackpressureError(message, cause=exc)
            if code in (
                grpc.StatusCode.UNAUTHENTICATED,
                grpc.StatusCode.PERMISSION_DENIED,
            ):
                message = f"event stream authorization failed with {code.name}"
                if details:
                    message = f"{message}: {details}"
                return StreamConnectionError(message, cause=exc)
            message = f"event stream RPC failed with status {code.name}"
            if details:
                message = f"{message}: {details}"
            return StreamConnectionError(message, cause=exc)
        return StreamConnectionError("event stream connection failed", cause=exc)


def _inspection_config(config: InspectionConfig) -> Any:
    proto = runtime_chat.Config(
        integration_tenant_id=config.integration_tenant_id or "",
        integration_type=config.integration_type or "",
    )
    for rule in config.enabled_rules or []:
        proto.enabled_rules.append(
            runtime_chat.RuleObject(
                rule_name=rule.rule_name.value if rule.rule_name is not None else "",
                rule_id=rule.rule_id or 0,
                entity_types=rule.entity_types or [],
                classification=(
                    runtime_chat.ClassificationTypes(rule.classification.value)
                    if rule.classification is not None
                    else runtime_chat.ClassificationTypes.NONE_VIOLATION
                ),
            )
        )
    return proto


def _to_wire(model: Any, message: Any) -> Any:
    """Convert a validated public Pydantic runtime model to private protobuf."""

    _, parse_dict, _, _ = require_wire_dependencies()
    return parse_dict(model.model_dump(mode="json"), message)
