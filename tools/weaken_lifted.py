#!/usr/bin/env python3
"""Mark the lifted functions listed in port/lifted_overrides.txt as weak.

    weaken_lifted.py RECOMP_DIR [--list FILE]

The port defines its own versions of those functions; a weak lifted definition
lets the port's strong one win at link time, and every direct call in the lifted
code then reaches the port's version. Run after each lift; a second run changes
nothing. Each listed function must be found exactly once.
"""
import argparse
from pathlib import Path
import re
import sys


def main():
    here = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("recomp_dir")
    ap.add_argument("--list", default=str(here / "port" / "lifted_overrides.txt"))
    a = ap.parse_args()
    names = []
    for line in Path(a.list).read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            names.append(f"func_{int(line, 16):08X}")
    found = {n: 0 for n in names}
    for path in sorted(Path(a.recomp_dir).glob("ppu_recomp_*.cpp")):
        text = path.read_text(encoding="utf-8")
        new = text
        for n in names:
            pat = re.compile(rf"^(?:__attribute__\(\(weak\)\) )?void {n}\(ppu_context\* ctx\) {{", re.M)
            hits = pat.findall(new)
            found[n] += len(hits)
            new = pat.sub(f"__attribute__((weak)) void {n}(ppu_context* ctx) {{", new)
        if new != text:
            path.write_text(new, encoding="utf-8")
            print(f"{path.name}: weakened")
    bad = {n: c for n, c in found.items() if c != 1}
    if bad:
        sys.exit(f"expected one definition each, found {bad}")
    print(f"{len(names)} lifted function(s) weak")


if __name__ == "__main__":
    main()
