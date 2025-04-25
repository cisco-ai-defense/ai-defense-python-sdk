"""
Utility functions for encoding HTTP bodies and serializing objects for the AI Defense SDK.
"""

import base64
from typing import Union, Any
from dataclasses import asdict, is_dataclass
from enum import Enum


def to_base64_bytes(data: Union[str, bytes]) -> str:
    """
    Encode a string or bytes object to a base64-encoded string.

    Args:
        data (str or bytes): The input data to encode.

    Returns:
        str: Base64-encoded string representation of the input.

    Raises:
        ValueError: If data is not of type str or bytes.
    """
    if isinstance(data, bytes):
        return base64.b64encode(data).decode()
    elif isinstance(data, str):
        return base64.b64encode(data.encode()).decode()
    else:
        raise ValueError("Input must be str or bytes.")


def convert(obj: Any) -> Any:
    """
    Recursively convert dataclasses, enums, and other objects to dicts/values for JSON serialization.

    Handles nested dataclasses, enums, lists, and dicts. This is useful for preparing objects
    for serialization (e.g., when sending requests to the AI Defense API).

    Args:
        obj: The object to convert (can be a dataclass, enum, list, dict, or primitive).

    Returns:
        The converted object as a dict, value, or list suitable for JSON serialization.
    """

    if is_dataclass(obj):
        return {k: convert(v) for k, v in asdict(obj).items()}
    elif isinstance(obj, Enum):
        return obj.value
    elif isinstance(obj, dict):
        return {k: convert(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert(v) for v in obj]
    else:
        return obj
