# Copyright 2025 Cisco Systems, Inc. and its affiliates
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

import base64
from typing import Dict, Optional, Any, Union
import requests
import json

from .constants import HTTP_REQ, HTTP_RES, HTTP_META, HTTP_METHOD, HTTP_BODY
from .inspection_client import InspectionClient
from .http_models import (
    HttpInspectRequest,
    HttpReqObject,
    HttpResObject,
    HttpMetaObject,
    HttpHdrObject,
    HttpHdrKvObject,
)
from .utils import convert, to_base64_bytes, ensure_base64_body
from .models import Metadata, InspectionConfig, InspectResponse
from ..config import Config
from ..exceptions import ValidationError


class HttpInspectionClient(InspectionClient):
    """
    Provides security and privacy inspection for HTTP requests and responses.

    Use this client to analyze HTTP traffic (requests or responses) for sensitive data, policy violations, or unsafe content. Supports both raw HTTP dictionaries and objects from popular HTTP libraries (e.g., requests, aiohttp).

    Example:
        client = HttpInspectionClient(api_key="...", config=Config(...))
        result = client.inspect(http_req={...})
        print(result.is_safe)

    Args:
        api_key (str): Your AI Defense API key.
        config (Config, optional): SDK-wide configuration for endpoints, logging, retries, etc.

    Attributes:
        endpoint (str): Full API endpoint for HTTP inspection.
        Rule, RuleName, HttpInspectRequest, ...: Shortcuts for internal models and enums.
    """

    def __init__(self, api_key: str, config: Config = None):
        """
        Create a new HTTP inspection client.

        Args:
            api_key (str): Your AI Defense API key.
            config (Config, optional): SDK configuration for endpoints, logging, retries, etc.
        """
        super().__init__(api_key, config)
        self.endpoint = f"{self.config.runtime_base_url}/api/v1/inspect/http"

    def inspect(
        self,
        http_req: Optional[Dict[str, Any]] = None,
        http_res: Optional[Dict[str, Any]] = None,
        http_meta: Optional[Dict[str, Any]] = None,
        metadata: Optional[Metadata] = None,
        config: Optional[InspectionConfig] = None,
        request_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> InspectResponse:
        """
        Direct interface for HTTP inspection API using dicts for http_req, http_res, and http_meta.
        Advanced users can interact directly with the HTTP inspection API.

        Args:
            http_req (dict, optional): HTTP request dictionary.
            http_res (dict, optional): HTTP response dictionary.
            http_meta (dict, optional): HTTP metadata dictionary.
            metadata (Metadata, optional): Additional metadata.
            config (InspectionConfig, optional): Inspection configuration.
            request_id (str, optional): Unique identifier for the request (usually a UUID) to enable request tracing.
            timeout (int, optional): Request timeout in seconds.

        Note:
            - The 'body' field for both request and response dicts must be a base64-encoded string representing the original bytes.
            - If you have a str, encode it to bytes first, then base64 encode.

        Example:
            ```python
            import base64
            from aidefense.runtime import HttpInspectionClient

            # Initialize client
            client = HttpInspectionClient(api_key="your_inspection_api_key")

            # Prepare HTTP request with base64 encoded body
            body = "Hello, world!"
            body_bytes = body.encode("utf-8")
            body_base64 = base64.b64encode(body_bytes).decode("utf-8")

            http_req = {
                "method": "POST",
                "headers": {"Content-Type": "text/plain"},
                "body": body_base64
            }

            http_meta = {"url": "https://example.com/api"} # this should be a valid url to model provider.

            # Inspect the HTTP request
            result = client.inspect(http_req=http_req, http_meta=http_meta)

            # Check if request is safe
            if result.is_safe:
                print("Request is safe to send")
            ```

        Returns:
            InspectResponse: Inspection results as an InspectResponse object.
        """
        self.config.logger.debug(
            f"inspect called | http_req: {http_req}, http_res: {http_res}, http_meta: {http_meta}, metadata: {metadata}, config: {config}, request_id: {request_id}"
        )

        if http_req:
            ensure_base64_body(convert(http_req))
        if http_res:
            ensure_base64_body(convert(http_res))
        return self._inspect(
            http_req,
            http_res,
            http_meta,
            metadata,
            config,
            request_id=request_id,
            timeout=timeout,
        )

    def inspect_request_from_http_library(
        self,
        http_request: Union[requests.PreparedRequest, requests.Request],
        metadata: Optional[Metadata] = None,
        config: Optional[InspectionConfig] = None,
        request_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> InspectResponse:
        """
        Inspect an HTTP request from a supported HTTP library (currently requests) that is being sent to the model provider.

        Args:
            http_request: HTTP request object from a supported library (currently requests.Request/PreparedRequest).
            metadata (Metadata, optional): Optional metadata about the user/application context.
            config (InspectionConfig, optional): Optional inspection configuration (rules, etc.).
            request_id (str, optional): Unique identifier for the request (usually a UUID) to enable request tracing.
            timeout (int, optional): Request timeout in seconds.

        Example:
            ```python
            import requests
            from aidefense.runtime import HttpInspectionClient

            # Initialize client
            client = HttpInspectionClient(api_key="your_inspection_api_key")

            # Create a requests.Request object
            req = requests.Request(
                method="POST",
                url="https://api.example.com/v1/completions", # this should be a valid url to model provider.
                headers={"Content-Type": "application/json"},
                json={"prompt": "Tell me about AI safety"}
            )

            # Prepare the request (optional)
            prepared_req = req.prepare()

            # Inspect the request
            result = client.inspect_request_from_http_library(prepared_req)

            # Check if request is safe
            if result.is_safe:
                # Send the request
                session = requests.Session()
                response = session.send(prepared_req)
            ```

        Returns:
            InspectResponse: Inspection results as an InspectResponse object.

        Raises:
            ValueError: If the HTTP request object is not supported.
        """
        self.config.logger.debug(
            f"inspect_request_from_http_library called | http_request: {http_request}, metadata: {metadata}, config: {config}, request_id: {request_id}"
        )
        method = None
        headers = {}
        body = b""
        url = None
        # Support both requests.PreparedRequest and requests.Request
        if isinstance(http_request, requests.PreparedRequest) or isinstance(
            http_request, requests.Request
        ):
            url = getattr(http_request, "url", None)
            http_req = self._build_http_req_from_http_library(http_request)
        else:
            raise ValueError(
                "Unsupported HTTP request type: only requests.Request and requests.PreparedRequest are supported"
            )

        # Fallback for unknown types
        if url is not None:
            url = str(url)
        # Prepare and inspect
        http_meta = HttpMetaObject(url=url or "")
        return self._inspect(
            http_req,
            None,
            http_meta,
            metadata,
            config,
            request_id=request_id,
            timeout=timeout,
        )

    def inspect_response_from_http_library(
        self,
        http_response: Any,
        metadata: Optional[Metadata] = None,
        config: Optional[InspectionConfig] = None,
        request_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> InspectResponse:
        """
        Inspect an HTTP response from a supported HTTP library (currently requests) that comes from model provider and return inspection results.

        Args:
            http_response: HTTP response object from a supported library.
            metadata (Metadata, optional): Additional metadata for inspection.
            config (InspectionConfig, optional): Inspection configuration.
            request_id (str, optional): Unique identifier for the request (usually a UUID) to enable request tracing.
            timeout (int, optional): Request timeout in seconds.

        Example:
            ```python
            import requests
            from aidefense.runtime import HttpInspectionClient
            from aidefense.runtime import InspectionConfig, Rule, RuleName

            # Initialize client
            client = HttpInspectionClient(api_key="your_inspection_api_key")

            # Make a request to an API
            response = requests.get("https://api.example.com/data") # this should be a valid url to model provider.

            # Create custom inspection config to check for PII
            config = InspectionConfig(
                enabled_rules=[Rule(rule_name=RuleName.PII)]
            )

            # Inspect the response
            result = client.inspect_response_from_http_library(
                http_response=response,
                config=config
            )

            # Check if response is safe
            if not result.is_safe:
                print(f"Response contains sensitive information: {result.classifications}")
            ```

        Returns:
            InspectResponse: Inspection result.
        """
        self.config.logger.debug(
            f"inspect_response_from_http_library called | http_response: {http_response}, metadata: {metadata}, config: {config}, request_id: {request_id}"
        )
        status_code = None
        headers = {}
        body = b""
        url = None
        http_request = None

        # Support requests.Response
        if isinstance(http_response, requests.Response):
            status_code = http_response.status_code
            headers = dict(http_response.headers)
            body = http_response.content
            url = http_response.url
            http_request = getattr(http_response, "request", None)

        else:
            raise ValueError(
                "Unsupported HTTP response type: only requests.Response is supported"
            )

        body_b64 = to_base64_bytes(body) if body else ""
        hdr_kvs = [self._header_to_kv(k, v) for k, v in (headers or {}).items()]
        http_res = HttpResObject(
            statusCode=status_code, headers=HttpHdrObject(hdrKvs=hdr_kvs), body=body_b64
        )
        # Build http_req from associated request if possible
        http_req = None
        if http_request is not None:
            http_req = self._build_http_req_from_http_library(http_request)
        # If http_req could not be built, raise a clear error
        if http_req is None:
            raise ValueError(
                "Could not extract HTTP request context from response object. 'http_req' is required for inspection."
            )
        http_meta = HttpMetaObject(url=url)
        return self._inspect(
            http_req,
            http_res,
            http_meta,
            metadata,
            config,
            request_id=request_id,
            timeout=timeout,
        )

    def inspect_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        body: Union[str, bytes, dict] = None,
        metadata: Optional[Metadata] = None,
        config: Optional[InspectionConfig] = None,
        request_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> InspectResponse:
        """
        Inspect an HTTP request with simplified arguments (method, url, headers, body).

        Args:
            method (str): HTTP request method.
            url (str): URL of the request.
            headers (dict, optional): HTTP request headers.
            body (bytes, str, or dict, optional): Request body as bytes, string, or dictionary (will be JSON-serialized).
            metadata (Metadata, optional): Additional metadata for inspection.
            config (InspectionConfig, optional): Inspection configuration.
            request_id (str, optional): Unique identifier for the request (usually a UUID) to enable request tracing.
            timeout (int, optional): Request timeout in seconds.

        Example:
            ```python
            import json
            from aidefense.runtime import HttpInspectionClient

            # Initialize client
            client = HttpInspectionClient(api_key="your_inspection_api_key")

            # Define request parameters
            method = "POST"
            url = "https://api.example.com/v1/conversation" # this should be a valid url to model provider.
            headers = {
                "Content-Type": "application/json",
                "Authorization": "Bearer sk-your-api-key"
            }

            # Create the request body
            body = json.dumps({
                "model": "gpt-4",
                "messages": [
                    {"role": "user", "content": "Tell me about cybersecurity risks"}
                ]
            })

            # Inspect the request
            result = client.inspect_request(
                method=method,
                url=url,
                headers=headers,
                body=body
            )

            # Check if it's safe to send
            if result.is_safe:
                print("Request is safe to send")
            ```

        Returns:
            InspectResponse: Inspection result.
        """
        if not isinstance(body, (str, bytes, dict)):
            raise ValidationError("Request body must be str, bytes, or dict")

        if isinstance(body, dict):
            # Convert dictionary to JSON string and then encode
            body_b64 = base64.b64encode(json.dumps(body).encode()).decode()
        elif isinstance(body, str):
            body_b64 = base64.b64encode(body.encode()).decode()
        elif isinstance(body, bytes):
            body_b64 = base64.b64encode(body).decode()

        hdr_kvs = [self._header_to_kv(k, v) for k, v in (headers or {}).items()]
        http_req = HttpReqObject(
            method=method, headers=HttpHdrObject(hdrKvs=hdr_kvs), body=body_b64
        )
        http_meta = HttpMetaObject(url=url)
        return self._inspect(
            http_req,
            None,
            http_meta,
            metadata,
            config,
            request_id=request_id,
            timeout=timeout,
        )

    def inspect_response(
        self,
        status_code: int,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        body: Union[str, bytes, dict] = None,
        request_method: str = None,
        request_headers: Optional[Dict[str, str]] = None,
        request_body: Union[str, bytes, dict] = None,
        request_metadata: Optional[Metadata] = None,
        metadata: Optional[Metadata] = None,
        config: Optional[InspectionConfig] = None,
        request_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> InspectResponse:
        """
        Inspect an HTTP response (status code, url, headers, body), with request context and metadata, for security, privacy, and policy violations.

        Args:
            status_code (int): HTTP response status code.
            url (str): URL associated with the response.
            headers (dict, optional): HTTP headers for the response.
            body (Union[bytes, str, dict]): Response body as bytes, string, or dictionary.
            request_method (str): HTTP request method for context.
            request_headers (dict, optional): HTTP request headers for context.
            request_body (Union[bytes, str, dict]): HTTP request body for context.
            request_metadata (Metadata, optional): Additional metadata for the request context.
            metadata (Metadata, optional): Additional metadata for the response context.
            config (InspectionConfig, optional): Inspection configuration rules.
            request_id (str, optional): Unique identifier for the request (usually a UUID) to enable request tracing.
            timeout (int, optional): Request timeout in seconds.

        Example:
            ```python
            import json
            from aidefense.runtime import HttpInspectionClient
            from aidefense.runtime import InspectionConfig, Rule, RuleName

            # Initialize client
            client = HttpInspectionClient(api_key="your_inspection_api_key")

            # Define API response details
            status_code = 200
            url = "https://api.example.com/user/profile" # this should be a valid url to model provider.
            headers = {"Content-Type": "application/json"}

            # Sample response with potential PII
            response_body = json.dumps({
                "user": {
                    "name": "John Doe",
                    "email": "john.doe@example.com",
                    "phone": "555-123-4567",
                    "address": "123 Main St, Anytown, USA"
                }
            })

            # Define original request details for context
            request_method = "GET"
            request_headers = {"Authorization": "Bearer token123"}
            request_body = json.dumps({"user_id": "12345"})

            # Create inspection config focused on PII detection
            config = InspectionConfig(
                enabled_rules=[Rule(rule_name=RuleName.PII)]
            )

            # Inspect the response
            result = client.inspect_response(
                status_code=status_code,
                url=url,
                headers=headers,
                body=response_body,
                request_method=request_method,
                request_headers=request_headers,
                request_body=request_body,
                config=config
            )

            # Check for PII or other issues
            if not result.is_safe:
                print(f"Found sensitive data in response: {result.classifications}")
            ```

        Returns:
            InspectResponse: The inspection result.
        """
        self.config.logger.debug(
            f"inspect_response called | status_code: {status_code}, url: {url}, headers: {headers}, body: {body}, request_method: {request_method}, request_headers: {request_headers}, request_body: {request_body}, request_metadata: {request_metadata}, metadata: {metadata}, config: {config}, request_id: {request_id}"
        )
        # Response body encoding
        if not isinstance(body, (str, bytes, dict)):
            raise ValidationError(
                f"Response body must be bytes, str, or dict; got {type(body)}"
            )

        elif isinstance(body, dict):
            # Convert dictionary to JSON string and then encode
            body_b64 = base64.b64encode(json.dumps(body).encode()).decode()
        elif isinstance(body, str):
            body_b64 = base64.b64encode(body.encode()).decode()
        elif isinstance(body, bytes):
            body_b64 = base64.b64encode(body).decode()

        hdr_kvs = [self._header_to_kv(k, v) for k, v in (headers or {}).items()]
        http_res = HttpResObject(
            statusCode=status_code, headers=HttpHdrObject(hdrKvs=hdr_kvs), body=body_b64
        )

        # Request context (optional)
        http_req = None
        if request_method or request_headers or request_body or request_metadata:
            if not isinstance(request_body, (str, bytes, dict)):
                raise ValidationError(
                    f"Request body must be bytes, str, or dict; got {type(request_body)}"
                )

            req_hdr_kvs = [
                self._header_to_kv(k, v) for k, v in (request_headers or {}).items()
            ]
            if request_body is None:
                req_body_b64 = ""
            elif isinstance(request_body, str):
                req_body_b64 = to_base64_bytes(request_body.encode())
            elif isinstance(request_body, dict):
                # Convert dictionary to JSON string and then encode
                req_body_b64 = base64.b64encode(
                    json.dumps(request_body).encode()
                ).decode()
            else:
                req_body_b64 = to_base64_bytes(request_body)
            http_req = HttpReqObject(
                method=request_method,
                headers=HttpHdrObject(hdrKvs=req_hdr_kvs),
                body=req_body_b64,
            )

        http_meta = HttpMetaObject(url=url)
        return self._inspect(
            http_req,
            http_res,
            http_meta,
            metadata,
            config,
            request_id=request_id,
            timeout=timeout,
        )

    def _inspect(
        self,
        http_req: HttpReqObject,
        http_res: Optional[HttpResObject],
        http_meta: HttpMetaObject,
        metadata: Optional[Metadata] = None,
        config: Optional[InspectionConfig] = None,
        request_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> InspectResponse:
        """
        Implements InspectionClient._inspect for HTTP inspection.
        See base class for contract. Handles validation and sends the inspection request.
        """
        self.config.logger.debug(
            f"_inspect called | http_req: {http_req}, http_res: {http_res}, http_meta: {http_meta}, metadata: {metadata}, config: {config}, request_id: {request_id}"
        )
        # Centralized validation for all HTTP inspection
        if config is None:
            config = InspectionConfig()
        if not config.enabled_rules:
            # Use precomputed default_enabled_rules from InspectionClient
            config.enabled_rules = self.default_enabled_rules
        request = HttpInspectRequest(
            http_req=http_req,
            http_res=http_res,
            http_meta=http_meta,
            metadata=metadata,
            config=config,
        )
        request_dict = self._prepare_request_data(request)
        self.config.logger.debug(f"Prepared request_dict: {request_dict}")
        # Overwrite config with a serializable version
        request_dict.update(self._prepare_inspection_config(config))
        self.validate_inspection_request(request_dict)
        headers = {
            "Content-Type": "application/json",
        }
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
        return self._parse_inspect_response(result)

    def _prepare_request_data(self, request: HttpInspectRequest) -> Dict[str, Any]:
        """
        Recursively convert all dataclass objects and enums in the request to dicts/values so the payload is JSON serializable.
        """
        self.config.logger.debug("Preparing request data for HTTP inspection API.")

        request_dict = {}
        if request.http_req:
            request_dict[HTTP_REQ] = convert(request.http_req)
        if request.http_res:
            request_dict[HTTP_RES] = convert(request.http_res)
        if request.http_meta:
            request_dict[HTTP_META] = convert(request.http_meta)
        if request.metadata:
            request_dict["metadata"] = convert(request.metadata)
        if request.config:
            request_dict["config"] = convert(request.config)
        self.config.logger.debug(f"Prepared request_dict: {request_dict}")
        return request_dict

    def validate_inspection_request(self, request_dict: Dict[str, Any]) -> None:
        """
        Validate both the inspection request dictionary and the config for required structure and fields.

        This validation covers the final serialized request dict (required keys, field types, and presence for API contract).

        Args:
            request_dict (Dict[str, Any]): The request dictionary to validate. Should include a 'config' key if config validation is desired.

        Raises:
            ValidationError: If the request is missing required fields, malformed, or config is invalid.
        """
        self.config.logger.debug(f"Validating request dict: {request_dict}")

        config = request_dict.get("config")
        if config is not None:
            if not config.get("enabled_rules") or not isinstance(
                config["enabled_rules"], list
            ):
                raise ValidationError(
                    "config.enabled_rules must be a non-empty list of Rule objects."
                )
        # Validate request dict structure (API contract)
        http_req = request_dict.get(HTTP_REQ)
        http_res = request_dict.get(HTTP_RES)
        if not http_req:
            raise ValidationError(f"'{HTTP_REQ}' must be provided.")
        if http_req:
            if not isinstance(http_req, dict):
                raise ValidationError(f"'{HTTP_REQ}' must be a dict.")
            if not http_req.get(HTTP_BODY):
                raise ValidationError(f"'{HTTP_REQ}' must have a non-empty 'body'.")
            if not http_req.get(HTTP_METHOD):
                raise ValidationError(f"'{HTTP_REQ}' must have a '{HTTP_METHOD}'.")
            if (
                http_req.get(HTTP_METHOD)
                not in self._request_handler.VALID_HTTP_METHODS
            ):
                raise ValidationError(
                    f"'{HTTP_REQ}' must have a valid '{HTTP_METHOD}' (one of {self._request_handler.VALID_HTTP_METHODS})."
                )
        if http_res:
            if not isinstance(http_res, dict):
                raise ValidationError(f"'{HTTP_RES}' must be a dict.")
            if "statusCode" not in http_res or http_res["statusCode"] is None:
                raise ValidationError(f"'{HTTP_RES}' must have a 'statusCode'.")
            if not http_res.get(HTTP_BODY):
                raise ValidationError(f"'{HTTP_RES}' must have a non-empty 'body'.")

    @staticmethod
    def _header_to_kv(key: str, value: str) -> HttpHdrKvObject:
        """
        Convert a header key-value pair to a HttpHdrKvObject.

        Args:
            key (str): The header key.
            value (str): The header value.

        Returns:
            HttpHdrKvObject: The header key-value object.
        """
        return HttpHdrKvObject(
            key=key,
            value=value,
        )

    def _build_http_req_from_http_library(
        self, http_request: Union[requests.PreparedRequest, requests.Request]
    ) -> HttpReqObject:
        method = getattr(http_request, HTTP_METHOD, None)
        req_headers = dict(getattr(http_request, "headers", {}))
        req_body = (
            getattr(http_request, "data", b"")
            or getattr(http_request, HTTP_BODY, b"")
            or getattr(http_request, "content", b"")
        )

        if not isinstance(req_body, (bytes, str, dict)):
            raise ValidationError("Request body must be bytes, str or dict")

        if isinstance(req_body, str):
            req_body = req_body.encode()
        if isinstance(req_body, dict):
            req_body = json.dumps(req_body).encode()

        req_body_b64 = base64.b64encode(req_body).decode() if req_body else ""
        req_hdr_kvs = [self._header_to_kv(k, v) for k, v in req_headers.items()]
        http_req = HttpReqObject(
            method=method,
            headers=HttpHdrObject(hdrKvs=req_hdr_kvs),
            body=req_body_b64,
        )
        return http_req
