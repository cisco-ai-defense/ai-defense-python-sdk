from aidefense.pydantic.runtime.google.api import annotations_pb2 as _annotations_pb2
from aidefense.pydantic.runtime.validate import validate_pb2 as _validate_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf import wrappers_pb2 as _wrappers_pb2
from aidefense.pydantic.runtime.protoc_gen_openapiv2.options import annotations_pb2 as _annotations_pb2_1
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ClassificationTypes(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    NONE_VIOLATION: _ClassVar[ClassificationTypes]
    SECURITY_VIOLATION: _ClassVar[ClassificationTypes]
    PRIVACY_VIOLATION: _ClassVar[ClassificationTypes]
    SAFETY_VIOLATION: _ClassVar[ClassificationTypes]
    RELEVANCE_VIOLATION: _ClassVar[ClassificationTypes]
    CUSTOM_GUARDRAIL_PROFILE_VIOLATION: _ClassVar[ClassificationTypes]

class SeverityType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    NONE_SEVERITY: _ClassVar[SeverityType]
    LOW: _ClassVar[SeverityType]
    MEDIUM: _ClassVar[SeverityType]
    HIGH: _ClassVar[SeverityType]

class AttackTechniqueTypes(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    NONE_ATTACK_TECHNIQUE: _ClassVar[AttackTechniqueTypes]
    DIRECT_REQUEST: _ClassVar[AttackTechniqueTypes]
    INDIRECT_REQUEST: _ClassVar[AttackTechniqueTypes]
    INTRUCTION_INJECTION: _ClassVar[AttackTechniqueTypes]
    OBFUSCATION: _ClassVar[AttackTechniqueTypes]
    FICTIONALIZATION: _ClassVar[AttackTechniqueTypes]

class Role(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    invalid_role: _ClassVar[Role]
    assistant: _ClassVar[Role]
    system: _ClassVar[Role]
    user: _ClassVar[Role]
    tool: _ClassVar[Role]
    function: _ClassVar[Role]

class ContentPartType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    invalid_content_part_type: _ClassVar[ContentPartType]
    text: _ClassVar[ContentPartType]
    image_url: _ClassVar[ContentPartType]
    input_audio: _ClassVar[ContentPartType]

class Action(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ActionUnspecified: _ClassVar[Action]
    Block: _ClassVar[Action]
    Allow: _ClassVar[Action]
    Redact: _ClassVar[Action]

class Application(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    APPLICATION_UNSPECIFIED: _ClassVar[Application]
    APPLICATION_MICROSOFT_COPILOT: _ClassVar[Application]

class FrameDirection(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    UNKNOWN: _ClassVar[FrameDirection]
    SERVER_TO_CLIENT: _ClassVar[FrameDirection]
    ClIENT_TO_SERVER: _ClassVar[FrameDirection]
NONE_VIOLATION: ClassificationTypes
SECURITY_VIOLATION: ClassificationTypes
PRIVACY_VIOLATION: ClassificationTypes
SAFETY_VIOLATION: ClassificationTypes
RELEVANCE_VIOLATION: ClassificationTypes
CUSTOM_GUARDRAIL_PROFILE_VIOLATION: ClassificationTypes
NONE_SEVERITY: SeverityType
LOW: SeverityType
MEDIUM: SeverityType
HIGH: SeverityType
NONE_ATTACK_TECHNIQUE: AttackTechniqueTypes
DIRECT_REQUEST: AttackTechniqueTypes
INDIRECT_REQUEST: AttackTechniqueTypes
INTRUCTION_INJECTION: AttackTechniqueTypes
OBFUSCATION: AttackTechniqueTypes
FICTIONALIZATION: AttackTechniqueTypes
invalid_role: Role
assistant: Role
system: Role
user: Role
tool: Role
function: Role
invalid_content_part_type: ContentPartType
text: ContentPartType
image_url: ContentPartType
input_audio: ContentPartType
ActionUnspecified: Action
Block: Action
Allow: Action
Redact: Action
APPLICATION_UNSPECIFIED: Application
APPLICATION_MICROSOFT_COPILOT: Application
UNKNOWN: FrameDirection
SERVER_TO_CLIENT: FrameDirection
ClIENT_TO_SERVER: FrameDirection

class RuleObject(_message.Message):
    __slots__ = ("rule_name", "rule_id", "entity_types", "classification", "profile_id")
    RULE_NAME_FIELD_NUMBER: _ClassVar[int]
    RULE_ID_FIELD_NUMBER: _ClassVar[int]
    ENTITY_TYPES_FIELD_NUMBER: _ClassVar[int]
    CLASSIFICATION_FIELD_NUMBER: _ClassVar[int]
    PROFILE_ID_FIELD_NUMBER: _ClassVar[int]
    rule_name: str
    rule_id: int
    entity_types: _containers.RepeatedScalarFieldContainer[str]
    classification: ClassificationTypes
    profile_id: str
    def __init__(self, rule_name: _Optional[str] = ..., rule_id: _Optional[int] = ..., entity_types: _Optional[_Iterable[str]] = ..., classification: _Optional[_Union[ClassificationTypes, str]] = ..., profile_id: _Optional[str] = ...) -> None: ...

class HttpHdrKvObject(_message.Message):
    __slots__ = ("key", "value")
    KEY_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    key: str
    value: str
    def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...

class HttpHdrObject(_message.Message):
    __slots__ = ("hdr_kvs",)
    HDR_KVS_FIELD_NUMBER: _ClassVar[int]
    hdr_kvs: _containers.RepeatedCompositeFieldContainer[HttpHdrKvObject]
    def __init__(self, hdr_kvs: _Optional[_Iterable[_Union[HttpHdrKvObject, _Mapping]]] = ...) -> None: ...

class Config(_message.Message):
    __slots__ = ("enabled_rules", "integration_tenant_id", "integration_type")
    ENABLED_RULES_FIELD_NUMBER: _ClassVar[int]
    INTEGRATION_TENANT_ID_FIELD_NUMBER: _ClassVar[int]
    INTEGRATION_TYPE_FIELD_NUMBER: _ClassVar[int]
    enabled_rules: _containers.RepeatedCompositeFieldContainer[RuleObject]
    integration_tenant_id: str
    integration_type: str
    def __init__(self, enabled_rules: _Optional[_Iterable[_Union[RuleObject, _Mapping]]] = ..., integration_tenant_id: _Optional[str] = ..., integration_type: _Optional[str] = ...) -> None: ...

class FunctionCall(_message.Message):
    __slots__ = ("name", "arguments")
    NAME_FIELD_NUMBER: _ClassVar[int]
    ARGUMENTS_FIELD_NUMBER: _ClassVar[int]
    name: str
    arguments: str
    def __init__(self, name: _Optional[str] = ..., arguments: _Optional[str] = ...) -> None: ...

class ToolFunction(_message.Message):
    __slots__ = ("name", "description", "parameters_json", "arguments_json")
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    PARAMETERS_JSON_FIELD_NUMBER: _ClassVar[int]
    ARGUMENTS_JSON_FIELD_NUMBER: _ClassVar[int]
    name: str
    description: str
    parameters_json: str
    arguments_json: str
    def __init__(self, name: _Optional[str] = ..., description: _Optional[str] = ..., parameters_json: _Optional[str] = ..., arguments_json: _Optional[str] = ...) -> None: ...

class ToolDefinition(_message.Message):
    __slots__ = ("type", "function")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    FUNCTION_FIELD_NUMBER: _ClassVar[int]
    type: str
    function: ToolFunction
    def __init__(self, type: _Optional[str] = ..., function: _Optional[_Union[ToolFunction, _Mapping]] = ...) -> None: ...

class ToolCall(_message.Message):
    __slots__ = ("id", "type", "function")
    ID_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    FUNCTION_FIELD_NUMBER: _ClassVar[int]
    id: str
    type: str
    function: ToolFunction
    def __init__(self, id: _Optional[str] = ..., type: _Optional[str] = ..., function: _Optional[_Union[ToolFunction, _Mapping]] = ...) -> None: ...

class ImageURL(_message.Message):
    __slots__ = ("url",)
    URL_FIELD_NUMBER: _ClassVar[int]
    url: str
    def __init__(self, url: _Optional[str] = ...) -> None: ...

class InputAudio(_message.Message):
    __slots__ = ("data", "format")
    DATA_FIELD_NUMBER: _ClassVar[int]
    FORMAT_FIELD_NUMBER: _ClassVar[int]
    data: str
    format: str
    def __init__(self, data: _Optional[str] = ..., format: _Optional[str] = ...) -> None: ...

class ContentPart(_message.Message):
    __slots__ = ("type", "text", "image_url", "input_audio")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    IMAGE_URL_FIELD_NUMBER: _ClassVar[int]
    INPUT_AUDIO_FIELD_NUMBER: _ClassVar[int]
    type: ContentPartType
    text: str
    image_url: ImageURL
    input_audio: InputAudio
    def __init__(self, type: _Optional[_Union[ContentPartType, str]] = ..., text: _Optional[str] = ..., image_url: _Optional[_Union[ImageURL, _Mapping]] = ..., input_audio: _Optional[_Union[InputAudio, _Mapping]] = ...) -> None: ...

class ContentPartList(_message.Message):
    __slots__ = ("items",)
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[ContentPart]
    def __init__(self, items: _Optional[_Iterable[_Union[ContentPart, _Mapping]]] = ...) -> None: ...

class MessageContent(_message.Message):
    __slots__ = ("text", "parts")
    TEXT_FIELD_NUMBER: _ClassVar[int]
    PARTS_FIELD_NUMBER: _ClassVar[int]
    text: str
    parts: ContentPartList
    def __init__(self, text: _Optional[str] = ..., parts: _Optional[_Union[ContentPartList, _Mapping]] = ...) -> None: ...

class Message(_message.Message):
    __slots__ = ("role", "content", "tool_calls", "tool_call_id", "function_call", "name")
    ROLE_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    TOOL_CALLS_FIELD_NUMBER: _ClassVar[int]
    TOOL_CALL_ID_FIELD_NUMBER: _ClassVar[int]
    FUNCTION_CALL_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    role: Role
    content: MessageContent
    tool_calls: _containers.RepeatedCompositeFieldContainer[ToolCall]
    tool_call_id: str
    function_call: FunctionCall
    name: str
    def __init__(self, role: _Optional[_Union[Role, str]] = ..., content: _Optional[_Union[MessageContent, _Mapping]] = ..., tool_calls: _Optional[_Iterable[_Union[ToolCall, _Mapping]]] = ..., tool_call_id: _Optional[str] = ..., function_call: _Optional[_Union[FunctionCall, _Mapping]] = ..., name: _Optional[str] = ...) -> None: ...

class Metadata(_message.Message):
    __slots__ = ("user", "created_at", "src_app", "dst_app", "sni", "dst_ip", "src_ip", "dst_host", "user_agent", "client_transaction_id", "model_name", "model_provider_name")
    USER_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    SRC_APP_FIELD_NUMBER: _ClassVar[int]
    DST_APP_FIELD_NUMBER: _ClassVar[int]
    SNI_FIELD_NUMBER: _ClassVar[int]
    DST_IP_FIELD_NUMBER: _ClassVar[int]
    SRC_IP_FIELD_NUMBER: _ClassVar[int]
    DST_HOST_FIELD_NUMBER: _ClassVar[int]
    USER_AGENT_FIELD_NUMBER: _ClassVar[int]
    CLIENT_TRANSACTION_ID_FIELD_NUMBER: _ClassVar[int]
    MODEL_NAME_FIELD_NUMBER: _ClassVar[int]
    MODEL_PROVIDER_NAME_FIELD_NUMBER: _ClassVar[int]
    user: str
    created_at: _timestamp_pb2.Timestamp
    src_app: str
    dst_app: str
    sni: str
    dst_ip: str
    src_ip: str
    dst_host: str
    user_agent: str
    client_transaction_id: str
    model_name: str
    model_provider_name: str
    def __init__(self, user: _Optional[str] = ..., created_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., src_app: _Optional[str] = ..., dst_app: _Optional[str] = ..., sni: _Optional[str] = ..., dst_ip: _Optional[str] = ..., src_ip: _Optional[str] = ..., dst_host: _Optional[str] = ..., user_agent: _Optional[str] = ..., client_transaction_id: _Optional[str] = ..., model_name: _Optional[str] = ..., model_provider_name: _Optional[str] = ...) -> None: ...

class DetectedPII(_message.Message):
    __slots__ = ("message_index", "type", "start_index", "end_index", "content_part_index")
    MESSAGE_INDEX_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    START_INDEX_FIELD_NUMBER: _ClassVar[int]
    END_INDEX_FIELD_NUMBER: _ClassVar[int]
    CONTENT_PART_INDEX_FIELD_NUMBER: _ClassVar[int]
    message_index: _wrappers_pb2.UInt64Value
    type: str
    start_index: _wrappers_pb2.UInt64Value
    end_index: _wrappers_pb2.UInt64Value
    content_part_index: _wrappers_pb2.UInt64Value
    def __init__(self, message_index: _Optional[_Union[_wrappers_pb2.UInt64Value, _Mapping]] = ..., type: _Optional[str] = ..., start_index: _Optional[_Union[_wrappers_pb2.UInt64Value, _Mapping]] = ..., end_index: _Optional[_Union[_wrappers_pb2.UInt64Value, _Mapping]] = ..., content_part_index: _Optional[_Union[_wrappers_pb2.UInt64Value, _Mapping]] = ...) -> None: ...

class DetectedSpan(_message.Message):
    __slots__ = ("message_index", "type", "entity_name", "start_index", "end_index", "content_part_index")
    MESSAGE_INDEX_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    ENTITY_NAME_FIELD_NUMBER: _ClassVar[int]
    START_INDEX_FIELD_NUMBER: _ClassVar[int]
    END_INDEX_FIELD_NUMBER: _ClassVar[int]
    CONTENT_PART_INDEX_FIELD_NUMBER: _ClassVar[int]
    message_index: _wrappers_pb2.UInt64Value
    type: str
    entity_name: str
    start_index: _wrappers_pb2.UInt64Value
    end_index: _wrappers_pb2.UInt64Value
    content_part_index: _wrappers_pb2.UInt64Value
    def __init__(self, message_index: _Optional[_Union[_wrappers_pb2.UInt64Value, _Mapping]] = ..., type: _Optional[str] = ..., entity_name: _Optional[str] = ..., start_index: _Optional[_Union[_wrappers_pb2.UInt64Value, _Mapping]] = ..., end_index: _Optional[_Union[_wrappers_pb2.UInt64Value, _Mapping]] = ..., content_part_index: _Optional[_Union[_wrappers_pb2.UInt64Value, _Mapping]] = ...) -> None: ...

class ChatInspectRequest(_message.Message):
    __slots__ = ("messages", "metadata", "config", "tools", "policy_id")
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    TOOLS_FIELD_NUMBER: _ClassVar[int]
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    messages: _containers.RepeatedCompositeFieldContainer[Message]
    metadata: Metadata
    config: Config
    tools: _containers.RepeatedCompositeFieldContainer[ToolDefinition]
    policy_id: str
    def __init__(self, messages: _Optional[_Iterable[_Union[Message, _Mapping]]] = ..., metadata: _Optional[_Union[Metadata, _Mapping]] = ..., config: _Optional[_Union[Config, _Mapping]] = ..., tools: _Optional[_Iterable[_Union[ToolDefinition, _Mapping]]] = ..., policy_id: _Optional[str] = ...) -> None: ...

class DefenseClawInspectRequest(_message.Message):
    __slots__ = ("messages", "metadata", "config", "tools", "dc_metadata", "device_id")
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    TOOLS_FIELD_NUMBER: _ClassVar[int]
    DC_METADATA_FIELD_NUMBER: _ClassVar[int]
    DEVICE_ID_FIELD_NUMBER: _ClassVar[int]
    messages: _containers.RepeatedCompositeFieldContainer[Message]
    metadata: Metadata
    config: Config
    tools: _containers.RepeatedCompositeFieldContainer[ToolDefinition]
    dc_metadata: _struct_pb2.Struct
    device_id: str
    def __init__(self, messages: _Optional[_Iterable[_Union[Message, _Mapping]]] = ..., metadata: _Optional[_Union[Metadata, _Mapping]] = ..., config: _Optional[_Union[Config, _Mapping]] = ..., tools: _Optional[_Iterable[_Union[ToolDefinition, _Mapping]]] = ..., dc_metadata: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., device_id: _Optional[str] = ...) -> None: ...

class HttpMetaObject(_message.Message):
    __slots__ = ("url", "protocol")
    URL_FIELD_NUMBER: _ClassVar[int]
    PROTOCOL_FIELD_NUMBER: _ClassVar[int]
    url: str
    protocol: str
    def __init__(self, url: _Optional[str] = ..., protocol: _Optional[str] = ...) -> None: ...

class HttpReqObject(_message.Message):
    __slots__ = ("method", "headers", "body", "split", "last")
    METHOD_FIELD_NUMBER: _ClassVar[int]
    HEADERS_FIELD_NUMBER: _ClassVar[int]
    BODY_FIELD_NUMBER: _ClassVar[int]
    SPLIT_FIELD_NUMBER: _ClassVar[int]
    LAST_FIELD_NUMBER: _ClassVar[int]
    method: str
    headers: HttpHdrObject
    body: str
    split: bool
    last: bool
    def __init__(self, method: _Optional[str] = ..., headers: _Optional[_Union[HttpHdrObject, _Mapping]] = ..., body: _Optional[str] = ..., split: bool = ..., last: bool = ...) -> None: ...

class HttpResObject(_message.Message):
    __slots__ = ("status_code", "status_string", "headers", "body", "split", "last")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    STATUS_STRING_FIELD_NUMBER: _ClassVar[int]
    HEADERS_FIELD_NUMBER: _ClassVar[int]
    BODY_FIELD_NUMBER: _ClassVar[int]
    SPLIT_FIELD_NUMBER: _ClassVar[int]
    LAST_FIELD_NUMBER: _ClassVar[int]
    status_code: int
    status_string: str
    headers: HttpHdrObject
    body: str
    split: bool
    last: bool
    def __init__(self, status_code: _Optional[int] = ..., status_string: _Optional[str] = ..., headers: _Optional[_Union[HttpHdrObject, _Mapping]] = ..., body: _Optional[str] = ..., split: bool = ..., last: bool = ...) -> None: ...

class HttpInspectRequest(_message.Message):
    __slots__ = ("http_req", "http_res", "http_meta", "metadata", "config", "policy_id")
    HTTP_REQ_FIELD_NUMBER: _ClassVar[int]
    HTTP_RES_FIELD_NUMBER: _ClassVar[int]
    HTTP_META_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    http_req: HttpReqObject
    http_res: HttpResObject
    http_meta: HttpMetaObject
    metadata: Metadata
    config: Config
    policy_id: str
    def __init__(self, http_req: _Optional[_Union[HttpReqObject, _Mapping]] = ..., http_res: _Optional[_Union[HttpResObject, _Mapping]] = ..., http_meta: _Optional[_Union[HttpMetaObject, _Mapping]] = ..., metadata: _Optional[_Union[Metadata, _Mapping]] = ..., config: _Optional[_Union[Config, _Mapping]] = ..., policy_id: _Optional[str] = ...) -> None: ...

class InspectResponse(_message.Message):
    __slots__ = ("classifications", "is_safe", "severity", "rules", "attack_technique", "explanation", "client_transaction_id", "event_id", "processed_rules", "action", "detected_pii", "detected_spans", "redacted_content")
    CLASSIFICATIONS_FIELD_NUMBER: _ClassVar[int]
    IS_SAFE_FIELD_NUMBER: _ClassVar[int]
    SEVERITY_FIELD_NUMBER: _ClassVar[int]
    RULES_FIELD_NUMBER: _ClassVar[int]
    ATTACK_TECHNIQUE_FIELD_NUMBER: _ClassVar[int]
    EXPLANATION_FIELD_NUMBER: _ClassVar[int]
    CLIENT_TRANSACTION_ID_FIELD_NUMBER: _ClassVar[int]
    EVENT_ID_FIELD_NUMBER: _ClassVar[int]
    PROCESSED_RULES_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    DETECTED_PII_FIELD_NUMBER: _ClassVar[int]
    DETECTED_SPANS_FIELD_NUMBER: _ClassVar[int]
    REDACTED_CONTENT_FIELD_NUMBER: _ClassVar[int]
    classifications: _containers.RepeatedScalarFieldContainer[ClassificationTypes]
    is_safe: bool
    severity: SeverityType
    rules: _containers.RepeatedCompositeFieldContainer[RuleObject]
    attack_technique: AttackTechniqueTypes
    explanation: str
    client_transaction_id: str
    event_id: str
    processed_rules: _containers.RepeatedCompositeFieldContainer[RuleObject]
    action: Action
    detected_pii: _containers.RepeatedCompositeFieldContainer[DetectedPII]
    detected_spans: _containers.RepeatedCompositeFieldContainer[DetectedSpan]
    redacted_content: str
    def __init__(self, classifications: _Optional[_Iterable[_Union[ClassificationTypes, str]]] = ..., is_safe: bool = ..., severity: _Optional[_Union[SeverityType, str]] = ..., rules: _Optional[_Iterable[_Union[RuleObject, _Mapping]]] = ..., attack_technique: _Optional[_Union[AttackTechniqueTypes, str]] = ..., explanation: _Optional[str] = ..., client_transaction_id: _Optional[str] = ..., event_id: _Optional[str] = ..., processed_rules: _Optional[_Iterable[_Union[RuleObject, _Mapping]]] = ..., action: _Optional[_Union[Action, str]] = ..., detected_pii: _Optional[_Iterable[_Union[DetectedPII, _Mapping]]] = ..., detected_spans: _Optional[_Iterable[_Union[DetectedSpan, _Mapping]]] = ..., redacted_content: _Optional[str] = ...) -> None: ...

class DefenseClawInspectResponse(_message.Message):
    __slots__ = ("classifications", "is_safe", "severity", "rules", "attack_technique", "explanation", "client_transaction_id", "event_id", "processed_rules", "action", "detected_pii", "detected_spans", "is_redaction_enabled")
    CLASSIFICATIONS_FIELD_NUMBER: _ClassVar[int]
    IS_SAFE_FIELD_NUMBER: _ClassVar[int]
    SEVERITY_FIELD_NUMBER: _ClassVar[int]
    RULES_FIELD_NUMBER: _ClassVar[int]
    ATTACK_TECHNIQUE_FIELD_NUMBER: _ClassVar[int]
    EXPLANATION_FIELD_NUMBER: _ClassVar[int]
    CLIENT_TRANSACTION_ID_FIELD_NUMBER: _ClassVar[int]
    EVENT_ID_FIELD_NUMBER: _ClassVar[int]
    PROCESSED_RULES_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    DETECTED_PII_FIELD_NUMBER: _ClassVar[int]
    DETECTED_SPANS_FIELD_NUMBER: _ClassVar[int]
    IS_REDACTION_ENABLED_FIELD_NUMBER: _ClassVar[int]
    classifications: _containers.RepeatedScalarFieldContainer[ClassificationTypes]
    is_safe: bool
    severity: SeverityType
    rules: _containers.RepeatedCompositeFieldContainer[RuleObject]
    attack_technique: AttackTechniqueTypes
    explanation: str
    client_transaction_id: str
    event_id: str
    processed_rules: _containers.RepeatedCompositeFieldContainer[RuleObject]
    action: Action
    detected_pii: _containers.RepeatedCompositeFieldContainer[DetectedPII]
    detected_spans: _containers.RepeatedCompositeFieldContainer[DetectedSpan]
    is_redaction_enabled: bool
    def __init__(self, classifications: _Optional[_Iterable[_Union[ClassificationTypes, str]]] = ..., is_safe: bool = ..., severity: _Optional[_Union[SeverityType, str]] = ..., rules: _Optional[_Iterable[_Union[RuleObject, _Mapping]]] = ..., attack_technique: _Optional[_Union[AttackTechniqueTypes, str]] = ..., explanation: _Optional[str] = ..., client_transaction_id: _Optional[str] = ..., event_id: _Optional[str] = ..., processed_rules: _Optional[_Iterable[_Union[RuleObject, _Mapping]]] = ..., action: _Optional[_Union[Action, str]] = ..., detected_pii: _Optional[_Iterable[_Union[DetectedPII, _Mapping]]] = ..., detected_spans: _Optional[_Iterable[_Union[DetectedSpan, _Mapping]]] = ..., is_redaction_enabled: bool = ...) -> None: ...

class MCPMessage(_message.Message):
    __slots__ = ("jsonrpc", "method", "params", "result", "error", "id")
    JSONRPC_FIELD_NUMBER: _ClassVar[int]
    METHOD_FIELD_NUMBER: _ClassVar[int]
    PARAMS_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    jsonrpc: str
    method: str
    params: _struct_pb2.Struct
    result: _struct_pb2.Struct
    error: MCPError
    id: _struct_pb2.Value
    def __init__(self, jsonrpc: _Optional[str] = ..., method: _Optional[str] = ..., params: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., result: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., error: _Optional[_Union[MCPError, _Mapping]] = ..., id: _Optional[_Union[_struct_pb2.Value, _Mapping]] = ...) -> None: ...

class MCPError(_message.Message):
    __slots__ = ("code", "message", "data")
    CODE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    code: int
    message: str
    data: _struct_pb2.Struct
    def __init__(self, code: _Optional[int] = ..., message: _Optional[str] = ..., data: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class MCPInspectResponse(_message.Message):
    __slots__ = ("jsonrpc", "result", "error", "id")
    JSONRPC_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    jsonrpc: str
    result: InspectResponse
    error: MCPInspectError
    id: _struct_pb2.Value
    def __init__(self, jsonrpc: _Optional[str] = ..., result: _Optional[_Union[InspectResponse, _Mapping]] = ..., error: _Optional[_Union[MCPInspectError, _Mapping]] = ..., id: _Optional[_Union[_struct_pb2.Value, _Mapping]] = ...) -> None: ...

class MCPInspectError(_message.Message):
    __slots__ = ("code", "message", "data")
    CODE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    code: int
    message: str
    data: _struct_pb2.Struct
    def __init__(self, code: _Optional[int] = ..., message: _Optional[str] = ..., data: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class ApplicationInfo(_message.Message):
    __slots__ = ("application", "casp_application_name")
    APPLICATION_FIELD_NUMBER: _ClassVar[int]
    CASP_APPLICATION_NAME_FIELD_NUMBER: _ClassVar[int]
    application: Application
    casp_application_name: str
    def __init__(self, application: _Optional[_Union[Application, str]] = ..., casp_application_name: _Optional[str] = ...) -> None: ...

class WebSocketMetadata(_message.Message):
    __slots__ = ("client_transaction_id", "application", "url", "req_headers", "resp_headers")
    CLIENT_TRANSACTION_ID_FIELD_NUMBER: _ClassVar[int]
    APPLICATION_FIELD_NUMBER: _ClassVar[int]
    URL_FIELD_NUMBER: _ClassVar[int]
    REQ_HEADERS_FIELD_NUMBER: _ClassVar[int]
    RESP_HEADERS_FIELD_NUMBER: _ClassVar[int]
    client_transaction_id: str
    application: ApplicationInfo
    url: str
    req_headers: HttpHdrObject
    resp_headers: HttpHdrObject
    def __init__(self, client_transaction_id: _Optional[str] = ..., application: _Optional[_Union[ApplicationInfo, _Mapping]] = ..., url: _Optional[str] = ..., req_headers: _Optional[_Union[HttpHdrObject, _Mapping]] = ..., resp_headers: _Optional[_Union[HttpHdrObject, _Mapping]] = ...) -> None: ...

class WebSocketFrame(_message.Message):
    __slots__ = ("direction", "body", "frame_id", "op_code")
    DIRECTION_FIELD_NUMBER: _ClassVar[int]
    BODY_FIELD_NUMBER: _ClassVar[int]
    FRAME_ID_FIELD_NUMBER: _ClassVar[int]
    OP_CODE_FIELD_NUMBER: _ClassVar[int]
    direction: FrameDirection
    body: bytes
    frame_id: int
    op_code: int
    def __init__(self, direction: _Optional[_Union[FrameDirection, str]] = ..., body: _Optional[bytes] = ..., frame_id: _Optional[int] = ..., op_code: _Optional[int] = ...) -> None: ...

class WebSocketInspectRequest(_message.Message):
    __slots__ = ("frames", "config", "metadata")
    FRAMES_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    frames: _containers.RepeatedCompositeFieldContainer[WebSocketFrame]
    config: Config
    metadata: WebSocketMetadata
    def __init__(self, frames: _Optional[_Iterable[_Union[WebSocketFrame, _Mapping]]] = ..., config: _Optional[_Union[Config, _Mapping]] = ..., metadata: _Optional[_Union[WebSocketMetadata, _Mapping]] = ...) -> None: ...

class WebSocketInspectResponse(_message.Message):
    __slots__ = ("inspect_response", "frame_id", "direction", "violated_content", "decoded_content")
    INSPECT_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    FRAME_ID_FIELD_NUMBER: _ClassVar[int]
    DIRECTION_FIELD_NUMBER: _ClassVar[int]
    VIOLATED_CONTENT_FIELD_NUMBER: _ClassVar[int]
    DECODED_CONTENT_FIELD_NUMBER: _ClassVar[int]
    inspect_response: InspectResponse
    frame_id: int
    direction: FrameDirection
    violated_content: str
    decoded_content: str
    def __init__(self, inspect_response: _Optional[_Union[InspectResponse, _Mapping]] = ..., frame_id: _Optional[int] = ..., direction: _Optional[_Union[FrameDirection, str]] = ..., violated_content: _Optional[str] = ..., decoded_content: _Optional[str] = ...) -> None: ...
