#!/usr/bin/env python3
"""Name the 20 edited-stadium slots of an EEDIT copy.

    set_stadium_names.py SRC DST --map stadiums.json

PES 2013's stadium creator keeps 20 stadiums: numbers 15..34 in Edit >
Stadium > Edit stadiums, after the game's 14. Their parts are the BLUS31029EST_*
saves (walls, fences, roofs, far side, thumbnail). In the EDIT save each one is
a 372-byte entry from 0x51FACE: the name twice (+0 and +97, 97 bytes each,
UTF-8, zero padded), then its settings. stadiums.json is {"<slot 0..19>":
"name"}; slots not named keep theirs. Only the two name fields of those slots
and the CRC change; the file is decoded again.
"""
import argparse
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pes2013_edit as edit  # noqa: E402

TABLE = 0x51FACE
STRIDE = 372
SLOTS = 20
FIELD = 97
NAME_MAX = 60


def read_names(data):
    return [data[TABLE + i * STRIDE:TABLE + i * STRIDE + FIELD].split(b"\0")[0].decode("utf-8", "replace")
            for i in range(SLOTS)]


def set_names(data, names):
    edit.decode(data)
    out = bytearray(data)
    for k, name in names.items():
        slot = int(k)
        if not 0 <= slot < SLOTS:
            raise ValueError(f"slot {slot} is not 0..{SLOTS - 1}")
        raw = name.strip().encode("utf-8")
        if not raw or len(raw) > NAME_MAX:
            raise ValueError(f"slot {slot}: name must be 1..{NAME_MAX} bytes")
        at = TABLE + slot * STRIDE
        if out[at:at + FIELD] != out[at + FIELD:at + 2 * FIELD]:
            raise ValueError(f"slot {slot}: the two name fields differ; layout differs")
        for f in (at, at + FIELD):
            out[f:f + FIELD] = raw + bytes(FIELD - len(raw))
    struct.pack_into(">I", out, 8, edit.crc32(out))
    names_at = {TABLE + s * STRIDE + j for s in range(SLOTS) for j in range(2 * FIELD)}
    if any(a != b and not (i in names_at or 8 <= i < 12) for i, (a, b) in enumerate(zip(data, out))):
        raise ValueError("a byte outside the stadium names changed")
    edit.decode(bytes(out))
    return bytes(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--map", required=True)
    a = ap.parse_args()
    if Path(a.src).resolve() == Path(a.dst).resolve():
        sys.exit("DST must be a different file")
    data = Path(a.src).read_bytes()
    names = json.loads(Path(a.map).read_text(encoding="utf-8"))
    before = read_names(data)
    out = set_names(data, names)
    Path(a.dst).write_bytes(out)
    for i, (old, new) in enumerate(zip(before, read_names(out))):
        mark = "" if old == new else f"   (was {old or '-'})"
        print(f"{i:2d} {new or '-'}{mark}")
    print(f"-> {a.dst}")


if __name__ == "__main__":
    main()
