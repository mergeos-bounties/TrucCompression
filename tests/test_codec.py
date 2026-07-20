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


def test_block_size_bounds() -> None:
    with pytest.raises(ValueError):
        compress_bytes(b"x", block_size=10)


def test_fixture_pack_roundtrip_and_ratio() -> None:
    """Load the 5 corpus samples from data/samples/, compress with fast=True,
    verify round-trip, and assert expected compression ratio bounds."""
    from pathlib import Path

    samples_dir = Path(__file__).parent.parent / "data" / "samples"
    fixtures = {
        "zeros.bin": {"max_ratio": 0.10},      # ~0.0835 observed
        "const.bin": {"max_ratio": 0.12},      # ~0.0967 observed
        "repeat.bin": {"max_ratio": 0.12},     # ~0.0981 observed
        "ramp.bin": {"max_ratio": 0.25},       # ~0.1899 observed
        "text.bin": {"max_ratio": 0.35},       # ~0.2673 observed
    }

    for fname, bounds in fixtures.items():
        path = samples_dir / fname
        assert path.exists(), f"Missing fixture: {path}"
        data = path.read_bytes()
        blob, report = compress_bytes(data, block_size=128, fast=True)
        restored, verify = decompress_bytes(blob)

        # Round-trip
        assert restored == data, f"{fname}: round-trip failed"
        assert verify["verified"] is True, f"{fname}: verification failed"
        assert report["sha256"] == verify["sha256"], f"{fname}: hash mismatch"

        # Ratio bound
        ratio = report["compressed_size"] / report["original_size"]
        assert ratio <= bounds["max_ratio"], (
            f"{fname}: ratio {ratio:.4f} exceeds bound {bounds['max_ratio']:.2f}"
        )

        # Sanity: known good ops present for well-compressed fixtures
        ops = report["operations"]
        if fname in {"zeros.bin", "const.bin"}:
            assert "CONST" in ops, f"{fname}: expected CONST op"
        if fname == "repeat.bin":
            assert "REPEAT" in ops, f"{fname}: expected REPEAT op"
        if fname == "ramp.bin":
            assert "DELTA_ZLIB" in ops, f"{fname}: expected DELTA_ZLIB op"
        if fname == "text.bin":
            assert "ZLIB" in ops, f"{fname}: expected ZLIB op"
