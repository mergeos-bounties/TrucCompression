# Contributing to TrucCompression

Thanks for helping improve a **public MergeOS product**.

## Setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -e ".[dev]"
ruff check src tests
pytest -q
truccompression demo
```

## PR checklist

1. Follow org Gate order (badges → security → CI).
2. Follow + star: [mergeos-bounties](https://github.com/mergeos-bounties), [mergeos](https://github.com/mergeos-bounties/mergeos), [mergeos-contracts](https://github.com/mergeos-bounties/mergeos-contracts).
3. Keep changes **lossless** — any new op must round-trip byte-for-byte with tests.
4. No secrets in fixtures or samples.
5. Prefer additive APIs; bump patch/minor in `pyproject.toml` when user-facing.

## Codec rules

- Container magic `MFC1` + SHA-256 of original payload is mandatory.
- New opcodes need: encode, decode, unit tests, demo mention if user-visible.
- High-entropy growth is OK (RAW fallback); do not claim universal shrinkage.

## Bounties

Claim an issue labeled `bounty`, open PR to **master**, wait for CI green and maintainer merge + MRG credit.
