#!/usr/bin/env python3
"""Export/import observed PES 2013 PS3 uniform overlays in isolated copies.

This is a 256x256 RGBA overlay, NOT a full kit atlas or an HD renderer mod.
Only the inspected 262179-byte format is supported. Originals are read-only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import zlib

SIZE = 262179
PIXELS = 256 * 256 * 4
MAGIC = b"\x89PNG\r\n\x1a\n"


def checksum(data):
    return zlib.crc32(data[:8] + bytes(4) + data[12:])


def validate(data):
    if len(data) != SIZE or data[:4] != bytes.fromhex("0d000001") or data[32] != 1:
        raise ValueError("Unsupported uniform save layout")
    if struct.unpack_from(">I", data, 8)[0] != checksum(data):
        raise ValueError("Uniform save CRC32 mismatch")


def png_chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def encode_png(rgba):
    if len(rgba) != PIXELS:
        raise ValueError("Expected 256x256 RGBA pixels")
    rows = b"".join(b"\0" + rgba[y * 1024:(y + 1) * 1024] for y in range(256))
    return (MAGIC + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 256, 256, 8, 6, 0, 0, 0))
            + png_chunk(b"IDAT", zlib.compress(rows)) + png_chunk(b"IEND", b""))


def decode_png(data):
    if not data.startswith(MAGIC):
        raise ValueError("Not a PNG")
    offset, compressed, seen_header, ended = 8, bytearray(), False, False
    while offset + 12 <= len(data):
        size = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4:offset + 8]
        end = offset + 8 + size
        if end + 4 > len(data):
            raise ValueError("Truncated PNG chunk")
        payload = data[offset + 8:end]
        if zlib.crc32(kind + payload) != struct.unpack_from(">I", data, end)[0]:
            raise ValueError("PNG chunk CRC mismatch")
        if not seen_header and kind != b"IHDR":
            raise ValueError("PNG must begin with IHDR")
        if kind == b"IHDR":
            if seen_header or payload != struct.pack(">IIBBBBB", 256, 256, 8, 6, 0, 0, 0):
                raise ValueError("Only non-interlaced 256x256 RGBA8 PNG is supported")
            seen_header = True
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            if size:
                raise ValueError("Invalid IEND")
            ended = True
            offset = end + 4
            break
        elif not kind[0] & 32 and kind != b"PLTE":
            raise ValueError("Unsupported critical PNG chunk")
        offset = end + 4
    if not ended or offset != len(data):
        raise ValueError("Missing IEND or trailing PNG data")
    decoder = zlib.decompressobj()
    raw = decoder.decompress(compressed, 256 * 1025 + 1)
    if len(raw) != 256 * 1025 or not decoder.eof or decoder.unused_data:
        raise ValueError("Invalid PNG decompressed length")
    pixels = bytearray()
    previous = bytes(1024)
    for y in range(256):
        start = y * 1025
        filter_type = raw[start]
        if filter_type > 4:
            raise ValueError("Invalid PNG row filter")
        row = bytearray(raw[start + 1:start + 1025])
        for x in range(1024):
            left = row[x - 4] if x >= 4 else 0
            above = previous[x]
            corner = previous[x - 4] if x >= 4 else 0
            if filter_type == 1:
                prediction = left
            elif filter_type == 2:
                prediction = above
            elif filter_type == 3:
                prediction = (left + above) // 2
            elif filter_type == 4:
                p = left + above - corner
                distances = (abs(p - left), abs(p - above), abs(p - corner))
                prediction = (left, above, corner)[distances.index(min(distances))]
            else:
                prediction = 0
            row[x] = (row[x] + prediction) & 255
        pixels.extend(row)
        previous = row
    return bytes(pixels)


def replace_pixels(data, rgba):
    validate(data)
    if len(rgba) != PIXELS:
        raise ValueError("Expected 256x256 RGBA pixels")
    output = bytearray(data)
    output[33:33 + PIXELS] = rgba
    struct.pack_into(">I", output, 8, checksum(output))
    validate(output)
    return bytes(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["export", "stage"])
    parser.add_argument("save", type=Path)
    parser.add_argument("--png", type=Path, required=True)
    parser.add_argument("--output-save", type=Path)
    args = parser.parse_args()
    original = (args.save / "DATA.BIN").read_bytes()
    validate(original)
    if args.mode == "export":
        with args.png.open("xb") as stream:
            stream.write(encode_png(original[33:33 + PIXELS]))
        return
    if args.output_save is None:
        parser.error("stage requires --output-save (new directory under analysis/)")
    destination = args.output_save.resolve()
    staging_root = Path(__file__).resolve().parent.parent / "analysis"
    if not destination.is_relative_to(staging_root) or destination == args.save.resolve():
        parser.error("Staging output must be a new directory under this project's analysis/")
    modified = replace_pixels(original, decode_png(args.png.read_bytes()))
    # copytree fails on an existing destination. No overwrite or save activation.
    shutil.copytree(args.save, destination, symlinks=False)
    (destination / "DATA.BIN").write_bytes(modified)
    (destination / "TEXTURE_CHANGE.json").write_text(json.dumps(dict(
        source=str(args.save.resolve()), source_sha256=hashlib.sha256(original).hexdigest(),
        output_sha256=hashlib.sha256(modified).hexdigest(), size=[256, 256],
        installed=False, game_tested=False, preview="ICON0 is the unchanged source preview"), indent=2) + "\n")


if __name__ == "__main__":
    main()
