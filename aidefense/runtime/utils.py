"""
Utility functions for encoding/decoding HTTP bodies and serializing objects for the AI Defense SDK.
"""

import base64
from typing import Union

import logging


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
