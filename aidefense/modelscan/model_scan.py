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

import os
from pathlib import Path
import sys
from time import monotonic, sleep
from typing import Collection, Optional, Union

from aidefense.exceptions import ScanTimeoutError, ValidationError
from .model_scan_base import (
    DEFAULT_MULTIPART_CONCURRENCY,
    ModelScan,
    UploadProgressCallback,
)
from .models import ScanStatus, ModelRepoConfig, ScanStatusInfo, GetScanStatusRequest

RETRY_COUNT_FOR_SCANNING = int(os.environ.get("AIDEFENSE_MODELSCAN_RETRY_COUNT", "120"))
WAIT_TIME_SECS_SUCCESSIVE_SCAN_INFO_CHECK = int(
    os.environ.get("AIDEFENSE_MODELSCAN_WAIT_TIME_SECS", "5")
)
DEFAULT_SCAN_TIMEOUT_SECONDS = (
    RETRY_COUNT_FOR_SCANNING * WAIT_TIME_SECS_SUCCESSIVE_SCAN_INFO_CHECK
)
END_SCAN_STATUS = [ScanStatus.COMPLETED, ScanStatus.FAILED, ScanStatus.CANCELED]
STATUS_SPINNER_REFRESH_SECONDS = 0.1


class _ConsoleStatusSpinner:
    """Render scan polling activity without adding a third-party dependency."""

    _FRAMES = ("|", "/", "-", "\\")

    def __init__(self):
        self._frame_index = 0
        self._rendered = False

    def render(self) -> None:
        frame = self._FRAMES[self._frame_index % len(self._FRAMES)]
        self._frame_index += 1
        self._rendered = True
        print(
            f"\r{frame} Upload complete. Waiting for scan status...",
            end="",
            file=sys.stderr,
            flush=True,
        )

    def wait(self, seconds: float) -> None:
        elapsed = 0.0
        while elapsed < seconds:
            self.render()
            delay = min(STATUS_SPINNER_REFRESH_SECONDS, seconds - elapsed)
            sleep(delay)
            elapsed += delay

    def close(self) -> None:
        if self._rendered:
            print("\r" + " " * 64 + "\r", end="", file=sys.stderr, flush=True)


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

    def __get_scan_info_wait_until_status(
        self,
        scan_id: str,
        statuses: Collection[ScanStatus],
        timeout_seconds: float = DEFAULT_SCAN_TIMEOUT_SECONDS,
        show_spinner: bool = True,
    ) -> ScanStatusInfo:
        """
        Wait for a scan to reach one of the specified status values.

        This private method polls the scan status at regular intervals until it reaches
        one of the target statuses or times out.

        Args:
            scan_id (str): The unique identifier of the scan to monitor.
            statuses: Acceptable status values to wait for.
            timeout_seconds: Maximum time to wait for a terminal status.
            show_spinner: Show a console spinner between status polls.

        Returns:
            ScanStatusInfo: The scan status information when the target status is reached.

        Raises:
            ScanTimeoutError: If polling expires. The server-side scan is preserved.
        """
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or timeout_seconds <= 0
        ):
            raise ValueError("scan_timeout_seconds must be greater than zero")

        deadline = monotonic() + timeout_seconds
        spinner = _ConsoleStatusSpinner() if show_spinner else None
        try:
            if spinner:
                spinner.render()
            while True:
                info = self.get_scan(
                    scan_id,
                    GetScanStatusRequest(
                        file_limit=50,
                        file_offset=0,
                        query=None,
                        severity=None,
                        risk_category=None,
                    ),
                )
                if info and info.scan_status_info.status in statuses:
                    return info.scan_status_info

                remaining_seconds = deadline - monotonic()
                if remaining_seconds <= 0:
                    break
                wait_seconds = min(
                    WAIT_TIME_SECS_SUCCESSIVE_SCAN_INFO_CHECK, remaining_seconds
                )
                if spinner:
                    spinner.wait(wait_seconds)
                else:
                    sleep(wait_seconds)
        finally:
            if spinner:
                spinner.close()

        raise ScanTimeoutError(
            (
                f"Scan {scan_id} did not reach a terminal state within "
                f"{timeout_seconds:g} seconds. The scan was not canceled or deleted. "
                "Retrieve its current status with "
                f'client.get_scan("{scan_id}", GetScanStatusRequest()).'
            ),
            scan_id=scan_id,
            timeout_seconds=timeout_seconds,
        )

    def cleanup_scan_data(self, scan_id: str) -> None:
        self.cancel_scan(scan_id)
        self.__get_scan_info_wait_until_status(
            scan_id, [ScanStatus.CANCELED], show_spinner=False
        )
        self.delete_scan(scan_id)

    def scan_file(
        self,
        file_path: Union[Path, str],
        *,
        max_concurrency: int = DEFAULT_MULTIPART_CONCURRENCY,
        show_progress: bool = True,
        progress_callback: Optional[UploadProgressCallback] = None,
        show_status_spinner: bool = True,
        scan_timeout_seconds: float = DEFAULT_SCAN_TIMEOUT_SECONDS,
    ) -> ScanStatusInfo:
        """
        Run a complete security scan on a model file using the AI Defense service.

        This is the main method for scanning files. It handles the entire scan workflow:
        registering a scan, uploading the file, triggering the scan, waiting for completion,
        and returning the results. If any errors occur, it automatically cleans up by
        canceling and deleting the scan.

        Args:
            file_path (Union[Path, str]): Path to the model file to be scanned.
                Can be a string path or pathlib.Path object.
            max_concurrency (int): Maximum number of file parts uploaded in parallel.
                Defaults to 10 and must be between 1 and 32.
            show_progress (bool): Show a console upload progress bar. Defaults to True.
            progress_callback: Optional callback receiving uploaded and total bytes.
            show_status_spinner: Show a spinner while waiting for scan results.
            scan_timeout_seconds: Maximum time to wait for scan analysis. Defaults to
                600 seconds. Upload time is not included.

        Returns:
            ScanStatusInfo: Complete scan status information including:
                - scan_id: The scan session identifier
                - status: Final scan status
                - analysis_results: List of file analysis results with threats
                - created_at/completed_at: Timestamps

        Raises:
            ScanTimeoutError: If scan polling times out. The scan is preserved so its
                status can be retrieved later with `get_scan()`.
            Exception: If another error occurs. The scan is automatically cleaned up.

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
        file_path = Path(file_path)
        self._validate_file_for_upload(file_path, enforce_max_size=False)

        res = self.register_scan()
        try:
            self.upload_file(
                res.scan_id,
                file_path,
                use_multipart_upload=True,
                max_concurrency=max_concurrency,
                show_progress=show_progress,
                progress_callback=progress_callback,
            )
            self.trigger_scan(res.scan_id)
            scan_info = self.__get_scan_info_wait_until_status(
                res.scan_id,
                END_SCAN_STATUS,
                timeout_seconds=scan_timeout_seconds,
                show_spinner=show_status_spinner,
            )
        except ScanTimeoutError:
            raise
        except Exception:
            if res.scan_id:
                self.cleanup_scan_data(res.scan_id)
            raise

        return scan_info

    def scan_repo(
        self,
        repo_config: ModelRepoConfig,
        *,
        show_status_spinner: bool = True,
        scan_timeout_seconds: float = DEFAULT_SCAN_TIMEOUT_SECONDS,
    ) -> ScanStatusInfo:  # type: ignore
        """
        Run a complete security scan on a model repository using the AI Defense service.

        This method handles the entire repository scan workflow: registering a scan,
        validating the repository URL and credentials, triggering the scan, waiting
        for completion, and returning the results. If any errors occur, it automatically
        cleans up by canceling and deleting the scan.

        Args:
            repo_config (ModelRepoConfig): Configuration object containing the repository
                URL, type, authentication credentials, and other scan parameters.
            show_status_spinner: Show a spinner while waiting for scan results.
            scan_timeout_seconds: Maximum time to wait for scan analysis. Defaults to
                600 seconds.

        Returns:
            ScanStatusInfo: Complete scan status information including:
                - scan_id: The scan session identifier
                - status: Final scan status
                - analysis_results: Repository analysis results with file-by-file findings
                - repository: Metadata about the scanned repository

        Raises:
            ScanTimeoutError: If scan polling times out. The scan is preserved so its
                status can be retrieved later with `get_scan()`.
            Exception: If another error occurs. The scan is automatically cleaned up.
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
            validation_response = self.validate_scan_url(res.scan_id, repo_config)
            if validation_response.error_message:
                raise ValidationError(validation_response.error_message)

            self.trigger_scan(res.scan_id)
            scan_info = self.__get_scan_info_wait_until_status(
                res.scan_id,
                END_SCAN_STATUS,
                timeout_seconds=scan_timeout_seconds,
                show_spinner=show_status_spinner,
            )
        except ScanTimeoutError:
            raise
        except Exception:
            if res.scan_id:
                self.cleanup_scan_data(res.scan_id)
            raise

        return scan_info
