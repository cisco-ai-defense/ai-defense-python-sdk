from aidefense.pydantic.runtime.validate import validate_pb2 as _validate_pb2
from aidefense.pydantic.runtime.ai_defense.inspection.v1 import inspection_pb2 as _inspection_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Direction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    DIRECTION_UNSPECIFIED: _ClassVar[Direction]
    DIRECTION_REQUEST: _ClassVar[Direction]
    DIRECTION_RESPONSE: _ClassVar[Direction]
DIRECTION_UNSPECIFIED: Direction
DIRECTION_REQUEST: Direction
DIRECTION_RESPONSE: Direction

class InspectionContext(_message.Message):
    __slots__ = ("session_id", "request_id", "conversation_id", "actor_id")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    CONVERSATION_ID_FIELD_NUMBER: _ClassVar[int]
    ACTOR_ID_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    request_id: str
    conversation_id: str
    actor_id: str
    def __init__(self, session_id: _Optional[str] = ..., request_id: _Optional[str] = ..., conversation_id: _Optional[str] = ..., actor_id: _Optional[str] = ...) -> None: ...

class ConversationPayload(_message.Message):
    __slots__ = ("messages",)
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    messages: _containers.RepeatedCompositeFieldContainer[_inspection_pb2.Message]
    def __init__(self, messages: _Optional[_Iterable[_Union[_inspection_pb2.Message, _Mapping]]] = ...) -> None: ...

class InspectionEvent(_message.Message):
    __slots__ = ("message_id", "sequence", "source", "direction", "is_final", "conversation")
    MESSAGE_ID_FIELD_NUMBER: _ClassVar[int]
    SEQUENCE_FIELD_NUMBER: _ClassVar[int]
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    DIRECTION_FIELD_NUMBER: _ClassVar[int]
    IS_FINAL_FIELD_NUMBER: _ClassVar[int]
    CONVERSATION_FIELD_NUMBER: _ClassVar[int]
    message_id: str
    sequence: int
    source: str
    direction: Direction
    is_final: bool
    conversation: ConversationPayload
    def __init__(self, message_id: _Optional[str] = ..., sequence: _Optional[int] = ..., source: _Optional[str] = ..., direction: _Optional[_Union[Direction, str]] = ..., is_final: bool = ..., conversation: _Optional[_Union[ConversationPayload, _Mapping]] = ...) -> None: ...

class InspectStreamStart(_message.Message):
    __slots__ = ("context", "inspection_config")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    INSPECTION_CONFIG_FIELD_NUMBER: _ClassVar[int]
    context: InspectionContext
    inspection_config: _inspection_pb2.Config
    def __init__(self, context: _Optional[_Union[InspectionContext, _Mapping]] = ..., inspection_config: _Optional[_Union[_inspection_pb2.Config, _Mapping]] = ...) -> None: ...

class InspectStreamEvents(_message.Message):
    __slots__ = ("events",)
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    events: _containers.RepeatedCompositeFieldContainer[InspectionEvent]
    def __init__(self, events: _Optional[_Iterable[_Union[InspectionEvent, _Mapping]]] = ...) -> None: ...

class InspectStreamRequest(_message.Message):
    __slots__ = ("start", "events")
    START_FIELD_NUMBER: _ClassVar[int]
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    start: InspectStreamStart
    events: InspectStreamEvents
    def __init__(self, start: _Optional[_Union[InspectStreamStart, _Mapping]] = ..., events: _Optional[_Union[InspectStreamEvents, _Mapping]] = ...) -> None: ...

class InspectionResult(_message.Message):
    __slots__ = ("through_sequences", "inspect_response")
    THROUGH_SEQUENCES_FIELD_NUMBER: _ClassVar[int]
    INSPECT_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    through_sequences: _containers.RepeatedScalarFieldContainer[int]
    inspect_response: _inspection_pb2.InspectResponse
    def __init__(self, through_sequences: _Optional[_Iterable[int]] = ..., inspect_response: _Optional[_Union[_inspection_pb2.InspectResponse, _Mapping]] = ...) -> None: ...
