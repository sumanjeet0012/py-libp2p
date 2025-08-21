# libp2p Record Module

The record module provides functionality for creating, validating, and selecting records in the libp2p network. It is similar to the [go-libp2p-record](https://github.com/libp2p/go-libp2p-record) module.

## Overview

Records in libp2p are key-value pairs that can be stored and retrieved from the network. The record module provides:

- **Record Creation**: Create new records with `MakePutRecord`
- **Validation**: Validate records using namespace-specific validators
- **Selection**: Select the best record when multiple records exist for the same key
- **Extensibility**: Add custom validators for new namespaces

## Key Components

### Record

The `Record` class represents a record with a key, value, and optional metadata:

```python
from libp2p.record import MakePutRecord

# Create a new record
record = MakePutRecord("/test/key", b"value", author="user")
print(f"Record: {record}")
```

### NamespacedValidator

The `NamespacedValidator` is the main validator that routes validation to namespace-specific validators:

```python
from libp2p.record import NamespacedValidator

validator = NamespacedValidator()

# Validate a record
try:
    validator.validate("/pk/QmTest", public_key_bytes)
    print("Validation passed!")
except Exception as e:
    print(f"Validation failed: {e}")

# Select best record from multiple values
selected_index = validator.select("/pk/QmTest", [value1, value2, value3])
```

### Key Format

Record keys follow the format: `/namespace/path`

- **namespace**: Determines which validator to use
- **path**: The specific identifier within the namespace

Examples:
- `/pk/QmPeerID123` - Public key record
- `/ipns/example.com` - IPNS record
- `/custom/mydata` - Custom namespace record

### Built-in Validators

#### PublicKeyValidator (namespace: "pk")

Validates public key records where:
- Key format: `/pk/<peer-id>`
- Value: Serialized public key (protobuf format)
- Validation: Ensures the public key matches the peer ID

### Custom Validators

You can add custom validators for new namespaces:

```python
from libp2p.record import Validator, NamespacedValidator

class MyValidator(Validator):
    def validate(self, key: str, value: bytes) -> None:
        # Custom validation logic
        if len(value) < 10:
            raise ValueError("Value too short")
    
    def select(self, key: str, values: list[bytes]) -> int:
        # Custom selection logic (e.g., select longest value)
        return max(range(len(values)), key=lambda i: len(values[i]))

# Add to validator
validator = NamespacedValidator()
validator.add_validator("myns", MyValidator())

# Now you can validate "/myns/..." keys
validator.validate("/myns/test", b"my custom data")
```

## Usage Examples

### Basic Record Operations

```python
from libp2p.record import MakePutRecord, NamespacedValidator

# Create a record
record = MakePutRecord("/test/example", b"Hello, World!")

# Create validator
validator = NamespacedValidator()

# This will fail because "test" namespace has no validator
try:
    validator.validate(record.key, record.value)
except Exception as e:
    print(f"Expected failure: {e}")
```

### Public Key Records

```python
from libp2p.record import NamespacedValidator
from libp2p.crypto.ed25519 import create_new_key_pair
from libp2p.peer.id import ID as PeerID

# Generate a key pair
keypair = create_new_key_pair()
peer_id = PeerID.from_pubkey(keypair.public_key)

# Create public key record
pk_key = f"/pk/{peer_id}"
pk_value = keypair.public_key.serialize()

# Validate
validator = NamespacedValidator()
validator.validate(pk_key, pk_value)  # Should pass

# Select (always returns 0 for pk records)
selected = validator.select(pk_key, [pk_value])
```

### Custom Namespace

```python
from libp2p.record import Validator, NamespacedValidator

class TimestampValidator(Validator):
    def validate(self, key: str, value: bytes) -> None:
        # Expect value to be a timestamp
        try:
            timestamp = float(value.decode())
            if timestamp < 0:
                raise ValueError("Timestamp cannot be negative")
        except ValueError:
            raise ValueError("Invalid timestamp format")
    
    def select(self, key: str, values: list[bytes]) -> int:
        # Select the most recent timestamp
        timestamps = []
        for value in values:
            try:
                timestamps.append(float(value.decode()))
            except ValueError:
                timestamps.append(0)  # Invalid timestamps get lowest priority
        
        return max(range(len(timestamps)), key=lambda i: timestamps[i])

# Use the custom validator
validator = NamespacedValidator()
validator.add_validator("timestamp", TimestampValidator())

# Validate timestamp records
validator.validate("/timestamp/event1", b"1640995200.0")

# Select most recent from multiple timestamps
values = [b"1640995200.0", b"1640995300.0", b"1640995100.0"]
selected = validator.select("/timestamp/event1", values)
print(f"Selected index: {selected}")  # Should be 1 (most recent)
```

## Error Handling

The module defines several exception types:

- `ErrInvalidRecordType`: Invalid record key format or unknown namespace
- `ErrInvalidRecord`: General record validation error
- `ErrInvalidPublicKey`: Public key validation error
- `ErrInvalidMultihash`: Multihash validation error

## Function Execution Flow

The module follows this execution flow:

1. **Record Creation**: `MakePutRecord(key, value)` creates a new record
2. **Validation**: `NamespacedValidator.validate(key, value)` validates the record
   - Splits the key into namespace and path
   - Finds the appropriate validator for the namespace
   - Calls the validator's `validate()` method
3. **Selection**: `NamespacedValidator.select(key, values)` selects the best record
   - Finds the appropriate validator for the namespace
   - Calls the validator's `select()` method

## Testing

Run the tests with:

```bash
python -m pytest tests/record/ -v
```

## Demo

See the complete demo at `examples/record_demo.py`:

```bash
python examples/record_demo.py
```

This demonstrates all the functionality including record creation, validation, selection, and custom validators.