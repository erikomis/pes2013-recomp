#!/usr/bin/env python3
"""Build a texture pack of 2026 faces from PES 2013 PC face files.

    build_face_pack.py EEDIT --faces face_files.json --capture DIR --clubs serie_a.json
                       --sources DIR --pack OUT_DIR [--width 512]

How it fits together:
- assign_unique_faces.py gave each player of face_files.json a face whose texture
  is his alone; the PS3 face texture is 256x512 DXT1.
- In Edit > Players, walking a club's list loads each player's face texture when
  his row is selected. A capture run with PS3_MODS_DUMP records, per row, the
  textures that appeared (DIR/rows_<club index>.json, clubs.json maps the index to
  the team id). Several runs may be given. A mapped player gets a key when
  exactly one 256x512 DXT1 texture was seen at his row and at no other player's
  row in any run (a late texture lands on the next row); otherwise he is
  reported and skipped.
- The PC face file (WESYS: zlib from +16, size at +12) holds a 1024x1024 or
  2048x2048 DDS in the same layout as the PS3 texture (which is half as wide as
  it is tall). Its first such DXT1/DXT5 image is box-filtered to WIDTH x 2*WIDTH
  (twice that for a 2048 source) and written as "<key>_<name>.png" in the pack
  (PS3_MODS_DIR / PS3_MODS).
"""
import argparse
import json
from pathlib import Path
import struct
import sys
import zipfile
import zlib
import unicodedata
import re

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pes2013_edit as edit  # noqa: E402

MAX_PAYLOAD = 64 * 1024 * 1024


def wesys_payload(data):
    if data[3:8] != b"WESYS":
        raise ValueError("not a WESYS file")
    size = struct.unpack_from("<I", data, 12)[0]
    if size > MAX_PAYLOAD:
        raise ValueError("payload too large")
    raw = zlib.decompressobj().decompress(data[16:], size)
    if len(raw) != size:
        raise ValueError("payload shorter than declared")
    return raw


def c565(c):
    return (((c >> 11) & 31) * 255 // 31, ((c >> 5) & 63) * 255 // 63, (c & 31) * 255 // 31)


def decode_dxt(buf, w, h, kind):
    out = bytearray(w * h * 3)
    o = 0
    for by in range(0, h, 4):
        for bx in range(0, w, 4):
            if kind == 5:
                o += 8
            c0, c1, idx = struct.unpack_from("<HHI", buf, o)
            o += 8
            p0, p1 = c565(c0), c565(c1)
            if c0 > c1 or kind == 5:
                pal = [p0, p1, tuple((2 * a + b) // 3 for a, b in zip(p0, p1)),
                       tuple((a + 2 * b) // 3 for a, b in zip(p0, p1))]
            else:
                pal = [p0, p1, tuple((a + b) // 2 for a, b in zip(p0, p1)), (0, 0, 0)]
            for i in range(16):
                q = ((by + i // 4) * w + bx + i % 4) * 3
                out[q:q + 3] = bytes(pal[(idx >> (2 * i)) & 3])
    return out


def face_texture(raw):
    at = raw.find(b"DDS ")
    while at >= 0:
        h, w = struct.unpack_from("<II", raw, at + 12)
        four = raw[at + 84:at + 88]
        kind = {b"DXT1": 1, b"DXT5": 5, b"DXT3": 5}.get(four)
        need = w * h // (2 if kind == 1 else 1)
        if kind and w == h and w in (1024, 2048) and at + 128 + need <= len(raw):
            return decode_dxt(raw[at + 128:], w, h, kind), w
        at = raw.find(b"DDS ", at + 4)
    raise ValueError("no 1024x1024 or 2048x2048 DXT face texture")


def resize(px, w, h, W, H):
    out = bytearray(W * H * 4)
    fx, fy = w // W, h // H
    n = fx * fy
    for y in range(H):
        for x in range(W):
            acc = [0, 0, 0]
            for yy in range(y * fy, y * fy + fy):
                base = (yy * w + x * fx) * 3
                for xx in range(fx):
                    q = base + xx * 3
                    acc[0] += px[q]; acc[1] += px[q + 1]; acc[2] += px[q + 2]
            o = (y * W + x) * 4
            out[o:o + 4] = bytes((acc[0] // n, acc[1] // n, acc[2] // n, 255))
    return out


def write_png(path, w, h, rgba):
    raw = b"".join(b"\0" + bytes(rgba[y * w * 4:(y + 1) * w * 4]) for y in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                           + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("eedit")
    ap.add_argument("--faces", required=True)
    ap.add_argument("--capture", required=True, action="append", help="capture run folder; may repeat")
    ap.add_argument("--clubs", required=True)
    ap.add_argument("--sources", required=True)
    ap.add_argument("--pack", required=True)
    ap.add_argument("--width", type=int, default=512, choices=(256, 512))
    a = ap.parse_args()
    dec = edit.decode(Path(a.eedit).read_bytes())
    rosters = {r["team_id"]: [m["player_id"] for m in r["members"]] for r in dec["rosters"]}
    # Every 256x512 DXT1 key seen at each player's row, over all capture runs. A
    # texture that finishes loading after the cursor moved lands on the next row,
    # so a key seen at more than one player's row belongs to none of them.
    sightings = {}
    for capdir in a.capture:
        for club in json.loads(Path(a.clubs).read_text(encoding="utf-8")):
            f = Path(capdir) / f"rows_{club['index']}.json"
            if not f.exists():
                continue
            members = rosters.get(club["team"], [])
            for row in json.loads(f.read_text(encoding="utf-8"))["rows"]:
                if row["row"] >= len(members):
                    continue
                pid = members[row["row"]]
                sightings.setdefault(pid, set())
                for t in row["textures"]:
                    if t[1] == "256x512" and t[2] == "DXT1":
                        sightings[pid].add(t[0])
    owners = {}
    for pid, keys in sightings.items():
        for k in keys:
            owners.setdefault(k, set()).add(pid)
    key_of, problems = {}, []
    for pid, keys in sightings.items():
        key_of[pid] = sorted(k for k in keys if owners[k] == {pid})
    faces = json.loads(Path(a.faces).read_text(encoding="utf-8"))["faces"]
    pack = Path(a.pack)
    pack.mkdir(parents=True, exist_ok=True)
    made = []
    src = Path(a.sources)
    for f in faces:
        keys = key_of.get(f["player_id"])
        if keys is None or len(keys) != 1:
            problems.append({"name": f["name"], "club": f["club"], "keys": keys})
            continue
        if f["member"]:
            with zipfile.ZipFile(src / f["archive"]) as zf:
                data = zf.read(f["member"])
        else:
            data = (src / f["archive"]).read_bytes()
        try:
            px, size = face_texture(wesys_payload(data))
        except ValueError as exc:
            problems.append({"name": f["name"], "club": f["club"], "error": str(exc)})
            continue
        out = pack / f"{keys[0]}_{slug(f['name'])}.png"
        width = a.width * size // 1024
        write_png(out, width, 2 * width, resize(px, size, size, width, 2 * width))
        made.append({"player_id": f["player_id"], "name": f["name"], "club": f["club"],
                     "key": keys[0], "file": out.name, "source": f["archive"]})
        print(f"{f['club'][:20]:20s} {f['name']:24s} {keys[0]}", flush=True)
    (pack / "pack.json").write_text(json.dumps({"faces": made, "skipped": problems},
                                               ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(made)} faces in {pack}; {len(problems)} skipped (see pack.json)")


if __name__ == "__main__":
    main()
