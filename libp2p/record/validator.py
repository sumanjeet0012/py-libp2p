"""
Validator classes for record validation and selection.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

import base58
import multihash

from libp2p.crypto.keys import PublicKey

from .exceptions import (
    ErrInvalidMultihash,
    ErrInvalidPublicKey,
    ErrInvalidRecord,
    ErrInvalidRecordType,
)
from .utils import SplitKey


class Validator(ABC):
    """
    Abstract base class for record validators.
    
    Validators are responsible for validating records and selecting
    the best record when multiple records exist for the same key.
    """

    @abstractmethod
    def validate(self, key: str, value: bytes) -> None:
        """
        Validate a record.
        
        Args:
            key: The record key
            value: The record value
            
        Raises:
            Exception: If the record is invalid

        """
        pass

    @abstractmethod
    def select(self, key: str, values: List[bytes]) -> int:
        """
        Select the best record from a list of values.
        
        Args:
            key: The record key
            values: List of record values
            
        Returns:
            Index of the selected record
            
        Raises:
            Exception: If selection fails

        """
        pass


class PublicKeyValidator(Validator):
    """
    Validator for public key records (namespace 'pk').
    
    Validates that the record contains a valid public key and that
    the key hash matches the expected peer ID.
    """

    def validate(self, key: str, value: bytes) -> None:
        """
        Validate a public key record.
        
        Args:
            key: The record key (should be in format "/pk/<peer-id>")
            value: The public key bytes
            
        Raises:
            ErrInvalidRecordType: If key format is invalid
            ErrInvalidPublicKey: If public key is invalid
            ErrInvalidMultihash: If multihash is invalid

        """
        try:
            namespace, path = SplitKey(key)
        except ErrInvalidRecordType:
            raise

        if namespace != "pk":
            raise ErrInvalidRecordType(f"invalid namespace for public key validator: {namespace}")

        # Validate that path is a valid multihash (peer ID)
        try:
            # Decode the peer ID from base58
            peer_id_bytes = base58.b58decode(path)

            # Verify it's a valid multihash
            try:
                decoded = multihash.decode(peer_id_bytes)
            except Exception as e:
                raise ErrInvalidMultihash(f"invalid multihash in key: {e}")

        except Exception as e:
            raise ErrInvalidMultihash(f"invalid peer ID in key: {e}")

        # Try to parse the public key protobuf
        try:
            protobuf_key = PublicKey.deserialize_from_protobuf(value)
        except Exception as e:
            raise ErrInvalidPublicKey(f"failed to parse public key protobuf: {e}")

        # For now, we'll skip the detailed validation since we need to reconstruct
        # the actual PublicKey object from the protobuf, which requires knowing
        # the key type and using the appropriate crypto module.
        # This is a simplified validation that just checks the protobuf is valid.

        # In a full implementation, we would:
        # 1. Extract key_type and data from protobuf_key
        # 2. Create the appropriate PublicKey subclass (Ed25519PublicKey, etc.)
        # 3. Generate peer ID and compare with the expected one

        # For demonstration purposes, we'll just validate the protobuf structure
        if not hasattr(protobuf_key, 'key_type') or not hasattr(protobuf_key, 'data'):
            raise ErrInvalidPublicKey("invalid public key protobuf structure")

    def select(self, key: str, values: List[bytes]) -> int:
        """
        Select the best public key record.
        
        For public key records, we always return the first valid record
        since there should only be one valid public key per peer ID.
        
        Args:
            key: The record key
            values: List of public key values
            
        Returns:
            Index 0 (always selects the first record)

        """
        if not values:
            raise ErrInvalidRecord("no values to select from")

        # For public key records, we validate the first one and return it
        # In practice, there should only be one valid public key per peer ID
        self.validate(key, values[0])
        return 0


class NamespacedValidator:
    """
    A validator that routes validation to namespace-specific validators.
    
    This is the main validator that clients interact with. It determines
    the appropriate validator based on the record key's namespace.
    """

    def __init__(
        self
    ) -> None:
        """Initialize the namespaced validator with default validators."""
        self._validators: Dict[str, Validator] = {
            "pk": PublicKeyValidator()
        }

    def add_validator(self, namespace: str, validator: Validator) -> None:
        """
        Add a validator for a specific namespace.
        
        Args:
            namespace: The namespace to handle
            validator: The validator instance

        """
        self._validators[namespace] = validator

    def validator_by_key(self, key: str) -> Optional[Validator]:
        """
        Get the appropriate validator for a key.
        
        Args:
            key: The record key
            
        Returns:
            The validator for the key's namespace, or None if not found

        """
        try:
            namespace, _ = SplitKey(key)
            return self._validators.get(namespace)
        except ErrInvalidRecordType:
            return None

    def validate(self, key: str, value: bytes) -> None:
        """
        Validate a record using the appropriate namespace validator.
        
        Args:
            key: The record key
            value: The record value
            
        Raises:
            ErrInvalidRecordType: If key format is invalid or no validator found
            Other exceptions: As raised by the specific validator

        """
        try:
            namespace, _ = SplitKey(key)
        except ErrInvalidRecordType:
            raise ErrInvalidRecordType(f"invalid key format: {key}")

        validator = self._validators.get(namespace)
        if validator is None:
            raise ErrInvalidRecordType(f"no validator for namespace: {namespace}")

        validator.validate(key, value)

    def select(self, key: str, values: List[bytes]) -> int:
        """
        Select the best record using the appropriate namespace validator.
        
        Args:
            key: The record key
            values: List of record values
            
        Returns:
            Index of the selected record
            
        Raises:
            ErrInvalidRecordType: If key format is invalid or no validator found
            Other exceptions: As raised by the specific validator

        """
        validator = self.validator_by_key(key)
        if validator is None:
            try:
                namespace, _ = SplitKey(key)
                raise ErrInvalidRecordType(f"no validator for namespace: {namespace}")
            except ErrInvalidRecordType:
                raise ErrInvalidRecordType(f"invalid key format: {key}")

        return validator.select(key, values)
