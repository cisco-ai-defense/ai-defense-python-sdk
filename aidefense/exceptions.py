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


class SDKError(Exception):
    """
    Base exception for SDK errors.

    Attributes:
        message (str): The error message.
        status_code (int, optional): The HTTP status code associated with the error.
    """

    def __init__(self, message: str, status_code: int = None):
        """
        Initialize the SDKError.

        Args:
            message (str): The error message.
            status_code (int, optional): The HTTP status code associated with the error.
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ValidationError(SDKError):
    """
    Exception for validation errors.

    Raised when input validation fails.
    """

    pass


class ApiError(SDKError):
    """
    Exception for API errors.

    Raised when an API call returns an error response.

    Attributes:
        message (str): The error message.
        status_code (int, optional): The HTTP status code associated with the error.
        request_id (str, optional): The unique request ID for tracing the failed API call.
    """

    def __init__(self, message: str, status_code: int = None, request_id: str = None):
        """
        Initialize the ApiError.

        Args:
            message (str): The error message.
            status_code (int, optional): The HTTP status code associated with the error.
            request_id (str, optional): The unique request ID for tracing the failed API call.
        """
        super().__init__(message, status_code)
        self.request_id = request_id
