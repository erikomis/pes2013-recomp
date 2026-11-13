#!/usr/bin/env python3
"""Put Copa do Brasil 2026 clubs that are not in the save into chosen team slots, in an EEDIT copy.

    add_cup_clubs_2026.py ORIGINAL SRC DST --squads domestic_squad_candidates.json
                          --clubs cup_clubs.json --manifest manifest.json --manifest-out out.json

cup_clubs.json lists {"squad": "<name in the squads file>", "team": <team id>,
"name": "PAYSANDU", "abbr": "PAY", "division": "C"} and, for a slot that is in no
league (no club picker shows it), "league": <league index> (set_leagues.py; 9 is
"Outros Times (Europa)", 38 places). For each club:
- the team gets its name in every language and its abbreviation (set_team_names.py);
- two players of one club with the same name get the last surname of their
  registration after it (the shirt shows the surname);
- its squad comes from the CBF match sheets in the squads file (players with the
  most appearances and starts first, as many as the slot's roster holds); each one
  takes one of the slot's existing player records: name, shirt name (no accents),
  shirt number, goalkeepers marked GK, nationality Brazil, and a face from the
  fictional players of the original Option File's generic and Master League teams,
  one no player wears when there is one left (never a famous face). Records the squad does not
  need leave the roster;
- a manifest entry in the 40-club manifest's form is added, with the match-sheet
  evidence, so set_player_stats_2026.py (positions, abilities) and
  fix_lineups_2026.py (the eleven by starts) treat these clubs like the others.

Only names, shirt names, numbers, the roster's player list, faces, nationality
and the GK position bytes change, plus the CRC; the file is decoded again.
"""
import argparse
import json
from pathlib import Path
import struct
import sys
import unicodedata

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pes2013_edit as edit  # noqa: E402
import set_leagues  # noqa: E402
from set_team_names import set_names  # noqa: E402

FACE = (164, 192)
GENERIC = list(range(2470, 2502)) + [2514, 2515] + [140, 141, 142, 2469, 2511, 2512, 2513]  # + Master League


def plain(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def fit(text, size):
    v = text.upper().strip()
    while len(v.encode("utf-8")) >= size:
        v = v[:-1].rstrip()
    return v


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("original")
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--squads", required=True)
    ap.add_argument("--clubs", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--manifest-out", required=True)
    a = ap.parse_args()
    if Path(a.src).resolve() == Path(a.dst).resolve():
        sys.exit("DST must be a different file")
    clubs = json.loads(Path(a.clubs).read_text(encoding="utf-8"))
    data = Path(a.src).read_bytes()
    current = set_leagues.read_leagues(data, set_leagues.B20)
    wanted = {}
    for c in clubs:
        k = c.get("league")
        if k is not None and c["team"] not in current[k]:
            wanted.setdefault(k, list(current[k])).append(c["team"])
    if wanted:
        data, _, _ = set_leagues.set_leagues(data, wanted, set_leagues.B20)
    data = set_names(data,
                     {str(c["team"]): {"name": c["name"], "abbr": c["abbr"]} for c in clubs})
    out = bytearray(data)
    cur = edit.decode(bytes(out))
    players = {p["id"]: p for p in cur["players"]}
    rosters = {r["team_id"]: r for r in cur["rosters"]}

    # fictional faces: the original file's generic teams, not worn by anyone now
    orig = Path(a.original).read_bytes()
    od = edit.decode(orig)
    oplayers = {p["id"]: p for p in od["players"]}
    worn = {bytes(out[p["offset"] + FACE[0]:p["offset"] + FACE[1]]) for p in cur["players"]}
    fresh, reused = [], []
    for r in od["rosters"]:
        if r["team_id"] in GENERIC:
            for m in r["members"]:
                o = oplayers[m["player_id"]]["offset"]
                f = orig[o + FACE[0]:o + FACE[1]]
                if f in fresh or f in reused:
                    continue
                (reused if f in worn else fresh).append(f)
    pool = fresh + reused      # unworn fictional faces first, then fictional ones already worn

    squads = {c["name"]: c for c in json.loads(Path(a.squads).read_text(encoding="utf-8"))["clubs"]}
    man = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    man["changes"] = [ch for ch in man["changes"] if ch["team_id"] not in {c["team"] for c in clubs}]
    for c in clubs:
        sq = squads[c["squad"]]
        roster = rosters[c["team"]]
        ids = [m["player_id"] for m in roster["members"]]
        def weight(x):
            ev = x.get("evidence") or []
            return (len(ev), sum(1 for e in ev if e.get("started")))
        ath = sorted(sq["athletes"], key=weight, reverse=True)
        keepers = [x for x in ath if x.get("goalkeeper")][:3]
        rest = [x for x in ath if not x.get("goalkeeper")]
        ath = (keepers + rest)[:len(ids)]
        if len(pool) < len(ath):
            sys.exit("not enough unused fictional faces")
        off = roster["offset"]
        new_ids = ids[:len(ath)]
        struct.pack_into(">32I", out, off + 4, *(new_ids + [0] * (32 - len(new_ids))))
        out[off + 132:off + 164] = bytes(32)
        assignments = []
        shown = [x["display_name"] or x["name"] for x in ath]
        keyed = [plain(k).upper() for k in shown]
        counts = {k: keyed.count(k) for k in keyed}
        for i, (pid, x) in enumerate(zip(new_ids, ath)):
            o = players[pid]["offset"]
            label = shown[i]
            shirt_label = label
            if counts[keyed[i]] > 1:          # two players of the club with one name: add the surname
                parts = [w for w in (x.get("name") or "").split()
                         if w.lower() not in ("de", "da", "do", "dos", "das", "e", "junior", "júnior", "filho", "neto")]
                if len(parts) >= 2:
                    label, shirt_label = f"{label} {parts[-1].title()}", parts[-1]
            name = fit(label, 46)
            shirt = fit(plain(shirt_label), 18)
            for rel, size, val in ((50, 46, name), (96, 18, shirt)):
                raw = val.encode("utf-8")
                out[o + rel:o + rel + size] = raw + bytes(size - len(raw))
            num = int(x.get("shirt_number") or 0)
            out[off + 132 + i] = num if 0 < num < 100 else 0
            out[o + FACE[0]:o + FACE[1]] = pool.pop(0)
            w = struct.unpack_from(">H", out, o + 216)[0]
            struct.pack_into(">H", out, o + 216, (w & ~(0x1FF << 3)) | (45 << 3))
            if x.get("goalkeeper"):
                out[o + 121] = (out[o + 121] & 0xF0) | 0
                out[o + 122] |= 1
            assignments.append({"pes_id": pid, "cbf_id": x.get("cbf_id"), "reference_name": x["display_name"],
                                "previous_name": players[pid]["name"], "name": name, "shirt_name": shirt,
                                "shirt_number": num, "evidence": x.get("evidence") or []})
        man["changes"].append({"club": f"{sq['name']}  - {sq['state']}", "team_id": c["team"],
                               "division_reference": c.get("division", "C"), "source": "copa_do_brasil_2026",
                               "duplicate_shirt_numbers": [], "assignments": assignments})
        print(f"{c['name']:12s} team {c['team']}: {len(ath)} players "
              f"({sum(1 for x in ath if x.get('goalkeeper'))} GK), {len(ids) - len(ath)} records left the roster")
    struct.pack_into(">I", out, 8, edit.crc32(out))
    back = edit.decode(bytes(out))
    br = {r["team_id"]: r for r in back["rosters"]}
    for ch in man["changes"][-len(clubs):]:
        got = [m["player_id"] for m in br[ch["team_id"]]["members"]]
        if got != [x["pes_id"] for x in ch["assignments"]]:
            sys.exit(f"team {ch['team_id']}: roster reads back differently")
    Path(a.dst).write_bytes(out)
    Path(a.manifest_out).write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {a.dst}, manifest {a.manifest_out}")


if __name__ == "__main__":
    main()
