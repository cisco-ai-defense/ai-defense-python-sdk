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

from pathlib import Path
from typing import Optional, Tuple, Dict

from requests import request

from aidefense.config import Config
from aidefense.management.auth import ManagementAuth
from aidefense.management.base_client import BaseClient
from aidefense.request_handler import HttpMethod
from aidefense.runtime.auth import RuntimeAuth
from aidefense.modelscan.models import (
    CreateScanObjectRequest, CreateScanObjectResponse, RegisterScanResponse,
    ModelRepoConfig, ValidateModelUrlResponse, ListScansRequest,
    ListScansResponse, GetScanStatusRequest, GetScanStatusResponse)
from aidefense.modelscan.routes import object_by_id, scan_by_id, SCAN_OBJECTS, SCANS

# Maximum file size in bytes (5GB)
KB = 1024
MB = 1024 * KB
GB = 1024 * MB
MAX_FILE_SIZE_BYTES = 5 * GB

class ModelScan(BaseClient):
    """
    Client for scanning AI/ML model files with Cisco AI Defense.

    The ModelScan class provides methods to upload, scan, and manage security scans of AI/ML model files.
    It communicates with the AI Defense model scanning API endpoints to detect potential security threats,
    malicious code, or other risks in model files.

    Typical usage:
        ```python
        from aidefense.modelscan import ModelScan
        from aidefense.modelscan.models import GetScanStatusRequest
        
        client = ModelScan(api_key="YOUR_MANAGEMENT_API_KEY")
        scan_id = client.register_scan().scan_id
        # ... upload files and trigger scan ...
        request = GetScanStatusRequest(file_limit=10, file_offset=0)
        scan_result = client.get_scan(scan_id, request)
        if scan_result.scan_status_info.status == ScanStatus.COMPLETED:
            print("Scan completed successfully")
        ```

    Args:
        api_key (str): Your Cisco AI Defense API key for authentication.
        config (Config, optional): SDK configuration for endpoints, logging, retries, etc.
            If not provided, a default Config is used.

    Attributes:
        auth (RuntimeAuth): Authentication handler for API requests.
        config (Config): SDK configuration instance.
        api_key (str): The API key used for authentication.
        endpoint_prefix (str): Base URL prefix for all model scan API endpoints.
    """

    def __init__(
            self, api_key: str, config: Optional[Config] = None, request_handler=None):
        """
        Initialize a ModelScan client instance.

        Args:
            api_key (str): Your Cisco AI Defense API key for authentication.
            config (Config, optional): SDK-level configuration for endpoints, logging, retries, etc.
                If not provided, a default Config instance is created.
        """
        super().__init__(ManagementAuth(api_key), config, request_handler)

    def create_scan_object(
            self, scan_id: str, req: CreateScanObjectRequest) -> Tuple[str, str]:
        """
        Create a scan object for a file within an existing scan.

        This method registers a file to be scanned within a scan session and returns
        the object ID and upload URL for the file.

        Args:
            scan_id (str): The unique identifier of the scan session.
            req (CreateScanObjectRequest): Request object containing file details.

        Returns:
            Tuple[str, str]: A tuple containing (object_id, upload_url) where:
                - object_id: Unique identifier for the scan object
                - upload_url: Pre-signed URL for uploading the file

        Example:
            ```python
            from aidefense.modelscan.models import CreateScanObjectRequest
            
            client = ModelScan(api_key="YOUR_MANAGEMENT_API_KEY")
            response = client.register_scan()
            req = CreateScanObjectRequest(file_name="model.pkl", size=1024000)
            object_id, upload_url = client.create_scan_object(response.scan_id, req)
            ```
        """
        res = self.make_request(
            method=HttpMethod.POST,
            path=f"{scan_by_id(scan_id)}/{SCAN_OBJECTS}",
            data=req.to_body_dict(patch=True),
        )
        result = CreateScanObjectResponse.model_validate(res)
        self.config.logger.debug(f"Raw API response: {result}")

        return result.object_id, result.upload_url

    def upload_scan_result(self, scan_id: str, scan_object_id: str, scan_result: dict) -> None:
        """
        Upload scan results for a specific scan object.

        This method is used to submit the results of a scan operation back to the AI Defense service.

        Args:
            scan_id (str): The unique identifier of the scan session.
            scan_object_id (str): The unique identifier of the scan object.
            scan_result (dict): Dictionary containing the scan results and findings.

        Example:
            ```python
            client = ModelScan(api_key="YOUR_MANAGEMENT_API_KEY")
            scan_result = {
                "threats_found": False,
                "scan_details": {"file_type": "pickle", "threats": []}
            }
            client.upload_scan_result(
                scan_id="scan_123",
                scan_object_id="obj_456",
                scan_result=scan_result
            )
            ```
        """
        result = self.make_request(
            method=HttpMethod.POST,
            path=f"{object_by_id(scan_id, scan_object_id)}/results",
            data={"scan_result": scan_result},
        )
        self.config.logger.debug(f"Raw API response: {result}")

    def mark_scan_completed(self, scan_id: str, errors: str = "") -> None:
        """
        Mark a scan as completed, optionally with error information.

        This method finalizes a scan session, indicating that all scanning operations
        have been completed. Any errors encountered during scanning can be reported.

        Args:
            scan_id (str): The unique identifier of the scan session to mark as completed.
            errors (str, optional): Any error messages or details encountered during scanning.
                Defaults to empty string if no errors occurred.

        Example:
            ```python
            client = ModelScan(api_key="YOUR_MANAGEMENT_API_KEY")
            # After completing all scan operations
            client.mark_scan_completed(scan_id="scan_123")
            
            # Or with errors
            client.mark_scan_completed(
                scan_id="scan_123",
                errors="Failed to process file: corrupted data"
            )
            ```
        """
        result = self.make_request(
            method=HttpMethod.PUT,
            path=f"{scan_by_id(scan_id)}/complete",
            data={"errors": errors},
        )
        self.config.logger.debug(f"Raw API response: {result}")

    def register_scan(self) -> RegisterScanResponse:
        """
        Register a new scan session with the AI Defense service.

        This method creates a new scan session and returns a unique scan ID that can be used
        for subsequent operations like uploading files and triggering scans.

        Returns:
            RegisterScanResponse: Response object containing scan_id and supported_file_types.

        Example:
            ```python
            client = ModelScan(api_key="YOUR_MANAGEMENT_API_KEY")
            response = client.register_scan()
            print(f"Created new scan with ID: {response.scan_id}")
            ```
        """
        res = self.make_request(
            method=HttpMethod.POST,
            path=f"{SCANS}/register",
        )
        result = RegisterScanResponse.model_validate(res)
        self.config.logger.debug(f"Raw API response: {result}")
        return result

    def _validate_file_for_upload(self, file_path: Path) -> None:
        if file_path.exists() is False:
            raise FileNotFoundError(f"File not found: {file_path}")

        file_size = file_path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"File size exceeds limit (allowed {MAX_FILE_SIZE_BYTES//GB} GB)")


    def upload_file(self, scan_id: str, file_path: Path) -> bool:
        """
        Upload a file to be scanned within an existing scan session.

        This method handles the complete file upload process: creating a scan object,
        getting the upload URL, and uploading the file content.

        Args:
            scan_id (str): The unique identifier of the scan session.
            file_path (Path): Path to the file to be uploaded and scanned.

        Returns:
            bool: True if the file was successfully uploaded, False otherwise.

        Example:
            ```python
            from pathlib import Path
            
            client = ModelScan(api_key="YOUR_MANAGEMENT_API_KEY")
            scan_id = client.register_scan()
            success = client.upload_file(
                scan_id=scan_id,
                file_path=Path("/path/to/model.pkl")
            )
            if success:
                print("File uploaded successfully")
            ```
        """
        file_path = Path(file_path)
        self._validate_file_for_upload(file_path)

        req = CreateScanObjectRequest(
            file_name=file_path.name,
            size=file_path.stat().st_size,
        )
        _, upload_url = self.create_scan_object(scan_id, req)

        with open(file_path, 'rb') as f:
            result = request(method=HttpMethod.PUT, url=upload_url, data=f)
        self.config.logger.debug(f"Raw API response: {result}")
        return True

    def trigger_scan(self, scan_id: str) -> None:
        """
        Trigger the execution of a scan for all uploaded files in a scan session.

        This method starts the actual scanning process for all files that have been
        uploaded to the specified scan session.

        Args:
            scan_id (str): The unique identifier of the scan session to execute.

        Example:
            ```python
            client = ModelScan(api_key="YOUR_MANAGEMENT_API_KEY")
            scan_id = client.register_scan()
            client.upload_file(scan_id, Path("model.pkl"))
            client.trigger_scan(scan_id)
            print("Scan started")
            ```
        """
        result = self.make_request(
            method=HttpMethod.PUT,
            path=f"{scan_by_id(scan_id)}/run",
        )
        self.config.logger.debug(f"Raw API response: {result}")

    def list_scans(self, req: ListScansRequest) -> ListScansResponse:
        """
        List all scans with pagination support.

        Retrieve a paginated list of all scan sessions associated with the current API key.

        Args:
            req (ListScansRequest): Request object with pagination and filter parameters.

        Returns:
            ListScansResponse: Response object containing scans list with pagination.

        Example:
            ```python
            from aidefense.modelscan.models import ListScansRequest
            
            client = ModelScan(api_key="YOUR_MANAGEMENT_API_KEY")
            
            # Get first 10 scans
            request = ListScansRequest(limit=10, offset=0)
            response = client.list_scans(request)
            
            # Get next 10 scans
            next_request = ListScansRequest(limit=10, offset=10)
            more_scans = client.list_scans(next_request)
            
            for scan in response.scans.items:
                print(f"Scan ID: {scan.scan_id}, Status: {scan.status}")
            ```
        """
        res = self.make_request(
            method=HttpMethod.GET,
            path=SCANS,
            params=req.to_params(),
        )
        result = ListScansResponse.model_validate(res)
        self.config.logger.debug(f"Raw API response: {result}")
        return result

    def get_scan(self, scan_id: str, req: GetScanStatusRequest) -> GetScanStatusResponse:
        """
        Get detailed information about a specific scan with pagination support for results.

        Retrieve comprehensive information about a scan session, including its status,
        results, and associated files.

        Args:
            scan_id (str): The unique identifier of the scan to retrieve.
            req (GetScanStatusRequest): Request object with pagination and filter parameters.

        Returns:
            GetScanStatusResponse: Response object containing detailed scan status information.

        Example:
            ```python
            from aidefense.modelscan.models import GetScanStatusRequest, ScanStatus
            
            client = ModelScan(api_key="YOUR_MANAGEMENT_API_KEY")
            request = GetScanStatusRequest(file_limit=10, file_offset=0)
            response = client.get_scan("scan_123", request)
            
            scan_info = response.scan_status_info
            if scan_info.status == ScanStatus.COMPLETED:
                for file_info in scan_info.analysis_results.items:
                    print(f"File: {file_info.name}, Threats: {len(file_info.threats.items)}")
            ```
        """
        res = self.make_request(
            method=HttpMethod.GET,
            path=scan_by_id(scan_id),
            params=req.to_params(),
        )
        result = GetScanStatusResponse.model_validate(res)
        self.config.logger.debug(f"Raw API response: {result}")
        return result

    def delete_scan(self, scan_id: str) -> None:
        """
        Delete a scan session and all associated data.

        This method permanently removes a scan session, including all uploaded files,
        scan results, and metadata. This action cannot be undone.

        Args:
            scan_id (str): The unique identifier of the scan session to delete.

        Example:
            ```python
            client = ModelScan(api_key="YOUR_MANAGEMENT_API_KEY")
            
            # Delete a completed scan
            client.delete_scan("scan_123")
            print("Scan deleted successfully")
            ```
        """
        result = self.make_request(
            method=HttpMethod.DELETE,
            path=scan_by_id(scan_id),
        )
        self.config.logger.debug(f"Raw API response: {result}")

    def cancel_scan(self, scan_id: str) -> None:
        """
        Cancel a running scan session.

        This method stops a scan that is currently in progress.
        The scan status will be updated to CANCELED.

        Args:
            scan_id (str): The unique identifier of the scan session to cancel.

        Example:
            ```python
            client = ModelScan(api_key="YOUR_MANAGEMENT_API_KEY")
            
            # Cancel a running scan
            client.cancel_scan("scan_123")
            print("Scan canceled")
            ```
        """
        result = self.make_request(
            method="POST",
            path=f"scans/{scan_id}/cancel",
        )
        self.config.logger.debug(f"Raw API response: {result}")

    def validate_scan_url(self, scan_id: str, req: ModelRepoConfig) -> ValidateModelUrlResponse:
        """
        Validate a repository URL for scanning with the AI Defense service.

        This method validates that a repository URL is accessible and properly configured
        for scanning. It checks the URL format, repository type, and authentication
        credentials to ensure the scan can proceed successfully.

        Args:
            scan_id (str): The unique identifier of the scan session.
            req (ModelRepoConfig): Repository configuration with URL, type, and auth.

        Returns:
            ValidateModelUrlResponse: Response indicating if URL is accessible with error details.

        Raises:
            RequestException: If the API request fails due to network issues.
            ValidationError: If the URL format is invalid or authentication fails.
            AuthenticationError: If the provided credentials are invalid or insufficient.

        Example:
            ```python
            from aidefense.modelscan.models import (
                ModelRepoConfig, Auth, HuggingFaceAuth, URLType
            )
            
            client = ModelScan(api_key="YOUR_MANAGEMENT_API_KEY")
            
            # Register a scan first
            response = client.register_scan()
            
            # Validate a HuggingFace repository
            repo_config = ModelRepoConfig(
                url="https://huggingface.co/username/model-name",
                type=URLType.HUGGING_FACE,
                auth=Auth(huggingface=HuggingFaceAuth(access_token="hf_token"))
            )
            result = client.validate_scan_url(response.scan_id, repo_config)
            
            if result.is_accessible:
                client.trigger_scan(response.scan_id)
            else:
                print(f"Validation failed: {result.error_message}")
            ```
        """
        res = self.make_request(
            method=HttpMethod.POST,
            path=f"{scan_by_id(scan_id)}/validate_url",
            data=req.to_body_dict(),
        )
        result = ValidateModelUrlResponse.model_validate(res)
        self.config.logger.debug(f"Raw API response: {result}")
        return result
