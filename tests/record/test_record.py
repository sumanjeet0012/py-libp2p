"""
Tests for the record module.
"""

import pytest

from libp2p.record import (
    ErrInvalidRecordType,
    MakePutRecord,
    NamespacedValidator,
    PublicKeyValidator,
    Record,
    SplitKey,
)


class TestRecord:
    """Test the Record class and MakePutRecord function."""

    def test_make_put_record(self):
        """Test creating a record with MakePutRecord."""
        key = "/test/key"
        value = b"test value"

        record = MakePutRecord(key, value)

        assert record.key == key
        assert record.value == value
        assert record.author is None
        assert record.timestamp is not None

    def test_record_equality(self):
        """Test record equality comparison."""
        key = "/test/key"
        value = b"test value"

        record1 = Record(key, value, "author1")
        record2 = Record(key, value, "author1")
        record3 = Record(key, value, "author2")

        assert record1 == record2
        assert record1 != record3

    def test_record_repr(self):
        """Test record string representation."""
        record = Record("/test/key", b"value", "author")
        repr_str = repr(record)

        assert "Record" in repr_str
        assert "/test/key" in repr_str
        assert "author" in repr_str


class TestSplitKey:
    """Test the SplitKey utility function."""

    def test_split_key_with_leading_slash(self):
        """Test splitting a key with leading slash."""
        namespace, path = SplitKey("/pk/QmTest")
        assert namespace == "pk"
        assert path == "QmTest"

    def test_split_key_without_leading_slash(self):
        """Test splitting a key without leading slash."""
        namespace, path = SplitKey("pk/QmTest")
        assert namespace == "pk"
        assert path == "QmTest"

    def test_split_key_with_multiple_slashes(self):
        """Test splitting a key with multiple slashes in path."""
        namespace, path = SplitKey("/namespace/path/with/slashes")
        assert namespace == "namespace"
        assert path == "path/with/slashes"

    def test_split_key_empty_key(self):
        """Test splitting an empty key raises exception."""
        with pytest.raises(ErrInvalidRecordType, match="empty key"):
            SplitKey("")

    def test_split_key_no_slash(self):
        """Test splitting a key without slash raises exception."""
        with pytest.raises(ErrInvalidRecordType, match="invalid key format"):
            SplitKey("noSlash")

    def test_split_key_empty_namespace(self):
        """Test splitting a key with empty namespace raises exception."""
        with pytest.raises(ErrInvalidRecordType, match="empty namespace"):
            SplitKey("//path")

    def test_split_key_empty_path(self):
        """Test splitting a key with empty path raises exception."""
        with pytest.raises(ErrInvalidRecordType, match="empty path"):
            SplitKey("namespace/")


class TestNamespacedValidator:
    """Test the NamespacedValidator class."""

    def test_validator_by_key_pk_namespace(self):
        """Test getting validator for pk namespace."""
        validator = NamespacedValidator()
        pk_validator = validator.validator_by_key("/pk/QmTest")

        assert isinstance(pk_validator, PublicKeyValidator)

    def test_validator_by_key_unknown_namespace(self):
        """Test getting validator for unknown namespace."""
        validator = NamespacedValidator()
        unknown_validator = validator.validator_by_key("/unknown/test")

        assert unknown_validator is None

    def test_validator_by_key_invalid_key(self):
        """Test getting validator for invalid key."""
        validator = NamespacedValidator()
        invalid_validator = validator.validator_by_key("invalid")

        assert invalid_validator is None

    def test_validate_unknown_namespace(self):
        """Test validating record with unknown namespace."""
        validator = NamespacedValidator()

        with pytest.raises(ErrInvalidRecordType, match="no validator for namespace"):
            validator.validate("/unknown/test", b"value")

    def test_validate_invalid_key(self):
        """Test validating record with invalid key."""
        validator = NamespacedValidator()

        with pytest.raises(ErrInvalidRecordType, match="invalid key format"):
            validator.validate("invalid", b"value")


if __name__ == "__main__":
    pytest.main([__file__])
