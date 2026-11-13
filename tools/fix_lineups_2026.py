#!/usr/bin/env python3
"""Set each 2026 club's starting eleven and bench, in an EEDIT copy.

    fix_lineups_2026.py ORIGINAL SRC DST --manifest manifest.json
                        --continental continental_mapping.json --stats stats_2026.json
                        [--report lineups.json]

The squad list (roster, tools/pes2013_edit.py) only says who is in a club. The
line-up is a separate table: 379 records of 2756 bytes from 0x400444, each
holding the team ID (u16 at -1448 from the line-up) and 32 bytes, the roster
slots in line-up order: entries 0..10 are the starters in the formation's
positions (0 the keeper), the rest the bench and reserves. Renaming a squad
leaves that table pointing at the same roster slots, so the eleven on the
pitch were whoever now sat in those slots, out of position.

For every club written by the 2026 tools this rewrites that order:
- a formation position's role is that of the player the stock Option File
  (ORIGINAL) had there, since the formation itself is unchanged.
- ranking: the 40 Brazilian clubs by starts in the club's recent CBF match
  sheets (manifest.json evidence), then appearances; the foreign clubs, which
  have no sheets here, by their abilities (stats_2026.json). One keeper.
- each outfield position takes the best-ranked free player of the same line
  (defence, midfield, attack) whose registered position is close to the role,
  else the best of the line, else of the squad; then the eleven are placed on
  the positions by least distance.
- then the bench by starts/appearances, then the unused slots.

Only those 32-byte arrays and the CRC change; the file is decoded again.
"""
import argparse
import collections
import itertools
import json
import math
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pes2013_edit as edit  # noqa: E402

BASE, STRIDE, RECORDS, TEAM_AT = 0x400444, 2756, 379, -1448
# position code -> (side, depth) on the pitch, for matching roles
XY = {0: (0, 0), 1: (0, 1.0), 2: (0, 1.2), 3: (-1, 1.4), 4: (1, 1.4), 5: (0, 2.0), 6: (0, 2.5),
      7: (-1, 2.7), 8: (1, 2.7), 9: (0, 3.2), 10: (-1, 3.6), 11: (1, 3.6), 12: (0, 3.7), 13: (0, 4.1)}


def lineup_offsets(data):
    out = {}
    for i in range(RECORDS):
        at = BASE + i * STRIDE
        if sorted(data[at:at + 32]) != list(range(32)):
            continue
        tid = struct.unpack_from(">H", data, at + TEAM_AT)[0]
        if tid != 0xFFFF:
            out.setdefault(tid, at)
    return out


def assign(roles, players):
    """players -> roles minimising position distance (Hungarian, small n)."""
    n = len(roles)
    cost = [[math.dist(XY[p], XY[r]) for r in roles] for p in players]
    # O(n^3) Hungarian
    INF = float("inf")
    u, v = [0.0] * (n + 1), [0.0] * (n + 1)
    p_, way = [0] * (n + 1), [0] * (n + 1)
    for i in range(1, n + 1):
        p_[0] = i
        j0 = 0
        minv, used = [INF] * (n + 1), [False] * (n + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p_[j0], INF, 0
            for j in range(1, n + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j], way[j] = cur, j0
                    if minv[j] < delta:
                        delta, j1 = minv[j], j
            for j in range(n + 1):
                if used[j]:
                    u[p_[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p_[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p_[j0] = p_[j1]
            j0 = j1
            if j0 == 0:
                break
    out = [None] * n          # role index -> player index
    for j in range(1, n + 1):
        out[j - 1] = p_[j] - 1
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("original")
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--continental", required=True)
    ap.add_argument("--stats", required=True)
    ap.add_argument("--report")
    a = ap.parse_args()
    if Path(a.src).resolve() == Path(a.dst).resolve():
        sys.exit("DST must be a different file")
    od, data = Path(a.original).read_bytes(), Path(a.src).read_bytes()
    orig, cur = edit.decode(od), edit.decode(data)
    oplayers = {p["id"]: p for p in orig["players"]}
    players = {p["id"]: p for p in cur["players"]}
    orosters = {r["team_id"]: r for r in orig["rosters"]}
    rosters = {r["team_id"]: r for r in cur["rosters"]}
    where = lineup_offsets(data)
    owhere = lineup_offsets(od)

    def pos_of(buf, plist, pid):
        return buf[plist[pid]["offset"] + 121] & 15

    # how much each player is worth as a starter
    score = {}
    man = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    clubs = []
    for ch in man["changes"]:
        clubs.append(ch["team_id"])
        for asg in ch["assignments"]:
            ev = asg.get("evidence") or []
            starts = sum(1 for e in ev if e.get("started"))
            score[asg["pes_id"]] = (starts, len(ev))
    stats = {p["player_id"]: p for p in json.loads(Path(a.stats).read_text(encoding="utf-8"))["players"]}
    for m in json.loads(Path(a.continental).read_text(encoding="utf-8")):
        if m["slot"] not in clubs:
            clubs.append(m["slot"])
        ab = stats.get(m["player_id"], {}).get("abilities") or {}
        key = ("gk",) if stats.get(m["player_id"], {}).get("position") == "GK" else \
            ("attack", "defence", "ball_control", "short_acc", "top_speed", "explosive", "teamwork")
        val = sum(ab.get(k, 50) for k in key) / len(key)
        score.setdefault(m["player_id"], (0, val / 100.0))

    out = bytearray(data)
    allowed = bytearray(len(data))
    allowed[8:12] = b"\1" * 4
    report = []
    for tid in clubs:
        if tid not in where or tid not in rosters:
            report.append({"team": tid, "skipped": "no line-up record or roster"})
            continue
        at = where[tid]
        old = list(data[at:at + 32])
        members = {m["slot"]: m["player_id"] for m in rosters[tid]["members"]}
        omembers = {m["slot"]: m["player_id"] for m in orosters.get(tid, {"members": []})["members"]}
        # roles of the eleven formation positions, from the stock line-up: the
        # ORIGINAL file's array, so running this again on its own output gives the
        # same result (the current array has been rewritten already)
        stock = list(od[owhere[tid]:owhere[tid] + 32]) if tid in owhere else old
        roles = []
        for k in range(11):
            pid = omembers.get(stock[k])
            roles.append(pos_of(od, oplayers, pid) if pid in oplayers else (0 if k == 0 else 6))
        ranked = sorted(members.items(), key=lambda sp: score.get(sp[1], (0, 0)), reverse=True)
        keepers = [sp for sp in ranked if pos_of(data, players, sp[1]) == 0]
        outfield = [sp for sp in ranked if pos_of(data, players, sp[1]) != 0]
        if not keepers or len(outfield) < 10:
            report.append({"team": tid, "skipped": "fewer than one keeper and ten outfield players"})
            continue
        gk = keepers[0]
        # pick by role: each formation position takes the best-ranked free player of
        # its line (defence, midfield, attack), nearest role first; defence first,
        # since a team is most often short of defenders
        line = lambda c: 0 if c == 0 else 1 if c <= 4 else 2 if c <= 9 else 3  # noqa: E731
        free = list(outfield)
        xi = [None] * 10
        for k in sorted(range(10), key=lambda k: (line(roles[k + 1]) != 1, line(roles[k + 1]) != 3)):
            want = roles[k + 1]
            same = [sp for sp in free if line(pos_of(data, players, sp[1])) == line(want)]
            pool = same or free
            # best ranked among the nearest-fitting quarter of the pool
            pool.sort(key=lambda sp: (math.dist(XY[pos_of(data, players, sp[1])], XY[want]) > 0.8,
                                      [-x for x in score.get(sp[1], (0, 0))]))
            xi[k] = pool[0]
            free.remove(pool[0])
        order = assign(roles[1:], [pos_of(data, players, pid) for _, pid in xi])
        starters = [gk[0]] + [xi[order[k]][0] for k in range(10)]
        bench = [s for s, _ in ranked if s not in starters]
        rest = [s for s in range(32) if s not in starters and s not in bench]
        new = starters + bench + rest
        assert sorted(new) == list(range(32))
        out[at:at + 32] = bytes(new)
        allowed[at:at + 32] = b"\1" * 32
        report.append({"team": tid, "name": next((t["name"] for t in cur["teams"] if t["id"] == tid), ""),
                       "starters": [players[members[s]]["name"] for s in starters],
                       "roles": roles,
                       "positions": [pos_of(data, players, members[s]) for s in starters]})
    struct.pack_into(">I", out, 8, edit.crc32(out))
    if any(x != y and not allowed[i] for i, (x, y) in enumerate(zip(data, out))):
        raise SystemExit("a byte outside the line-up arrays changed")
    edit.decode(bytes(out))
    Path(a.dst).write_bytes(out)
    if a.report:
        Path(a.report).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    done = [r for r in report if "starters" in r]
    print(f"{len(done)} line-ups written, {len(report) - len(done)} skipped -> {a.dst}")
    for r in report:
        if "skipped" in r:
            print("  skipped", r["team"], r["skipped"])


if __name__ == "__main__":
    main()
