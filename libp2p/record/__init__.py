"""
Record module for py-libp2p.

This module provides functionality for creating, validating, and selecting
records in the libp2p network, similar to the go-libp2p-record module.
"""

from .exceptions import ErrInvalidRecordType
from .record import MakePutRecord, Record
from .validator import NamespacedValidator, PublicKeyValidator, Validator
from .utils import SplitKey

__all__ = [
    "ErrInvalidRecordType",
    "MakePutRecord",
    "Record",
    "NamespacedValidator",
    "PublicKeyValidator",
    "Validator",
    "SplitKey",
]
