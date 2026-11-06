#!/usr/bin/env python3
"""Give chosen players a face no other player in the file wears, in an EEDIT copy.

    assign_unique_faces.py ORIGINAL SRC DST --players face_files.json

A texture pack replaces a texture by its content, so a downloaded face can only
be put on one player if that player's face texture is his alone. The face and
hair are bytes 164..191 of the player record (fix_faces_2026.py). A built face
(byte 167 bit 0 clear) is not enough: players with different built faces were
seen sharing one face texture. The faces given here are special faces (byte 167
bit 0 set, the real players' faces with their own texture) that the stock
Option File (ORIGINAL) had on records since renamed, and that no record of SRC
uses; each goes to one player of face_files.json ("faces": [{"player_id": ...}]).
The head shape and hair are that old player's; the face texture comes from the
pack.
"""
import argparse
import collections
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pes2013_edit as edit  # noqa: E402

FACE = slice(164, 192)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("original")
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--players", required=True)
    a = ap.parse_args()
    if Path(a.src).resolve() == Path(a.dst).resolve():
        sys.exit("DST must be a different file")
    od, data = Path(a.original).read_bytes(), Path(a.src).read_bytes()
    orig, cur = edit.decode(od), edit.decode(data)
    players = {p["id"]: p for p in cur["players"]}
    used = collections.Counter(data[p["offset"] + FACE.start:p["offset"] + FACE.stop] for p in cur["players"])
    free = []
    for p in orig["players"]:
        b = od[p["offset"] + FACE.start:p["offset"] + FACE.stop]
        if not used[b] and (b[3] & 1) and b not in free:
            free.append(b)
    want = [f["player_id"] for f in json.loads(Path(a.players).read_text(encoding="utf-8"))["faces"]]
    if len(want) > len(free):
        raise SystemExit(f"{len(want)} players but only {len(free)} unused faces")
    out = bytearray(data)
    for pid, face in zip(want, free):
        o = players[pid]["offset"]
        out[o + FACE.start:o + FACE.stop] = face
    struct.pack_into(">I", out, 8, edit.crc32(out))
    allowed = {players[pid]["offset"] + i for pid in want for i in range(FACE.start, FACE.stop)}
    if any(x != y and not (i in allowed or 8 <= i < 12) for i, (x, y) in enumerate(zip(data, out))):
        raise SystemExit("a byte outside the face fields changed")
    after = edit.decode(bytes(out))
    check = collections.Counter(bytes(out[p["offset"] + FACE.start:p["offset"] + FACE.stop]) for p in after["players"])
    if any(check[bytes(out[players[pid]["offset"] + FACE.start:players[pid]["offset"] + FACE.stop])] != 1 for pid in want):
        raise SystemExit("a chosen player's face is not unique")
    Path(a.dst).write_bytes(out)
    print(f"{len(want)} players got a face of their own ({len(free)} were free) -> {a.dst}")


if __name__ == "__main__":
    main()
