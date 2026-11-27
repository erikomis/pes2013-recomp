#!/usr/bin/env python3
"""Lift the SPU images embedded in the game's EBOOT and register them for the
SPURS/workload dispatch (port/spu/spu_workloads.c).

    lift_spu.py --toolkit DIR [--images DIR] [--out DIR]

The same work as tools/lift_spu.sh, in Python so the Windows build
(tools/windows/rebuild.ps1) runs it without zsh; see lift_spu.sh for why the
four images below are lifted with --code-end and why --merge-chunks is not used.
Keep the two tables in step.
"""
import argparse
from pathlib import Path
import subprocess
import sys

# SPU images whose executable segment embeds a data tail: end of real code.
SPU_CODE_END = {
    "spu_0001": "0xb350",
    "spu_0006": "0x1e258",
    "spu_0007": "0x22fd0",
    "spu_0008": "0x23210",   # the CRIWARE SPURS task two CreateTask calls await
}


def main():
    root = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--toolkit", required=True, help="the ps3recomp checkout")
    ap.add_argument("--images", default=str(root / "analysis" / "BLUS31029" / "spu"),
                    help="the extracted SPU ELFs (extract_spu_images.py output)")
    ap.add_argument("--out", default=str(root / "port" / "spu"))
    a = ap.parse_args()
    kit = Path(a.toolkit) / "tools"
    img = Path(a.images)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    elves = sorted(img.glob("spu_*.elf"))
    if not elves:
        sys.exit(f"no spu_*.elf in {img} (run the toolkit's extract_spu_images.py first)")
    for elf in elves:
        stem = elf.stem
        ce = SPU_CODE_END.get(stem.split("_at_")[0])
        cmd = [sys.executable, str(kit / "spu_lifter.py"), str(elf), "--auto-functions", str(elf),
               "--symbol-prefix", f"{stem}_", "--output", str(out / stem),
               "--source-name", "spu_recomp.c", "--header-name", "spu_recomp.h"]
        if ce:
            cmd += ["--code-end", ce]
        print(f"[lift_spu] {stem}" + (f" (code-end {ce})" if ce else ""), flush=True)
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL)
    subprocess.check_call([sys.executable, str(kit / "build_spu_workloads.py"), "--images", str(img),
                           "--lifted", str(out), "--out", str(out / "spu_workloads.c"),
                           "--constructor", "--skip-lift"])


if __name__ == "__main__":
    main()
