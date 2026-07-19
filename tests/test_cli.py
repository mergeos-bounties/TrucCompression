"""CLI smoke tests."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from truccompression.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output
    assert "MFC1" in result.output


def test_demo() -> None:
    result = runner.invoke(app, ["demo"])
    assert result.exit_code == 0
    assert "demo complete" in result.output


def test_compress_decompress_roundtrip(tmp_path: Path) -> None:
    src = tmp_path / "in.bin"
    mfc = tmp_path / "out.mfc"
    out = tmp_path / "restored.bin"
    src.write_bytes(b"ABC" * 1000)

    r1 = runner.invoke(app, ["compress", str(src), str(mfc), "--fast", "--verify"])
    assert r1.exit_code == 0
    assert mfc.exists()

    r2 = runner.invoke(app, ["decompress", str(mfc), str(out)])
    assert r2.exit_code == 0
    assert out.read_bytes() == src.read_bytes()

    r3 = runner.invoke(app, ["info", str(mfc)])
    assert r3.exit_code == 0
    assert "sha256" in r3.output


def test_bench() -> None:
    result = runner.invoke(app, ["bench"])
    assert result.exit_code == 0
    assert "bench" in result.output.lower() or "Saved" in result.output or "zeros" in result.output
