"""Fixture pack smoke tests for issue #1: 5 corpus samples + expected ratio smoke."""

from __future__ import annotations

from pathlib import Path

import pytest

from truccompression import compress_bytes, decompress_bytes


def test_fixture_pack_smoke() -> None:
    """Test the 5 corpus samples from data/samples/ with fast=True and size bounds."""
    base = Path("data/samples")
    fixtures = [
        ("zeros.bin", 4096),
        ("const.bin", 2048),
        ("repeat.bin", 2048),
        ("text.bin", 3072),
        ("ramp.bin", 2048),
    ]

    for name, expected_size in fixtures:
        path = base / name
        assert path.exists(), f"Missing fixture: {path}"
        data = path.read_bytes()
        assert len(data) == expected_size, f"Wrong size for {name}"

        # Compress with fast=True (as required by issue)
        blob, report = compress_bytes(data, fast=True)
        assert blob, f"Empty blob for {name}"

        # Decompress and verify round-trip
        restored, verify = decompress_bytes(blob)
        assert verify["verified"] is True, f"Verification failed for {name}"
        assert restored == data, f"Round-trip failed for {name}"

        # Basic sanity: compressed should be <= original (or not explode wildly)
        # Note: RLE/const etc should shrink; ramp may grow slightly but not 10x
        assert len(blob) <= expected_size * 3, f"Compression exploded for {name}: {len(blob)} > {expected_size * 3}"


def test_fixture_pack_individual() -> None:
    """Individual tests for each fixture to match issue description exactly."""
    base = Path("data/samples")

    # zeros.bin
    zeros = (base / "zeros.bin").read_bytes()
    blob, _ = compress_bytes(zeros, fast=True)
    restored, verify = decompress_bytes(blob)
    assert verify["verified"]
    assert restored == zeros

    # const.bin
    const = (base / "const.bin").read_bytes()
    blob, _ = compress_bytes(const, fast=True)
    restored, verify = decompress_bytes(blob)
    assert verify["verified"]
    assert restored == const

    # repeat.bin
    repeat = (base / "repeat.bin").read_bytes()
    blob, _ = compress_bytes(repeat, fast=True)
    restored, verify = decompress_bytes(blob)
    assert verify["verified"]
    assert restored == repeat

    # text.bin
    text = (base / "text.bin").read_bytes()
    blob, _ = compress_bytes(text, fast=True)
    restored, verify = decompress_bytes(blob)
    assert verify["verified"]
    assert restored == text

    # ramp.bin
    ramp = (base / "ramp.bin").read_bytes()
    blob, _ = compress_bytes(ramp, fast=True)
    restored, verify = decompress_bytes(blob)
    assert verify["verified"]
    assert restored == ramp