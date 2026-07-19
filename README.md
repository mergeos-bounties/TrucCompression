# TrucCompression

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-0.1.0-0E8A16.svg)](pyproject.toml)
[![CI](https://github.com/mergeos-bounties/TrucCompression/actions/workflows/ci.yml/badge.svg)](https://github.com/mergeos-bounties/TrucCompression/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![MergeOS](https://img.shields.io/badge/MergeOS-bounties-5319E7.svg)](https://github.com/mergeos-bounties)
[![Pages](https://img.shields.io/badge/docs-GitHub%20Pages-222.svg)](https://mergeos-bounties.github.io/TrucCompression/)

**TrucCompression** is a public MergeOS product for **lossless experimental data compression**. It implements the **Math Formula Codec (MFC1)** container: each file is encoded as a sequence of reversible block “formulas” (CONST, REPEAT, COPY_PREVIOUS, ZLIB, BZ2, LZMA, DELTA+ZLIB, XOR+ZLIB, or RAW). The encoder scores candidates per block and keeps the smallest payload. Round-trips are **byte-for-byte** with a SHA-256 seal in the header.

Product site: [mergeos-bounties.github.io/TrucCompression](https://mergeos-bounties.github.io/TrucCompression/) · Source: [github.com/mergeos-bounties/TrucCompression](https://github.com/mergeos-bounties/TrucCompression)

## Live playground (GitHub Pages)

Open **[mergeos-bounties.github.io/TrucCompression](https://mergeos-bounties.github.io/TrucCompression/)** to:

1. Load a **sample fixture** (zeros, const, repeat, text, ramp, noise, WAV tone, PNG) or drop your own file  
2. **Compress** with browser MFC1 and **restore** with SHA-256 verify  
3. **Compare** size / ratio / time against **Gzip** and **Deflate/zlib** (`CompressionStream`)  
4. Download `.mfc` and restored bytes — all client-side, nothing uploaded  

Sample files also live under `docs/samples/` and `data/samples/` for CLI testing.

## Highlights

| Area | Detail |
| --- | --- |
| Format | `MFC1` container, versioned header + block records |
| Integrity | SHA-256 of original payload verified on decompress |
| CLI | `version`, `demo`, `compress`, `decompress`, `info`, `bench` |
| Pages | Interactive compress / restore / compare + fixtures |
| Offline | Demo and unit tests need no network |
| Honesty | High-entropy / already-compressed data may grow (RAW fallback) |

## Quick start

```powershell
cd TrucCompression
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
truccompression version
truccompression demo
```

Compress / decompress:

```powershell
truccompression compress .\data\samples\zeros.bin .\out.mfc --fast --verify
truccompression info .\out.mfc
truccompression decompress .\out.mfc .\restored.bin
```

macOS / Linux: activate with `source .venv/bin/activate`.

## CLI reference

| Command | Purpose |
| --- | --- |
| `truccompression version` | Package version + format + op list |
| `truccompression demo` | Offline fixtures + round-trip table |
| `truccompression compress IN OUT` | Encode to `.mfc` (`--block-size`, `--fast`, `--verify`) |
| `truccompression decompress IN OUT` | Decode MFC → original bytes |
| `truccompression info IN` | Validate and print JSON report |
| `truccompression bench [FILE]` | Ratio/time on file or synthetic corpus |

Alias entrypoint: `mfc` (same CLI).

### Library

```python
from truccompression import compress_bytes, decompress_bytes

blob, report = compress_bytes(b"AAAA" * 1000, fast=True)
data, verify = decompress_bytes(blob)
assert data == b"AAAA" * 1000 and verify["verified"]
```

## Block operations

| Op | When it wins |
| --- | --- |
| `CONST` | All bytes equal |
| `REPEAT` | Tileable pattern |
| `COPY_PREVIOUS` | Block equals previous block |
| `ZLIB` / `BZ2` / `LZMA` | General entropy coding |
| `DELTA_ZLIB` / `XOR_ZLIB` | Correlated sequences after transform |
| `RAW` | Cheapest when nothing compresses |

## Repository layout

```text
src/truccompression/   # codec + CLI
tests/                 # pytest
docs/                  # GitHub Pages site
data/samples/          # tiny offline fixtures
.github/workflows/     # ci + pages
```

## Development

```powershell
pip install -e ".[dev]"
ruff check src tests
pytest -q
truccompression demo
truccompression bench
```

## MergeOS bounties

Star → claim bounty issue → PR to **master** → MRG **25–200**.  
See [docs/BOUNTY.md](docs/BOUNTY.md) and [mergeos](https://github.com/mergeos-bounties/mergeos).

Required community badges on PRs: follow [mergeos-bounties](https://github.com/mergeos-bounties), star [mergeos](https://github.com/mergeos-bounties/mergeos) + [mergeos-contracts](https://github.com/mergeos-bounties/mergeos-contracts).

## License

MIT — see [LICENSE](LICENSE).
