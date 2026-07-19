"""Tests for CLI --json-report flag."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from truccompression.cli import app

runner = CliRunner()


def test_json_report(tmp_path: Path):
    """--json-report writes a valid JSON file with expected fields."""
    inp = tmp_path / "input.bin"
    inp.write_bytes(b"\x00" * 4096)
    out = tmp_path / "out.mfc"
    report_path = tmp_path / "report.json"

    result = runner.invoke(app, [
        "compress", str(inp), str(out),
        "--fast", "--verify",
        "--json-report", str(report_path),
    ])
    assert result.exit_code == 0, result.output
    assert report_path.exists()

    data = json.loads(report_path.read_text())
    assert "input" in data
    assert "output" in data
    assert "original_size" in data
    assert "compressed_size" in data
    assert "ratio" in data
    assert "saved_percent" in data
    assert "block_size" in data
    assert "block_count" in data
    assert "sha256" in data
    assert "operations" in data
    assert "elapsed_seconds" in data
    assert data["original_size"] == 4096


def test_compress_without_json_report(tmp_path: Path):
    """Compress works without --json-report flag."""
    inp = tmp_path / "input.bin"
    inp.write_bytes(b"ABCD" * 256)
    out = tmp_path / "out.mfc"

    result = runner.invoke(app, ["compress", str(inp), str(out), "--fast"])
    assert result.exit_code == 0
    assert out.exists()


def test_json_report_content_accuracy(tmp_path: Path):
    """JSON report values match actual compression results."""
    from truccompression.codec import compress_bytes

    data = b"hello world " * 100
    inp = tmp_path / "input.bin"
    inp.write_bytes(data)
    out = tmp_path / "out.mfc"
    report_path = tmp_path / "report.json"

    result = runner.invoke(app, [
        "compress", str(inp), str(out),
        "--fast", "--json-report", str(report_path),
    ])
    assert result.exit_code == 0

    report = json.loads(report_path.read_text())
    _, expected_report = compress_bytes(data, block_size=262144, fast=True)

    assert report["original_size"] == expected_report["original_size"]
    assert report["sha256"] == expected_report["sha256"]
