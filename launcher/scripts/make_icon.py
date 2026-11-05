#!/usr/bin/env python3
# Regenerate the placeholder icon: python3 scripts/make_icon.py src-tauri/icons/app-icon.png
# then: npx tauri icon src-tauri/icons/app-icon.png
# An original placeholder (no game art, no logo, no club or competition mark): a
# plain football (a white ball with a dark centre pentagon and five edge
# patches) on a pitch-green rounded square. Standard library only.
import math, struct, sys, zlib

N = 1024
C = N / 2
R = 330  # the ball's radius


def rr(px, py, r=200, m=40):
    x0, y0, x1, y1 = m, m, N - m, N - m
    cx = min(max(px, x0 + r), x1 - r)
    cy = min(max(py, y0 + r), y1 - r)
    return (px - cx) ** 2 + (py - cy) ** 2 <= r * r and x0 <= px <= x1 and y0 <= py <= y1


def polygon(cx, cy, rad, rot):
    return [(cx + rad * math.cos(rot + k * 2 * math.pi / 5), cy + rad * math.sin(rot + k * 2 * math.pi / 5)) for k in range(5)]


def inside(pts, x, y):
    n, hit = len(pts), False
    for i in range(n):
        (ax, ay), (bx, by) = pts[i], pts[(i + 1) % n]
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            hit = not hit
    return hit


UP = -math.pi / 2
CENTRE = polygon(C, C, 118, UP)
# five patches pushed out along the centre pentagon's corners, cut by the ball's edge
EDGE = [polygon(C + 300 * math.cos(UP + k * 2 * math.pi / 5), C + 300 * math.sin(UP + k * 2 * math.pi / 5), 110, UP + k * 2 * math.pi / 5 + math.pi) for k in range(5)]


def ball(px, py):
    """0 outside the ball, 1 white, 2 dark (a patch, a seam or the rim)."""
    d = math.hypot(px - C, py - C)
    if d > R:
        return 0
    if d > R - 16:
        return 2
    if inside(CENTRE, px, py) or any(inside(p, px, py) for p in EDGE):
        return 2
    # seams from the centre pentagon's corners to the edge patches
    for k in range(5):
        a = UP + k * 2 * math.pi / 5
        ax, ay = CENTRE[k]
        bx, by = C + 190 * math.cos(a), C + 190 * math.sin(a)
        t = max(0.0, min(1.0, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / ((bx - ax) ** 2 + (by - ay) ** 2)))
        if math.hypot(px - (ax + t * (bx - ax)), py - (ay + t * (by - ay))) <= 9:
            return 2
    return 1


S = [(0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75)]
rows = []
for y in range(N):
    row = bytearray([0])
    for x in range(N):
        a = 0
        col = [0.0, 0.0, 0.0]
        for sx, sy in S:
            px, py = x + sx, y + sy
            if not rr(px, py):
                continue
            a += 1
            t = y / N
            # pitch green, darker below, with faint mowing stripes
            stripe = 6 if int(py / 128) % 2 else 0
            bg = (24 - 10 * t + stripe, 96 - 40 * t + stripe, 58 - 24 * t + stripe)
            k = ball(px, py)
            c = bg if k == 0 else (236, 240, 236) if k == 1 else (22, 28, 26)
            for i in range(3):
                col[i] += c[i]
        if a == 0:
            row += b"\0\0\0\0"
            continue
        row += bytes([int(col[0] / a), int(col[1] / a), int(col[2] / a), int(255 * a / 4)])
    rows.append(bytes(row))


def chunk(t, d):
    return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)


png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", N, N, 8, 6, 0, 0, 0))
       + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b""))
open(sys.argv[1], "wb").write(png)
