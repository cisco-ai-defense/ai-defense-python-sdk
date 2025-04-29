import base64
from typing import Dict, Optional, Any, Union, List
import requests

from .constants import HTTP_REQ, HTTP_RES, HTTP_META, HTTP_METHOD, HTTP_BODY

from .inspection_client import InspectionClient
from ..exceptions import ValidationError
from .http_models import (
    HttpInspectRequest,
    HttpReqObject,
    HttpResObject,
    HttpMetaObject,
    HttpHdrObject,
    HttpHdrKvObject,
)
from .models import Metadata, InspectionConfig, InspectResponse, Rule, RuleName
from ..config import Config
from .utils import convert, to_base64_bytes


class HttpInspectionClient(InspectionClient):
    """
    Provides security and privacy inspection for HTTP requests and responses.

    Use this client to analyze HTTP traffic (requests or responses) for sensitive data, policy violations, or unsafe content. Supports both raw HTTP dictionaries and objects from popular HTTP libraries (e.g., requests, aiohttp).

    Example:
        client = HttpInspectionClient(api_key="...", config=Config(...))
        result = client.inspect_http_raw(http_req={...})
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

    def inspect_http_raw(
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
        Direct interface for HTTP API inspection using raw dicts for http_req, http_res, and http_meta.
        Advanced users can interact directly with the HTTP inspection API.

        Args:
            http_req (dict, optional): HTTP request dictionary.
            http_res (dict, optional): HTTP response dictionary.
            http_meta (dict, optional): HTTP metadata dictionary.
            metadata (Metadata, optional): Additional metadata.
            config (InspectionConfig, optional): Inspection configuration.
            request_id (str, optional): Unique identifier for the request (usually a UUID) to enable request tracing.

        Note:
            - The 'body' field for both request and response dicts must be a base64-encoded string representing the original bytes.
            - If you have a str, encode it to bytes first, then base64 encode.

        Returns:
            InspectResponse: Inspection results as an InspectResponse object.
        """
        self.config.logger.debug(
            f"inspect_http_raw called | http_req: {http_req}, http_res: {http_res}, http_meta: {http_meta}, metadata: {metadata}, config: {config}, request_id: {request_id}"
        )

        # Validate and encode bodies if necessary
        def ensure_base64_body(d: Optional[Dict[str, Any]]) -> None:
            if d and d.get(HTTP_BODY):
                body = d[HTTP_BODY]
                if isinstance(body, bytes):
                    d[HTTP_BODY] = to_base64_bytes(body)
                elif isinstance(body, str):
                    # Heuristic: if not valid base64, treat as raw string and encode
                    try:
                        base64.b64decode(body)
                        # Already base64
                    except Exception:
                        d[HTTP_BODY] = to_base64_bytes(body)
                elif body is None:
                    d[HTTP_BODY] = ""
                else:
                    raise ValueError(
                        "HTTP body must be bytes, str, or base64-encoded string."
                    )

        if http_req:
            ensure_base64_body(convert(http_req))
        if http_res:
            ensure_base64_body(convert(http_res))
        return self._inspect(
            http_req, http_res, http_meta, metadata, config, request_id=request_id, timeout=timeout
        )

    def inspect_request_from_http_library(
        self,
        http_request: Any,
        metadata: Optional[Metadata] = None,
        config: Optional[InspectionConfig] = None,
        request_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> InspectResponse:
        """
        Inspect an HTTP request from a popular HTTP library (e.g., requests, aiohttp).

        Args:
            http_request: HTTP request object from a supported library (e.g., requests.Request, requests.PreparedRequest).
            metadata (Metadata, optional): Additional metadata for inspection.
            config (InspectionConfig, optional): Inspection configuration.
            request_id (str, optional): Unique identifier for the request (usually a UUID) to enable request tracing.

        Returns:
            InspectResponse: Inspection result.
        """
        self.config.logger.debug(
            f"inspect_request_from_http_library called | http_request: {http_request}, metadata: {metadata}, config: {config}, request_id: {request_id}"
        )
        method = None
        headers = {}
        body = b""
        url = None
        # Support both requests.PreparedRequest and requests.Request
        if isinstance(http_request, requests.PreparedRequest) or isinstance(http_request, requests.Request):
            method = getattr(http_request, HTTP_METHOD, None)
            headers = dict(getattr(http_request, "headers", {}))
            body = getattr(http_request, HTTP_BODY, b"") or getattr(http_request, "data", b"")
            url = getattr(http_request, "url", None)
            if isinstance(body, str):
                body = body.encode()
        else:
            raise ValueError("Unsupported HTTP request type: only requests.Request and requests.PreparedRequest are supported")

        # Fallback for unknown types
        if not method:
            method = getattr(http_request, HTTP_METHOD, None)
        if not headers:
            headers = dict(getattr(http_request, "headers", {}))
        if not body:
            body = getattr(http_request, HTTP_BODY, b"") or getattr(
                http_request, "content", b""
            )
            if isinstance(body, str):
                body = body.encode()
        if not url:
            url = getattr(http_request, "url", None)
            if url is not None:
                url = str(url)
        # Prepare and inspect
        hdr_kvs = [self._header_to_kv(k, v) for k, v in headers.items()]
        # Always base64-encode bytes body
        if not isinstance(body, (bytes, type(None))):
            raise ValueError(
                "HTTP request body must be bytes or None for base64 encoding."
            )

        http_req = HttpReqObject(
            method=method,
            headers=HttpHdrObject(hdrKvs=hdr_kvs),
            body=to_base64_bytes(body or b""),
        )
        http_meta = HttpMetaObject(url=url or "")
        return self._inspect(
            http_req, None, http_meta, metadata, config, request_id=request_id, timeout=timeout
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
        Inspect an HTTP response from a supported HTTP library (e.g., requests, aiohttp).

        Args:
            http_response: HTTP response object from a supported library.
            metadata (Metadata, optional): Additional metadata for inspection.
            config (InspectionConfig, optional): Inspection configuration.
            request_id (str, optional): Unique identifier for the request (usually a UUID) to enable request tracing.

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
            raise ValueError("Unsupported HTTP response type: only requests.Response is supported")

        body_b64 = to_base64_bytes(body) if body else ""
        hdr_kvs = [self._header_to_kv(k, v) for k, v in (headers or {}).items()]
        http_res = HttpResObject(
            statusCode=status_code, headers=HttpHdrObject(hdrKvs=hdr_kvs), body=body_b64
        )
        # Build http_req from associated request if possible
        http_req = None
        if http_request is not None:
            method = getattr(http_request, HTTP_METHOD, None)
            req_headers = dict(getattr(http_request, "headers", {}))
            req_body = getattr(http_request, HTTP_BODY, b"") or getattr(http_request, "data", b"") or getattr(http_request, "content", b"")
            if isinstance(req_body, str):
                req_body = req_body.encode()
            req_body_b64 = base64.b64encode(req_body).decode() if req_body else ""
            req_hdr_kvs = [self._header_to_kv(k, v) for k, v in req_headers.items()]
            http_req = HttpReqObject(
                method=method,
                headers=HttpHdrObject(hdrKvs=req_hdr_kvs),
                body=req_body_b64,
            )
        # If http_req could not be built, raise a clear error
        if http_req is None:
            raise ValueError(
                "Could not extract HTTP request context from response object. 'http_req' is required for inspection."
            )
        http_meta = HttpMetaObject(url=url)
        return self._inspect(
            http_req, http_res, http_meta, metadata, config, request_id=request_id, timeout=timeout
        )

    def inspect_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        body: Union[str, bytes, None] = None,
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
            body (bytes or str, optional): Request body as bytes or string.
            metadata (Metadata, optional): Additional metadata for inspection.
            config (InspectionConfig, optional): Inspection configuration.
            request_id (str, optional): Unique identifier for the request (usually a UUID) to enable request tracing.

        Returns:
            InspectResponse: Inspection result.
        """
        if body is None:
            body_b64 = ""
        elif isinstance(body, str):
            body_b64 = base64.b64encode(body.encode()).decode()
        else:
            body_b64 = base64.b64encode(body).decode()
        hdr_kvs = [self._header_to_kv(k, v) for k, v in (headers or {}).items()]
        http_req = HttpReqObject(
            method=method, headers=HttpHdrObject(hdrKvs=hdr_kvs), body=body_b64
        )
        http_meta = HttpMetaObject(url=url)
        return self._inspect(
            http_req, None, http_meta, metadata, config, request_id=request_id, timeout=timeout
        )

    def inspect_response(
        self,
        status_code: int,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        body: Union[str, bytes, None] = None,
        request_method: Optional[str] = None,
        request_headers: Optional[dict] = None,
        request_body: Optional[bytes] = None,
        request_metadata: Optional[Metadata] = None,
        metadata: Optional[Metadata] = None,
        config: Optional[InspectionConfig] = None,
        request_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> InspectResponse:
        """
        Inspect an HTTP response (status code, url, headers, body), with optional request context and metadata, for security, privacy, and policy violations.

        Args:
            status_code (int): HTTP response status code.
            url (str): URL associated with the response.
            headers (dict, optional): HTTP headers for the response.
            body (bytes or str, optional): Response body as bytes or string.
            request_method (str, optional): HTTP request method for context.
            request_headers (dict, optional): HTTP request headers for context.
            request_body (bytes or str, optional): HTTP request body for context.
            request_metadata (Metadata, optional): Additional metadata for the request context.
            metadata (Metadata, optional): Additional metadata for the response context.
            config (InspectionConfig, optional): Inspection configuration rules.
            request_id (str, optional): Unique identifier for the request (usually a UUID) to enable request tracing.

        Returns:
            InspectResponse: The inspection result.
        """
        self.config.logger.debug(
            f"inspect_response called | status_code: {status_code}, url: {url}, headers: {headers}, body: {body}, request_method: {request_method}, request_headers: {request_headers}, request_body: {request_body}, request_metadata: {request_metadata}, metadata: {metadata}, config: {config}, request_id: {request_id}"
        )
        # Response body encoding
        if body is None:
            body_b64 = ""
        elif isinstance(body, str):
            body_b64 = base64.b64encode(body.encode()).decode()
        else:
            body_b64 = base64.b64encode(body).decode()
        hdr_kvs = [self._header_to_kv(k, v) for k, v in (headers or {}).items()]
        http_res = HttpResObject(
            statusCode=status_code, headers=HttpHdrObject(hdrKvs=hdr_kvs), body=body_b64
        )

        # Request context (optional)
        http_req = None
        if request_method or request_headers or request_body or request_metadata:
            req_hdr_kvs = [
                self._header_to_kv(k, v) for k, v in (request_headers or {}).items()
            ]
            if request_body is None:
                req_body_b64 = ""
            elif isinstance(request_body, str):
                req_body_b64 = to_base64_bytes(request_body.encode())
            else:
                req_body_b64 = to_base64_bytes(request_body)
            http_req = HttpReqObject(
                method=request_method,
                headers=HttpHdrObject(hdrKvs=req_hdr_kvs),
                body=req_body_b64,
            )
            # Optionally attach request_metadata to the request as needed by your API
            # (If you want to attach request_metadata to the main metadata, merge here or pass as a separate field)

        http_meta = HttpMetaObject(url=url)
        return self._inspect(
            http_req, http_res, http_meta, metadata, config, request_id=request_id, timeout=timeout
        )

    def _inspect(
        self,
        http_req: HttpReqObject,
        http_res: Optional[HttpResObject],
        http_meta: HttpMetaObject,
        metadata: Optional[Metadata] = None,
        config: Optional[InspectionConfig] = None,
        entities_map: Optional[Dict[str, List[str]]] = None,
        request_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> InspectResponse:
        """
        Implements InspectionClient._inspect for HTTP inspection.
        See base class for contract. Handles validation and sends the inspection request.
        """
        self.config.logger.debug(
            f"_inspect called | http_req: {http_req}, http_res: {http_res}, http_meta: {http_meta}, metadata: {metadata}, config: {config}, entities_map: {entities_map}, request_id: {request_id}"
        )
        # Centralized validation for all HTTP inspection
        if config is None:
            config = InspectionConfig()
        if not config.enabled_rules:
            if entities_map:
                # Use user-provided entities_map
                config.enabled_rules = [
                    Rule(rule_name=rn, entity_types=entities_map.get(rn))
                    for rn in RuleName
                ]
            else:
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
            if http_req.get(HTTP_METHOD) not in VALID_HTTP_METHODS:
                raise ValidationError(f"'{HTTP_REQ}' must have a valid '{HTTP_METHOD}' (one of {VALID_HTTP_METHODS}).")
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
