#!/usr/bin/env python3
"""Inventory PS3 Option File visual assets without modifying saves.

ICON0.PNG is a preview, not the actual texture. Raw DATA.BIN pixel layouts are
not inferred from byte length. Outputs are local, game-derived evidence.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import zlib


def inspect(root):
    assets = []
    for folder in sorted(root.iterdir()):
        path = folder / "DATA.BIN"
        if not folder.is_dir() or not path.is_file():
            continue
        category = next((kind for prefix, kind in (
            ("BLUS31029EUNIFORM", "uniform"), ("BLUS31029EFACE", "face"),
            ("BLUS31029EST_", "stadium"), ("BLUS31029ELCEM", "competition_emblem"))
            if folder.name.startswith(prefix)), None)
        if category is None:
            continue
        data = path.read_bytes()
        if len(data) < 12:
            raise ValueError(f"Truncated visual save: {path}")
        checksum = zlib.crc32(data[:8] + bytes(4) + data[12:])
        icon = next((p for p in folder.iterdir() if p.name.lower() == "icon0.png"), None)
        preview = None
        if icon:
            header = icon.read_bytes()[:24]
            if header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR":
                width, height = struct.unpack(">II", header[16:24])
                preview = dict(path=str(icon), width=width, height=height)
        assets.append(dict(save=folder.name, category=category, data_path=str(path),
                           bytes=len(data), header_hex=data[:32].hex(),
                           sha256=hashlib.sha256(data).hexdigest(),
                           crc32_valid=checksum == struct.unpack_from(">I", data, 8)[0],
                           preview=preview, texture_layout="unmapped",
                           season="unverified", replacement_installed=False))
    return dict(assets=assets, counts=dict(Counter(a["category"] for a in assets)),
                invalid_crc32=sum(not a["crc32_valid"] for a in assets),
                note="Preview dimensions are not texture dimensions. No HD replacement is installed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("savedata", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.savedata), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
