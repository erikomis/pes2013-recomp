#!/usr/bin/env python3
"""Make a 2x pitch texture for a texture pack from the game's own pitch.

    make_hd_pitch.py SRC.png DST.png [--detail 0..1] [--seed N]

SRC is the pitch as PS3_MODS_DUMP wrote it (2048x1024: the whole pitch, mowing
stripes and lines painted in). DST is twice the size: each pixel is upsampled
bilinearly, then a fine grass grain (a tiled noise of short vertical blades,
seeded, so the same input gives the same output) is added to the grass only;
line pixels (bright, unsaturated) are left without grain so they stay clean.
It is the same pitch, sharper at 1080p and above, not a new turf.
"""
import argparse
import random
import struct
import zlib
from pathlib import Path


def read_png(path):
    d = Path(path).read_bytes()
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit("not a PNG")
    i, idat = 8, b""
    while i < len(d):
        n, t = struct.unpack(">I4s", d[i:i + 8])
        c = d[i + 8:i + 8 + n]
        i += 12 + n
        if t == b"IHDR":
            w, h, bd, ct, _, _, il = struct.unpack(">IIBBBBB", c)
        elif t == b"IDAT":
            idat += c
    if bd != 8 or ct not in (2, 6) or il:
        raise SystemExit("only 8-bit RGB/RGBA, non-interlaced")
    bpp = 3 if ct == 2 else 4
    raw = zlib.decompress(idat)
    stride = w * bpp
    out = bytearray(w * h * 3)
    prev = bytearray(stride)
    o = 0
    for y in range(h):
        f = raw[o]; o += 1
        line = bytearray(raw[o:o + stride]); o += stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        prev = line
        row = out[y * w * 3:(y + 1) * w * 3]
        if bpp == 3:
            out[y * w * 3:(y + 1) * w * 3] = line
        else:
            out[y * w * 3:(y + 1) * w * 3] = bytes(v for k in range(w) for v in line[k * 4:k * 4 + 3])
        del row
    return w, h, out


def write_png(path, w, h, rgb):
    raw = b"".join(b"\0" + bytes(rgb[y * w * 3:(y + 1) * w * 3]) for y in range(h))

    def chunk(t, data):
        return struct.pack(">I", len(data)) + t + data + struct.pack(">I", zlib.crc32(t + data) & 0xFFFFFFFF)
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                           + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def grain_tile(size, seed):
    """Signed grain in -1..1: short vertical blades over a soft noise."""
    rnd = random.Random(seed)
    t = [0.0] * (size * size)
    for _ in range(size * size // 6):
        x, y = rnd.randrange(size), rnd.randrange(size)
        length, v = rnd.randint(2, 5), rnd.uniform(-1, 1)
        for k in range(length):
            t[((y + k) % size) * size + x] += v * (1 - k / length)
    m = max(abs(v) for v in t) or 1
    return [v / m for v in t]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--detail", type=float, default=0.5)
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args()
    w, h, px = read_png(a.src)
    W, H = 2 * w, 2 * h
    out = bytearray(W * H * 3)
    T = 256
    tile = grain_tile(T, a.seed)
    amp = 22 * a.detail
    for Y in range(H):
        sy = (Y - 0.5) / 2
        y0 = max(0, min(h - 1, int(sy)))
        y1 = min(h - 1, y0 + 1)
        fy = max(0.0, min(1.0, sy - y0))
        r0, r1 = y0 * w * 3, y1 * w * 3
        trow = (Y % T) * T
        for X in range(W):
            sx = (X - 0.5) / 2
            x0 = max(0, min(w - 1, int(sx)))
            x1 = min(w - 1, x0 + 1)
            fx = max(0.0, min(1.0, sx - x0))
            q = (Y * W + X) * 3
            c = []
            for k in range(3):
                top = px[r0 + x0 * 3 + k] * (1 - fx) + px[r0 + x1 * 3 + k] * fx
                bot = px[r1 + x0 * 3 + k] * (1 - fx) + px[r1 + x1 * 3 + k] * fx
                c.append(top * (1 - fy) + bot * fy)
            mx, mn = max(c), min(c)
            line = mx > 150 and mx - mn < 40
            g = 0 if line else tile[trow + X % T] * amp * (0.6 + 0.4 * (c[1] / 255))
            out[q] = max(0, min(255, int(c[0] + g * 0.8)))
            out[q + 1] = max(0, min(255, int(c[1] + g)))
            out[q + 2] = max(0, min(255, int(c[2] + g * 0.6)))
    write_png(a.dst, W, H, out)
    print(f"{w}x{h} -> {W}x{H} -> {a.dst}")


if __name__ == "__main__":
    main()
