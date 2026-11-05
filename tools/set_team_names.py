#!/usr/bin/env python3
"""Give teams one name in every language and their abbreviation, in an EEDIT copy.

    set_team_names.py SRC DST --map names.json

A team record (tools/pes2013_edit.py, 1460 bytes) holds 20 name fields of 72 bytes,
one per game language, then the 3-letter abbreviation at +1440. A name written into
the first field only shows in one language: the others, and the abbreviation, keep
the old team's. names.json is {"<team id>": {"name": "...", "abbr": "ABC"}}.

Only those fields change. The CRC is recomputed, the result is decoded again with
pes2013_edit.decode, and every other byte is checked unchanged. SRC is not modified.
"""
import argparse
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pes2013_edit as edit  # noqa: E402

NAME_FIELDS = 20
NAME_SIZE = 72
ABBR_AT = 1440
ABBR_SIZE = 4


def set_names(data, names):
    before = edit.decode(data)
    teams = {t["id"]: t for t in before["teams"]}
    out, allowed = bytearray(data), bytearray(len(data))
    allowed[8:12] = b"\1" * 4
    for key, want in names.items():
        tid = int(key)
        if tid not in teams:
            raise ValueError(f"team {tid} is not in this file")
        name, abbr = want["name"].strip(), want["abbr"].strip().upper()
        raw, rabbr = name.encode("utf-8"), abbr.encode("ascii")
        if not name or len(raw) >= NAME_SIZE:
            raise ValueError(f"team {tid}: name must be 1..{NAME_SIZE - 1} bytes")
        if not 1 <= len(rabbr) <= ABBR_SIZE - 1:
            raise ValueError(f"team {tid}: abbreviation must be 1..3 letters")
        base = teams[tid]["offset"]
        for f in range(NAME_FIELDS):
            at = base + f * NAME_SIZE
            out[at:at + NAME_SIZE] = raw + bytes(NAME_SIZE - len(raw))
            allowed[at:at + NAME_SIZE] = b"\1" * NAME_SIZE
        at = base + ABBR_AT
        out[at:at + ABBR_SIZE] = rabbr + bytes(ABBR_SIZE - len(rabbr))
        allowed[at:at + ABBR_SIZE] = b"\1" * ABBR_SIZE
    struct.pack_into(">I", out, 8, edit.crc32(out))
    if any(a != b and not allowed[i] for i, (a, b) in enumerate(zip(data, out))):
        raise ValueError("a byte outside the name fields changed")
    after = edit.decode(bytes(out))
    got = {t["id"]: t["name"] for t in after["teams"]}
    for key, want in names.items():
        if got[int(key)] != want["name"].strip():
            raise ValueError(f"team {key} reads back as {got[int(key)]!r}")
    if [(p["id"], p["name"]) for p in after["players"]] != [(p["id"], p["name"]) for p in before["players"]]:
        raise ValueError("players changed")
    return bytes(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--map", required=True)
    a = ap.parse_args()
    if Path(a.src).resolve() == Path(a.dst).resolve():
        sys.exit("DST must be a different file")
    names = json.loads(Path(a.map).read_text(encoding="utf-8"))
    out = set_names(Path(a.src).read_bytes(), names)
    Path(a.dst).write_bytes(out)
    print(f"{len(names)} teams renamed in all {NAME_FIELDS} languages -> {a.dst}")


if __name__ == "__main__":
    main()
