#!/usr/bin/env python3
"""Export experimental RGB5A1 face previews; never edit a save.

Offset 82 and 256x256 RGB layout are visual hypotheses. Alpha, metadata and
player links remain unverified. These previews are not replacement textures.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from uniform_texture import checksum, encode_png


def preview(data):
    if len(data) != 131172 or data[:4] != bytes.fromhex('0c000001'):
        raise ValueError('Unsupported face layout')
    if struct.unpack_from('>I', data, 8)[0] != checksum(data):
        raise ValueError('Face CRC mismatch')
    rgba = bytearray()
    for (pixel,) in struct.iter_unpack('>H', data[82:82 + 131072]):
        rgba.extend((((pixel >> 11) & 31) * 255 // 31,
                     ((pixel >> 6) & 31) * 255 // 31,
                     ((pixel >> 1) & 31) * 255 // 31, 255))
    return encode_png(rgba)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('savedata', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / 'analysis'
    dest = args.output.resolve()
    if not dest.is_relative_to(root) or dest == root:
        parser.error('Output must be a new directory beneath analysis/')
    files = sorted(args.savedata.glob('BLUS31029EFACE*/DATA.BIN'))
    if not files:
        parser.error('No face saves found')
    dest.mkdir(parents=True, exist_ok=False)
    rows = []
    for path in files:
        data = path.read_bytes()
        name = path.parent.name + '.png'
        (dest / name).write_bytes(preview(data))
        rows.append(dict(save=path.parent.name, source=str(path), preview=name,
                         sha256=hashlib.sha256(data).hexdigest(), player_id=None))
    (dest / 'index.json').write_text(json.dumps(dict(
        layout_status='experimental RGB5A1, offset 82; opaque preview',
        import_supported=False, player_links_verified=False, faces=rows), indent=2))
    cards = '\n'.join(f'<figure><img loading="lazy" src="{r["preview"]}" '
                      f'width="160" height="160"><figcaption>{r["save"]}</figcaption></figure>'
                      for r in rows)
    (dest / 'index.html').write_text('''<!doctype html><meta charset="utf-8">
<title>Faces existentes — revisão</title>
<style>body{font:16px system-ui;background:#17191d;color:#eee;padding:24px}
main{display:flex;flex-wrap:wrap}figure{margin:8px}figcaption{font-size:12px}</style>
<h1>Faces existentes</h1><p>Prévias experimentais. Jogadores ainda não identificados;
nenhuma face de 2026 instalada. Transparência não representada.</p><main>'''
                                  + cards + '</main>')
    print(f'{len(rows)} experimental face previews exported')


if __name__ == '__main__':
    main()
