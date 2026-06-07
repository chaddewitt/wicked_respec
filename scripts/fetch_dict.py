#!/usr/bin/env python3
"""Download the game's Zstd dictionary to assets/cerimal_zstd.dict (idempotent).

    python scripts/fetch_dict.py

Exits 0 if the dictionary is present/valid afterward, 1 (with instructions) otherwise.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.dict_fetch import ensure_dict, default_dict_path, manual_instructions


def main():
    path = default_dict_path()
    if ensure_dict(path):
        print(f"OK: Zstd dictionary present at {path}")
        return 0
    print(manual_instructions(path), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
