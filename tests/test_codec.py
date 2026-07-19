"""Core MFC codec round-trip tests."""

from __future__ import annotations

import zlib

import pytest

from truccompression.codec import (
    CodecError,
    compress_bytes,
    decompress_bytes,
    find_repeat_pattern,
)


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"\x00" * 100,
        b"A" * 500,
        b"AB" * 300,
        b"hello world " * 80,
        bytes(range(256)) * 4,
        zlib.compress(b"payload" * 200),
    ],
)
def test_round_trip(data: bytes) -> None:
    blob, report = compress_bytes(data, block_size=128, fast=True)
    restored, verify = decompress_bytes(blob)
    assert restored == data
    assert report["original_size"] == len(data)
    assert verify["verified"] is True
    assert report["sha256"] == verify["sha256"]


def test_const_and_repeat_ops_preferred() -> None:
    data = b"Z" * 4096
    blob, report = compress_bytes(data, block_size=1024, fast=True)
    assert report["compressed_size"] < report["original_size"]
    assert "CONST" in report["operations"] or "REPEAT" in report["operations"]
    restored, _ = decompress_bytes(blob)
    assert restored == data


def test_copy_previous() -> None:
    block = b"pattern-1234" * 32
    data = block + block
    blob, report = compress_bytes(data, block_size=len(block), fast=True)
    assert report["block_count"] == 2
    # Second block may be COPY_PREVIOUS when identical
    restored, _ = decompress_bytes(blob)
    assert restored == data


def test_find_repeat_pattern() -> None:
    assert find_repeat_pattern(b"ababab") == b"ab"
    assert find_repeat_pattern(b"abc") is None


def test_corrupt_magic() -> None:
    blob, _ = compress_bytes(b"abc", block_size=64, fast=True)
    bad = b"XXXX" + blob[4:]
    with pytest.raises(CodecError):
        decompress_bytes(bad)


def test_rle_round_trip_run_data() -> None:
    """RLE-friendly data: long runs of same byte."""
    data = b"\x00" * 300 + b"\xff" * 200 + b"\xAA" * 100
    blob, report = compress_bytes(data, block_size=1024, fast=True)
    assert "RLE" in report["operations"]
    restored, _ = decompress_bytes(blob)
    assert restored == data


def test_rle_round_trip_no_runs() -> None:
    """Non-RLE data: no repeated bytes — should not use RLE op."""
    data = bytes(range(256)) * 4
    blob, report = compress_bytes(data, block_size=1024, fast=True)
    restored, _ = decompress_bytes(blob)
    assert restored == data
    # RLE would be wasteful here (all unique), so RAW or zlib wins
    assert "RLE" not in report["operations"] or report["operations"]["RLE"] == 0


def test_rle_large_runs() -> None:
    """Large blocks with single-value runs."""
    data = b"\x42" * 70000 + b"\x99" * 30000
    blob, report = compress_bytes(data, block_size=65536, fast=True)
    assert "RLE" in report["operations"]
    restored, _ = decompress_bytes(blob)
    assert restored == data


def test_rle_and_other_ops_share_block() -> None:
    """Multi-block with mixed content: RLE should win on run blocks."""
    data = b"\x00" * 5000 + bytes(range(200)) + b"\xff" * 5000
    blob, report = compress_bytes(data, block_size=4096, fast=True)
    restored, _ = decompress_bytes(blob)
    assert restored == data


def test_block_size_bounds() -> None:
    with pytest.raises(ValueError):
        compress_bytes(b"x", block_size=10)
