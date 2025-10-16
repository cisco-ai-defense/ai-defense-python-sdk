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
from time import sleep
from typing import Dict, Union

from .model_scan_base import ModelScan
from .models import ScanStatus, ModelRepoConfig, ScanStatusInfo, GetScanStatusRequest

RETRY_COUNT_FOR_SCANNING = 30
WAIT_TIME_SECS_SUCCESSIVE_SCAN_INFO_CHECK = 2
END_SCAN_STATUS = [ScanStatus.COMPLETED, ScanStatus.FAILED, ScanStatus.CANCELED]

class ModelScanClient(ModelScan):
    """
    High-level client for AI Defense model scanning operations.

    ModelScanClient extends the base ModelScan class to provide convenient methods
    for scanning both individual files and entire repositories. It handles the complete
    scan workflow including registration, upload, execution, monitoring, and cleanup.

    This client automatically manages scan lifecycle, including error handling and
    resource cleanup to ensure scans don't leave orphaned resources in the system.

    Typical Usage:
        ```python
        from aidefense.modelscan import ModelScanClient
        from aidefense.modelscan.models import (
            ModelRepoConfig, Auth, HuggingFaceAuth, URLType, ScanStatus
        )
        from aidefense import Config
        
        # Initialize the client
        client = ModelScanClient(
            api_key="YOUR_MANAGEMENT_API_KEY",
            config=Config(management_base_url="https://api.security.cisco.com")
        )
        
        # Scan a local file
        file_result = client.scan_file("/path/to/model.pkl")
        if file_result.status == ScanStatus.COMPLETED:
            print("File scan completed")
        
        # Scan a repository
        repo_config = ModelRepoConfig(
            url="https://huggingface.co/username/model-name",
            type=URLType.HUGGING_FACE,
            auth=Auth(huggingface=HuggingFaceAuth(access_token="hf_token"))
        )
        repo_result = client.scan_repo(repo_config)
        if repo_result.status == ScanStatus.COMPLETED:
            print("Repository scan completed")
        ```

    Attributes:
        Inherits all attributes from the base ModelScan class including:
        - api_key: The API key for authentication
        - config: Configuration object with service settings
        - auth: Authentication handler
        - endpoint_prefix: Base URL for API endpoints
    """
    def __get_scan_info_wait_until_status(self, scan_id: str, status: [ScanStatus]) -> ScanStatusInfo:
        """
        Wait for a scan to reach one of the specified status values.

        This private method polls the scan status at regular intervals until it reaches
        one of the target statuses or times out.

        Args:
            scan_id (str): The unique identifier of the scan to monitor.
            status (List[ScanStatus]): List of acceptable status values to wait for.

        Returns:
            ScanStatusInfo: The scan status information when the target status is reached.

        Raises:
            Exception: If the scan times out before reaching the target status.
        """
        for _ in range(RETRY_COUNT_FOR_SCANNING):
            info = self.get_scan(scan_id, GetScanStatusRequest(file_limit=50, file_offset=0))
            if info and info.scan_status_info.status in status:
                return info.scan_status_info

            sleep(WAIT_TIME_SECS_SUCCESSIVE_SCAN_INFO_CHECK)

        raise Exception("Scan timed out")

    def cleanup_scan_data(self, scan_id: str) -> None:
        self.cancel_scan(scan_id)
        self.__get_scan_info_wait_until_status(scan_id, ScanStatus.CANCELED)
        self.delete_scan(scan_id)


    def scan_file(self, file_path: Union[Path, str]) -> ScanStatusInfo:
        """
        Run a complete security scan on a model file using the AI Defense service.

        This is the main method for scanning files. It handles the entire scan workflow:
        registering a scan, uploading the file, triggering the scan, waiting for completion,
        and returning the results. If any errors occur, it automatically cleans up by
        canceling and deleting the scan.

        Args:
            file_path (Union[Path, str]): Path to the model file to be scanned.
                Can be a string path or pathlib.Path object.

        Returns:
            ScanStatusInfo: Complete scan status information including:
                - scan_id: The scan session identifier
                - status: Final scan status
                - analysis_results: List of file analysis results with threats
                - created_at/completed_at: Timestamps

        Raises:
            Exception: If the scan fails, times out, or encounters any errors during processing.
                The scan will be automatically canceled and cleaned up before raising the exception.

        Example:
            ```python
            from pathlib import Path
            from aidefense.modelscan import ModelScanClient
            from aidefense.modelscan.models import ScanStatus
            
            client = ModelScanClient(api_key="YOUR_MANAGEMENT_API_KEY")
            
            try:
                # Scan a pickle file
                result = client.scan_file("/path/to/suspicious_model.pkl")
                
                # Check the results
                if result.status == ScanStatus.COMPLETED:
                    print("Scan completed successfully")
                    
                    # Check for threats
                    for file_info in result.analysis_results.items:
                        if file_info.threats.items:
                            print(f"⚠️  Threats found in {file_info.name}")
                        else:
                            print(f"✅ {file_info.name} is clean")
                            
                elif result.status == ScanStatus.FAILED:
                    print("Scan failed")
                    
            except Exception as e:
                print(f"Scan error: {e}")
            ```
        """
        res = self.register_scan()
        file_path = Path(file_path)
        try:
            self.upload_file(res.scan_id, file_path)
            self.trigger_scan(res.scan_id)
            scan_info = self.__get_scan_info_wait_until_status(res.scan_id, END_SCAN_STATUS)
        except Exception as e:
            if res.scan_id:
                self.cleanup_scan_data(res.scan_id)
            raise e

        return scan_info

    def scan_repo(self, repo_config: ModelRepoConfig) -> ScanStatusInfo:  # type: ignore
        """
        Run a complete security scan on a model repository using the AI Defense service.

        This method handles the entire repository scan workflow: registering a scan,
        validating the repository URL and credentials, triggering the scan, waiting
        for completion, and returning the results. If any errors occur, it automatically
        cleans up by canceling and deleting the scan.

        Args:
            repo_config (ModelRepoConfig): Configuration object containing the repository
                URL, type, authentication credentials, and other scan parameters.

        Returns:
            ScanStatusInfo: Complete scan status information including:
                - scan_id: The scan session identifier
                - status: Final scan status
                - analysis_results: Repository analysis results with file-by-file findings
                - repository: Metadata about the scanned repository

        Raises:
            Exception: If the scan fails, times out, or encounters any errors during processing.
                The scan will be automatically canceled and cleaned up before raising the exception.
            ValidationError: If the repository URL is invalid or inaccessible.
            AuthenticationError: If the provided repository credentials are invalid.

        Example:
            ```python
            from aidefense.modelscan import ModelScanClient
            from aidefense.modelscan.models import (
                ModelRepoConfig, Auth, HuggingFaceAuth, URLType, ScanStatus
            )
            
            client = ModelScanClient(api_key="YOUR_MANAGEMENT_API_KEY")
            
            try:
                # Configure repository scan
                repo_config = ModelRepoConfig(
                    url="https://huggingface.co/username/suspicious-model",
                    type=URLType.HUGGING_FACE,
                    auth=Auth(huggingface=HuggingFaceAuth(access_token="hf_token"))
                )
                
                # Run the scan
                result = client.scan_repo(repo_config)
                
                # Check the results
                if result.status == ScanStatus.COMPLETED:
                    print("Repository scan completed successfully")
                    
                    # Check for threats
                    for file_info in result.analysis_results.items:
                        if file_info.threats.items:
                            print(f"⚠️  Threats found in {file_info.name}")
                        else:
                            print(f"✅ {file_info.name} is clean")

                elif result.status == ScanStatus.FAILED:
                    print("Repository scan failed")
                    
            except Exception as e:
                print(f"Repository scan error: {e}")
            ```
        """
        res = self.register_scan()
        try:
            self.validate_scan_url(res.scan_id, repo_config)
            self.trigger_scan(res.scan_id)
            scan_info = self.__get_scan_info_wait_until_status(res.scan_id, END_SCAN_STATUS)
        except Exception as e:
            if res.scan_id:
                self.cleanup_scan_data(res.scan_id)
            raise e

        return scan_info
