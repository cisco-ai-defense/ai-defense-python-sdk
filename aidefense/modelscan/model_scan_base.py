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

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
import sys
from threading import Lock, local
from time import sleep
from typing import Callable, Dict, Optional, Tuple
from urllib.parse import urlparse

import requests

from aidefense.config import Config
from aidefense.exceptions import SDKError
from aidefense.management.auth import ManagementAuth
from aidefense.management.base_client import BaseClient
from aidefense.request_handler import HttpMethod
from aidefense.runtime.auth import RuntimeAuth
from aidefense.modelscan.models import (
    AbortMultipartUploadRequest,
    CompleteMultipartUploadRequest,
    CompletedMultipartUploadPart,
    CreateScanObjectRequest,
    CreateScanObjectResponse,
    GetMultipartUploadPartUrlsRequest,
    GetMultipartUploadPartUrlsResponse,
    GetScanStatusRequest,
    GetScanStatusResponse,
    ListScansRequest,
    ListScansResponse,
    ModelRepoConfig,
    RegisterScanResponse,
    ValidateModelUrlResponse,
)
from aidefense.modelscan.routes import (
    SCAN_OBJECTS,
    SCANS,
    multipart_abort,
    multipart_complete,
    multipart_part_urls,
    object_by_id,
    scan_by_id,
)

# Maximum file size for the legacy single-PUT upload path (5 GiB).
# Multipart upload limits are enforced by the service when the object is created.
KB = 1024
MB = 1024 * KB
GB = 1024 * MB
MAX_FILE_SIZE_BYTES = 5 * GB
MAX_MULTIPART_PARTS = 10_000
PART_URL_BATCH_SIZE = 32
DEFAULT_MULTIPART_CONCURRENCY = 10
MAX_MULTIPART_CONCURRENCY = 32
MAX_PART_UPLOAD_ATTEMPTS = 3
PART_UPLOAD_RETRY_BACKOFF_SECONDS = 0.5
PRESIGNED_URL_EXPIRATION_CODES = ("ExpiredToken", "RequestExpired")
UploadProgressCallback = Callable[[int, int], None]


class _ConsoleUploadProgress:
    """Render a dependency-free progress bar for interactive SDK callers."""

    def __init__(self, width: int = 30):
        self._width = width
        self._lock = Lock()

    def __call__(self, uploaded_bytes: int, total_bytes: int) -> None:
        ratio = min(1.0, uploaded_bytes / total_bytes) if total_bytes else 1.0
        filled = int(self._width * ratio)
        bar = "#" * filled + "-" * (self._width - filled)
        uploaded_mb = uploaded_bytes / MB
        total_mb = total_bytes / MB
        with self._lock:
            print(
                f"\rUploading [{bar}] {ratio:6.1%} "
                f"({uploaded_mb:.1f}/{total_mb:.1f} MiB)",
                end="\n" if uploaded_bytes >= total_bytes else "",
                file=sys.stderr,
                flush=True,
            )


class _BoundedFileReader:
    """Read only one byte range from a file without buffering the whole part."""

    def __init__(self, file_path: Path, offset: int, length: int):
        self._file = file_path.open("rb")
        self._offset = offset
        self._length = length
        self._position = 0
        self._file.seek(offset)

    def __len__(self) -> int:
        return self._length

    def tell(self) -> int:
        return self._position

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:
            position = offset
        elif whence == 1:
            position = self._position + offset
        elif whence == 2:
            position = self._length + offset
        else:
            raise ValueError("invalid seek mode")
        if position < 0 or position > self._length:
            raise ValueError("seek is outside the multipart file range")
        self._file.seek(self._offset + position)
        self._position = position
        return position

    def read(self, size: int = -1) -> bytes:
        remaining = self._length - self._position
        if remaining <= 0:
            return b""
        read_size = remaining if size is None or size < 0 else min(size, remaining)
        data = self._file.read(read_size)
        self._position += len(data)
        return data

    def close(self) -> None:
        self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()


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
        self, api_key: str, config: Optional[Config] = None, request_handler=None
    ):
        """
        Initialize a ModelScan client instance.

        Args:
            api_key (str): Your Cisco AI Defense API key for authentication.
            config (Config, optional): SDK-level configuration for endpoints, logging, retries, etc.
                If not provided, a default Config instance is created.
        """
        super().__init__(ManagementAuth(api_key), config, request_handler)

    def create_scan_object(
        self, scan_id: str, req: CreateScanObjectRequest
    ) -> Tuple[str, str]:
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
        result = self._create_scan_object_response(scan_id, req)
        if not result.upload_url:
            raise SDKError("Scan object response did not include an upload URL")

        return result.object_id, result.upload_url

    def _create_scan_object_response(
        self, scan_id: str, req: CreateScanObjectRequest
    ) -> CreateScanObjectResponse:
        res = self.make_request(
            method=HttpMethod.POST,
            path=f"{scan_by_id(scan_id)}/{SCAN_OBJECTS}",
            data=req.to_body_dict(patch=True),
        )
        result = CreateScanObjectResponse.model_validate(res)
        self.config.logger.debug("Created model scan object %s", result.object_id)
        return result

    def create_multipart_scan_object(
        self, scan_id: str, req: CreateScanObjectRequest
    ) -> CreateScanObjectResponse:
        """Create a scan object backed by an S3 multipart upload."""
        multipart_request = req.model_copy(update={"use_multipart_upload": True})
        result = self._create_scan_object_response(scan_id, multipart_request)
        if result.multipart_upload is None:
            raise SDKError(
                "Scan object response did not include multipart upload details"
            )
        return result

    def get_multipart_upload_part_urls(
        self, scan_id: str, object_id: str, req: GetMultipartUploadPartUrlsRequest
    ) -> GetMultipartUploadPartUrlsResponse:
        """Request presigned S3 URLs for one batch of multipart part numbers."""
        res = self.make_request(
            method=HttpMethod.POST,
            path=multipart_part_urls(scan_id, object_id),
            data=req.to_body_dict(),
        )
        return GetMultipartUploadPartUrlsResponse.model_validate(res)

    def complete_multipart_upload(
        self, scan_id: str, object_id: str, req: CompleteMultipartUploadRequest
    ) -> None:
        """Complete a multipart upload after every part has an ETag."""
        self.make_request(
            method=HttpMethod.POST,
            path=multipart_complete(scan_id, object_id),
            data=req.to_body_dict(),
        )

    def abort_multipart_upload(
        self, scan_id: str, object_id: str, req: AbortMultipartUploadRequest
    ) -> None:
        """Abort an incomplete multipart upload."""
        self.make_request(
            method=HttpMethod.POST,
            path=multipart_abort(scan_id, object_id),
            data=req.to_body_dict(),
        )

    def upload_scan_result(
        self, scan_id: str, scan_object_id: str, scan_result: dict
    ) -> None:
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

    def _validate_file_for_upload(
        self, file_path: Path, *, enforce_max_size: bool = True
    ) -> None:
        if file_path.exists() is False:
            raise FileNotFoundError(f"File not found: {file_path}")

        file_size = file_path.stat().st_size
        if file_size <= 0:
            raise ValueError("File must not be empty")
        if enforce_max_size and file_size > MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"File size exceeds limit (allowed {MAX_FILE_SIZE_BYTES//GB} GB)"
            )

    @staticmethod
    def _validate_presigned_upload_url(upload_url: str) -> None:
        parsed_url = urlparse(upload_url)
        hostname = (parsed_url.hostname or "").lower()
        if parsed_url.scheme != "https" or not hostname.endswith(
            (".amazonaws.com", ".amazonaws.com.cn")
        ):
            raise SDKError("The service returned an invalid multipart upload URL")

    @staticmethod
    def _is_recoverable_part_upload_error(error: Exception) -> bool:
        if isinstance(error, (requests.ConnectionError, requests.Timeout)):
            return True
        if not isinstance(error, requests.HTTPError) or error.response is None:
            return False
        status_code = error.response.status_code
        if status_code == 429 or status_code >= 500:
            return True
        response_text = error.response.text or ""
        return status_code in (400, 403) and any(
            code in response_text for code in PRESIGNED_URL_EXPIRATION_CODES
        )

    def _upload_multipart_part(
        self,
        file_path: Path,
        part_number: int,
        part_size_bytes: int,
        file_size: int,
        upload_url: str,
        session: Optional[requests.Session] = None,
    ) -> str:
        self._validate_presigned_upload_url(upload_url)
        offset = (part_number - 1) * part_size_bytes
        length = min(part_size_bytes, file_size - offset)
        with _BoundedFileReader(file_path, offset, length) as file_part:
            requester = session or requests
            response = requester.put(
                upload_url,
                data=file_part,
                headers={
                    "Content-Length": str(length),
                    "Content-Type": "application/octet-stream",
                },
                timeout=self.config.timeout,
                allow_redirects=False,
            )
        if response.status_code < 200 or response.status_code >= 300:
            raise requests.HTTPError(
                f"Multipart part upload failed with status {response.status_code}",
                response=response,
            )
        etag = response.headers.get("ETag")
        if not etag or len(etag) > 2048:
            raise SDKError("Multipart part upload did not return a valid ETag")
        return etag

    def _upload_file_multipart(
        self,
        scan_id: str,
        file_path: Path,
        max_concurrency: int,
        progress_callback: Optional[UploadProgressCallback],
    ) -> bool:
        if not isinstance(max_concurrency, int) or isinstance(max_concurrency, bool):
            raise ValueError("max_concurrency must be an integer")
        if max_concurrency < 1 or max_concurrency > MAX_MULTIPART_CONCURRENCY:
            raise ValueError(
                f"max_concurrency must be between 1 and {MAX_MULTIPART_CONCURRENCY}"
            )

        file_size = file_path.stat().st_size
        req = CreateScanObjectRequest(
            file_name=file_path.name,
            size=file_size,
            use_multipart_upload=True,
        )
        create_response = self.create_multipart_scan_object(scan_id, req)
        multipart_upload = create_response.multipart_upload
        if multipart_upload is None:  # Defensive guard for non-Pydantic callers/mocks.
            raise SDKError(
                "Scan object response did not include multipart upload details"
            )

        object_id = create_response.object_id
        upload_id = multipart_upload.upload_id
        part_size_bytes = multipart_upload.part_size_bytes
        part_count = (file_size + part_size_bytes - 1) // part_size_bytes
        if part_count < 1 or part_count > MAX_MULTIPART_PARTS:
            self.abort_multipart_upload(
                scan_id,
                object_id,
                AbortMultipartUploadRequest(upload_id=upload_id),
            )
            raise SDKError("Invalid multipart upload part count")

        refresh_lock = Lock()
        sessions_lock = Lock()
        worker_state = local()
        worker_sessions = []

        def get_worker_session() -> requests.Session:
            worker_session = getattr(worker_state, "session", None)
            if worker_session is None:
                worker_session = requests.Session()
                worker_state.session = worker_session
                with sessions_lock:
                    worker_sessions.append(worker_session)
            return worker_session

        def get_part_url(part_number: int) -> str:
            with refresh_lock:
                response = self.get_multipart_upload_part_urls(
                    scan_id,
                    object_id,
                    GetMultipartUploadPartUrlsRequest(
                        upload_id=upload_id,
                        part_numbers=[part_number],
                    ),
                )
            matching_parts = [
                part for part in response.parts if part.part_number == part_number
            ]
            if len(matching_parts) != 1:
                raise SDKError(
                    "The service did not return the requested multipart upload URL"
                )
            return matching_parts[0].upload_url

        def upload_part(
            part_number: int, upload_url: str
        ) -> CompletedMultipartUploadPart:
            current_url = upload_url
            for attempt in range(MAX_PART_UPLOAD_ATTEMPTS):
                try:
                    etag = self._upload_multipart_part(
                        file_path,
                        part_number,
                        part_size_bytes,
                        file_size,
                        current_url,
                        session=get_worker_session(),
                    )
                    return CompletedMultipartUploadPart(
                        part_number=part_number, etag=etag
                    )
                except Exception as error:
                    is_last_attempt = attempt + 1 == MAX_PART_UPLOAD_ATTEMPTS
                    if is_last_attempt or not self._is_recoverable_part_upload_error(
                        error
                    ):
                        raise SDKError(
                            f"Multipart upload part {part_number} failed"
                        ) from None
                    sleep(PART_UPLOAD_RETRY_BACKOFF_SECONDS * (2**attempt))
                    current_url = get_part_url(part_number)
            raise SDKError(f"Multipart upload part {part_number} failed")

        completed_parts = []
        uploaded_bytes = 0
        if progress_callback:
            progress_callback(uploaded_bytes, file_size)
        try:
            part_numbers = list(range(1, part_count + 1))
            try:
                with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
                    next_part_index = 0
                    futures = {}

                    def submit_next_batch() -> None:
                        nonlocal next_part_index
                        batch_part_numbers = part_numbers[
                            next_part_index : next_part_index + PART_URL_BATCH_SIZE
                        ]
                        if not batch_part_numbers:
                            return
                        urls_response = self.get_multipart_upload_part_urls(
                            scan_id,
                            object_id,
                            GetMultipartUploadPartUrlsRequest(
                                upload_id=upload_id,
                                part_numbers=batch_part_numbers,
                            ),
                        )
                        upload_urls = {
                            part.part_number: part.upload_url
                            for part in urls_response.parts
                        }
                        if len(urls_response.parts) != len(batch_part_numbers) or set(
                            upload_urls
                        ) != set(batch_part_numbers):
                            raise SDKError(
                                "The service did not return every requested multipart upload URL"
                            )

                        for number in batch_part_numbers:
                            future = executor.submit(
                                upload_part, number, upload_urls[number]
                            )
                            futures[future] = number
                        next_part_index += len(batch_part_numbers)

                    # Keep at most two URL batches in flight. This bounds URL age and
                    # memory while allowing workers to cross batch boundaries without
                    # waiting for the slowest part in the preceding batch.
                    while (
                        next_part_index < len(part_numbers)
                        and len(futures) < 2 * PART_URL_BATCH_SIZE
                    ):
                        submit_next_batch()

                    while futures:
                        done, _ = wait(futures, return_when=FIRST_COMPLETED)
                        for future in done:
                            part_number = futures.pop(future)
                            completed_parts.append(future.result())
                            uploaded_bytes += min(
                                part_size_bytes,
                                file_size - (part_number - 1) * part_size_bytes,
                            )
                            if progress_callback:
                                progress_callback(uploaded_bytes, file_size)

                        if (
                            next_part_index < len(part_numbers)
                            and len(futures) <= PART_URL_BATCH_SIZE
                        ):
                            submit_next_batch()
            finally:
                for worker_session in worker_sessions:
                    worker_session.close()

            completed_parts.sort(key=lambda part: part.part_number)
            self.complete_multipart_upload(
                scan_id,
                object_id,
                CompleteMultipartUploadRequest(
                    upload_id=upload_id,
                    parts=completed_parts,
                ),
            )
            return True
        except Exception:
            try:
                self.abort_multipart_upload(
                    scan_id,
                    object_id,
                    AbortMultipartUploadRequest(upload_id=upload_id),
                )
            except Exception:
                self.config.logger.warning(
                    "Failed to abort multipart upload for scan object %s", object_id
                )
            raise

    def upload_file(
        self,
        scan_id: str,
        file_path: Path,
        *,
        use_multipart_upload: bool = True,
        max_concurrency: int = DEFAULT_MULTIPART_CONCURRENCY,
        show_progress: bool = True,
        progress_callback: Optional[UploadProgressCallback] = None,
    ) -> bool:
        """
        Upload a file to be scanned within an existing scan session.

        This method handles the complete file upload process: creating a scan object,
        getting the upload URL, and uploading the file content.

        Args:
            scan_id (str): The unique identifier of the scan session.
            file_path (Path): Path to the file to be uploaded and scanned.
            show_progress (bool): Show a console upload progress bar. Defaults to True.
            progress_callback: Optional callback receiving uploaded and total bytes.

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
        self._validate_file_for_upload(
            file_path, enforce_max_size=not use_multipart_upload
        )

        console_progress = _ConsoleUploadProgress() if show_progress else None

        def report_progress(uploaded_bytes: int, total_bytes: int) -> None:
            if console_progress:
                console_progress(uploaded_bytes, total_bytes)
            if progress_callback:
                progress_callback(uploaded_bytes, total_bytes)

        if use_multipart_upload:
            return self._upload_file_multipart(
                scan_id,
                file_path,
                max_concurrency,
                report_progress if console_progress or progress_callback else None,
            )

        req = CreateScanObjectRequest(
            file_name=file_path.name,
            size=file_path.stat().st_size,
        )
        _, upload_url = self.create_scan_object(scan_id, req)

        report_progress(0, file_path.stat().st_size)
        with open(file_path, "rb") as f:
            result = requests.request(method=HttpMethod.PUT, url=upload_url, data=f)
        result.raise_for_status()
        report_progress(file_path.stat().st_size, file_path.stat().st_size)
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

    def get_scan(
        self, scan_id: str, req: GetScanStatusRequest
    ) -> GetScanStatusResponse:
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

    def validate_scan_url(
        self, scan_id: str, req: ModelRepoConfig
    ) -> ValidateModelUrlResponse:
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
