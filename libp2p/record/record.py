"""
Record creation and management functionality.
"""

import time
from typing import Any, Optional


class Record:
    """
    Represents a record in the libp2p network.
    
    A record contains a key-value pair along with metadata.
    """

    def __init__(
        self,
        key: str,
        value: bytes,
        author: Optional[str] = None,
        timestamp: Optional[float] = None
    ):
        """
        Initialize a new Record.
        
        Args:
            key: The record key
            value: The record value as bytes
            author: Optional author identifier
            timestamp: Optional timestamp, defaults to current time

        """
        self.key = key
        self.value = value
        self.author = author
        self.timestamp = timestamp or time.time()

    def __eq__(self, other: Any) -> bool:
        """Check equality with another Record."""
        if not isinstance(other, Record):
            return False
        return (
            self.key == other.key and
            self.value == other.value and
            self.author == other.author
        )

    def __repr__(self) -> str:
        """String representation of the Record."""
        return f"Record(key='{self.key}', value_len={len(self.value)}, author='{self.author}')"


def MakePutRecord(key: str, value: bytes, author: Optional[str] = None) -> Record:
    """
    Create a new Record for putting into the network.
    
    Args:
        key: The record key
        value: The record value as bytes
        author: Optional author identifier
        
    Returns:
        A new Record instance

    """
    return Record(key=key, value=value, author=author)
