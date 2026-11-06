#!/usr/bin/env python3
"""Paint the 2026 Brasileirão ball (Nike Control) over PES 2013's default ball texture.

    make_ball_2026.py --base BALL.png --crest CBF.png --out OUT.png [--dark DARK.png --out-dark OUT2.png]

BALL.png is the default ball as PS3_MODS_DUMP wrote it (512x512: a band across the
upper half that wraps the ball, the rest plain). The 2026 ball, from photos: white,
small blue hexagonal dots all over, three larger panels shading from blue to yellow,
the CBF crest, a green swoosh and three short yellow ticks. This draws that at
1024x1024 on the same layout: the dots everywhere, the panels and the crest in the
band where the PES logo was, the swoosh below it. It is a drawing from photos, not
Nike's artwork.

The game also loads a darker copy of the same ball (another light setup); with
--dark, the drawing is darkened per channel by the ratio between the two dumps'
plain areas and written to OUT2.
"""
import argparse
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_hd_pitch import read_png, write_png  # noqa: E402

S = 1024
WHITE = (238, 241, 245)
BLUE = (38, 152, 224)
BLUE_D = (20, 110, 200)
YELLOW = (244, 214, 18)
GREEN = (24, 160, 72)


def hexagon(cx, cy, r, x, y):
    dx, dy = abs(x - cx), abs(y - cy)
    return dy <= r * 0.866 and 0.866 * dx + 0.5 * dy <= r * 0.866


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", required=True)
    ap.add_argument("--crest", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dark")
    ap.add_argument("--out-dark")
    a = ap.parse_args()
    img = bytearray(bytes(WHITE) * (S * S))

    def put(x, y, c):
        if 0 <= x < S and 0 <= y < S:
            img[(y * S + x) * 3:(y * S + x) * 3 + 3] = bytes(c)

    def fill_hex(cx, cy, r, colour):
        for y in range(int(cy - r), int(cy + r) + 1):
            for x in range(int(cx - r), int(cx + r) + 1):
                if hexagon(cx, cy, r, x, y):
                    c = colour(x, y) if callable(colour) else colour
                    put(x % S, y, c)

    rnd = random.Random(2026)
    # small blue dots on a jittered grid (x wraps: the texture wraps the ball)
    step = 92
    for gy in range(0, S, step):
        for gx in range(0, S, step):
            cx = gx + step / 2 + rnd.uniform(-18, 18) + (step / 2 if (gy // step) % 2 else 0)
            cy = gy + step / 2 + rnd.uniform(-18, 18)
            fill_hex(cx, cy, rnd.uniform(16, 26), BLUE)
    # three large gradient panels in the band (y 80..480 at 1024)
    def grad(top, bottom):
        def f(x, y):
            t = max(0.0, min(1.0, (y - top) / (bottom - top)))
            return tuple(int(BLUE_D[k] * (1 - t) + YELLOW[k] * t) for k in range(3))
        return f
    for cx, cy in ((330, 350), (512, 410), (694, 350)):
        fill_hex(cx, cy, 86, grad(cy - 86, cy + 86))
    # crest where the PES logo was (centre of the band)
    cw, ch, crest = read_png(a.crest)
    tw = 150
    th = int(ch * tw / cw)
    x0, y0 = 512 - tw // 2, 160 - th // 2
    for y in range(th):
        for x in range(tw):
            q = ((y * ch // th) * cw + x * cw // tw) * 3
            c = crest[q:q + 3]
            if 24 < sum(c) < 3 * 245:  # drop the transparent (read as black) and white background
                put(x0 + x, y0 + y, c)
    # three short yellow ticks above the crest
    for k, ang in enumerate((-0.5, 0.0, 0.5)):
        for t in range(40):
            for w in range(-3, 4):
                x = int(512 + math.sin(ang) * (60 + t) + w * math.cos(ang))
                y = int(100 - math.cos(ang) * (t - 10))
                put(x, y, YELLOW)
    # green swoosh under the panels: a short hook, then a body that rises and thins to a tip
    for x in range(560, 880):
        u = (x - 560) / 320
        yc = 600 - 120 * u ** 1.4 + 40 * (1 - u) ** 6
        half = max(2.0, 22 * (1 - u) ** 0.8 * (1 - math.exp(-u * 18)))
        for y in range(int(yc - half), int(yc + half) + 1):
            put(x, y, GREEN)
    write_png(a.out, S, S, img)
    print(f"-> {a.out}")
    if a.dark and a.out_dark:
        bw, bh, base = read_png(a.base)
        dw, dh, dark = read_png(a.dark)
        ratio = []
        for k in range(3):
            sb = sd = 0
            for y in range(bh * 3 // 5, bh * 4 // 5):
                for x in range(0, bw // 2):
                    sb += base[(y * bw + x) * 3 + k]
                    sd += dark[(y * dw + x) * 3 + k]
            ratio.append(sd / max(1, sb))
        out = bytearray(len(img))
        for i in range(0, len(img), 3):
            for k in range(3):
                out[i + k] = min(255, int(img[i + k] * ratio[k]))
        write_png(a.out_dark, S, S, out)
        print(f"-> {a.out_dark} (ratio {', '.join(f'{r:.2f}' for r in ratio)})")


if __name__ == "__main__":
    main()
