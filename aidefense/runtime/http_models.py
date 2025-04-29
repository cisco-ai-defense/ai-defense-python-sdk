from typing import List, Optional
from dataclasses import dataclass
from aidefense.runtime.models import Metadata, InspectionConfig


@dataclass
class HttpHdrKvObject:
    key: str  # HTTP header key
    value: str  # HTTP header value


@dataclass
class HttpHdrObject:
    hdrKvs: Optional[List[HttpHdrKvObject]] = None


@dataclass
class HttpReqObject:
    method: Optional[str] = None
    headers: Optional[HttpHdrObject] = None
    body: str = ""
    split: Optional[bool] = None
    last: Optional[bool] = None


@dataclass
class HttpResObject:
    statusCode: int = 200
    statusString: Optional[str] = None
    headers: Optional[HttpHdrObject] = None
    body: str = ""
    split: Optional[bool] = None
    last: Optional[bool] = None


@dataclass
class HttpMetaObject:
    url: str = ""
    protocol: Optional[str] = None


@dataclass
class HttpInspectRequest:
    """
    Request object for HTTP inspection API.

    Attributes:
        http_req (Optional[HttpReqObject]): HTTP request details.
        http_res (Optional[HttpResObject]): HTTP response details.
        http_meta (Optional[HttpMetaObject]): HTTP metadata (e.g., URL).
        metadata (Optional[Metadata]): Additional metadata (user, app, etc.).
        config (Optional[InspectionConfig]): Inspection configuration for the request.
    """

    http_req: Optional[HttpReqObject] = None
    http_res: Optional[HttpResObject] = None
    http_meta: Optional[HttpMetaObject] = None
    metadata: Optional[Metadata] = None
    config: Optional[InspectionConfig] = None
