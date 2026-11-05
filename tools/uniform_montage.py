#!/usr/bin/env python3
"""Build numbered contact sheets of BLUS31029EUNIFORM saves. Read-only.

Downloads stay out of the repo; output is written under analysis/ only.
RGBA8 256x256 overlays are sampled downsample and pasted in save-number
order, one decimal label per cell, N cells per sheet.
"""
import argparse
from pathlib import Path
import struct
import sys
import zlib

STRIDE = 4
DATA_OFFSET = 33
PIXELS = 256 * 256 * 4

GLYPHS = {
    "0": ["111", "101", "101", "101", "101", "101", "111"],
    "1": ["010", "110", "010", "010", "010", "010", "111"],
    "2": ["111", "001", "001", "111", "100", "100", "111"],
    "3": ["111", "001", "001", "111", "001", "001", "111"],
    "4": ["101", "101", "101", "111", "001", "001", "001"],
    "5": ["111", "100", "100", "111", "001", "001", "111"],
    "6": ["111", "100", "100", "111", "101", "101", "111"],
    "7": ["111", "001", "001", "001", "001", "001", "001"],
    "8": ["111", "101", "101", "111", "101", "101", "111"],
    "9": ["111", "101", "101", "111", "001", "001", "111"],
    " ": ["000"] * 7,
    "F": ["111", "100", "100", "111", "100", "100", "100"],
    "A": ["010", "101", "101", "111", "101", "101", "101"],
    "L": ["100", "100", "100", "100", "100", "100", "111"],
    "T": ["111", "010", "010", "010", "010", "010", "010"],
}


def parse_png(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a png")
    pos, width, height, bitdepth, colortype = 8, 0, 0, 0, 0
    idat = []
    while pos < len(data):
        length, kind = struct.unpack_from(">I4s", data, pos)
        body = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            width, height, bitdepth, colortype = struct.unpack_from(">IIBB", body)
        elif kind == b"IDAT":
            idat.append(body)
        pos += 12 + length
    if bitdepth != 8 or colortype != 6:
        raise ValueError("expect 8-bit RGBA png")
    raw = zlib.decompress(b"".join(idat))
    channels, out, prev = 4, bytearray(), bytearray(width * 4)
    stride = width * 4
    for y in range(height):
        line = raw[y * (stride + 1): (y + 1) * (stride + 1)]
        row = bytearray(width * 4)
        shift = 0
        for i in range(stride):
            left = row[i - 4] if i >= 4 else 0
            up = prev[i]
            ul = prev[i - 4] if i >= 4 else 0
            x = line[i + 1]
            if line[0] == 0:
                shift = x
            elif line[0] == 1:
                shift = x + left
            elif line[0] == 2:
                shift = x + up
            elif line[0] == 3:
                shift = x + (left + up) // 2
            elif line[0] == 4:
                a, b, c = left, up, ul
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                shift = x + (a if pa <= pb and pa <= pc else b if pb <= pc else c)
            else:
                raise ValueError("unsupported filter")
            row[i] = shift & 0xFF
        out += row
        prev = row
    return width, height, bytes(out)


def encode_png(width, height, rgba):
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + \
            struct.pack(">I", zlib.crc32(kind + payload))

    raw = b"".join(b"\0" + rgba[y * width * 4:(y + 1) * width * 4]
                   for y in range(height))
    return (struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0) and
            b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def draw_text(canvas, sheet_w, x, y, text, color=(255, 255, 255, 255)):
    for ch in text.upper():
        glyph = GLYPHS.get(ch, GLYPHS[" "])
        for gy, rowbits in enumerate(glyph):
            for gx, bit in enumerate(rowbits):
                if bit == "1":
                    py = y + gy
                    px = x + gx
                    canvas[(py * sheet_w + px) * 4:(py * sheet_w + px) * 4 + 4] = bytes(color)
        x += 4


def sample_256_to(canvas, sheet_w, ox, oy, edge, rgba):
    step = 256 // edge
    for y in range(edge):
        sy = (y * step + step // 2) * 256 * 4
        for x in range(edge):
            sx = (x * step + step // 2) * 4
            src = sy + sx
            dst = ((oy + y) * sheet_w + ox + x) * 4
            canvas[dst:dst + 4] = rgba[src:src + 4]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("savedata", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--edge", type=int, default=120,
                        help="cell pixel size, must divide 256")
    parser.add_argument("--cols", type=int, default=8)
    parser.add_argument("--rows", type=int, default=6)
    parser.add_argument("--prefix", default="uni")
    args = parser.parse_args()

    saves = sorted(args.savedata.glob("BLUS31029EUNIFORM*/DATA.BIN"))
    numbers = [int(p.parent.name.replace("BLUS31029EUNIFORM", "")) for p in saves]
    edge, cols, rows = args.edge, args.cols, args.rows
    if 256 % edge or edge > 256:
        parser.error("--edge must divide 256")
    per = cols * rows
    label_h = 10

    total = 0
    for start in range(0, len(saves), per):
        batch = list(zip(numbers[start:start + per], saves[start:start + per]))
        sheet_w = cols * (edge + 2)
        sheet_h = rows * (edge + label_h + 2)
        canvas = bytearray(b"\x20") * 0
        canvas = bytearray(sheet_w * sheet_h * 4)
        for i in range(0, len(canvas), 4):
            canvas[i:i + 4] = b"\x18\x18\x18\xff"
        for idx, (num, path) in enumerate(batch):
            data = path.read_bytes()
            if len(data) != 262179:
                raise ValueError(f"{path} unsupported size")
            rgba = data[DATA_OFFSET:DATA_OFFSET + PIXELS]
            cx, cy = idx % cols, idx // cols
            ox, oy = cx * (edge + 2) + 1, cy * (edge + label_h + 2) + 1
            sample_256_to(canvas, sheet_w, ox, oy, edge, rgba)
            label = f" {num:04d} "[:9]
            lab_y = oy + edge + 1
            for ly in range(label_h - 1):
                yy = lab_y + ly
                for xx in range(ox, ox + edge):
                    canvas[(yy * sheet_w + xx) * 4:(yy * sheet_w + xx) * 4 + 4] = b"\x00\x00\x00\xff"
            draw_text(canvas, sheet_w, ox + 2, lab_y + 1, label)
            total += 1
        out_dir = args.output
        out_dir.mkdir(parents=True, exist_ok=True)
        name = f"{args.prefix}_{start // per + 1:02d}_{numbers[start]:04d}-{numbers[min(start + per, len(saves)) - 1]:04d}.png"
        (out_dir / name).write_bytes(encode_png(sheet_w, sheet_h, bytes(canvas)))
    print(f"{total} uniformes em {(len(saves) + per - 1) // per} sheets")


if __name__ == "__main__":
    main()
