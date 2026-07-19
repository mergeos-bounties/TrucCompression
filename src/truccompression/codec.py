
#!/usr/bin/env python3
"""
TrucCompression MFC (Math Formula Codec) — lossless experimental binary compressor.

The file is represented as a sequence of block instructions ("formulas"):
CONST, REPEAT, COPY_PREVIOUS, DELTA+ZLIB, XOR+ZLIB, ZLIB, BZ2, LZMA, or RAW.

This is a real, byte-for-byte reversible prototype. It does not claim that
random/already-compressed data can always be made smaller.
"""
from __future__ import annotations

import argparse
import bz2
import hashlib
import json
import lzma
import struct
import sys
import time
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

MAGIC = b"MFC1"
VERSION = 1

# Opcodes
OP_RAW = 0
OP_CONST = 1
OP_REPEAT = 2
OP_COPY_PREVIOUS = 3
OP_ZLIB = 4
OP_BZ2 = 5
OP_LZMA = 6
OP_DELTA_ZLIB = 7
OP_XOR_ZLIB = 8
OP_RLE = 9

OP_NAMES = {
    OP_RAW: "RAW",
    OP_CONST: "CONST",
    OP_REPEAT: "REPEAT",
    OP_COPY_PREVIOUS: "COPY_PREVIOUS",
    OP_ZLIB: "ZLIB",
    OP_BZ2: "BZ2",
    OP_LZMA: "LZMA",
    OP_DELTA_ZLIB: "DELTA_ZLIB",
    OP_XOR_ZLIB: "XOR_ZLIB",
    OP_RLE: "RLE",
}

# Per-block record:
# opcode: uint8
# original_size: uint32
# payload_size: uint32
BLOCK_HEADER = struct.Struct("<BII")
FILE_HEADER = struct.Struct("<4sBIIQ32s")
# magic, version, block_size, block_count, original_size, sha256


class CodecError(Exception):
    pass


@dataclass(frozen=True)
class Candidate:
    opcode: int
    payload: bytes

    @property
    def stored_size(self) -> int:
        return BLOCK_HEADER.size + len(self.payload)


def chunks(data: bytes, block_size: int) -> Iterable[bytes]:
    for i in range(0, len(data), block_size):
        yield data[i:i + block_size]


def find_repeat_pattern(block: bytes, max_pattern: int = 256) -> bytes | None:
    """Return shortest repeated pattern, or None."""
    n = len(block)
    if n < 2:
        return None
    upper = min(max_pattern, n // 2)
    for p in range(1, upper + 1):
        if n % p == 0 and block == block[:p] * (n // p):
            return block[:p]
    return None


def delta_encode(block: bytes) -> bytes:
    if not block:
        return b""
    out = bytearray(len(block))
    out[0] = block[0]
    prev = block[0]
    for i in range(1, len(block)):
        cur = block[i]
        out[i] = (cur - prev) & 0xFF
        prev = cur
    return bytes(out)


def delta_decode(encoded: bytes) -> bytes:
    if not encoded:
        return b""
    out = bytearray(len(encoded))
    out[0] = encoded[0]
    for i in range(1, len(encoded)):
        out[i] = (out[i - 1] + encoded[i]) & 0xFF
    return bytes(out)


def xor_encode(block: bytes) -> bytes:
    if not block:
        return b""
    out = bytearray(len(block))
    out[0] = block[0]
    for i in range(1, len(block)):
        out[i] = block[i] ^ block[i - 1]
    return bytes(out)


def xor_decode(encoded: bytes) -> bytes:
    if not encoded:
        return b""
    out = bytearray(len(encoded))
    out[0] = encoded[0]
    for i in range(1, len(encoded)):
        out[i] = encoded[i] ^ out[i - 1]
    return bytes(out)


def rle_encode(block: bytes) -> bytes:
    """Run-length encode a byte string.

    Payload format: sequence of (byte: uint8, count: uint16) pairs.
    Runs longer than 65535 are split into multiple pairs.
    Smallest run: 1 byte encodes as 3 bytes — only beneficial when
    runs exceed 3 identical bytes.
    """
    if not block:
        return b""
    payload = bytearray()
    i = 0
    n = len(block)
    while i < n:
        b = block[i]
        j = i + 1
        while j < n and block[j] == b:
            j += 1
        run_len = j - i
        
        # Split runs longer than 65535 into multiple chunks
        while run_len > 0:
            chunk_len = min(run_len, 65535)
            payload.append(b)                    # byte value
            payload.extend(struct.pack("<H", chunk_len))  # run length
            run_len -= chunk_len
        
        i = j
    return bytes(payload)


def rle_decode(payload: bytes, original_size: int) -> bytes:
    """Decode RLE payload back to original bytes."""
    out = bytearray(original_size)
    pos = 0
    idx = 0
    while idx < len(payload):
        if idx + 3 > len(payload):
            raise CodecError("Truncated RLE payload")
        b = payload[idx]
        run_len = struct.unpack("<H", payload[idx + 1:idx + 3])[0]
        idx += 3
        end = pos + run_len
        if end > original_size:
            raise CodecError("RLE payload exceeds original_size")
        out[pos:end] = bytes([b]) * run_len
        pos = end
    if pos != original_size:
        raise CodecError(
            f"RLE decoded size mismatch: expected {original_size}, got {pos}"
        )
    return bytes(out)


def encode_block(block: bytes, previous: bytes | None, fast: bool = False) -> Candidate:
    candidates: list[Candidate] = [Candidate(OP_RAW, block)]

    if block and all(b == block[0] for b in block):
        candidates.append(Candidate(OP_CONST, bytes([block[0]])))

    pattern = find_repeat_pattern(block)
    if pattern is not None:
        # Payload: uint16 pattern length + pattern bytes
        candidates.append(Candidate(OP_REPEAT, struct.pack("<H", len(pattern)) + pattern))

    if previous is not None and block == previous:
        candidates.append(Candidate(OP_COPY_PREVIOUS, b""))

    candidates.append(Candidate(OP_ZLIB, zlib.compress(block, level=9)))
    candidates.append(Candidate(OP_BZ2, bz2.compress(block, compresslevel=9)))

    if not fast:
        candidates.append(
            Candidate(
                OP_LZMA,
                lzma.compress(
                    block,
                    format=lzma.FORMAT_XZ,
                    preset=9 | lzma.PRESET_EXTREME,
                ),
            )
        )

    dz = zlib.compress(delta_encode(block), level=9)
    candidates.append(Candidate(OP_DELTA_ZLIB, dz))

    xz = zlib.compress(xor_encode(block), level=9)
    candidates.append(Candidate(OP_XOR_ZLIB, xz))

    rle_payload = rle_encode(block)
    # Only use RLE if it's actually smaller than raw
    if rle_payload:
        rle_candidate = Candidate(OP_RLE, rle_payload)
        if rle_candidate.stored_size < len(block):
            candidates.append(rle_candidate)

    return min(candidates, key=lambda c: c.stored_size)


def decode_block(opcode: int, payload: bytes, original_size: int, previous: bytes | None) -> bytes:
    if opcode == OP_RAW:
        out = payload
    elif opcode == OP_CONST:
        if len(payload) != 1:
            raise CodecError("Invalid CONST payload")
        out = payload * original_size
    elif opcode == OP_REPEAT:
        if len(payload) < 2:
            raise CodecError("Invalid REPEAT payload")
        pattern_len = struct.unpack("<H", payload[:2])[0]
        pattern = payload[2:]
        if pattern_len != len(pattern) or pattern_len == 0 or original_size % pattern_len:
            raise CodecError("Invalid REPEAT pattern")
        out = pattern * (original_size // pattern_len)
    elif opcode == OP_COPY_PREVIOUS:
        if previous is None or len(previous) != original_size:
            raise CodecError("Invalid COPY_PREVIOUS reference")
        out = previous
    elif opcode == OP_ZLIB:
        out = zlib.decompress(payload)
    elif opcode == OP_BZ2:
        out = bz2.decompress(payload)
    elif opcode == OP_LZMA:
        out = lzma.decompress(payload)
    elif opcode == OP_DELTA_ZLIB:
        out = delta_decode(zlib.decompress(payload))
    elif opcode == OP_XOR_ZLIB:
        out = xor_decode(zlib.decompress(payload))
    elif opcode == OP_RLE:
        out = rle_decode(payload, original_size)
    else:
        raise CodecError(f"Unknown opcode: {opcode}")

    if len(out) != original_size:
        raise CodecError(
            f"Decoded block size mismatch: expected {original_size}, got {len(out)}"
        )
    return out


def compress_bytes(data: bytes, block_size: int = 262_144, fast: bool = False) -> tuple[bytes, dict]:
    if block_size < 64 or block_size > 16 * 1024 * 1024:
        raise ValueError("block_size must be between 64 B and 16 MiB")

    encoded_blocks: list[tuple[Candidate, int]] = []
    stats: dict[str, int] = {}
    previous: bytes | None = None

    for block in chunks(data, block_size):
        candidate = encode_block(block, previous, fast=fast)
        encoded_blocks.append((candidate, len(block)))
        name = OP_NAMES[candidate.opcode]
        stats[name] = stats.get(name, 0) + 1
        previous = block

    digest = hashlib.sha256(data).digest()
    header = FILE_HEADER.pack(
        MAGIC,
        VERSION,
        block_size,
        len(encoded_blocks),
        len(data),
        digest,
    )

    out = bytearray(header)
    for candidate, original_size in encoded_blocks:
        out.extend(BLOCK_HEADER.pack(candidate.opcode, original_size, len(candidate.payload)))
        out.extend(candidate.payload)

    report = {
        "version": VERSION,
        "original_size": len(data),
        "compressed_size": len(out),
        "ratio": (len(out) / len(data)) if data else 0.0,
        "saved_percent": (1.0 - len(out) / len(data)) * 100.0 if data else 0.0,
        "block_size": block_size,
        "block_count": len(encoded_blocks),
        "sha256": digest.hex(),
        "operations": stats,
    }
    return bytes(out), report


def decompress_bytes(blob: bytes) -> tuple[bytes, dict]:
    if len(blob) < FILE_HEADER.size:
        raise CodecError("File is too short")

    magic, version, block_size, block_count, original_size, expected_hash = FILE_HEADER.unpack(
        blob[:FILE_HEADER.size]
    )
    if magic != MAGIC:
        raise CodecError("Not an MFC file")
    if version != VERSION:
        raise CodecError(f"Unsupported MFC version: {version}")

    offset = FILE_HEADER.size
    output = bytearray()
    previous: bytes | None = None
    stats: dict[str, int] = {}

    for index in range(block_count):
        if offset + BLOCK_HEADER.size > len(blob):
            raise CodecError(f"Truncated block header at block {index}")
        opcode, raw_size, payload_size = BLOCK_HEADER.unpack(
            blob[offset:offset + BLOCK_HEADER.size]
        )
        offset += BLOCK_HEADER.size

        end = offset + payload_size
        if end > len(blob):
            raise CodecError(f"Truncated payload at block {index}")
        payload = blob[offset:end]
        offset = end

        block = decode_block(opcode, payload, raw_size, previous)
        output.extend(block)
        previous = block
        name = OP_NAMES.get(opcode, f"UNKNOWN_{opcode}")
        stats[name] = stats.get(name, 0) + 1

    if offset != len(blob):
        raise CodecError(f"Unexpected trailing data: {len(blob) - offset} bytes")
    if len(output) != original_size:
        raise CodecError(
            f"Total size mismatch: expected {original_size}, got {len(output)}"
        )

    actual_hash = hashlib.sha256(output).digest()
    if actual_hash != expected_hash:
        raise CodecError("SHA-256 mismatch; file is corrupt or decoding is incorrect")

    report = {
        "version": version,
        "original_size": original_size,
        "compressed_size": len(blob),
        "block_size": block_size,
        "block_count": block_count,
        "sha256": actual_hash.hex(),
        "operations": stats,
        "verified": True,
    }
    return bytes(output), report


def human_size(n: int) -> str:
    units = ["B", "KiB", "MiB", "GiB"]
    value = float(n)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{n} B"


def cmd_compress(args: argparse.Namespace) -> int:
    src = Path(args.input)
    dst = Path(args.output)
    data = src.read_bytes()

    t0 = time.perf_counter()
    blob, report = compress_bytes(data, block_size=args.block_size, fast=args.fast)
    elapsed = time.perf_counter() - t0
    dst.write_bytes(blob)

    print(f"Input       : {src}")
    print(f"Output      : {dst}")
    print(f"Original    : {human_size(report['original_size'])}")
    print(f"Compressed  : {human_size(report['compressed_size'])}")
    print(f"Ratio       : {report['ratio'] * 100:.3f}%")
    print(f"Saved       : {report['saved_percent']:.3f}%")
    print(f"Blocks      : {report['block_count']}")
    print(f"Operations  : {json.dumps(report['operations'], ensure_ascii=False)}")
    print(f"SHA-256     : {report['sha256']}")
    print(f"Time        : {elapsed:.3f} s")

    if args.verify:
        restored, verify_report = decompress_bytes(blob)
        if restored != data:
            raise CodecError("Verification failed: restored bytes differ")
        print("Verify      : OK — byte-for-byte identical")
    return 0


def cmd_decompress(args: argparse.Namespace) -> int:
    src = Path(args.input)
    dst = Path(args.output)
    blob = src.read_bytes()

    t0 = time.perf_counter()
    data, report = decompress_bytes(blob)
    elapsed = time.perf_counter() - t0
    dst.write_bytes(data)

    print(f"Input       : {src}")
    print(f"Output      : {dst}")
    print(f"Restored    : {human_size(len(data))}")
    print(f"SHA-256     : {report['sha256']}")
    print(f"Operations  : {json.dumps(report['operations'], ensure_ascii=False)}")
    print("Verify      : OK")
    print(f"Time        : {elapsed:.3f} s")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    blob = Path(args.input).read_bytes()
    _, report = decompress_bytes(blob)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Lossless experimental formula-list binary compressor"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_c = sub.add_parser("compress", aliases=["c"], help="Compress a file")
    p_c.add_argument("input")
    p_c.add_argument("output")
    p_c.add_argument(
        "--block-size",
        type=int,
        default=262_144,
        help="Block size in bytes (default: 262144)",
    )
    p_c.add_argument(
        "--fast",
        action="store_true",
        help="Skip the slow LZMA candidate",
    )
    p_c.add_argument(
        "--verify",
        action="store_true",
        help="Immediately decompress and compare byte-for-byte",
    )
    p_c.set_defaults(func=cmd_compress)

    p_d = sub.add_parser("decompress", aliases=["d"], help="Decompress an MFC file")
    p_d.add_argument("input")
    p_d.add_argument("output")
    p_d.set_defaults(func=cmd_decompress)

    p_i = sub.add_parser("info", aliases=["i"], help="Validate and show MFC metadata")
    p_i.add_argument("input")
    p_i.set_defaults(func=cmd_info)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except (OSError, ValueError, CodecError, lzma.LZMAError, zlib.error) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
