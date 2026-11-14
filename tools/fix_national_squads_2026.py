#!/usr/bin/env python3
"""Make national squads out of club players, in an EEDIT copy.

    fix_national_squads_2026.py SRC DST [--report out.json]

The Master League keeps one entry for every player of its world (clubs, the
competitions' extra clubs and the national teams) and its save holds 8000 of
them (port/pes_ml.cpp). The 2026 profile's Libertadores brings 31 clubs of the
save with full squads, and the world comes to 8355: a Master League can be
created but not loaded. Most national squads still hold players of 2013 that no
club has any more (1555 of them), and each counts as one more entry.

National squads use player records of their own, apart from the club ones (also in
the stock file). Each squad player no club has is replaced, in his roster slot, by
the club record of the same player when there is exactly one (same name and
nationality); otherwise by a club player of the same
nationality (+216, 9 bits from bit 3) and the same registered position (+121 & 15),
or failing that the same line (goalkeeper or not), who is not in that squad yet.
Clubs are tried by league (England, Spain, Italy, France, Netherlands, Portugal,
Série A, other European clubs, Série B, the South American league), then clubs
in no league; within a club, in roster order. A player goes to one national
squad only. A player with no candidate stays. Classic teams (900-910) and the
Master League's own teams are left alone. The roster slots, shirt numbers and
line-ups do not change; only the rosters' player IDs and the CRC do.
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

SPECIAL = {140, 141, 142, 1416, 2469, 2511, 2512, 2513, 1709, 1372, 1373, 1375, 1377}
CLASSIC = set(range(900, 911))
LEAGUE_ORDER = [0, 4, 2, 1, 3, 5, 8, 9, 7, 6]


def plain(name):
    return unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().upper().strip()


def is_national(team_id):
    """National teams: IDs below 100, 1000-1199, and Serbia and Montenegro (1550, 1551)."""
    return 0 < team_id < 100 or 1000 <= team_id < 1200 or team_id in (1550, 1551)


def nationality(data, p):
    return (struct.unpack_from(">H", data, p["offset"] + 216)[0] >> 3) & 0x1FF


def position(data, p):
    return data[p["offset"] + 121] & 0x0F


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--report")
    a = ap.parse_args()
    if Path(a.src).resolve() == Path(a.dst).resolve():
        sys.exit("DST must be a different file")
    data = bytearray(Path(a.src).read_bytes())
    dec = edit.decode(bytes(data))
    players = {p["id"]: p for p in dec["players"]}
    names = {t["id"]: t["name"] for t in dec["teams"]}
    rosters = {r["team_id"]: r for r in dec["rosters"]}
    ids = {t: [m["player_id"] for m in r["members"]] for t, r in rosters.items()}
    leagues = set_leagues.read_leagues(bytes(data), set_leagues.B20)
    in_league = {t for v in leagues.values() for t in v}
    national = [t for t in rosters if is_national(t)]
    clubs = [t for k in LEAGUE_ORDER for t in leagues[k]]
    clubs += [t for t in sorted(rosters) if t not in in_league and t not in national
              and t not in SPECIAL and t not in CLASSIC and t not in clubs]
    club_players = {p for t in clubs for p in ids[t]}

    # club players by nationality, best clubs first
    by_nat = {}
    for t in clubs:
        for p in ids[t]:
            lst = by_nat.setdefault(nationality(data, players[p]), [])
            if p not in lst:
                lst.append(p)
    taken = {p for t in national for p in ids[t] if p in club_players}   # already called up
    report, replaced, kept = [], 0, 0
    # first pass: the same player's club record (same name and nationality, one only)
    by_name = {}
    for q in club_players:
        by_name.setdefault((plain(players[q]["name"]), nationality(data, players[q])), []).append(q)
    squads = {t: list(ids[t]) for t in national}
    for t in national:
        for i, p in enumerate(squads[t]):
            if p in club_players:
                continue
            c = [q for q in by_name.get((plain(players[p]["name"]), nationality(data, players[p])), [])
                 if q not in taken and q not in squads[t]]
            if len(c) == 1:
                squads[t][i] = c[0]
                taken.add(c[0])
                replaced += 1
                report.append({"team": names.get(t), "slot": i, "out": players[p]["name"],
                               "in": players[c[0]]["name"], "by": "name"})
    # second pass: a club player of the same nationality and position
    for t in national:
        squad = squads[t]
        nats = [nationality(data, players[p]) for p in squad]
        nat = max(set(nats), key=nats.count) if nats else None
        new = list(squad)
        for i, p in enumerate(squad):
            if p in club_players:
                continue
            want = position(data, players[p])
            pool = [q for q in by_nat.get(nat, []) if q not in taken and q not in new]
            pick = next((q for q in pool if position(data, players[q]) == want), None)
            if pick is None:
                pick = next((q for q in pool if (position(data, players[q]) == 0) == (want == 0)), None)
            if pick is None:
                kept += 1
                continue
            new[i] = pick
            taken.add(pick)
            replaced += 1
            report.append({"team": names.get(t), "slot": i, "out": players[p]["name"],
                           "in": players[pick]["name"], "by": "position"})
        if new != ids[t]:
            struct.pack_into(f">{len(new)}I", data, rosters[t]["offset"] + 4, *new)
    struct.pack_into(">I", data, 8, edit.crc32(data))
    back = edit.decode(bytes(data))
    br = {r["team_id"]: [m["player_id"] for m in r["members"]] for r in back["rosters"]}
    for t in national:
        if len(br[t]) != len(ids[t]) or len(set(br[t])) != len(br[t]):
            sys.exit(f"team {t}: squad does not read back")
    Path(a.dst).write_bytes(data)
    if a.report:
        Path(a.report).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(national)} national squads: {replaced} players replaced by club players, "
          f"{kept} kept (no club player of that nationality left) -> {a.dst}")


if __name__ == "__main__":
    main()
