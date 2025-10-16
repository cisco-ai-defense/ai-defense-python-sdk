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

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import Field
from pydantic import root_validator

from aidefense.management.models.common import Paging
from aidefense.models.base import AIDefenseModel


class URLType(Enum):
    """Type of model URL provider."""

    NONE_URLType = 0
    HUGGING_FACE = 1


class RegisterScanRequest(AIDefenseModel):
    """Request message for registering a scan (no fields)."""


class FileSubcategory(AIDefenseModel):
    """Supported file subcategory information.

    Args:
        name: Subcategory name (e.g., "Keras", "PyTorch", "Pickle").
        file_extensions: List of supported file extensions.
    """

    name: str
    file_extensions: List[str]


class FileCategory(AIDefenseModel):
    """Supported file category information.

    Args:
        name: Category name (e.g., "ML Models", "Data Formats").
        subcategories: List of subcategories.
    """

    name: str
    subcategories: List[FileSubcategory]


class SupportedFileTypes(AIDefenseModel):
    """Supported file types information organized by categories and subcategories.

    Args:
        categories: List of file categories.
    """

    categories: List[FileCategory]


class RegisterScanResponse(AIDefenseModel):
    """Response message for registering a scan.

    Args:
        scan_id: Unique identifier for the scan (UUID string).
        supported_file_types: Information about supported file types.
    """

    scan_id: str
    supported_file_types: SupportedFileTypes


class FileObject(AIDefenseModel):
    """Object representing a file to be scanned.

    Args:
        file_name: The file name to be scanned.
    """

    file_name: str


class HuggingFaceAuth(AIDefenseModel):
    """Authentication for HuggingFace.

    Args:
        access_token: API token for HuggingFace.
    """

    access_token: str


class Auth(AIDefenseModel):
    """Authentication container for different providers.

    Only one of the supported providers should be set at a time.

    Args:
        huggingface: HuggingFace auth settings.
    """

    huggingface: Optional[HuggingFaceAuth] = None

    @root_validator
    def _validate_oneof(cls, values):  # type: ignore[override]
        # Enforce oneof semantics: at most one provider
        provided = [v for v in [values.get("huggingface")] if v is not None]
        if len(provided) > 1:
            raise ValueError("Only one auth provider can be set")
        return values


class URLObject(AIDefenseModel):
    """Object representing a URL to be scanned.

    Args:
        url: The repository/model URL.
        version_id: Optional commit hash or version identifier.
        type: Type of the URL provider (e.g., HUGGING_FACE).
        auth: Optional authentication for accessing the URL.
    """

    url: str
    type: URLType
    version_id: Optional[str] = None
    auth: Optional[Auth] = None


class ScanObject(AIDefenseModel):
    """Object representing either a file or URL to be scanned.

    Exactly one of `file_object` or `url_object` must be provided.

    Args:
        file_object: File-based scan object.
        url_object: URL-based scan object.
    """

    file_object: Optional[FileObject] = None
    url_object: Optional[URLObject] = None

    @root_validator
    def _validate_oneof(cls, values):  # type: ignore[override]
        fo = values.get("file_object")
        uo = values.get("url_object")
        if (fo is None) == (uo is None):
            raise ValueError("Exactly one of 'file_object' or 'url_object' must be set")
        return values


class CreateScanObjectRequest(AIDefenseModel):
    """Request message to create a scan object and generate a presigned URL.

    Args:
        file_name: The file to be scanned.
        scan_object: The scan object to create.
        size: Optional size of the object (bytes).
    """

    file_name: str
    size: Optional[int] = None
    scan_object: Optional[ScanObject] = None


class CreateScanObjectResponse(AIDefenseModel):
    """Response message for creating a scan object.

    Args:
        upload_url: Pre-signed URL for file upload.
        object_id: Unique identifier for the scan object (UUID string).
    """

    object_id: str
    upload_url: Optional[str] = None


class ModelRepoConfig(AIDefenseModel):
    """Request message for validating repository/model URL access.

    Args:
        url: URL of the repository/model to validate.
        type: Type of the URL provider.
        auth: Optional authentication for accessing the repository.
    """
    url: str
    type: URLType
    auth: Optional[Auth] = None


class ValidateModelUrlResponse(AIDefenseModel):
    """Response message for validating repository access.

    Args:
        is_accessible: Whether the URL is accessible.
        error_message: Error message if validation failed.
    """

    is_accessible: bool
    error_message: Optional[str] = None


class AnalysisType(str, Enum):
    """Type of analysis performed on the scan."""
    NONE_ANALYSIS_TYPE = "NONE_ANALYSIS_TYPE"
    FILE_ANALYSIS = "FILE_ANALYSIS"
    REPOSITORY_ANALYSIS = "REPOSITORY_ANALYSIS"


class ScanStatus(str, Enum):
    """Current status of a scan."""
    NONE_SCAN_STATUS = "NONE_SCAN_STATUS"
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"
    SKIPPED = "SKIPPED"
    DOWNLOADING = "DOWNLOADING"


class RiskCategory(str, Enum):
    """Risk category classification for files."""
    NONE_RISK_CATEGORY = "NONE_RISK_CATEGORY"
    VULNERABLE = "VULNERABLE"
    NO_THREATS = "NO_THREATS"
    NOT_SCANNED = "NOT_SCANNED"


class ThreatType(str, Enum):
    """Type of threat detected in a file."""
    NONE_THREAT_TYPE = "NONE_THREAT_TYPE"
    STACKED_PICKLE = "STACKED_PICKLE"
    UNSAFE_IMPORT = "UNSAFE_IMPORT"
    SUSPICIOUS_STRING = "SUSPICIOUS_STRING"
    METHOD_TAMPERING = "METHOD_TAMPERING"
    REDUCE_EXPLOIT = "REDUCE_EXPLOIT"
    CODE_EXECUTION = "CODE_EXECUTION"
    EVAL_EXEC = "EVAL_EXEC"
    OS_COMMAND = "OS_COMMAND"
    MULTIPLE_PROTO = "MULTIPLE_PROTO"
    SUSPICIOUS_IMPORT = "SUSPICIOUS_IMPORT"
    SUSPICIOUS_TENSORFLOW_OP = "SUSPICIOUS_TENSORFLOW_OP"
    DANGEROUS_TENSORFLOW_OP = "DANGEROUS_TENSORFLOW_OP"
    WARNING = "WARNING"
    SUSPICIOUS_KERAS_CONFIG = "SUSPICIOUS_KERAS_CONFIG"
    SUSPICIOUS_KERAS_LAMBDA_LAYER = "SUSPICIOUS_KERAS_LAMBDA_LAYER"
    DANGEROUS_KERAS_LAMBDA_LAYER = "DANGEROUS_KERAS_LAMBDA_LAYER"
    SUSPICIOUS_KERAS_CUSTOM_OBJECTS = "SUSPICIOUS_KERAS_CUSTOM_OBJECTS"
    SUSPICIOUS_CONFIG = "SUSPICIOUS_CONFIG"
    SUSPICIOUS_DATASET_CODE = "SUSPICIOUS_DATASET_CODE"
    MALICIOUS_JINJA2_TEMPLATE = "MALICIOUS_JINJA2_TEMPLATE"


class Severity(str, Enum):
    """Severity level of a detected threat."""
    NONE_SEVERITY = "NONE_SEVERITY"
    SAFE = "SAFE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


def restore_enum_wrapper(cls, values):
    for name, field in cls.__fields__.items():
        value = values.get(name)
        if isinstance(value, str) and issubclass(field.type_, Enum):
            try:
                values[name] = field.type_(value)
            except ValueError:
                pass  # leave as-is if invalid
    return values


class ThreatInfo(AIDefenseModel):
    """Information about a detected threat."""
    id: str = Field(..., description="Unique identifier for the threat")
    threat_id: str = Field(..., description="Threat identifier code")
    threat_type: ThreatType = Field(..., description="Type of threat detected")
    severity: Severity = Field(..., description="Severity level")
    details: str = Field(..., description="Detailed threat information")
    description: str = Field(..., description="Human-readable description")

    @root_validator
    def __restore_enums(cls, values):
        return restore_enum_wrapper(cls, values)


class SubTechnique(AIDefenseModel):
    """Sub-technique level grouping with threat evidence."""
    sub_technique_id: str = Field(..., description="Sub-technique identifier (e.g., AITech-9.3.1)")
    sub_technique_name: str = Field(..., description="Human-readable name of the sub-technique")
    description: str = Field(..., description="Description of the sub-technique")
    indicators: List[str] = Field(default_factory=list, description="List of indicators")
    max_severity: Severity = Field(..., description="Highest severity in this sub-technique")
    items: List[ThreatInfo] = Field(default_factory=list, description="List of threat detections")

    @root_validator
    def __restore_enums(cls, values):
        return restore_enum_wrapper(cls, values)


class Technique(AIDefenseModel):
    """Technique-level grouping of threats."""
    technique_id: str = Field(..., description="Technique identifier (e.g., AITech-9.3)")
    technique_name: str = Field(..., description="Human-readable name of the technique")
    items: List[SubTechnique] = Field(default_factory=list, description="List of sub-techniques")


class ThreatInfoList(AIDefenseModel):
    """Hierarchical view of threats grouped by taxonomy.

    Args:
        items: List of technique-level threat groupings.
        paging: Pagination information.
    """
    items: List[Technique] = Field(default_factory=list, description="List of technique groupings")
    paging: Paging = Field(..., description="Pagination information")


class FileInfo(AIDefenseModel):
    """Metadata for an analyzed file and detected issues.

    Args:
        name: File name.
        size: File size in bytes.
        status: Status of the file analysis.
        threats: Threat information associated with the file.
        reason: Optional reason for scan status (e.g., why it was skipped).
    """
    name: str = Field(..., description="File name")
    size: int = Field(..., description="File size in bytes")
    status: ScanStatus = Field(..., description="Analysis status")
    threats: ThreatInfoList = Field(..., description="Detected threats")
    reason: Optional[str] = Field(None, description="Reason for status")

    @root_validator
    def __restore_enums(cls, values):
        return restore_enum_wrapper(cls, values)


class AnalysisResult(AIDefenseModel):
    """List of analyzed files with pagination.

    Args:
        items: List of file information objects.
        paging: Pagination information.
    """
    items: List[FileInfo] = Field(default_factory=list, description="Analyzed files")
    paging: Paging = Field(..., description="Pagination information")


class RepositoryInfo(AIDefenseModel):
    """Details about a scanned repository.

    Args:
        url: URL of the repository.
        version: Version or commit hash of the repository.
        files_scanned: Number of files scanned in the repository.
    """
    url: str = Field(..., description="Repository URL")
    version: str = Field(..., description="Version or commit hash")
    files_scanned: int = Field(..., description="Number of files scanned")


class ScanStatusInfo(AIDefenseModel):
    """Comprehensive status information for a scan.

    Args:
        scan_id: Unique identifier for the scan (UUID).
        status: Current status of the scan.
        created_at: Timestamp when the scan was created.
        completed_at: Timestamp when the scan was completed.
        type: Type of analysis performed.
        repository: Repository information (if applicable).
        analysis_results: Results of the analysis.
    """
    scan_id: str = Field(..., description="Unique scan identifier")
    status: ScanStatus = Field(..., description="Current scan status")
    created_at: datetime = Field(..., description="Creation timestamp")
    completed_at: datetime = Field(..., description="Completion timestamp")
    type: AnalysisType = Field(..., description="Analysis type")
    repository: Optional[RepositoryInfo] = Field(None, description="Repository information")
    analysis_results: AnalysisResult = Field(..., description="Analysis results")

    @root_validator
    def __restore_enums(cls, values):
        return restore_enum_wrapper(cls, values)


class GetScanStatusRequest(AIDefenseModel):
    """Request parameters for retrieving scan status.

    Args:
        file_limit: Limit on number of files to return.
        file_offset: Offset for pagination of files.
        query: Search string for filtering vulnerabilities.
        severity: List of severity levels to filter by.
        risk_category: Risk category to filter by.
    """
    file_limit: int = Field(default=10, description="File result limit")
    file_offset: int = Field(default=0, description="File result offset")
    query: Optional[str] = Field(None, description="Search query")
    severity: Optional[List[Severity]] = Field(None, description="Severity filters")
    risk_category: Optional[RiskCategory] = Field(None, description="Risk category filter")


class GetScanStatusResponse(AIDefenseModel):
    """Response containing scan status information.

    Args:
        scan_status_info: Detailed scan status information.
    """
    scan_status_info: ScanStatusInfo = Field(..., description="Scan status details")


class ScanSummary(AIDefenseModel):
    """High-level summary information for a scan.

    Args:
        scan_id: Unique identifier for the scan (UUID).
        name: Name of the file or repository scanned.
        type: Type of analysis performed.
        files_scanned: Number of files scanned.
        created_at: Timestamp when the scan was created.
        issues_by_severity: Map of severity levels to issue counts.
        status: Current status of the scan.
    """
    scan_id: str = Field(..., description="Unique scan identifier")
    name: str = Field(..., description="File or repository name")
    type: AnalysisType = Field(..., description="Analysis type")
    files_scanned: int = Field(..., description="Number of files scanned")
    created_at: datetime = Field(..., description="Creation timestamp")
    issues_by_severity: Dict[str, int] = Field(default_factory=dict, description="Issues by severity")
    status: ScanStatus = Field(..., description="Current scan status")

    @root_validator
    def __restore_enums(cls, values):
        return restore_enum_wrapper(cls, values)


class Scans(AIDefenseModel):
    """List of scan summaries with pagination.

    Args:
        items: List of scan summary objects.
        paging: Pagination information.
    """
    items: List[ScanSummary] = Field(default_factory=list, description="Scan summaries")
    paging: Paging = Field(..., description="Pagination information")


class ListScansRequest(AIDefenseModel):
    """Request parameters for listing scans.

    Args:
        limit: Maximum number of scans to return.
        offset: Offset for pagination.
        name: Filter by artifact name (file or repository).
        scan_date: Filter by scan creation date.
        type: Filter by analysis type.
        severity: Filter by threat severity levels.
        status: Filter by scan status values.
    """
    limit: int = Field(default=100, ge=0, description="Result limit")
    offset: int = Field(default=0, ge=0, description="Result offset")
    name: Optional[str] = Field(None, description="Artifact name filter")
    scan_date: Optional[datetime] = Field(None, description="Scan date filter")
    type: Optional[AnalysisType] = Field(None, description="Analysis type filter")
    severity: Optional[List[Severity]] = Field(None, description="Severity filters")
    status: Optional[List[ScanStatus]] = Field(None, description="Status filters")


class ListScansResponse(AIDefenseModel):
    """Response containing list of scans.

    Args:
        scans: List of scans with pagination information.
    """
    scans: Scans = Field(..., description="Scans list with pagination")
