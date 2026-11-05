#!/usr/bin/env python3
"""Rasterize UV-map probes to analysis only; not an installer or final converter."""
import argparse
import hashlib
import json
import math
from pathlib import Path

import ftex_convert as fc


def rasterize(rgba, sw, sh, pairs, width, height, flip_y=True):
    output = bytearray(width * height * 4)
    covered = bytearray(width * height)
    degenerate = 0
    def xy(uv, w, h):
        return uv[0] * w, (1 - uv[1] if flip_y else uv[1]) * h
    for pair in pairs:
        a, b, c = [xy(v, width, height) for v in pair['target_uvs']]
        src = [xy(v, sw, sh) for v in pair['source_uvs']]
        den = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(den) < 1e-10:
            degenerate += 1
            continue
        for y in range(max(0, math.floor(min(a[1], b[1], c[1]))),
                       min(height, math.ceil(max(a[1], b[1], c[1])))):
            for x in range(max(0, math.floor(min(a[0], b[0], c[0]))),
                           min(width, math.ceil(max(a[0], b[0], c[0])))):
                px, py = x + .5, y + .5
                wa = ((b[1]-c[1])*(px-c[0])+(c[0]-b[0])*(py-c[1]))/den
                wb = ((c[1]-a[1])*(px-c[0])+(a[0]-c[0])*(py-c[1]))/den
                wc = 1-wa-wb
                if min(wa, wb, wc) < -1e-7:
                    continue
                sx = min(sw-1, max(0, int(wa*src[0][0]+wb*src[1][0]+wc*src[2][0])))
                sy = min(sh-1, max(0, int(wa*src[0][1]+wb*src[1][1]+wc*src[2][1])))
                pos, sample = (y*width+x)*4, (sy*sw+sx)*4
                output[pos:pos+4] = rgba[sample:sample+4]
                covered[y*width+x] = 1
    return output, dict(covered_pixels=sum(covered), total_pixels=width*height,
                        degenerate_triangles=degenerate)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--club', default='Flamengo')
    ap.add_argument('--slot', choices=['p1', 'p2'], default='p1')
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    base = root / 'analysis/visual-2026'
    inventory = json.loads((base / 'coverage/kit_slots.json').read_text())
    club = next(c for c in inventory['clubs'] if c['club'] == args.club)
    slot = next(s for s in club['slots'] if s['slot'] == args.slot)
    source = root / slot['texture']
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != slot['sha256']:
        raise ValueError('Source hash mismatch')
    info = fc.read_ftex(source)
    info['data'] = raw
    rgba, sw, sh = fc.decode_frame_rgba(info, 0)
    mapping_path = base / 'kit-uv-map/pes2013-1024x512.json'
    mapping = json.loads(mapping_path.read_text())['data']
    if [sw, sh] != mapping['source_size']:
        raise ValueError('Source dimensions do not match map')
    width, height = mapping['target_size']
    # Use a fixed inventory-derived numeric directory, never a user-supplied path.
    out = base / 'kit-uv-probes' / f"club-{inventory['clubs'].index(club):02d}-{args.slot}"
    out.mkdir(parents=True, exist_ok=True)
    variants = []
    for flip in (True, False):
        pixels, stats = rasterize(rgba, sw, sh, mapping['triangle_pairs'], width, height, flip)
        filename = 'uv-bottom-left.png' if flip else 'uv-top-left.png'
        png = fc.encode_png_rgba(pixels, width, height)
        (out / filename).write_bytes(png)
        variants.append(dict(file=filename, sha256=hashlib.sha256(png).hexdigest(), **stats))
    record = dict(club=args.club, slot=args.slot, source=str(source.relative_to(root)),
                  source_sha256=slot['sha256'], map_sha256=hashlib.sha256(mapping_path.read_bytes()).hexdigest(),
                  size=[width, height], sampling='nearest_probe_only', variants=variants,
                  alpha='preserved_from_source', installed=False, ps3_verified=False,
                  note='Orientation alternatives. No collar/captain-armband postprocessing, seam padding or mip generation.')
    (out / 'manifest.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(record, ensure_ascii=False))


if __name__ == '__main__':
    main()
