#!/usr/bin/env python3
"""Grid of BLUS31029EUNIFORM ICON0.NNG previews (game-rendered kit previews),
labeled with the save number. Read-only; output goes under analysis/ only.
"""
import argparse
from pathlib import Path
import struct
import sys
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from uniform_montage import GLYPHS, parse_png

# decode of ICON0 320x176 -> near-half
BG = b"\x18\x18\x18\xff"


def label_canvas(W, x, y, text, color=(255, 255, 0, 255), scale=2):
    for ch in text.upper():
        glyph = GLYPHS.get(ch, GLYPHS[" "])
        for gy, rowbits in enumerate(glyph):
            for gx, bit in enumerate(rowbits):
                if bit != "1":
                    continue
                for dy in range(scale):
                    for dx in range(scale):
                        px = x + gx * scale + dx
                        py = y + gy * scale + dy
                        base = (py * W + px) * 4
                        canvas[base:base + 4] = bytes(color)


def main():
    global canvas
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("savedata", type=Path)
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.savedata
    cols, rows = 4, 3
    cw, ch_ = 160, 80
    labe_h = 14
    per = cols * rows

    nums = sorted(int(l) for l in open('/tmp/euni_nums.txt') if args.start <= int(l) <= args.end)
    if not nums:
        raise SystemExit("no saves in interval")

    for s in range(0, len(nums), per):
        batch = nums[s:s + per]
        W, H = cols * (cw + 2) + 2, (ch_ + labe_h + 2) * rows + 2
        canvas = bytearray(BG * (W * H))
        for idx, num in enumerate(batch):
            path = root / f"BLUS31029EUNIFORM{num:03d}" / "ICON0.PNG"
            try:
                px = parse_png(path.read_bytes())
            except ValueError as err:
                raise SystemExit(f"{path}: {err}")
            w0, h0, rgb = px
            step = 2
            ox = 2 + (idx % cols) * (cw + 2)
            oy = 2 + (idx // cols) * (ch_ + labe_h + 2)
            for yy in range(ch_):
                sy = yy * step
                for xx in range(cw):
                    sx = xx * step
                    sa = (sy * w0 + sx) * 4
                    da = ((oy + yy) * W + ox + xx) * 4
                    canvas[da:da + 4] = rgb[sa:sa + 4]
            label_canvas(W, ox + 4, oy + ch_ + 1, f"{num:04d}", scale=2)
        out = args.output
        out.mkdir(parents=True, exist_ok=True)
        name = f"icons_{batch[0]:04d}-{batch[-1]:04d}.png"
        (out / name).write_bytes(encode_png(W, H, bytes(canvas)))
        print(name)


def encode_png(width, height, rgba):
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + \
            struct.pack(">I", zlib.crc32(kind + payload))

    raw = b"".join(b"\0" + rgba[y * width * 4:(y + 1) * width * 4] for y in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


if __name__ == "__main__":
    main()
