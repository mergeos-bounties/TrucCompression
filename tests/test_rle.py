"""Tests for RLE opcode."""

from __future__ import annotations

from truccompression.codec import (
    OP_RLE,
    compress_bytes,
    decompress_bytes,
    rle_encode,
    rle_decode,
)


def test_rle_encode_decode_roundtrip():
    data = b"\x00\x00\x00\x41\x41\x42\x42\x42\x42"
    encoded = rle_encode(data)
    decoded = rle_decode(encoded, len(data))
    assert decoded == data


def test_rle_empty():
    assert rle_encode(b"") == b""
    assert rle_decode(b"", 0) == b""


def test_rle_single_byte():
    encoded = rle_encode(b"\x41")
    decoded = rle_decode(encoded, 1)
    assert decoded == b"\x41"


def test_rle_long_run():
    data = b"\x00" * 1000
    encoded = rle_encode(data)
    assert len(encoded) < len(data)
    decoded = rle_decode(encoded, len(data))
    assert decoded == data


def test_rle_in_compress_bytes():
    """RLE-friendly data should use RLE opcode or smaller alternative."""
    data = b"\x00\x00\x00\x00\x41\x41\x41\x41\x42\x42\x42\x42" * 100
    blob, report = compress_bytes(data, block_size=256, fast=True)
    restored, verify = decompress_bytes(blob)
    assert restored == data
    assert verify["verified"] is True


def test_rle_non_rle_data():
    """Non-RLE-friendly data should still round-trip correctly."""
    data = bytes(range(256)) * 4
    blob, report = compress_bytes(data, block_size=256, fast=True)
    restored, verify = decompress_bytes(blob)
    assert restored == data
    assert verify["verified"] is True


def test_rle_does_not_break_existing():
    """Existing opcodes still work alongside RLE."""
    data = b"hello world " * 80
    blob, report = compress_bytes(data, block_size=128, fast=True)
    restored, _ = decompress_bytes(blob)
    assert restored == data


def test_rle_opcode_in_names():
    """OP_RLE is registered in OP_NAMES."""
    from truccompression.codec import OP_NAMES
    assert OP_RLE in OP_NAMES
    assert OP_NAMES[OP_RLE] == "RLE"
