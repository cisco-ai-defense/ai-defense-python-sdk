"""
Utility functions for encoding/decoding HTTP bodies and serializing objects for the AI Defense SDK.
"""
import base64
from typing import Union

import logging

def to_base64_bytes(data: Union[str, bytes], logger=None) -> str:
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

def from_base64_bytes(b64str: str, logger=None) -> bytes:
    """
    Decode a base64-encoded string back to bytes.
    """
    if logger:
        logger.debug(f"from_base64_bytes called | b64str: {b64str}")
    """
    Decode a base64-encoded string back to bytes.

    Args:
        b64str (str): Base64-encoded string to decode.

    Returns:
        bytes: Decoded bytes.

    Raises:
        ValueError: If input is not a valid base64 string or not a string.
    """
    return base64.b64decode(b64str)


def convert(obj, logger=None):
    """
    Recursively convert dataclasses, enums, and other objects to dicts/values for JSON serialization.
    """
    if logger:
        logger.debug(f"convert called | obj type: {type(obj)}, obj: {obj}")
    """
    Recursively convert dataclasses, enums, and other objects to dicts/values for JSON serialization.

    Handles nested dataclasses, enums, lists, and dicts. This is useful for preparing objects
    for serialization (e.g., when sending requests to the AI Defense API).

    Args:
        obj: The object to convert (can be a dataclass, enum, list, dict, or primitive).

    Returns:
        The converted object as a dict, value, or list suitable for JSON serialization.
    """
    from dataclasses import asdict, is_dataclass
    from enum import Enum

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
