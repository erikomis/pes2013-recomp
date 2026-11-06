#!/usr/bin/env python3
"""Put 2026 sponsor boards on the stadium creator's ad boards, in a profile copy.

    make_fence_2026.py SAVEDATA --boards DIR --pick fences.json [--preview OUT.png]

SAVEDATA is a profile's savedata folder (never the owner's own tree). Its
BLUS31029EST_FENCE<nnn> saves are the ad boards and banners of the 20 stadiums
built with the stadium creator: a 49-byte header (CRC32 at +8 over the file with
those 4 bytes zeroed, as the uniform saves), then a DDS: 512x256 DXT5 with its 10
mip levels. A board is the opaque band of the image (rows 84..170 on most, the
whole image on some); the rest is transparent.

fences.json lists the saves to change ({"fences": ["BLUS31029EST_FENCE011", ...]})
- boards, not supporters' banners or club flags, chosen by looking at them. In
each, the band is refilled with 2026 board art from DIR (PNG, converted from the
Brasileirão 2025/26 adboard pack): three 2:1 sponsor tiles, or the
"BRASILEIRÃO Betano" banner across the band, alternating. Pixels outside the band
stay; the image is encoded to DXT5 again with every mip level, the CRC is
recomputed, and each changed save is decoded back and checked.
"""
import argparse
import json
from pathlib import Path
import struct
import sys
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_hd_pitch import read_png  # noqa: E402  (8-bit RGB/RGBA PNG reader)

W, H, MIPS = 512, 256, 10


def checksum(data):
    return zlib.crc32(data[:8] + bytes(4) + data[12:])


# ---- DXT5 ------------------------------------------------------------------
def c565(c):
    return (((c >> 11) & 31) * 255 // 31, ((c >> 5) & 63) * 255 // 63, (c & 31) * 255 // 31)


def to565(r, g, b):
    return ((r * 31 + 127) // 255) << 11 | ((g * 63 + 127) // 255) << 5 | ((b * 31 + 127) // 255)


def decode_dxt5(buf, w, h):
    out = bytearray(w * h * 4)
    o = 0
    for by in range(0, h, 4):
        for bx in range(0, w, 4):
            a0, a1 = buf[o], buf[o + 1]
            bits = int.from_bytes(buf[o + 2:o + 8], "little")
            al = [a0, a1] + ([((6 - i) * a0 + i * a1) // 6 for i in range(1, 7)] if a0 > a1
                             else [((4 - i) * a0 + i * a1) // 4 for i in range(1, 5)] + [0, 255])
            c0, c1, idx = struct.unpack_from("<HHI", buf, o + 8)
            p0, p1 = c565(c0), c565(c1)
            pal = [p0, p1, tuple((2 * a + b) // 3 for a, b in zip(p0, p1)), tuple((a + 2 * b) // 3 for a, b in zip(p0, p1))]
            for i in range(16):
                x, y = bx + i % 4, by + i // 4
                if x < w and y < h:
                    q = (y * w + x) * 4
                    out[q:q + 3] = bytes(pal[(idx >> (2 * i)) & 3])
                    out[q + 3] = al[(bits >> (3 * i)) & 7]
            o += 16
    return out


def encode_dxt5(px, w, h):
    out = bytearray()
    for by in range(0, max(h, 4), 4):
        for bx in range(0, max(w, 4), 4):
            blk = []
            for i in range(16):
                x, y = min(bx + i % 4, w - 1), min(by + i // 4, h - 1)
                q = (y * w + x) * 4
                blk.append(tuple(px[q:q + 4]))
            # alpha: 8-level ramp between the block's max and min
            amax, amin = max(p[3] for p in blk), min(p[3] for p in blk)
            if amax == amin:
                abits, a0, a1 = 0, amax, amin
            else:
                a0, a1 = amax, amin
                ramp = [a0, a1] + [((6 - i) * a0 + i * a1) // 6 for i in range(1, 7)]
                abits = 0
                for i, p in enumerate(blk):
                    k = min(range(8), key=lambda j: abs(ramp[j] - p[3]))
                    abits |= k << (3 * i)
            # colour: the two most distant colours as endpoints
            best, e0, e1 = -1, blk[0], blk[0]
            for i in range(16):
                for j in range(i + 1, 16):
                    d = sum((blk[i][k] - blk[j][k]) ** 2 for k in range(3))
                    if d > best:
                        best, e0, e1 = d, blk[i], blk[j]
            c0, c1 = to565(*e0[:3]), to565(*e1[:3])
            if c0 < c1:
                c0, c1 = c1, c0
            if c0 == c1:
                idx = 0
            else:
                p0, p1 = c565(c0), c565(c1)
                pal = [p0, p1, tuple((2 * a + b) // 3 for a, b in zip(p0, p1)), tuple((a + 2 * b) // 3 for a, b in zip(p0, p1))]
                idx = 0
                for i, p in enumerate(blk):
                    k = min(range(4), key=lambda j: sum((pal[j][m] - p[m]) ** 2 for m in range(3)))
                    idx |= k << (2 * i)
            out += bytes((a0, a1)) + abits.to_bytes(6, "little") + struct.pack("<HHI", c0, c1, idx)
    return bytes(out)


def half(px, w, h):
    nw, nh = max(1, w // 2), max(1, h // 2)
    out = bytearray(nw * nh * 4)
    for y in range(nh):
        for x in range(nw):
            acc = [0, 0, 0, 0]
            n = 0
            for dy in (0, 1):
                for dx in (0, 1):
                    sx, sy = min(w - 1, 2 * x + dx), min(h - 1, 2 * y + dy)
                    q = (sy * w + sx) * 4
                    for k in range(4):
                        acc[k] += px[q + k]
                    n += 1
            out[(y * nw + x) * 4:(y * nw + x) * 4 + 4] = bytes(v // n for v in acc)
    return out, nw, nh


# ---- art -------------------------------------------------------------------
def load_rgba(path):
    w, h, rgb = read_png(path)
    px = bytearray(w * h * 4)
    for i in range(w * h):
        px[i * 4:i * 4 + 3] = rgb[i * 3:i * 3 + 3]
        px[i * 4 + 3] = 255
    return w, h, px


def crop_resize(src, sw, sh, box, tw, th):
    x0, y0, x1, y1 = box
    out = bytearray(tw * th * 4)
    for y in range(th):
        sy = y0 + (y * (y1 - y0)) // th
        for x in range(tw):
            sx = x0 + (x * (x1 - x0)) // tw
            q = (sy * sw + sx) * 4
            out[(y * tw + x) * 4:(y * tw + x) * 4 + 4] = src[q:q + 4]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("savedata")
    ap.add_argument("--boards", required=True)
    ap.add_argument("--pick", required=True)
    ap.add_argument("--preview")
    a = ap.parse_args()
    sd = Path(a.savedata)
    if "rpcs3" in sd.resolve().parts:
        sys.exit("refusing to write into the owner's rpcs3 tree; use a profile copy")
    boards = Path(a.boards)
    # 90systemAd_face_09: 2x2 square cells (Betano, Assai, Sicoob, Betnacional); each
    # logo sits on its cell's middle half, which is the 2:1 tile used here.
    bw, bh, quad = load_rgba(boards / "90systemAd_face_09_bsm.png")
    hw, hh = bw // 2, bh // 2
    tiles = [crop_resize(quad, bw, bh, (x * hw, y * hh + hh // 4, (x + 1) * hw, y * hh + 3 * hh // 4), 256, 128)
             for y in (0, 1) for x in (0, 1)]
    rw, rh, br = load_rgba(boards / "BR25.png")              # the "BRASILEIRAO Betano" banner, 8:1
    banner = crop_resize(br, rw, rh, (0, 0, rw, rh), 512, 64)

    picks = json.loads(Path(a.pick).read_text(encoding="utf-8"))["fences"]
    previews = []
    for n, name in enumerate(picks):
        f = sd / name / "DATA.BIN"
        data = f.read_bytes()
        at = data.find(b"DDS ")
        if at != 49 or struct.unpack_from("<II", data, at + 12) != (H, W) or data[at + 84:at + 88] != b"DXT5":
            raise SystemExit(f"{name}: not the 512x256 DXT5 layout")
        if struct.unpack_from(">I", data, 8)[0] != checksum(data):
            raise SystemExit(f"{name}: CRC does not match before the change")
        px = decode_dxt5(data[at + 128:], W, H)
        rows = [sum(1 for x in range(W) if px[(y * W + x) * 4 + 3] > 128) for y in range(H)]
        band = [y for y, c in enumerate(rows) if c > W * 0.3]
        if not band or band[-1] - band[0] < 16:
            print(f"{name}: no board band, skipped")
            continue
        y0, y1 = band[0], band[-1] + 1
        bh_ = y1 - y0
        # cells: three 2:1 tiles, or banner + tile, on the band's width
        if n % 2 and bh_ * 6 >= W * 0.8:
            cells = [(0, W, banner, 512, 64)]
        else:
            k = max(1, round(W / (2 * bh_)))
            cells = [(i * W // k, (i + 1) * W // k, tiles[(n + i) % 4], 256, 128) for i in range(k)]
        for cx0, cx1, art, aw, ah in cells:
            cw = cx1 - cx0
            for y in range(bh_):
                sy = y * ah // bh_
                for x in range(cw):
                    sx = x * aw // cw
                    q = (sy * aw + sx) * 4
                    o = ((y0 + y) * W + cx0 + x) * 4
                    px[o:o + 3] = art[q:q + 3]
                    px[o + 3] = 255
        levels, lw, lh, cur = [], W, H, px
        for _ in range(MIPS):
            levels.append(encode_dxt5(cur, lw, lh))
            if lw == 1 and lh == 1:
                break
            cur, lw, lh = half(cur, lw, lh)
        body = b"".join(levels)
        if len(body) != len(data) - at - 128:
            raise SystemExit(f"{name}: mip chain size {len(body)} differs from {len(data) - at - 128}")
        out = bytearray(data[:at + 128] + body)
        struct.pack_into(">I", out, 8, checksum(out))
        back = decode_dxt5(bytes(out[at + 128:]), W, H)
        if struct.unpack_from(">I", out, 8)[0] != checksum(out) or len(back) != W * H * 4:
            raise SystemExit(f"{name}: check failed")
        f.write_bytes(out)
        previews.append(back)
        print(f"{name}: band {y0}..{y1 - 1}, {len(cells)} cells", flush=True)
    if a.preview and previews:
        tw, th, cols = 256, 128, 4
        rows_ = (len(previews) + cols - 1) // cols
        sheet = bytearray(tw * cols * th * rows_ * 3)
        for i, p in enumerate(previews):
            for y in range(th):
                for x in range(tw):
                    q = ((2 * y) * W + 2 * x) * 4
                    o = (((i // cols) * th + y) * tw * cols + (i % cols) * tw + x) * 3
                    sheet[o:o + 3] = p[q:q + 3]
        from make_hd_pitch import write_png
        write_png(a.preview, tw * cols, th * rows_, sheet)
    print(f"{len(previews)} boards written in {sd}")


if __name__ == "__main__":
    main()
