"""
Utility functions for the record module.
"""

from typing import Tuple

from .exceptions import ErrInvalidRecordType


def SplitKey(key: str) -> Tuple[str, str]:
    """
    Split a record key into namespace and path components.
    
    Expected key format: "/namespace/path" or "namespace/path"
    
    Args:
        key: The record key to split
        
    Returns:
        A tuple of (namespace, path)
        
    Raises:
        ErrInvalidRecordType: If the key format is invalid

    """
    if not key:
        raise ErrInvalidRecordType("empty key")

    # Remove leading slash if present
    if key.startswith("/"):
        key = key[1:]

    # Split on first slash
    parts = key.split("/", 1)

    if len(parts) < 2:
        raise ErrInvalidRecordType(f"invalid key format: {key}")

    namespace, path = parts

    if not namespace:
        raise ErrInvalidRecordType("empty namespace")

    if not path:
        raise ErrInvalidRecordType("empty path")

    return namespace, path
