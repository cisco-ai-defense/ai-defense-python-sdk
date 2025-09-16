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

"""Base client for the AI Defense Management API."""

from typing import Dict, Any, Optional, Type, TypeVar, cast, Protocol, runtime_checkable
from pydantic import BaseModel, ValidationError as PydanticValidationError

from ..config import Config
from .auth import ManagementAuth
from ..request_handler import RequestHandler
from ..exceptions import ResponseParseError, ValidationError

# Type variable for Pydantic models
T = TypeVar('T', bound=BaseModel)

class BaseClient:
    """
    Base client for all resource clients in the AI Defense Management API.
    
    This client provides common functionality for authentication, request handling,
    and resource management. Resource-specific clients should inherit from this class.
    
    Args:
        api_key (str): Your AI Defense Management API key for authentication.
        config (Config, optional): SDK configuration for endpoints, logging, retries, etc.
            If not provided, a default singleton Config is used.
        request_handler: The request handler to use for making API requests.
            This should be an instance of ManagementClient.
        api_version (str, optional): API version to use. Default is "v1".
    
    Attributes:
        api_key (str): The API key used for management API authentication.
        config (Config): The runtime configuration object.
        api_version (str): The API version being used.
    """
    
    # Default API version
    DEFAULT_API_VERSION = "v1"
    
    def __init__(
        self,
        api_key: str,
        config: Optional[Config] = None,
        request_handler: Optional[RequestHandler] = None,
        api_version: Optional[str] = None
    ):
        """
        Initialize the BaseClient.
        
        Args:
            api_key (str): Your AI Defense Management API key for authentication.
            config (Config, optional): SDK configuration for endpoints, logging, retries, etc.
                If not provided, a default singleton Config is used.
            request_handler: The request handler to use for making API requests.
                This should be an instance of ManagementClient.
            api_version (str, optional): API version to use. Default is "v1".
        """
        self.api_key = api_key
        self.config = config or Config()
        self._auth = ManagementAuth(api_key)
        self.api_version = api_version or self.DEFAULT_API_VERSION
        
        self._request_handler = request_handler or RequestHandler(config)

    
    def _get_url(self, path: str) -> str:
        """
        Construct the full URL for an API endpoint.

        Args:
            path (str): The API endpoint path.

        Returns:
            str: The full URL for the API endpoint.
        """
        # Use the management_base_url from config and append the API path
        base_url = self.config.management_base_url.rstrip('/')
        api_path = f"/api/ai-defense/{self.api_version}".rstrip('/')
        path = path.lstrip('/')

        return f"{base_url}{api_path}/{path}"
    
    def _filter_none(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter out None values from a dictionary.
        
        Args:
            data: Dictionary to filter
            
        Returns:
            Dictionary with None values removed
        """
        return {k: v for k, v in data.items() if v is not None}
    
    def _parse_response(self, model_class: Type[T], data: Any, context: str) -> T:
        """
        Parse API response into a Pydantic model.
        
        Args:
            model_class: Pydantic model class to parse into
            data: Data to parse
            context: Context for error messages
            
        Returns:
            Parsed model instance
            
        Raises:
            ValidationError: If the data fails validation
            ResponseParseError: If the response cannot be parsed
        """
        if data is None:
            raise ResponseParseError(
                message=f"Missing required data for {context}",
                response_data=data
            )
            
        try:
            return cast(T, model_class.parse_obj(data))
        except PydanticValidationError as e:
            self.config.logger.warning(f"Failed to parse {context}: {e}")
            raise ResponseParseError(f"Failed to parse {context}: {e}") from e
    
    def make_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make a request to the API.

        Args:
            method (str): HTTP method (GET, POST, PUT, DELETE).
            path (str): API endpoint path.
            params (Dict[str, Any], optional): Query parameters.
            data (Dict[str, Any], optional): Request body data.
            headers (Dict[str, str], optional): Additional headers.

        Returns:
            Dict[str, Any]: The API response.

        Raises:
            ValidationError: For bad requests.
            ApiError: For API errors.
            SDKError: For other errors.
            ResponseParseError: If the response cannot be parsed.
        """
        url = self._get_url(path)
        
        return self._request_handler.request(
            method=method,
            url=url,
            auth=self._auth,
            headers=headers,
            json_data=data,
            params=params,
            timeout=self.config.timeout
        )
