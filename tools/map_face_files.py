#!/usr/bin/env python3
"""Match downloaded PES 2013 PC face files to the 2026 players of a profile.

    map_face_files.py EEDIT --manifest manifest.json --squads candidate_squads.json
                      --sources DIR --out face_files.json

DIR holds the face packs: TM Games' per-club ZIPs (<Club>2026.zip), its mixed
facepack_tm_games.zip and the PESfooty Flamengo RARs extracted under
flamengo-pesfooty/extracted/. Each "<name>_face.bin" is matched by name: every
word of the file name must be a word of the player's 2026 full name or of his
name in the save, and exactly one player of the club (of all 40 clubs for the
mixed pack) may match. Anything else is listed as unmatched, not guessed.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import unicodedata
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pes2013_edit as edit  # noqa: E402

CLUB = {"Athletico": "Athletico", "Atletico": "Atlético Mineiro", "Bahia": "Bahia",
        "Botafogo": "Botafogo  - RJ", "Bragantino": "Bragantino", "Chapecoense": "Chapecoense",
        "Corinthians": "Corinthians", "Coritiba": "Coritiba", "Cruzeiro": "Cruzeiro",
        "Flamengo": "Flamengo", "Fluminense": "Fluminense", "Grêmio": "Grêmio",
        "Mirassol": "Mirassol", "Palmeiras": "Palmeiras", "Remo": "Remo", "Santos": "Santos",
        "SãoPaulo": "São Paulo", "Vitória": "Vitória", "Vitória2": "Vitória"}


def key(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z ]", " ", s).split())


def member_name(info):
    """zipfile decodes non-UTF-8 names as cp437; these packs store UTF-8 or
    cp850 (Windows, Portuguese) names, so the bytes are decoded again."""
    raw = info.filename
    if not info.flag_bits & 0x800:
        b = raw.encode("cp437")
        for enc in ("utf-8", "cp850"):
            try:
                return b.decode(enc)
            except UnicodeError:
                continue
    return raw


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("eedit")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--sources", required=True)
    ap.add_argument("--squads", required=True, help="the 2026 squads with full names (CBF ids)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    dec = edit.decode(Path(a.eedit).read_bytes())
    players = {p["id"]: p for p in dec["players"]}
    man = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    full = {}
    for c in json.loads(Path(a.squads).read_text(encoding="utf-8"))["clubs"]:
        for ath in c["athletes"]:
            if ath.get("cbf_id"):
                full[ath["cbf_id"]] = " ".join([ath.get("name") or "", ath.get("display_name") or ""])
    clubs = {}
    for ch in man["changes"]:
        rows = []
        for asg in ch["assignments"]:
            words = (set(key(asg.get("reference_name")).split()) | set(key(players[asg["pes_id"]]["name"]).split())
                     | set(key(full.get(asg["cbf_id"])).split()))
            rows.append({"player_id": asg["pes_id"], "name": players[asg["pes_id"]]["name"], "words": words})
        clubs[ch["club"]] = rows

    def find(stem, club_names):
        w = [t for t in key(stem).split() if len(t) > 1]
        if not w:
            return []
        hits = []
        for cn in club_names:
            for r in clubs[cn]:
                if all(t in r["words"] for t in w):
                    hits.append((cn, r))
        return hits

    files = []
    src = Path(a.sources)
    for z in sorted(src.glob("*.zip")):
        prefix = z.stem.replace("2026", "")
        if z.name == "facepack_tm_games.zip":
            scope = list(clubs)
        elif prefix in CLUB:
            scope = [c for c in clubs if c.startswith(CLUB[prefix])]
        else:
            continue
        with zipfile.ZipFile(z) as zf:
            for info in zf.infolist():
                n = member_name(info)
                if n.lower().endswith("_face.bin"):
                    files.append((z.name, info.filename, n[:-9], scope))
    for f in sorted((src / "flamengo-pesfooty" / "extracted").glob("*/*_face.bin")):
        files.append((str(f.relative_to(src)), None, f.name[:-9], [c for c in clubs if c.startswith("Flamengo")]))
        files[-1] = (files[-1][0], None, f.parent.name.replace("-face-pes-2013", "").replace("-", " "), files[-1][3])

    out, unmatched, seen = [], [], set()
    for archive, member, stem, scope in files:
        hits = find(stem, scope)
        if len(hits) == 1 and hits[0][1]["player_id"] not in seen:
            cn, r = hits[0]
            seen.add(r["player_id"])
            out.append({"player_id": r["player_id"], "club": cn, "name": r["name"],
                        "archive": archive, "member": member, "file_name": stem})
        else:
            unmatched.append({"archive": archive, "file_name": stem,
                              "candidates": [h[1]["name"] for h in hits]})
    Path(a.out).write_text(json.dumps({"faces": out, "unmatched": unmatched}, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    print(f"{len(out)} faces matched to a 2026 player, {len(unmatched)} not -> {a.out}")


if __name__ == "__main__":
    main()
