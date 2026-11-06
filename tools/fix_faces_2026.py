#!/usr/bin/env python3
"""Take the wrong faces off renamed players, in an EEDIT copy.

    fix_faces_2026.py ORIGINAL SRC DST [--own own_faces.json] [--manifest faces.json]

The 2026 squads were written into existing player records (names, shirt names,
numbers), so each new player still wore the face of the record's old owner:
Alan Franco with Ronaldinho's face, Ziyech with Seedorf's. In a player record
(tools/pes2013_edit.py, 228 bytes):

- bytes 164..191 hold the face and the hair. Copying them from another record
  gives that record's face and hair, and nothing else changes: position,
  abilities and build stay (checked in Edit > Players > Face).
- bytes 114..115 repeat the low 16 bits of the player ID.

For every player whose name differs from ORIGINAL (the Option File before any
2026 change), this writes:

- if the player's name is in --own (a JSON list of names checked by hand to be
  the same person as the one record of that name in ORIGINAL): that record's
  face, so the player gets their own face, when only one 2026 player has that
  name (three are called LUIZ GUSTAVO). A name alone is not enough: "J.
  GARCÍA" or "JOÃO VICTOR" are different people. Players with a full name that
  ORIGINAL holds once are listed in the manifest as candidates for --own;
- otherwise a face of a fictional player from the generic clubs of ORIGINAL
  (2470..2501, 2514, 2515), chosen from the player's name, different for each
  player of a squad where the pool allows it.

The CRC is recomputed, every byte outside those fields is checked unchanged and
the result is decoded again. SRC and ORIGINAL are not modified.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import unicodedata

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pes2013_edit as edit  # noqa: E402

FACE = slice(164, 192)
GENERIC_TEAMS = list(range(2470, 2502)) + [2514, 2515]


def key(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().upper()
    return " ".join(re.sub(r"[^A-Z ]", " ", s).split())


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("original")
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--own")
    ap.add_argument("--manifest")
    a = ap.parse_args()
    if Path(a.src).resolve() == Path(a.dst).resolve():
        sys.exit("DST must be a different file")
    od = Path(a.original).read_bytes()
    data = Path(a.src).read_bytes()
    orig, cur = edit.decode(od), edit.decode(data)
    oplayers = {p["id"]: p for p in orig["players"]}
    orosters = {r["team_id"]: r for r in orig["rosters"]}

    pool = []
    for tid in GENERIC_TEAMS:
        for m in orosters.get(tid, {"members": []})["members"]:
            p = oplayers[m["player_id"]]
            pool.append((p["id"], od[p["offset"] + FACE.start:p["offset"] + FACE.stop]))
    if len(pool) < 100:
        raise SystemExit(f"only {len(pool)} fictional faces in ORIGINAL; is it the stock Option File?")

    byname = collections.defaultdict(list)
    for p in orig["players"]:
        byname[key(p["name"])].append(p["id"])

    own_names = {key(n) for n in json.loads(Path(a.own).read_text(encoding="utf-8"))} if a.own else set()
    renamed = collections.Counter(key(p["name"]) for p in cur["players"]
                                  if p["id"] in oplayers and oplayers[p["id"]]["name"] != p["name"])
    team_of = {}
    for r in cur["rosters"]:
        for m in r["members"]:
            team_of.setdefault(m["player_id"], r["team_id"])

    out = bytearray(data)
    allowed = bytearray(len(data))
    allowed[8:12] = b"\1" * 4
    used = collections.defaultdict(set)
    own, candidates, generic = [], [], 0
    for p in cur["players"]:
        o = oplayers.get(p["id"])
        if not o or o["name"] == p["name"]:
            continue
        at = p["offset"]
        k = key(p["name"])
        cands = [i for i in byname.get(k, []) if i != p["id"]]
        full = len(k.split()) >= 2 and not re.match(r"^[A-Z] ", k)
        if full and len(cands) == 1 and k not in own_names:
            candidates.append({"player": p["id"], "name": p["name"], "record": cands[0]})
        if k in own_names and len(cands) == 1 and renamed[k] == 1:
            src = oplayers[cands[0]]
            face = od[src["offset"] + FACE.start:src["offset"] + FACE.stop]
            own.append({"player": p["id"], "name": p["name"], "face_of": src["id"]})
        else:
            team = team_of.get(p["id"])
            h = int.from_bytes(hashlib.sha256(p["name"].encode()).digest()[:8], "big")
            for step in range(len(pool)):
                fid, face = pool[(h + step) % len(pool)]
                if fid not in used[team]:
                    break
            used[team].add(fid)
            generic += 1
        out[at + FACE.start:at + FACE.stop] = face
        allowed[at + FACE.start:at + FACE.stop] = b"\1" * (FACE.stop - FACE.start)

    struct.pack_into(">I", out, 8, edit.crc32(out))
    if any(x != y and not allowed[i] for i, (x, y) in enumerate(zip(data, out))):
        raise SystemExit("a byte outside the face fields changed")
    after = edit.decode(bytes(out))
    if [(p["id"], p["name"]) for p in after["players"]] != [(p["id"], p["name"]) for p in cur["players"]]:
        raise SystemExit("players changed")
    Path(a.dst).write_bytes(out)
    if a.manifest:
        Path(a.manifest).write_text(json.dumps(
            {"own_face": own, "generic_faces": generic, "pool": len(pool),
             "own_candidates": candidates},
            ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(own)} players with their own face, {generic} with a fictional face "
          f"(pool of {len(pool)}) -> {a.dst}")
    missing = own_names - {key(x["name"]) for x in own}
    if missing:
        print("in --own but not one record in ORIGINAL or not a renamed player:", sorted(missing))
    for x in own:
        print(f"  {x['name']}: face of record {x['face_of']}")


if __name__ == "__main__":
    main()
