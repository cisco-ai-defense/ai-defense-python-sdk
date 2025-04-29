"""Base client implementation for interacting with APIs."""

import requests
import uuid
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from requests.auth import AuthBase

from .version import version
from .config import Config
from .exceptions import SDKError, ValidationError, ApiError

REQUEST_ID_HEADER = "x-aidefense-request-id"


class BaseClient(ABC):
    """
    Base client for all API interactions.

    Provides methods for making HTTP requests, handling errors, and managing
    session configurations.

    Attributes:
        USER_AGENT (str): The user agent string for the SDK.
        config (Config): The configuration object for the client.
        _session (requests.Session): The HTTP session used for making requests.
    """

    USER_AGENT = f"Cisco-AI-Defense-Python-SDK/{version}"
    VALID_HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}

    def __init__(self, config: Config):
        """
        Initialize the BaseClient.

        Args:
            config (Config): The configuration object containing settings like
                             connection pool, timeout, and logger.
        """
        self.config = config
        self._session = requests.Session()
        # Apply connection pool config
        self._session.mount("https://", config.connection_pool)
        self._session.headers.update(
            {"User-Agent": self.USER_AGENT, "Content-Type": "application/json"}
        )

    def get_request_id(self) -> str:
        """Generate a unique request ID.

        Returns:
            str: A unique identifier for the request.
        """
        request_id = str(uuid.uuid4())
        self.config.logger.debug(f"get_request_id called | returning: {request_id}")
        return request_id

    def request(
        self,
        method: str,
        url: str,
        auth: AuthBase,
        request_id: str = None,
        headers: Dict = None,
        json_data: Dict = None,
        timeout: int = None,
    ) -> Dict:
        """Make an HTTP request with error handling.

        Args:
            method (str): The HTTP method (e.g., 'GET', 'POST').
            url (str): The URL for the request.
            auth (AuthBase): The authentication object for the request.
            headers (Dict, optional): Additional headers for the request.
            json_data (Dict, optional): JSON payload for the request.
            timeout (int, optional): Timeout for the request in seconds.

        Returns:
            Dict: The JSON response from the API.

        Raises:
            SDKError: For authentication errors.
            ValidationError: For bad requests.
            ApiError: For other API errors.
        """
        self.config.logger.debug(
            f"request called | method: {method}, url: {url}, request_id: {request_id}, headers: {headers}, json_data: {json_data}"
        )
        try:
            if method not in self.VALID_HTTP_METHODS:
                raise ValidationError(f"Invalid HTTP method: {method}")

            if not url or not url.startswith(("http://", "https://")):
                raise ValidationError(f"Invalid URL: {url}")

            headers = headers or {}
            request_id = request_id or self.get_request_id()
            headers[REQUEST_ID_HEADER] = request_id

            # Use the provided auth object to set headers
            if auth:
                request = requests.Request(
                    method=method, url=url, headers=headers, json=json_data
                )
                prepared_request = auth(request.prepare())
                headers.update(prepared_request.headers)

            response = self._session.request(
                method=method,
                url=url,
                headers=headers,
                json=json_data,
                timeout=timeout or self.config.timeout,
            )

            if response.status_code >= 400:
                return self._handle_error_response(response, request_id)

            return response.json()

        except requests.RequestException as e:
            self.config.logger.error(f"Request failed: {e}")
            raise

    def _handle_error_response(
        self, response: requests.Response, request_id: str = None
    ) -> Dict:
        """Handle error responses from the API.

        Args:
            response (requests.Response): The HTTP response object.
            request_id (str, optional): The unique request ID for tracing the failed API call.

        Returns:
            Dict: The parsed error data.

        Raises:
            SDKError: For authentication errors.
            ValidationError: For bad requests.
            ApiError: For other API errors.
        """
        self.config.logger.debug(
            f"_handle_error_response called | status_code: {response.status_code}, response: {response.text}"
        )
        try:
            error_data = response.json()
        except ValueError:
            error_data = {"message": response.text or "Unknown error"}

        error_message = error_data.get("message", "Unknown error")

        if response.status_code == 401:
            raise SDKError(
                f"Authentication error: {error_message}", response.status_code
            )
        elif response.status_code == 400:
            raise ValidationError(f"Bad request: {error_message}", response.status_code)
        else:
            raise ApiError(
                f"API error {response.status_code}: {error_message}",
                response.status_code,
                request_id=request_id,
            )
