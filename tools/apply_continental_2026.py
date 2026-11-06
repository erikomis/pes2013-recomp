#!/usr/bin/env python3
"""Put the 2026 Libertadores and Sudamericana foreign clubs into an EEDIT copy.

    apply_continental_2026.py SRC DST --plan plan.json --squads squad_references.json
                              [--competitions pes13_competitions.txt] [--mapping out.json]

The game's own continental clubs (team IDs above 16000) take their squads from
the game's database, not from the EDIT save, so their players cannot be changed.
Each foreign club therefore goes into a club slot the save does hold a squad for:
its own slot where the save has one, else a generic or unused one. For each club
in plan.json this writes:

- the name in all 20 language fields and the abbreviation (set_team_names.py);
- the squad: names, shirt names and numbers of the 2026 players, in the slot's
  existing player records (goalkeepers first, then defenders, midfielders and
  forwards; the first eleven are the starters). A record that another squad
  also uses (a national team) is left alone. Attributes, positions and faces stay
  the old player's.

and then the league tables (set_leagues.py, "leagues" in the plan) and the
competition lists for the port (port/pes_leagues.cpp, "competitions").

plan.json:
  {"clubs": [{"name": "...", "abbr": "ABC", "slot": 2483, "squad": "<squad name or club_key>"}],
   "leagues": {"6": [team ids]},
   "competitions": {"27": [team ids]}}
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
import set_team_names  # noqa: E402

ORDER = {"Goalkeeper": 0, "Defender": 1, "Midfielder": 2, "Forward": 3}
NAME_AT, NAME_SIZE = 50, 46
SHIRT_AT, SHIRT_SIZE = 96, 18


def fit(text, size):
    raw = text.encode("utf-8")
    while len(raw) >= size:
        text = text[:-1]
        raw = text.encode("utf-8")
    return raw + bytes(size - len(raw))


def names_for(display):
    parts = [p for p in display.replace(".", ". ").split() if p]
    if not parts:
        return None
    upper = [unicodedata.normalize("NFC", p).upper() for p in parts]
    if len(upper) == 1:
        return upper[0], upper[0]
    surname = upper[-1]
    if len(upper) >= 3 and upper[-2] in ("DE", "DA", "DOS", "DEL", "LA", "DI", "VAN"):
        surname = upper[-2] + " " + upper[-1]
    return f"{upper[0][0]}. {surname}", surname


def pick(athletes, slots):
    """At most `slots` players: starters GK, 4 D, 4 M, 2 F, then the rest by role."""
    by = {0: [], 1: [], 2: [], 3: []}
    for a in athletes:
        by[ORDER.get(a.get("position"), 2)].append(a)
    for v in by.values():
        v.sort(key=lambda a: int(a["shirt_number"]) if str(a.get("shirt_number", "")).isdigit() else 99)
    first = by[0][:1] + by[1][:4] + by[2][:4] + by[3][:2]
    rest = by[0][1:3] + by[1][4:] + by[2][4:] + by[3][2:] + by[0][3:]
    return (first + rest)[:slots]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--squads", required=True)
    ap.add_argument("--competitions")
    ap.add_argument("--mapping")
    a = ap.parse_args()
    if Path(a.src).resolve() == Path(a.dst).resolve():
        sys.exit("DST must be a different file")
    plan = json.loads(Path(a.plan).read_text(encoding="utf-8"))
    squads = {}
    for c in json.loads(Path(a.squads).read_text(encoding="utf-8"))["clubs"]:
        squads.setdefault(c["club_key"], c)
        squads.setdefault(c["name"], c)

    data = Path(a.src).read_bytes()
    names = {str(c["slot"]): {"name": c["name"], "abbr": c["abbr"]} for c in plan["clubs"]}
    data = set_team_names.set_names(data, names)

    dec = edit.decode(data)
    players = {p["id"]: p for p in dec["players"]}
    rosters = {r["team_id"]: r for r in dec["rosters"]}
    uses = {}
    for r in dec["rosters"]:
        for m in r["members"]:
            uses[m["player_id"]] = uses.get(m["player_id"], 0) + 1
    out = bytearray(data)
    report = []
    mapping = []
    for c in plan["clubs"]:
        squad = squads.get(c["squad"])
        r = rosters.get(c["slot"])
        if not squad or not r:
            raise ValueError(f"{c['name']}: no squad '{c['squad']}' or no roster for slot {c['slot']}")
        free = [i for i, m in enumerate(r["members"]) if uses.get(m["player_id"], 0) == 1]
        chosen = pick(squad["athletes"], len(free))
        written = 0
        for i, athlete in zip(free, chosen):
            nm = names_for(athlete["display_name"] or athlete["name"])
            if not nm:
                continue
            member = r["members"][i]
            p = players[member["player_id"]]
            out[p["offset"] + NAME_AT:p["offset"] + NAME_AT + NAME_SIZE] = fit(nm[0], NAME_SIZE)
            out[p["offset"] + SHIRT_AT:p["offset"] + SHIRT_AT + SHIRT_SIZE] = fit(nm[1], SHIRT_SIZE)
            num = int(athlete["shirt_number"]) if str(athlete.get("shirt_number", "")).isdigit() else 0
            if 1 <= num <= 99:
                out[r["offset"] + 132 + member["slot"]] = num
            written += 1
            mapping.append({"player_id": member["player_id"], "slot": c["slot"], "squad": c["squad"],
                            "athlete": {k: athlete.get(k) for k in ("name", "display_name", "espn_id",
                                                                   "birth_date", "position", "shirt_number")}})
        report.append((c["name"], c["slot"], written, len(r["members"]), len(squad["athletes"])))
    struct.pack_into(">I", out, 8, edit.crc32(out))
    data = bytes(out)
    edit.decode(data)

    if plan.get("leagues"):
        wanted = {int(k): [int(t) for t in v] for k, v in plan["leagues"].items()}
        data, _, _ = set_leagues.set_leagues(data, wanted, set_leagues.B20)
    Path(a.dst).write_bytes(data)

    if a.competitions and plan.get("competitions"):
        lines = ["# Competition club lists for port/pes_leagues.cpp: <competition> <team id>..."]
        for k, v in plan["competitions"].items():
            lines.append(f"{k} " + " ".join(str(t) for t in v))
        Path(a.competitions).write_text("\n".join(lines) + "\n", encoding="utf-8")

    if a.mapping:
        Path(a.mapping).write_text(json.dumps(mapping, ensure_ascii=False, indent=1), encoding="utf-8")

    for name, slot, written, members, total in report:
        print(f"{slot:5d} {name:28s} {written:2d} players named of {members} records ({total} in the 2026 squad)")
    print(f"-> {a.dst}")


if __name__ == "__main__":
    main()
