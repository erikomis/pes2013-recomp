#!/usr/bin/env python3
"""Add the in-match face keys to a face pack built by build_face_pack.py.

    add_match_faces.py PACK --edit-dump DIR --capture DIR --clubs serie_a.json --eedit EEDIT
                       --match DUMP_DIR[:FIRST_FRAME] [--match ...] [--max-d 150] [--ratio 2.5]

In Edit > Players a player's face is a 256x512 DXT1 texture, and the pack keys
come from there (build_face_pack.py). In a match the game builds each starter's
face texture again at load time, and for most players the result differs a
little from the Edit one (a few levels of colour here and there), so it has
another key and the pack does not reach it.

This pairs them by image: every 256x512 DXT1 texture a match dump wrote after
FIRST_FRAME is compared with every face texture of the Edit capture dump (the
face area, brightness-normalised, 32x64 samples, mean squared difference). A
match texture takes the Edit face whose difference is at most --max-d and at
most 1/--ratio of the next best one; when that Edit key is in the pack, the
pack's image is copied under the match key ("<match key>_<name>-match.png").
A match key paired with the Edit faces of two different players over the runs is
dropped (a face and its alias keys are one player).
Pairs from earlier runs (pack.json "match_faces") are kept, so runs can be
added one at a time.
pack.json gets a "match_faces" list with the distances.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pes2013_edit as edit  # noqa: E402
from make_hd_pitch import read_png  # noqa: E402


def sample(path, w_=32, h_=64):
    w, h, p = read_png(path)
    out = []
    for y in range(h_):
        sy = int(h * (0.15 + 0.7 * y / h_))
        for x in range(w_):
            sx = int(w * (0.2 + 0.6 * x / w_))
            q = (sy * w + sx) * 3
            out.append(p[q] + p[q + 1] + p[q + 2])
    m = sum(out) / len(out)
    return [v - m for v in out]


def diff(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) / len(a)


def faces_in(dump, first=0):
    keys = []
    for line in (Path(dump) / "textures.txt").read_text().splitlines():
        p = line.split()
        if len(p) > 3 and p[1] == "256x512" and p[2] == "DXT1" and int(p[-1]) >= first:
            if (Path(dump) / f"{p[0]}.png").exists():
                keys.append(p[0])
    return keys


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("pack")
    ap.add_argument("--edit-dump", required=True)
    ap.add_argument("--capture", required=True)
    ap.add_argument("--clubs", required=True)
    ap.add_argument("--eedit", required=True)
    ap.add_argument("--match", required=True, action="append")
    ap.add_argument("--max-d", type=float, default=150)
    ap.add_argument("--ratio", type=float, default=2.5)
    a = ap.parse_args()
    pack = Path(a.pack)
    meta = json.loads((pack / "pack.json").read_text(encoding="utf-8"))
    by_edit = {f["key"]: f for f in meta["faces"]}
    # the other Edit keys of a face (add_face_aliases.py) point at the same face
    by_pid = {f["player_id"]: f for f in meta["faces"]}
    for x in meta.get("aliases", []):
        if x["player_id"] in by_pid:
            by_edit.setdefault(x["key"], by_pid[x["player_id"]])
    dec = edit.decode(Path(a.eedit).read_bytes())
    rosters = {r["team_id"]: [m["player_id"] for m in r["members"]] for r in dec["rosters"]}
    names = {p["id"]: p["name"] for p in dec["players"]}
    owner = {}
    for c in json.loads(Path(a.clubs).read_text(encoding="utf-8")):
        f = Path(a.capture) / f"rows_{c['index']}.json"
        if f.exists():
            for r in json.loads(f.read_text(encoding="utf-8"))["rows"]:
                if len(r["textures"]) == 1 and r["row"] < len(rosters.get(c["team"], [])):
                    owner.setdefault(r["textures"][0][0], set()).add(rosters[c["team"]][r["row"]])
    ref = {k: sample(Path(a.edit_dump) / f"{k}.png") for k in set(faces_in(a.edit_dump))}
    # pairs from earlier runs stay, unless a new run pairs that match key elsewhere
    found = {m["match_key"]: {m["edit_key"]} for m in meta.get("match_faces", [])}
    rows = list(meta.get("match_pairing", []))
    for r in rows:                     # every pairing kept from earlier runs counts again
        if r.get("accepted"):
            found.setdefault(r["match"], set()).add(r["edit"])
    for spec in a.match:
        dump, _, first = spec.partition(":")
        for k in faces_in(dump, int(first or 0)):
            s = sample(Path(dump) / f"{k}.png")
            ranked = sorted((diff(s, v), ek) for ek, v in ref.items())
            d0, k0 = ranked[0]
            # the runner-up is the best face that is a different image (the Edit dump
            # can hold the same face twice under two keys, a few levels apart)
            d1 = next((d for d, ek in ranked[1:] if diff(ref[k0], ref[ek]) > 20), float("inf"))
            ok = d0 <= a.max_d and d1 >= a.ratio * d0
            who = sorted(names[p] for p in owner.get(k0, ()))
            rows.append({"match": k, "edit": k0, "d0": round(d0, 1), "d1": round(d1, 1), "player": who,
                         "accepted": ok, "in_pack": k0 in by_edit, "dump": dump})
            if ok:
                found.setdefault(k, set()).add(k0)
    added = []
    for k, eks in sorted(found.items()):
        # several Edit keys are fine when they are one player's (a face and its aliases)
        owners = {by_edit[e]["player_id"] if e in by_edit else e for e in eks}
        if len(owners) != 1 or k in eks:
            continue
        ek = next((e for e in sorted(eks) if e in by_edit), None)
        if ek is None:
            continue
        src = by_edit[ek]
        out = pack / f"{k}_{Path(src['file']).stem.split('_', 1)[1]}-match.png"
        shutil.copyfile(pack / src["file"], out)
        added.append({"match_key": k, "edit_key": ek, "player_id": src["player_id"], "name": src["name"],
                      "file": out.name})
    keep = {a["file"] for a in added}
    for f in pack.glob("*-match.png"):
        if f.name not in keep:
            f.unlink()
    meta["match_faces"] = added
    meta["match_pairing"] = rows
    (pack / "pack.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    acc = sum(1 for r in rows if r["accepted"])
    print(f"{len(rows)} match faces seen, {acc} paired with an Edit face, {len(added)} added to {pack}")
    for r in rows:
        if not r["accepted"]:
            print(f"  unpaired {r['match']} best {r['edit']} d {r['d0']} / {r['d1']} {r['player']}")


if __name__ == "__main__":
    main()
