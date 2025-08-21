"""
Record-specific exceptions for the libp2p record module.
"""

from libp2p.exceptions import BaseLibp2pError


class ErrInvalidRecordType(BaseLibp2pError):
    """Raised when a record has an invalid type or format."""
    pass


class ErrInvalidRecord(BaseLibp2pError):
    """Raised when a record is invalid."""
    pass


class ErrInvalidPublicKey(BaseLibp2pError):
    """Raised when a public key is invalid."""
    pass


class ErrInvalidMultihash(BaseLibp2pError):
    """Raised when a multihash is invalid."""
    pass
