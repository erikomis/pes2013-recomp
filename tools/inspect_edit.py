#!/usr/bin/env python3
"""Read-only reconnaissance of a decrypted PS3 EEDIT DATA.BIN.

Prints JSON to stdout. Text hits are evidence, NOT decoded team/player records.
Usage: inspect_edit.py path/to/DATA.BIN --text CORINTHIANS --text NEYMAR
"""
import argparse
import hashlib
import json
from pathlib import Path


def inspect(path, terms):
    data = path.read_bytes()
    hits = []
    for term in terms:
        if not term:
            raise ValueError("search text cannot be empty")
        for encoding in ("utf-8", "utf-16-le", "utf-16-be"):
            needle = term.encode(encoding)
            start = 0
            offsets = []
            while (offset := data.find(needle, start)) != -1:
                offsets.append(f"0x{offset:X}")
                start = offset + len(needle)
            if offsets:
                hits.append(dict(text=term, encoding=encoding, offsets=offsets))
    return dict(path=str(path), size_bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                header_hex=data[:32].hex(), text_hits=hits,
                schema_validated=False,
                note="Text matches do not establish player IDs or club membership.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    parser.add_argument("--text", action="append", default=[])
    args = parser.parse_args()
    try:
        result = inspect(args.data, args.text)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
