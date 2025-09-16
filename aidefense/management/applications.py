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

"""Application management client for the AI Defense Management API."""
from typing import Optional

from .base_client import BaseClient
from .models.application import (
    Application,
    Applications,
    ApplicationSortBy,
    ListApplicationsRequest,
    ListApplicationsResponse,
    CreateApplicationRequest,
    CreateApplicationResponse,
    UpdateApplicationRequest,
    UpdateApplicationResponse,
    DeleteApplicationResponse,
)
from ..config import Config


class ApplicationManagementClient(BaseClient):
    """
    Client for managing applications in the AI Defense Management API.

    Provides methods for creating, retrieving, updating, and deleting
    applications in the AI Defense Management API.
    """

    def __init__(
        self, api_key: str, config: Optional[Config] = None, request_handler=None
    ):
        """
        Initialize the ApplicationManagementClient.

        Args:
            api_key (str): Your AI Defense Management API key for authentication.
            config (Config, optional): SDK configuration for endpoints, logging, retries, etc.
                Defaults to the singleton Config if not provided.
            request_handler: Request handler for making API requests (should be an instance of ManagementClient).
        """
        super().__init__(api_key, config, request_handler)

    def list_applications(
        self, request: ListApplicationsRequest
    ) -> ListApplicationsResponse:
        """
        List applications.

        Args:
            request: ListApplicationsRequest object containing optional parameters:
                - limit: Maximum number of applications to return
                - offset: Number of applications to skip
                - expanded: Whether to include expanded application details
                - sort_by: Field to sort by
                - order: Sort order ('asc' or 'desc')

        Returns:
            ListApplicationsResponse: Response containing a list of applications.

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                request = ListApplicationsRequest(
                    limit=10,
                    sort_by=ApplicationSortBy.application_name,
                    order="asc"
                )
                response = client.applications.list_applications(request)
                for app in response.applications.items:
                    print(f"{app.application_id}: {app.application_name}")
        """
        # Prepare parameters for API call
        params = self._filter_none(
            {
                "limit": request.limit,
                "offset": request.offset,
                "expanded": request.expanded,
                "sort_by": (
                    request.sort_by.value
                    if isinstance(request.sort_by, ApplicationSortBy)
                    else request.sort_by
                ),
                "order": (
                    request.order.value
                    if hasattr(request.order, "value")
                    else request.order
                ),
            }
        )

        response = self.make_request("GET", "applications", params=params)
        applications = self._parse_response(
            Applications, response.get("applications", {}), "applications response"
        )
        return ListApplicationsResponse(applications=applications)

    def get_application(
        self, application_id: str, expanded: bool = None
    ) -> Application:
        """
        Get an application by ID.

        Args:
            application_id (str): ID of the application
            expanded (bool, optional): Whether to include expanded details

        Returns:
            Application: Response containing application details.

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                application_id = "123e4567-e89b-12d3-a456-426614174000"
                application = client.applications.get_application(application_id, expanded=True)
                print(f"Application name: {application.application_name}")
        """
        params = self._filter_none({"expanded": expanded})
        response = self.make_request(
            "GET", f"applications/{application_id}", params=params
        )
        application = self._parse_response(
            Application, response.get("application", {}), "application response"
        )
        return application

    def create_application(
        self, request: CreateApplicationRequest
    ) -> CreateApplicationResponse:
        """
        Create an application.

        Args:
            request: The application creation request containing:
                - application_name: Name for the application
                - description: Description for the application (optional)
                - connection_type: Type of connection (API or Gateway)

        Returns:
            CreateApplicationResponse: The created application ID

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                request = CreateApplicationRequest(
                    application_name="My App",
                    description="My description",
                    connection_type=ConnectionType.API
                )
                response = client.applications.create_application(request)
                print(f"Created application with ID: {response.application_id}")
        """
        data = self._filter_none(
            {
                "application_name": request.application_name,
                "description": request.description,
                "connection_type": (
                    request.connection_type.value
                    if hasattr(request.connection_type, "value")
                    else request.connection_type
                ),
            }
        )

        response = self.make_request("POST", "applications", data=data)
        return CreateApplicationResponse(
            application_id=response.get("application_id", "")
        )

    def update_application(
        self, application_id: str, request: UpdateApplicationRequest
    ) -> UpdateApplicationResponse:
        """
        Update an application.

        Args:
            application_id (str): ID of the application to update
            request: UpdateApplicationRequest containing:
                - application_name: New name (optional)
                - description: New description (optional)

        Returns:
            UpdateApplicationResponse: Empty response object.

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                application_id = "123e4567-e89b-12d3-a456-426614174000"
                request = UpdateApplicationRequest(
                    application_name="Updated App Name",
                    description="Updated description"
                )
                response = client.applications.update_application(application_id, request)
        """
        data = self._filter_none(
            {
                "application_name": request.application_name,
                "description": request.description,
            }
        )
        self.make_request("PUT", f"applications/{application_id}", data=data)
        return UpdateApplicationResponse()

    def delete_application(self, application_id: str) -> DeleteApplicationResponse:
        """
        Delete an application.

        Args:
            application_id (str): ID of the application to delete

        Returns:
            DeleteApplicationResponse: Empty response object.

        Raises:
            ValidationError, ApiError, SDKError

        Example:
            .. code-block:: python

                application_id = "123e4567-e89b-12d3-a456-426614174000"
                response = client.applications.delete_application(application_id)
        """
        self.make_request("DELETE", f"applications/{application_id}")
        return DeleteApplicationResponse()
