"""Stage 2026 kitpack kits (Kitserver .ftex) into PS3 PES2013 EUNIFORM saves.

Pipeline: pick kitpack .ftex -> decode a native 256x256 mip (or box-downscale
a bigger one) -> compose the EUNIFORM canvas -> call uniform_texture.py's
stage (--output-save) so the output always stays a new directory under
analysis/.

Composition modes
----------------
  full      Raw kitserver atlas mapped straight onto the 256x256 canvas.
            Provisional: used for the in-game UV probe. Likely wrong
            layout on the model; keep only for diagnosis.
  composite Region-based re-render (crest/sponsors/pattern) from the atlas
            onto the PES13 EUNIFORM layout. NOT IMPLEMENTED YET: it needs
            the per-region template derived in-game.

Derived-data policy: never writes outside analysis/. The owner's saves
under rpcs3/ are read-only inputs here.

Usage:
  python tools/stage_uniforms_2026.py \
      --club Flamengo --slot p1 \
      --save-id 419 \
      --source analysis/test-save-flamengo-2026/gamedata/dev_hdd0/home/00000001/savedata/BLUS31029EUNIFORM419 \
      --staged-name flamengo-home-2026
"""

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
KITPACK_ROOT = REPO / "analysis/visual-2026/sources/kitpackAB2026/extracted"
STAGED_ROOT = REPO / "analysis/staged"
PNG_CACHE = REPO / "analysis/visual-2026/ftex-png"


def find_ftex(club, slot):
    for serie in ("Serie A", "Serie B"):
        cand = KITPACK_ROOT / f"uniformes/kit-server/Brasileirao {serie}" / club / slot
        if cand.exists():
            ftex = sorted(cand.glob("*.ftex"))
            if ftex:
                return ftex[0]
    raise SystemExit(f"no .ftex for club={club!r} slot={slot!r} under {KITPACK_ROOT}")


def render_full(club, slot, alpha_opaque=True):
    """Decode the fitting native mip so the result is 256x256 with no
    resample for 2048x2048 sources (mip 3 is 256). Requires ftex_convert."""
    sys.path.insert(0, str(REPO / "tools"))
    import ftex_convert as fc

    src = find_ftex(club, slot)
    info = fc.read_ftex(src)
    info["data"] = Path(src).read_bytes()
    rgba, w, h = fc.decode_frame_rgba(info, 3)   # 256x256 native for 2048 sources
    if (w, h) != (256, 256):
        rgba = fc.box_downscale(rgba, w, h, 256)
    if alpha_opaque:
        for o in range(3, len(rgba), 4):
            rgba[o] = 255
    out = PNG_CACHE / f"{club}_{slot}_full256.png"
    out.write_bytes(fc.encode_png_rgba(rgba, 256, 256))
    return out


def stage(png, source_save, staged_name):
    dest = STAGED_ROOT / staged_name
    cmd = [sys.executable, str(REPO / "tools/uniform_texture.py"), "stage",
           str(source_save), "--png", str(png), "--output-save", str(dest)]
    subprocess.run(cmd, check=True)
    return dest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--club", required=True)
    ap.add_argument("--slot", required=True, choices=["p1", "p2", "p1x1", "g1", "g2", "g3"])
    ap.add_argument("--save-id", type=int, required=True,
                    help="EUNIFORM save number (e.g. 419)")
    ap.add_argument("--source", type=Path, required=True,
                    help="existing EUNIFORM save directory used as base")
    ap.add_argument("--staged-name", required=True)
    ap.add_argument("--mode", choices=["full", "composite"], default="full")
    args = ap.parse_args(argv)

    if args.mode == "composite":
        raise SystemExit("composite mode not implemented yet: needs the "
                         "in-game UV/region template (docs pending)")
    png = render_full(args.club, args.slot)
    print(f"rendered {png}")
    dest = stage(png, args.source, args.staged_name)
    print(f"staged {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
