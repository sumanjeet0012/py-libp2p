#!/usr/bin/env python3
"""
Demo script showing how to use the libp2p record module.

This script demonstrates:
1. Creating records with MakePutRecord
2. Validating records with NamespacedValidator
3. Selecting the best record from multiple options
4. Working with public key records
5. Adding custom validators for new namespaces
"""

import os
import sys

# Add the parent directory to the path so we can import libp2p
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from libp2p.crypto.ed25519 import create_new_key_pair
from libp2p.peer.id import ID as PeerID
from libp2p.record import (
    ErrInvalidRecordType,
    MakePutRecord,
    NamespacedValidator,
    SplitKey,
    Validator,
)


class CustomValidator(Validator):
    """Example custom validator for demonstration."""

    def validate(self, key: str, value: bytes) -> None:
        """Validate that the value is not empty."""
        if not value:
            raise ValueError("value cannot be empty")

        # Custom validation logic here
        if len(value) < 5:
            raise ValueError("value must be at least 5 bytes")

    def select(self, key: str, values: list[bytes]) -> int:
        """Select the longest value."""
        if not values:
            raise ValueError("no values to select from")

        # Find the index of the longest value
        max_length = 0
        selected_index = 0

        for i, value in enumerate(values):
            if len(value) > max_length:
                max_length = len(value)
                selected_index = i

        return selected_index


def demo_basic_record_operations():
    """Demonstrate basic record creation and operations."""
    print("=== Basic Record Operations ===")

    # Create a simple record
    key = "/test/example"
    value = b"Hello, libp2p records!"

    record = MakePutRecord(key, value, author="demo-user")

    print(f"Created record: {record}")
    print(f"Key: {record.key}")
    print(f"Value: {record.value.decode()}")
    print(f"Author: {record.author}")
    print(f"Timestamp: {record.timestamp}")
    print()


def demo_key_splitting():
    """Demonstrate key splitting functionality."""
    print("=== Key Splitting Demo ===")

    test_keys = [
        "/pk/QmTest123",
        "/custom/namespace/path",
        "ipns/example.com",
        "/test/multi/level/path",
    ]

    for key in test_keys:
        try:
            namespace, path = SplitKey(key)
            print(f"Key: {key}")
            print(f"  Namespace: {namespace}")
            print(f"  Path: {path}")
        except ErrInvalidRecordType as e:
            print(f"Key: {key} - ERROR: {e}")
        print()


def demo_validation():
    """Demonstrate record validation."""
    print("=== Record Validation Demo ===")

    validator = NamespacedValidator()

    # Test with unknown namespace (should fail)
    try:
        validator.validate("/unknown/test", b"some value")
        print("Validation passed (unexpected)")
    except ErrInvalidRecordType as e:
        print(f"Validation failed as expected: {e}")

    # Add a custom validator
    validator.add_validator("custom", CustomValidator())

    # Test with custom namespace
    try:
        validator.validate("/custom/test", b"valid long value")
        print("Custom validation passed")
    except Exception as e:
        print(f"Custom validation failed: {e}")

    # Test with invalid value for custom validator
    try:
        validator.validate("/custom/test", b"bad")
        print("Custom validation passed (unexpected)")
    except Exception as e:
        print(f"Custom validation failed as expected: {e}")

    print()


def demo_selection():
    """Demonstrate record selection."""
    print("=== Record Selection Demo ===")

    validator = NamespacedValidator()
    validator.add_validator("custom", CustomValidator())

    # Test selection with custom validator (selects longest)
    key = "/custom/test"
    values = [b"short", b"this is a much longer value", b"medium length value"]

    try:
        selected_index = validator.select(key, values)
        selected_value = values[selected_index]
        print(f"Selected value at index {selected_index}: {selected_value.decode()}")
    except Exception as e:
        print(f"Selection failed: {e}")

    print()


def demo_public_key_records():
    """Demonstrate public key record handling."""
    print("=== Public Key Records Demo ===")

    try:
        # Generate a key pair
        keypair = create_new_key_pair()
        peer_id = PeerID.from_pubkey(keypair.public_key)

        print(f"Generated peer ID: {peer_id}")

        # Create a public key record
        pk_key = f"/pk/{peer_id}"
        pk_value = keypair.public_key.serialize()

        print(f"Public key record key: {pk_key}")
        print(f"Public key value length: {len(pk_value)} bytes")

        # Validate the public key record
        validator = NamespacedValidator()

        try:
            validator.validate(pk_key, pk_value)
            print("Public key validation passed!")
        except Exception as e:
            print(f"Public key validation failed: {e}")

        # Test selection (should always return index 0 for pk records)
        try:
            selected_index = validator.select(pk_key, [pk_value])
            print(f"Selected public key at index: {selected_index}")
        except Exception as e:
            print(f"Public key selection failed: {e}")

    except Exception as e:
        print(f"Public key demo failed: {e}")

    print()


def main():
    """Run all demonstrations."""
    print("libp2p Record Module Demo")
    print("=" * 50)
    print()

    demo_basic_record_operations()
    demo_key_splitting()
    demo_validation()
    demo_selection()
    demo_public_key_records()

    print("Demo completed!")


if __name__ == "__main__":
    main()
