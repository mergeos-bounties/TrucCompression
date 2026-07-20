"""Fixture pack smoke tests for data/samples/."""

from __future__ import annotations

import pathlib

import pytest

from truccompression.codec import compress_bytes, decompress_bytes

SAMPLES_DIR = pathlib.Path(__file__).resolve().parent.parent / "data" / "samples"

FIXTURES = ["zeros.bin", "const.bin", "repeat.bin", "text.bin", "ramp.bin"]


@pytest.fixture(params=FIXTURES)
def fixture_data(request):
    path = SAMPLES_DIR / request.param
    if not path.exists():
        pytest.skip(f"Fixture {request.param} not found")
    return (request.param, path.read_bytes())


def test_fixture_round_trip(fixture_data):
    """Each fixture round-trips through compress/decompress."""
    name, data = fixture_data
    blob, report = compress_bytes(data, block_size=128, fast=True)
    restored, verify = decompress_bytes(blob)
    assert restored == data, f"Round-trip failed for {name}"
    assert verify["verified"] is True


def test_fixture_size_bounds(fixture_data):
    """Compressed size stays within reasonable bounds."""
    name, data = fixture_data
    if len(data) == 0:
        return
    blob, report = compress_bytes(data, block_size=128, fast=True)
    # Compressed output should not be more than 2x original for these simple fixtures
    assert report["compressed_size"] <= len(data) * 2, (
        f"Compressed {name} is {report['compressed_size']} > {len(data) * 2}"
    )


def test_all_fixtures_present():
    """All 5 expected fixtures exist in data/samples/."""
    for name in FIXTURES:
        path = SAMPLES_DIR / name
        assert path.exists(), f"Missing fixture: {name}"


def test_fixture_non_empty():
    """Fixtures are non-empty."""
    for name in FIXTURES:
        path = SAMPLES_DIR / name
        if path.exists():
            assert path.stat().st_size > 0, f"Empty fixture: {name}"
