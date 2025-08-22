from .pb import record_pb2
from typing import Any, Optional
import time



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
        signature: Optional[bytes] = None
    ):
        """
        Initialize a new Record.
        
        Args:
            key: The record key
            value: The record value as bytes
            author: Optional author identifier
            signature: Optional PKI signature for the key+value+author

        """
        self.key = key
        self.value = value
        self.author = author
        self.signature = signature
        self.timestamp = time.time()  # Set current timestamp 

    def to_proto(self) -> record_pb2.Record:
        """Convert to protobuf Record message."""
        proto_record = record_pb2.Record()
        proto_record.key = self.key.encode("utf-8")
        proto_record.value = self.value
        if self.author:
            proto_record.author = self.author
        if self.signature:
            proto_record.signature = self.signature
        return proto_record

    @staticmethod
    def from_proto(proto: record_pb2.Record) -> "Record":
        """Convert from protobuf Record message."""
        record = Record(
            key=proto.key.decode("utf-8"),
            value=proto.value,
            author=proto.author if proto.author else None,
            signature=proto.signature if proto.signature else None
        )
        if proto.timeReceived:
            record.timestamp = time.mktime(time.strptime(proto.timeReceived, '%Y-%m-%dT%H:%M:%SZ'))
        return record

    def __repr__(self) -> str:
        return (
            f"Record(key='{self.key}', value_len={len(self.value)}, "
            f"author='{self.author}', signature_len={len(self.signature) if self.signature else 0})"
        )

    def __eq__(self, other: object) -> bool:
        """Check equality of two Record objects."""
        if not isinstance(other, Record):
            return NotImplemented
        return (
            self.key == other.key
            and self.value == other.value
            and self.author == other.author
            and self.signature == other.signature
        )


def MakePutRecord(
    key: str,
    value: bytes,
    author: Optional[str] = None,
    signature: Optional[bytes] = None
) -> Record:
    """
    Create a new Record for putting into the network.
    """
    return Record(key=key, value=value, author=author, signature=signature)
