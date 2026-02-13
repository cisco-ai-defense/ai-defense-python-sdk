# Copyright 2026 Cisco Systems, Inc. and its affiliates
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

"""
MCP (Model Context Protocol) inspection client for Cisco AI Defense.

This module provides the MCPInspectionClient for inspecting MCP JSON-RPC 2.0
messages for security, privacy, and safety violations.
"""

from typing import Dict, Any, Optional, Union

from .utils import convert
from .inspection_client import InspectionClient
from .models import InspectResponse, Action, Classification, Severity, Rule, RuleName
from .mcp_models import MCPMessage, MCPError, MCPInspectResponse, MCPInspectError
from ..config import Config
from ..exceptions import ValidationError


class MCPInspectionClient(InspectionClient):
    """
    Client for inspecting MCP (Model Context Protocol) JSON-RPC 2.0 messages with Cisco AI Defense.

    The MCPInspectionClient provides methods to inspect MCP messages (requests, responses,
    and notifications) for security, privacy, and safety risks. It communicates with the
    /api/v1/inspect/mcp endpoint and leverages the base InspectionClient for authentication,
    configuration, and request handling.

    MCP Message Types:
        - Request: has 'method' + 'id' (client→server, expects response)
        - Response: has 'result'/'error' + 'id' (server→client)
        - Notification: has 'method', no 'id' (one-way, no response)

    Use Cases:
        - Inspect tool calls before execution (e.g., database queries, file access)
        - Validate resource access requests (e.g., file URIs, network resources)
        - Scan prompt template arguments for injection attacks
        - Check responses for data leakage (PII, credentials, secrets)

    Typical usage:
        ```python
        from aidefense.runtime import MCPInspectionClient, MCPMessage

        client = MCPInspectionClient(api_key="your_api_key")

        # Create an MCP message to inspect
        message = MCPMessage(
            jsonrpc="2.0",
            method="tools/call",
            params={"name": "search_documentation", "arguments": {"query": "SSL configuration"}},
            id=1
        )

        result = client.inspect(message, request_id="unique-request-id")
        if result.result and result.result.is_safe:
            print("MCP message is safe to process")
        ```

    Args:
        api_key (str): Your Cisco AI Defense API key.
        config (Config, optional): SDK configuration for endpoints, logging, retries, etc.
            If not provided, a default singleton Config is used.

    Attributes:
        endpoint (str): The API endpoint for MCP inspection requests.
    """

    def __init__(self, api_key: str, config: Config = None):
        """
        Initialize an MCPInspectionClient instance.

        Args:
            api_key (str): Your Cisco AI Defense API key for authentication.
            config (Config, optional): SDK-level configuration for endpoints, logging, retries, etc.
        """
        config = config or Config()
        super().__init__(api_key, config)
        self.endpoint = f"{self.config.runtime_base_url}/api/v1/inspect/mcp"

    def inspect(
        self,
        message: MCPMessage,
        request_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> MCPInspectResponse:
        """
        Inspect an MCP JSON-RPC 2.0 message for security, privacy, and safety violations.

        Automatically detects message type (request/response/notification) from JSON-RPC structure.

        Args:
            message (MCPMessage): The MCP message to inspect.
            request_id (str, optional): Unique identifier for the request (usually a UUID)
                to enable request tracing.
            timeout (int, optional): Request timeout in seconds.

        Returns:
            MCPInspectResponse: Inspection results wrapped in JSON-RPC 2.0 format.
                Check result.is_safe to determine if the MCP message is safe to process.

        Example:
            ```python
            from aidefense.runtime import MCPInspectionClient, MCPMessage

            # Initialize client
            client = MCPInspectionClient(api_key="your_inspection_api_key")

            # Create an MCP tool call request to inspect
            message = MCPMessage(
                jsonrpc="2.0",
                method="tools/call",
                params={
                    "name": "execute_sql",
                    "arguments": {"query": "SELECT * FROM users WHERE id = 1"}
                },
                id="req-123"
            )

            # Inspect the message
            result = client.inspect(
                message=message,
                request_id=str(uuid.uuid4()),
            )

            # Check inspection results
            if result.result and result.result.is_safe:
                print("MCP message is safe to execute")
            elif result.error:
                print(f"Inspection error: {result.error.message}")
            else:
                print(f"Message flagged: {result.result.explanation}")
            ```
        """
        self.config.logger.debug(
            f"Inspecting MCP message: {message} | Request ID: {request_id}"
        )
        return self._inspect(message, request_id, timeout)

    def inspect_tool_call(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        message_id: Optional[Union[str, int]] = None,
        request_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> MCPInspectResponse:
        """
        Convenience method to inspect an MCP tools/call request.

        Args:
            tool_name (str): The name of the tool being called.
            arguments (Dict[str, Any], optional): The arguments passed to the tool.
            message_id (Union[str, int], optional): The JSON-RPC message ID.
            request_id (str, optional): Unique identifier for the request to enable tracing.
            timeout (int, optional): Request timeout in seconds.

        Returns:
            MCPInspectResponse: Inspection results wrapped in JSON-RPC 2.0 format.

        Example:
            ```python
            from aidefense.runtime import MCPInspectionClient

            client = MCPInspectionClient(api_key="your_api_key")

            result = client.inspect_tool_call(
                tool_name="execute_command",
                arguments={"command": "ls -la /etc/passwd"},
                message_id=1
            )

            if result.result and not result.result.is_safe:
                print("Potentially dangerous tool call detected!")
            ```
        """
        self.config.logger.debug(
            f"Inspecting MCP tool call: {tool_name} | Arguments: {arguments}, Message ID: {message_id}, Request ID: {request_id}"
        )
        message = MCPMessage(
            jsonrpc="2.0",
            method="tools/call",
            params={"name": tool_name, "arguments": arguments or {}},
            id=message_id,
        )
        return self._inspect(message, request_id, timeout)

    def inspect_resource_read(
        self,
        uri: str,
        message_id: Optional[Union[str, int]] = None,
        request_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> MCPInspectResponse:
        """
        Convenience method to inspect an MCP resources/read request.

        Args:
            uri (str): The URI of the resource being accessed.
            message_id (Union[str, int], optional): The JSON-RPC message ID.
            request_id (str, optional): Unique identifier for the request to enable tracing.
            timeout (int, optional): Request timeout in seconds.

        Returns:
            MCPInspectResponse: Inspection results wrapped in JSON-RPC 2.0 format.

        Example:
            ```python
            from aidefense.runtime import MCPInspectionClient

            client = MCPInspectionClient(api_key="your_api_key")

            result = client.inspect_resource_read(
                uri="file:///etc/passwd",
                message_id="read-123"
            )

            if result.result and not result.result.is_safe:
                print("Sensitive resource access detected!")
            ```
        """
        self.config.logger.debug(
            f"Inspecting MCP resource read: {uri} | Message ID: {message_id}, Request ID: {request_id}"
        )
        message = MCPMessage(
            jsonrpc="2.0",
            method="resources/read",
            params={"uri": uri},
            id=message_id,
        )
        return self._inspect(message, request_id, timeout)

    def inspect_response(
        self,
        result_data: Dict[str, Any],
        method: str,
        params: Optional[Dict[str, Any]] = None,
        message_id: Optional[Union[str, int]] = None,
        request_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> MCPInspectResponse:
        """
        Convenience method to inspect an MCP response message.

        Response inspection requires the original request's method and params for context,
        so the API can understand what request this response is for.

        Args:
            result_data (Dict[str, Any]): The result data from the MCP response.
            method (str): The method from the original request (e.g., "tools/call").
                Required for response inspection to provide context.
            params (Dict[str, Any], optional): The params from the original request.
                Required for response inspection to provide context.
            message_id (Union[str, int], optional): The JSON-RPC message ID.
            request_id (str, optional): Unique identifier for the request to enable tracing.
            timeout (int, optional): Request timeout in seconds.

        Returns:
            MCPInspectResponse: Inspection results wrapped in JSON-RPC 2.0 format.

        Example:
            ```python
            from aidefense.runtime import MCPInspectionClient

            client = MCPInspectionClient(api_key="your_api_key")

            # Inspect a tool response containing potentially sensitive data
            result = client.inspect_response(
                result_data={
                    "content": [
                        {"type": "text", "text": "User email: john.doe@example.com"}
                    ]
                },
                method="tools/call",
                params={"name": "get_user_info", "arguments": {"user_id": "123"}},
                message_id=1
            )

            if result.result and not result.result.is_safe:
                print("Response contains sensitive data!")
            ```
        """
        # Mandatory for response inspection: method and params provide context for the API
        if not method or not isinstance(method, str):
            raise ValidationError(
                "inspect_response requires 'method' (original request method, non-empty string)."
            )
        if params is None or not isinstance(params, dict):
            raise ValidationError(
                "inspect_response requires 'params' (original request params) as a dict."
            )

        self.config.logger.debug(
            f"Inspecting MCP response: {result_data} | Method: {method}, Params: {params}, Message ID: {message_id}, Request ID: {request_id}"
        )
        message = MCPMessage(
            jsonrpc="2.0",
            method=method,
            params=params,
            result=result_data,
            id=message_id,
        )
        return self._inspect(message, request_id, timeout)

    def _inspect(
        self,
        message: MCPMessage,
        request_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> MCPInspectResponse:
        """
        Implements the inspection logic for MCP messages.

        This method validates the input message, prepares the request, sends it to the API,
        and parses the inspection response.

        Args:
            message (MCPMessage): The MCP message to inspect.
            request_id (str, optional): Unique identifier for the request to enable tracing.
            timeout (int, optional): Request timeout in seconds.

        Returns:
            MCPInspectResponse: Inspection results wrapped in JSON-RPC 2.0 format.

        Raises:
            ValidationError: If the input message is invalid.
        """
        self.config.logger.debug(
            f"Starting MCP inspection | Message: {message}, Request ID: {request_id}"
        )

        if not isinstance(message, MCPMessage):
            raise ValidationError("'message' must be an MCPMessage object.")

        request_dict = self._prepare_request_data(message)
        self.validate_mcp_message(request_dict)

        headers = {"Content-Type": "application/json"}
        result = self._request_handler.request(
            method="POST",
            url=self.endpoint,
            auth=self.auth,
            headers=headers,
            json_data=request_dict,
            request_id=request_id,
            timeout=timeout,
        )
        self.config.logger.debug(f"Raw API response: {result}")
        return self._parse_mcp_inspect_response(result)

    def validate_mcp_message(self, request_dict: Dict[str, Any]) -> None:
        """
        Validate the MCP message dictionary before sending to the API.

        Validates according to JSON-RPC 2.0 and MCP specification:
            - 'jsonrpc' must be "2.0"
            - Must have either 'method' (for requests/notifications) or 'result'/'error' (for responses)
            - For response body (has 'result'): 'method' and 'params' are mandatory for API context
            - 'params', 'result', 'error', and 'data' must be dicts when present

        Args:
            request_dict (Dict[str, Any]): The request dictionary to validate.

        Raises:
            ValidationError: If the message is missing required fields or is malformed.
        """
        self.config.logger.debug(
            f"Validating MCP message dictionary | Request dict: {request_dict}"
        )

        # jsonrpc must be "2.0"
        jsonrpc = request_dict.get("jsonrpc")
        if jsonrpc != "2.0":
            self.config.logger.error("'jsonrpc' must be '2.0'.")
            raise ValidationError("MCP message: 'jsonrpc' must be '2.0'.")

        has_method = "method" in request_dict and request_dict.get("method")
        has_result = "result" in request_dict and request_dict.get("result") is not None
        has_error = "error" in request_dict and request_dict.get("error") is not None

        # Must have method (request/notification) or result/error (response)
        if not has_method and not has_result and not has_error:
            self.config.logger.error(
                "MCP message must have 'method' (for requests/notifications) or 'result'/'error' (for responses)."
            )
            raise ValidationError(
                "MCP message must have 'method' (for requests/notifications) or 'result'/'error' (for responses)."
            )

        # Request or notification message (has method)
        if has_method:
            params = request_dict.get("params")
            if params is not None and not isinstance(params, dict):
                self.config.logger.error(
                    "Request/notification message: 'params' must be a dict if provided."
                )
                raise ValidationError(
                    "Request/notification message: 'params' must be a dict if provided."
                )

        # Response message (has result): result must be dict; method and params required
        if has_result:
            result = request_dict.get("result")
            if not isinstance(result, dict):
                self.config.logger.error(
                    "Response message: 'result' must be a dict."
                )
                raise ValidationError(
                    "Response message: 'result' must be a dict."
                )
            if not has_method:
                self.config.logger.error(
                    "Response message must include 'method' (original request method)."
                )
                raise ValidationError(
                    "Response message must include 'method' (original request method)."
                )
            params = request_dict.get("params")
            if params is None or not isinstance(params, dict):
                self.config.logger.error(
                    "Response message must include 'params' (original request params) as a dict."
                )
                raise ValidationError(
                    "Response message must include 'params' (original request params) as a dict."
                )

        # Error response message (has error)
        if has_error:
            error = request_dict.get("error")
            if not isinstance(error, dict):
                self.config.logger.error(
                    "Error response message: 'error' must be a dict."
                )
                raise ValidationError(
                    "Error response message: 'error' must be a dict."
                )
            if "code" not in error or not isinstance(error.get("code"), int):
                self.config.logger.error(
                    "Error response message: 'error.code' must be an integer."
                )
                raise ValidationError(
                    "Error response message: 'error.code' must be an integer."
                )
            if "message" not in error or not isinstance(error.get("message"), str):
                self.config.logger.error(
                    "Error response message: 'error.message' must be a string."
                )
                raise ValidationError(
                    "Error response message: 'error.message' must be a string."
                )
            if "data" in error and error.get("data") is not None:
                if not isinstance(error.get("data"), dict):
                    self.config.logger.error(
                        "Error response message: 'error.data' must be a dict if provided."
                    )
                    raise ValidationError(
                        "Error response message: 'error.data' must be a dict if provided."
                    )

    def _prepare_request_data(self, message: MCPMessage) -> Dict[str, Any]:
        """
        Convert an MCPMessage dataclass to a dictionary suitable for the API.

        Handles the special case where 'id' can be either a string or integer.

        Args:
            message (MCPMessage): The MCPMessage dataclass instance.

        Returns:
            Dict[str, Any]: Dictionary representation of the message for JSON serialization.
        """
        self.config.logger.debug("Preparing request data for MCP inspection API.")

        request_dict = {"jsonrpc": message.jsonrpc}

        if message.method is not None:
            request_dict["method"] = message.method

        if message.params is not None:
            request_dict["params"] = convert(message.params)

        if message.result is not None:
            request_dict["result"] = convert(message.result)

        if message.error is not None:
            request_dict["error"] = convert(message.error)

        if message.id is not None:
            request_dict["id"] = message.id

        self.config.logger.debug(f"Prepared request dict: {request_dict}")
        return request_dict

    def _parse_mcp_inspect_response(
        self, response_data: Dict[str, Any]
    ) -> MCPInspectResponse:
        """
        Parse API response into an MCPInspectResponse object.

        Args:
            response_data (Dict[str, Any]): The response data returned by the API.

        Returns:
            MCPInspectResponse: The parsed MCP inspection response object.
        """
        self.config.logger.debug(
            f"_parse_mcp_inspect_response called | response_data: {response_data}"
        )

        jsonrpc = response_data.get("jsonrpc", "2.0")

        # Extract ID - can be string or int
        response_id = response_data.get("id")

        # Check if response contains error
        if "error" in response_data and response_data.get("error"):
            error_data = response_data["error"]
            error = MCPInspectError(
                code=error_data.get("code", -32603),
                message=error_data.get("message", "Unknown error"),
                data=error_data.get("data"),
            )
            return MCPInspectResponse(
                jsonrpc=jsonrpc,
                error=error,
                id=response_id,
            )

        # Parse the result (InspectResponse)
        result_data = response_data.get("result", response_data)

        # If result is directly the inspect response (not wrapped in "result" key)
        if "result" in response_data and isinstance(response_data["result"], dict):
            result_data = response_data["result"]

        # Parse the InspectResponse from result_data
        inspect_result = self._parse_inspect_response(result_data)

        return MCPInspectResponse(
            jsonrpc=jsonrpc,
            result=inspect_result,
            id=response_id,
        )

