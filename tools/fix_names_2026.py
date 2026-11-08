#!/usr/bin/env python3
"""Give the 2026 players their known names, and stock-style shirt names, in an EEDIT copy.

    fix_names_2026.py SRC DST --manifest manifest.json --squads candidate_squads.json
                      --continental continental_mapping.json [--overrides names.json]
                      [--report names.json]

The Brazilian squads were named from the CBF registration nickname, which is
sometimes only the first given name: "JORGE" is Jorginho, "LUIZ" is Luiz Araújo,
"DYOGO" is Dyogo Alves. For each Brazilian-club player this writes:
- the name from --overrides (cbf_id -> name), when listed;
- else ESPN's two-word display name, when the CBF nickname is one word and is
  that name's first word (Luiz -> Luiz Araújo); a one-word nickname that is a
  surname (Plata, Arrascaeta) stays, as the stock Option File writes foreigners;
- else, when two players of one club share a name, ESPN's name for each, or the
  name and the last surname of the registration;
- else the name as it is.
The shirt name follows the stock file: no accents ("LÉO ORTIZ" -> "LEO ORTIZ"),
and a renamed player gets his new name on the shirt, or its last word when it
does not fit in 17 bytes. The continental players keep their names ("J. GÓMEZ");
only the accents leave their shirts.

Only the name (+50, 46 bytes) and shirt name (+96, 18 bytes) fields and the CRC
change; the file is decoded again.
"""
import argparse
import collections
import json
from pathlib import Path
import struct
import sys
import unicodedata

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pes2013_edit as edit  # noqa: E402


PARTICLES = {"de", "da", "do", "dos", "das", "e"}


def plain(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def fit(text, size):
    v = text.upper().strip()
    while len(v.encode("utf-8")) >= size:
        v = v[:-1].rstrip()
    return v


def shirt_of(name):
    s = plain(name).upper()
    return s if len(s) < 18 else plain(name.split()[-1]).upper()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--squads", required=True)
    ap.add_argument("--continental", required=True)
    ap.add_argument("--overrides")
    ap.add_argument("--report")
    a = ap.parse_args()
    if Path(a.src).resolve() == Path(a.dst).resolve():
        sys.exit("DST must be a different file")
    data = Path(a.src).read_bytes()
    cur = edit.decode(data)
    players = {p["id"]: p for p in cur["players"]}
    athletes = {x["cbf_id"]: x for c in json.loads(Path(a.squads).read_text(encoding="utf-8"))["clubs"]
                for x in c["athletes"]}
    over = json.loads(Path(a.overrides).read_text(encoding="utf-8")) if a.overrides else {}
    man = json.loads(Path(a.manifest).read_text(encoding="utf-8"))

    def espn(cbf_id):
        e = (athletes.get(cbf_id, {}).get("espn_candidates") or [{}])[0]
        return e.get("display_name")

    want = {}          # player id -> (name, shirt, why)
    for ch in man["changes"]:
        names = {}
        for s in ch["assignments"]:
            cbf, pid = s["cbf_id"], s["pes_id"]
            now = players[pid]["name"]
            e = espn(cbf)
            if cbf in over:
                names[pid] = (over[cbf], "override")
            elif (len(now.split()) == 1 and e and len(e.split()) == 2
                  and plain(e.split()[0]).lower() == plain(now).lower()):
                names[pid] = (e, "espn")
            else:
                names[pid] = (now, None)
        seen = collections.Counter(plain(n).upper() for n, _ in names.values())
        for s in ch["assignments"]:
            pid, (n, why) = s["pes_id"], names[s["pes_id"]]
            e = espn(s["cbf_id"])
            if seen[plain(n).upper()] > 1 and why is None:
                if e and len(e.split()) in (2, 3) and plain(e).upper() != plain(n).upper():
                    names[pid] = (e, "duplicate")
                else:
                    full = [w for w in (athletes.get(s["cbf_id"], {}).get("name") or "").split()
                            if w.lower() not in PARTICLES and w.lower() not in ("junior", "filho", "neto")]
                    if len(full) >= 2:
                        names[pid] = (f"{n.split()[0]} {full[-1].title()}", "duplicate")
        for pid, (n, why) in names.items():
            nm = fit(n, 46)
            sh = fit(shirt_of(n), 18) if why else fit(plain(players[pid]["shirt_name"]), 18)
            want[pid] = (nm, sh, why)
    for m in json.loads(Path(a.continental).read_text(encoding="utf-8")):
        p = players[m["player_id"]]
        want.setdefault(m["player_id"], (p["name"], fit(plain(p["shirt_name"]), 18), None))

    out = bytearray(data)
    allowed = bytearray(len(data))
    allowed[8:12] = b"\1" * 4
    report = []
    for pid, (nm, sh, why) in want.items():
        p = players[pid]
        for rel, size, val in ((50, 46, nm), (96, 18, sh)):
            raw = val.encode("utf-8")
            at = p["offset"] + rel
            out[at:at + size] = raw + bytes(size - len(raw))
            allowed[at:at + size] = b"\1" * size
        if (nm, sh) != (p["name"], p["shirt_name"]):
            report.append({"player_id": pid, "from": [p["name"], p["shirt_name"]], "to": [nm, sh], "why": why})
    struct.pack_into(">I", out, 8, edit.crc32(out))
    if any(x != y and not allowed[i] for i, (x, y) in enumerate(zip(data, out))):
        raise SystemExit("a byte outside the name fields changed")
    back = {p["id"]: p for p in edit.decode(bytes(out))["players"]}
    for pid, (nm, sh, _) in want.items():
        if (back[pid]["name"], back[pid]["shirt_name"]) != (nm, sh):
            raise SystemExit(f"player {pid}: read back {back[pid]['name']!r} {back[pid]['shirt_name']!r}")
    Path(a.dst).write_bytes(out)
    if a.report:
        Path(a.report).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    c = collections.Counter(r["why"] for r in report)
    print(f"{len(report)} players changed ({dict(c)}) -> {a.dst}")


if __name__ == "__main__":
    main()
