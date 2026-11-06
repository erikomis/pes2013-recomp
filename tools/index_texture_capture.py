#!/usr/bin/env python3
"""Index an existing runtime dump for manual texture identification, never install."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import struct

ROW = re.compile(r'^([0-9a-fA-F]{16})\s+(\d+)x\s*(\d+)\s+(\S+)\s+fmt (0x[0-9a-fA-F]+) loc (\d+) off (0x[0-9a-fA-F]+) frame (\d+)$')


def parse_row(line):
    match = ROW.fullmatch(line.strip())
    if not match:
        raise ValueError('Malformed texture index row: ' + line[:120])
    key, w, h, encoding, fmt, location, offset, frame = match.groups()
    return dict(key=key.lower(), width=int(w), height=int(h), encoding=encoding,
                format=int(fmt, 16), location=int(location), offset=offset, frame=int(frame))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('capture', type=Path, help='Directory containing textures.txt and PNGs')
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    directory = args.capture.resolve()
    if not directory.is_relative_to(root / 'analysis'):
        raise ValueError('Capture must be inside analysis/')
    records, errors, seen = [], [], set()
    for line in (directory / 'textures.txt').read_text().splitlines():
        if not line.strip():
            continue
        record = parse_row(line)
        if record['key'] in seen:
            continue
        seen.add(record['key'])
        path = directory / (record['key']+'.png')
        try:
            data = path.read_bytes()
            if data[:8] != b'\x89PNG\r\n\x1a\n' or data[12:16] != b'IHDR':
                raise ValueError('Invalid PNG header')
            if struct.unpack('>II', data[16:24]) != (record['width'], record['height']):
                raise ValueError('PNG dimensions differ from runtime index')
            record.update(sha256=hashlib.sha256(data).hexdigest(), club=None, slot=None,
                          identity_verified=False)
            records.append(record)
        except (OSError, ValueError, struct.error) as exc:
            errors.append(dict(key=record['key'], error=str(exc)))
    cards = []
    for r in sorted(records, key=lambda r: (r['width'] != 2*r['height'], -r['width']*r['height'])):
        key = r['key']
        cards.append(f'<figure><a href="{key}.png"><img loading="lazy" src="{key}.png"></a>'
                     f'<figcaption>{key}<br>{r["width"]}×{r["height"]} · {html.escape(r["encoding"])}'
                     f' · quadro {r["frame"]}</figcaption></figure>')
    (directory / 'review.html').write_text('<!doctype html><meta charset="utf-8"><title>Texturas capturadas</title>'
        '<style>body{background:#222;color:white;font:16px system-ui}main{display:flex;flex-wrap:wrap}'
        'figure{width:320px;margin:12px}img{max-width:100%;max-height:260px;object-fit:contain}</style>'
        '<h1>Texturas capturadas</h1><p>Identidade ainda não confirmada. Proporção 2:1 aparece primeiro; '
        'isso não prova que a imagem seja uma camisa. Nenhuma substituição ativada.</p><main>'
        + ''.join(cards) + '</main>')
    (directory / 'review.json').write_text(json.dumps(dict(textures=records, errors=errors,
        installed=False), indent=2)+'\n')
    print(f'{len(records)} textures; {len(errors)} errors; {directory / "review.html"}')
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
