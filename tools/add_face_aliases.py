#!/usr/bin/env python3
"""Add the other Edit-mode keys a pack face can have, from a second capture run.

    add_face_aliases.py PACK --base CAPTURE_DIR --other CAPTURE_DIR [--other ...]
                        --clubs serie_a.json --eedit EEDIT

A player's face texture in Edit > Players is not always the same bytes: in two
capture runs about one row in ten got a different key, with the save unchanged.
A pack only knows the key it was built with (build_face_pack.py, from --base),
so that face then shows in some runs and not in others.

For each club this lines up a row of an --other run with the --base run by its
neighbours: the nearest rows above and below whose keys both runs saw must be
the same distance apart in both (a lost or doubled button press shifts the
rows, and then nothing in that stretch is used). A row that lines up, whose key
differs from the --base key and belongs to no other row of any run, and whose
player has a face in the pack, gets that key as an alias: the pack's image is
copied as "<key>_<name>-alt.png" and listed in pack.json "aliases".
"""
import argparse
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pes2013_edit as edit  # noqa: E402


def rows_of(capdir, idx):
    f = Path(capdir) / f"rows_{idx}.json"
    if not f.exists():
        return None
    return [[t[0] for t in r["textures"] if t[1] == "256x512" and t[2] == "DXT1"]
            for r in json.loads(f.read_text(encoding="utf-8"))["rows"]]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("pack")
    ap.add_argument("--base", required=True)
    ap.add_argument("--other", required=True, action="append")
    ap.add_argument("--clubs", required=True)
    ap.add_argument("--eedit", required=True)
    a = ap.parse_args()
    pack = Path(a.pack)
    meta = json.loads((pack / "pack.json").read_text(encoding="utf-8"))
    by_player = {f["player_id"]: f for f in meta["faces"]}
    dec = edit.decode(Path(a.eedit).read_bytes())
    rosters = {r["team_id"]: [m["player_id"] for m in r["members"]] for r in dec["rosters"]}
    clubs = json.loads(Path(a.clubs).read_text(encoding="utf-8"))
    # every key seen anywhere, and at which (club, row): a key at two places is no alias
    seen = {}
    for c in clubs:
        for capdir in [a.base] + a.other:
            rows = rows_of(capdir, c["index"])
            for i, ks in enumerate(rows or []):
                for k in ks:
                    seen.setdefault(k, set()).add((c["index"], i))
    aliases = {x["key"]: x for x in meta.get("aliases", [])}
    for c in clubs:
        base = rows_of(a.base, c["index"])
        if not base:
            continue
        where = {ks[0]: i for i, ks in enumerate(base) if len(ks) == 1}
        members = rosters.get(c["team"], [])
        for capdir in a.other:
            rows = rows_of(capdir, c["index"])
            if not rows:
                continue
            anchors = [(i, where[ks[0]]) for i, ks in enumerate(rows) if len(ks) == 1 and ks[0] in where]
            for i, ks in enumerate(rows):
                if len(ks) != 1 or ks[0] in where:
                    continue
                before = [x for x in anchors if x[0] < i]
                after = [x for x in anchors if x[0] > i]
                if not before or not after:
                    continue
                (j, rj), (l, rl) = before[-1], after[0]
                if rl - rj != l - j:
                    continue
                row = rj + (i - j)
                k = ks[0]
                if len({p for p in seen.get(k, ())}) != 1 or row >= len(members):
                    continue
                face = by_player.get(members[row])
                if not face or k == face["key"] or k in aliases:
                    continue
                out = f"{k}_{Path(face['file']).stem.split('_', 1)[1]}-alt.png"
                shutil.copyfile(pack / face["file"], pack / out)
                aliases[k] = {"key": k, "edit_key": face["key"], "player_id": face["player_id"],
                              "name": face["name"], "club": face["club"], "file": out}
                print(f"{face['club'][:20]:20s} {face['name']:22s} {face['key']} + {k}")
    meta["aliases"] = sorted(aliases.values(), key=lambda x: x["key"])
    (pack / "pack.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(meta['aliases'])} alias keys in {pack}")


if __name__ == "__main__":
    main()
