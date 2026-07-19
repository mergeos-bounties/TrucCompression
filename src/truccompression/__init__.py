"""TrucCompression — lossless experimental formula-list binary compressor (MFC)."""

from __future__ import annotations

from truccompression.codec import (
    CodecError,
    OP_NAMES,
    compress_bytes,
    decompress_bytes,
    human_size,
)

__version__ = "0.1.0"

__all__ = [
    "CodecError",
    "OP_NAMES",
    "compress_bytes",
    "decompress_bytes",
    "human_size",
    "__version__",
]
