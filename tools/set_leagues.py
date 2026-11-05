#!/usr/bin/env python3
"""Set which clubs play in a league, in an EEDIT copy.

    set_leagues.py SRC DST --map leagues.json [--layout b20|original]

The EDIT save keeps every league's clubs in one table of 210 big-endian u16 team
IDs at 0x516AA6, 0xFFFF for an empty slot. Each league owns a fixed range of it,
set in the game's code (func_00D4ECA8 counts, func_00D4ED6C starts):

    league  0 England 20   1 France 20   2 Italy 20   3 Netherlands 18
            4 Spain 20     5 Portugal 16 6 Latin America 18
            7 Série B 18   8 Série A 20  9 other European clubs 40

`b20` is the layout after port/eboot_patches.txt: Série B 20 (from slot 190),
other European clubs 38. A save written with it must be played with the patched
build: the stock game would read the first two Série B clubs as European ones.

leagues.json is {"<league index>": [team id, ...]}; leagues not named keep their
clubs. A club may appear in one league only. Clubs taken out of a league stay in
the save, just not in any league. The CRC is recomputed and every other byte is
checked unchanged. SRC is not modified.
"""
import argparse
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pes2013_edit as edit  # noqa: E402

TABLE = 0x516AA6
SLOTS = 210
EMPTY = 0xFFFF
ORIGINAL = {0: (0, 20), 1: (20, 20), 2: (40, 20), 3: (60, 18), 4: (78, 20), 5: (98, 16),
            6: (134, 18), 7: (192, 18), 8: (114, 20), 9: (152, 40)}
B20 = {**ORIGINAL, 7: (190, 20), 9: (152, 38)}
LAYOUTS = {"original": ORIGINAL, "b20": B20}


def read_leagues(data, layout):
    slots = struct.unpack_from(f">{SLOTS}H", data, TABLE)
    return {k: [t for t in slots[s:s + n] if t != EMPTY] for k, (s, n) in layout.items()}


def set_leagues(data, wanted, layout):
    before = edit.decode(data)
    known = {t["id"] for t in before["teams"]}
    current = read_leagues(data, layout)
    leagues = {k: list(v) for k, v in current.items()}
    for k, ids in wanted.items():
        if k not in layout:
            raise ValueError(f"no league {k}")
        if len(ids) > layout[k][1]:
            raise ValueError(f"league {k} holds {layout[k][1]} clubs, {len(ids)} given")
        missing = [t for t in ids if t not in known]
        if missing:
            raise ValueError(f"league {k}: unknown team ids {missing}")
        leagues[k] = list(ids)
    seen = {}
    for k, ids in leagues.items():
        for t in ids:
            if t in seen:
                raise ValueError(f"team {t} is in league {seen[t]} and league {k}")
            seen[t] = k
    slots = [EMPTY] * SLOTS
    for k, (s, n) in layout.items():
        slots[s:s + len(leagues[k])] = leagues[k]
    out = bytearray(data)
    struct.pack_into(f">{SLOTS}H", out, TABLE, *slots)
    struct.pack_into(">I", out, 8, edit.crc32(out))
    lo, hi = TABLE, TABLE + 2 * SLOTS
    if any(a != b and not (lo <= i < hi or 8 <= i < 12) for i, (a, b) in enumerate(zip(data, out))):
        raise ValueError("a byte outside the league table changed")
    edit.decode(bytes(out))
    if read_leagues(bytes(out), layout) != leagues:
        raise ValueError("the table does not read back as written")
    return bytes(out), current, leagues


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--map", required=True)
    ap.add_argument("--layout", choices=sorted(LAYOUTS), default="b20")
    a = ap.parse_args()
    if Path(a.src).resolve() == Path(a.dst).resolve():
        sys.exit("DST must be a different file")
    wanted = {int(k): [int(t) for t in v]
              for k, v in json.loads(Path(a.map).read_text(encoding="utf-8")).items()}
    out, before, after = set_leagues(Path(a.src).read_bytes(), wanted, LAYOUTS[a.layout])
    Path(a.dst).write_bytes(out)
    for k in sorted(wanted):
        gone = [t for t in before[k] if t not in after[k]]
        new = [t for t in after[k] if t not in before[k]]
        print(f"league {k}: {len(after[k])} clubs; in {new}; out {gone}")
    print(f"-> {a.dst} ({a.layout} layout)")


if __name__ == "__main__":
    main()
