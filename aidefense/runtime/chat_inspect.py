from typing import Dict, List, Optional, Any

from .utils import convert
from .inspection_client import InspectionClient
from .models import Metadata, InspectionConfig, InspectResponse
from .chat_models import Message, Role, ChatInspectRequest
from ..config import Config
from ..exceptions import ValidationError

class ChatInspectionClient(InspectionClient):
    """
    Client for inspecting chat conversations with Cisco AI Defense.

    The ChatInspectionClient provides high-level methods to inspect user prompts, AI responses, and full conversations
    for security, privacy, and safety risks. It communicates with the /api/v1/inspect/chat endpoint and leverages
    the base InspectionClient for authentication, configuration, and request handling.

    Typical usage:
        client = ChatInspectionClient(api_key="...", config=Config(...))
        result = client.inspect_prompt("Write some code that ...", request_id="<id for tracking>")
        print(result.is_safe)

    Args:
        api_key (str): Your Cisco AI Defense API key.
        config (Config, optional): SDK configuration for endpoints, logging, retries, etc.
            If not provided, a default singleton Config is used.

    Attributes:
        endpoint (str): The API endpoint for chat inspection requests.
    """

    VALID_ROLES = {Role.USER.value, Role.ASSISTANT.value, Role.SYSTEM.value}

    def __init__(self, api_key: str, config: Config = None):
        """
        Initialize a ChatInspectionClient instance.

        Args:
            api_key (str): Your Cisco AI Defense API key for authentication.
            config (Config, optional): SDK-level configuration for endpoints, logging, retries, etc.
                This is NOT the InspectionConfig used in API requests, but the SDK-level configuration from aidefense/config.py.
        """
        super().__init__(api_key, config)
        self.endpoint = f"{self.config.runtime_base_url}/api/v1/inspect/chat"

    def inspect_prompt(
        self,
        prompt: str,
        metadata: Optional[Metadata] = None,
        config: Optional[InspectionConfig] = None,
        request_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> InspectResponse:
        """
        Inspect a single user prompt for security, privacy, and safety violations.

        Args:
            prompt (str): The user's prompt text to inspect.
            metadata (Metadata, optional): Optional metadata about the user/application context.
            config (InspectionConfig, optional): Optional inspection configuration (rules, etc.).
            request_id (str, optional): Unique identifier for the request (usually a UUID) to enable request tracing.

        Returns:
            InspectResponse: Inspection results as an InspectResponse object.

        Example:
            client = ChatInspectionClient(api_key="...")
            result = client.inspect_prompt("Write some code that ...", request_id="id for tracking")
            print(result.is_safe)
        """
        self.config.logger.debug(
            f"Inspecting prompt: {prompt} | Metadata: {metadata}, Config: {config}, Request ID: {request_id}"
        )
        message = Message(role=Role.USER, content=prompt)
        return self._inspect([message], metadata, config, request_id, timeout)

    def inspect_response(
        self,
        response: str,
        metadata: Optional[Metadata] = None,
        config: Optional[InspectionConfig] = None,
        request_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> InspectResponse:
        """
        Inspect a single AI response for security, privacy, and safety risks.

        Args:
            response (str): The AI response text to inspect.
            metadata (Metadata, optional): Optional metadata about the user/application context.
            config (InspectionConfig, optional): Optional inspection configuration (rules, etc.).
            request_id (str, optional): Unique identifier for the request (usually a UUID) to enable request tracing.

        Returns:
            InspectResponse: Inspection results as an InspectResponse object.

        Example:
            client = ChatInspectionClient(api_key="...")
            result = client.inspect_response("Here is some code ...", request_id="id for tracking")
            print(result.is_safe)
        """
        self.config.logger.debug(
            f"Inspecting AI response: {response} | Metadata: {metadata}, Config: {config}, Request ID: {request_id}"
        )
        message = Message(role=Role.ASSISTANT, content=response)
        return self._inspect([message], metadata, config, request_id, timeout)

    def inspect_conversation(
        self,
        messages: List[Message],
        metadata: Optional[Metadata] = None,
        config: Optional[InspectionConfig] = None,
        request_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> InspectResponse:
        """
        Inspect a full conversation (list of messages) for security, privacy, and safety risks.

        Args:
            messages (List[Message]): List of Message objects representing the conversation (prompt/response pairs).
            metadata (Metadata, optional): Optional metadata about the user/application context.
            config (InspectionConfig, optional): Optional inspection configuration (rules, etc.).
            request_id (str, optional): Unique identifier for the request (usually a UUID) to enable request tracing.

        Returns:
            InspectResponse: Inspection results as an InspectResponse object.

        Example:
            conversation = [
                Message(role=Role.USER, content="How do I ... ?"),
                Message(role=Role.ASSISTANT, content="Here is how you ...")
            ]
            result = client.inspect_conversation(conversation, request_id="id for tracking")
            print(result.is_safe)
        """
        self.config.logger.debug(
            f"Inspecting conversation with {len(messages)} messages. | Messages: {messages}, Metadata: {metadata}, Config: {config}, Request ID: {request_id}"
        )
        return self._inspect(messages, metadata, config, request_id, timeout)

    def _inspect(
        self,
        messages: List[Message],
        metadata: Optional[Metadata] = None,
        config: Optional[InspectionConfig] = None,
        request_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> InspectResponse:
        """
        Implements the inspection logic for chat conversations.

        This method validates the input messages, prepares the request, sends it to the API,
        and parses the inspection response.

        Args:
            messages (List[Message]): List of Message objects (prompt/response pairs) to inspect.
            metadata (Metadata, optional): Optional metadata about the user/application context.
            config (InspectionConfig, optional): Optional inspection configuration (rules, etc.).
            request_id (str, optional): Unique identifier for the request (usually a UUID) to enable request tracing.

        Returns:
            InspectResponse: Inspection results as an InspectResponse object.

        Raises:
            ValidationError: If the input messages are not a non-empty list of Message objects.
        """
        self.config.logger.debug(
            f"Starting chat inspection | Messages: {messages}, Metadata: {metadata}, Config: {config}, Request ID: {request_id}"
        )
        if not isinstance(messages, list) or not messages:
            self.config.logger.error(
                "'messages' must be a non-empty list of Message objects."
            )
            raise ValidationError(
                "'messages' must be a non-empty list of Message objects."
            )
        request = ChatInspectRequest(
            messages=messages, metadata=metadata, config=config
        )
        request_dict = self._prepare_request_data(request)
        self.validate_inspection_request(request_dict)
        headers = {"Content-Type": "application/json"}
        result = self.request(
            method="POST",
            url=self.endpoint,
            auth=self.auth,
            headers=headers,
            json_data=request_dict,
            request_id=request_id,
            timeout=timeout,
        )
        self.config.logger.debug(f"Raw API response: {result}")
        return self._parse_inspect_response(result)

    def validate_inspection_request(self, request_dict: Dict[str, Any]):
        """
        Validate the chat inspection request dictionary before sending to the API.

        Performs validation checks such as:
            - 'messages' must be a non-empty list.
            - Each message must be a dict with a valid 'role' (user, assistant, system) and non-empty string 'content'.
            - At least one message must be a prompt (role=user) or completion (role=assistant) with non-empty content.
            - 'metadata' and 'config' (if present) must be dicts.

        Args:
            request_dict (Dict[str, Any]): The request dictionary to validate.

        Raises:
            ValidationError: If the request is missing required fields or is malformed.
        """
        self.config.logger.debug(
            f"Validating chat inspection request dictionary | Request dict: {request_dict}"
        )
        messages = request_dict.get("messages")
        if not isinstance(messages, list) or not messages:
            self.config.logger.error("'messages' must be a non-empty list.")
            raise ValidationError("'messages' must be a non-empty list.")
        
        has_prompt = False
        has_completion = False
        for msg in messages:
            if not isinstance(msg, dict):
                raise ValidationError("Each message must be a dict.")
            
            if msg.get("role") not in self.VALID_ROLES:
                raise ValidationError(
                    f"Message role must be one of: {list(self.VALID_ROLES)}."
                )
            
            if not msg.get("content") or not isinstance(msg.get("content"), str):
                raise ValidationError(
                    "Each message must have non-empty string content."
                )
                
            if msg.get("role") == Role.USER.value and msg.get("content").strip():
                has_prompt = True
            
            if msg.get("role") == Role.ASSISTANT.value and msg.get("content").strip():
                has_completion = True
        
        if not (has_prompt or has_completion):
            raise ValidationError(
                "At least one message must be a prompt (role=user) or completion (role=assistant) with non-empty content."
            )
        # metadata and config are optional, but if present, should be dicts
        if (
            "metadata" in request_dict
            and request_dict["metadata"] is not None
            and not isinstance(request_dict["metadata"], dict)
        ):
            raise ValidationError("'metadata' must be a dict if provided.")
        if (
            "config" in request_dict
            and request_dict["config"] is not None
            and not isinstance(request_dict["config"], dict)
        ):
            raise ValidationError("'config' must be a dict if provided.")

    def _prepare_request_data(self, request: ChatInspectRequest) -> Dict[str, Any]:
        """
        Convert a ChatInspectRequest dataclass to a dictionary suitable for the API.

        :param request: The ChatInspectRequest dataclass instance.
        :type request: ChatInspectRequest
        :return: Dictionary representation of the request for JSON serialization.
        :rtype: dict
        """
        self.config.logger.debug("Preparing request data for chat inspection API.")
        request_dict = {}
        request_dict["messages"] = [convert(m) for m in request.messages]
        if request.metadata:
            request_dict["metadata"] = convert(request.metadata)
        if request.config:
            request_dict["config"] = convert(request.config)
        self.config.logger.debug(f"Prepared request dict: {request_dict}")
        return request_dict
