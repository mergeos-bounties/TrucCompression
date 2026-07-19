"""TrucCompression CLI — compress / decompress / info / demo / bench."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from truccompression import __version__
from truccompression.codec import (
    CodecError,
    OP_NAMES,
    compress_bytes,
    decompress_bytes,
    human_size,
)

app = typer.Typer(
    help="TrucCompression — lossless experimental MFC binary compressor.",
    no_args_is_help=True,
)
console = Console()


@app.command("version")
def version_cmd() -> None:
    """Print package version and codec format."""
    console.print(
        {
            "version": __version__,
            "format": "MFC1",
            "ops": list(OP_NAMES.values()),
        }
    )


@app.command("demo")
def demo_cmd(
    fast: bool = typer.Option(True, help="Skip slow LZMA candidate (default on for smoke)"),
) -> None:
    """Offline smoke: compress synthetic fixtures and verify round-trip."""
    samples = {
        "zeros": b"\x00" * 4096,
        "const_aa": b"A" * 2048,
        "repeat_ab": (b"AB" * 1024),
        "text": (b"hello world " * 256),
        "ramp": bytes(range(256)) * 8,
    }
    table = Table(title="TrucCompression demo (offline)")
    table.add_column("Fixture")
    table.add_column("Original")
    table.add_column("Compressed")
    table.add_column("Saved %")
    table.add_column("Top ops")
    table.add_column("Verify")

    for name, data in samples.items():
        blob, report = compress_bytes(data, block_size=1024, fast=fast)
        restored, _ = decompress_bytes(blob)
        ok = restored == data
        ops = ", ".join(f"{k}:{v}" for k, v in sorted(report["operations"].items()))
        table.add_row(
            name,
            human_size(report["original_size"]),
            human_size(report["compressed_size"]),
            f"{report['saved_percent']:.1f}",
            ops[:48],
            "OK" if ok else "FAIL",
        )
        if not ok:
            raise CodecError(f"demo fixture {name} failed round-trip")

    console.print(table)
    console.print(f"[green]demo complete[/green] — TrucCompression {__version__}")


@app.command("compress")
def compress_cmd(
    input: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    output: Path = typer.Argument(...),
    block_size: int = typer.Option(262_144, help="Block size in bytes"),
    fast: bool = typer.Option(False, help="Skip slow LZMA candidate"),
    verify: bool = typer.Option(False, help="Round-trip verify after compress"),
) -> None:
    """Compress a file to MFC format."""
    data = input.read_bytes()
    t0 = time.perf_counter()
    blob, report = compress_bytes(data, block_size=block_size, fast=fast)
    elapsed = time.perf_counter() - t0
    output.write_bytes(blob)
    console.print(f"Input       : {input}")
    console.print(f"Output      : {output}")
    console.print(f"Original    : {human_size(report['original_size'])}")
    console.print(f"Compressed  : {human_size(report['compressed_size'])}")
    console.print(f"Ratio       : {report['ratio'] * 100:.3f}%")
    console.print(f"Saved       : {report['saved_percent']:.3f}%")
    console.print(f"Blocks      : {report['block_count']}")
    console.print(f"Operations  : {json.dumps(report['operations'], ensure_ascii=False)}")
    console.print(f"SHA-256     : {report['sha256']}")
    console.print(f"Time        : {elapsed:.3f} s")
    if verify:
        restored, _ = decompress_bytes(blob)
        if restored != data:
            raise CodecError("Verification failed: restored bytes differ")
        console.print("Verify      : OK — byte-for-byte identical")


@app.command("decompress")
def decompress_cmd(
    input: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    output: Path = typer.Argument(...),
) -> None:
    """Decompress an MFC file."""
    blob = input.read_bytes()
    t0 = time.perf_counter()
    data, report = decompress_bytes(blob)
    elapsed = time.perf_counter() - t0
    output.write_bytes(data)
    console.print(f"Input       : {input}")
    console.print(f"Output      : {output}")
    console.print(f"Restored    : {human_size(len(data))}")
    console.print(f"SHA-256     : {report['sha256']}")
    console.print(f"Operations  : {json.dumps(report['operations'], ensure_ascii=False)}")
    console.print("Verify      : OK")
    console.print(f"Time        : {elapsed:.3f} s")


@app.command("info")
def info_cmd(
    input: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
) -> None:
    """Validate and show MFC metadata (full decompress + verify hash)."""
    blob = input.read_bytes()
    _, report = decompress_bytes(blob)
    console.print_json(json.dumps(report, ensure_ascii=False))


@app.command("bench")
def bench_cmd(
    input: Optional[Path] = typer.Argument(
        None,
        exists=True,
        dir_okay=False,
        readable=True,
        help="Optional file; default uses synthetic fixtures",
    ),
    block_size: int = typer.Option(65_536, help="Block size"),
    fast: bool = typer.Option(True, help="Skip LZMA for faster bench"),
) -> None:
    """Benchmark compress ratio/time on a file or synthetic data."""
    if input is not None:
        payloads = {input.name: input.read_bytes()}
    else:
        payloads = {
            "zeros_64k": b"\x00" * 65_536,
            "text_64k": (b"lorem ipsum dolor sit amet " * 2500)[:65_536],
            "random_64k": bytes((i * 37 + 11) % 256 for i in range(65_536)),
        }

    table = Table(title="TrucCompression bench")
    table.add_column("Name")
    table.add_column("Original")
    table.add_column("Compressed")
    table.add_column("Saved %")
    table.add_column("Time s")
    table.add_column("Ops")

    for name, data in payloads.items():
        t0 = time.perf_counter()
        blob, report = compress_bytes(data, block_size=block_size, fast=fast)
        elapsed = time.perf_counter() - t0
        restored, _ = decompress_bytes(blob)
        if restored != data:
            raise CodecError(f"bench {name} round-trip failed")
        ops = ",".join(f"{k}:{v}" for k, v in sorted(report["operations"].items()))
        table.add_row(
            name,
            human_size(report["original_size"]),
            human_size(report["compressed_size"]),
            f"{report['saved_percent']:.2f}",
            f"{elapsed:.3f}",
            ops[:40],
        )
    console.print(table)


def main() -> None:
    try:
        app()
    except (OSError, ValueError, CodecError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
