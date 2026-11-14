#!/usr/bin/env python3
"""Make the commentary call 2026 players by their names, or by none, in an EEDIT copy.

    fix_callnames_2026.py ORIGINAL SRC DST [--report out.json]

Each player record has, at +114, a big-endian u16: the player ID whose recorded
name the commentary says (the player's own ID when he has a recording, another
player's when they share a name, 0xFFFF for none). The 2026 profile renamed about
two thousand records and left that field alone, so the commentary called those
players by the 2013 names.

For every record whose name differs from ORIGINAL's, the field becomes:
- the field of an ORIGINAL player with exactly the same name (accents and case
  ignored), one whose field is his own ID first: that recording says the name;
- else, for a name of two words or more, a recording of its last word (the
  surname: "ANDRE SILVA" is called "Silva"), then of its first word;
- else 0xFFFF: the commentary says no name, which beats a wrong one.
Only bytes +114..115 and the CRC change; the file is decoded again.
"""
import argparse
import json
from pathlib import Path
import struct
import sys
import unicodedata

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pes2013_edit as edit  # noqa: E402

CALL = 114
NONE = 0xFFFF


def plain(s):
    return " ".join(unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper().split())


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("original")
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--report")
    a = ap.parse_args()
    if Path(a.src).resolve() == Path(a.dst).resolve():
        sys.exit("DST must be a different file")
    orig = Path(a.original).read_bytes()
    data = bytearray(Path(a.src).read_bytes())
    od = {p["id"]: p for p in edit.decode(orig)["players"]}
    cur = edit.decode(bytes(data))

    # name -> the best commentary value among ORIGINAL players with that name
    best = {}
    for p in od.values():
        if not p["name"]:
            continue
        v = struct.unpack_from(">H", orig, p["offset"] + CALL)[0]
        if v == NONE:
            continue
        k = plain(p["name"])
        rank = 0 if v == (p["id"] & 0xFFFF) else 1
        if k not in best or rank < best[k][0]:
            best[k] = (rank, v)

    report, named, silent = [], 0, 0
    for p in cur["players"]:
        o = od.get(p["id"])
        if not o or not p["name"] or plain(p["name"]) == plain(o["name"]):
            continue
        k = plain(p["name"])
        hit = best.get(k)
        words = [w for w in k.split() if len(w) > 2 and w not in ("DOS", "DAS", "DE", "DA", "DO", "JUNIOR", "FILHO", "NETO")]
        if not hit and len(words) >= 2:              # a two-word name: the surname, then the first name
            hit = best.get(words[-1]) or best.get(words[0])
        v = hit[1] if hit else NONE
        old = struct.unpack_from(">H", data, p["offset"] + CALL)[0]
        struct.pack_into(">H", data, p["offset"] + CALL, v)
        if v == NONE:
            silent += 1
        else:
            named += 1
        report.append({"id": p["id"], "name": p["name"], "was": o["name"], "old": old, "new": v,
                       "says": od[v]["name"] if v in od else None})
    struct.pack_into(">I", data, 8, edit.crc32(data))
    edit.decode(bytes(data))
    allowed = {pp["offset"] + CALL + i for pp in cur["players"] for i in (0, 1)}
    src = Path(a.src).read_bytes()
    if any(x != y and not (i in allowed or 8 <= i < 12) for i, (x, y) in enumerate(zip(src, data))):
        sys.exit("a byte outside the commentary fields changed")
    Path(a.dst).write_bytes(data)
    if a.report:
        Path(a.report).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(report)} renamed players: {named} called by a recording of their name, "
          f"{silent} with no name (no recording of it) -> {a.dst}")


if __name__ == "__main__":
    main()
