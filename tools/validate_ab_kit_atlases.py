#!/usr/bin/env python3
"""Check generated atlases against inventory and PNG integrity, without game claims."""
import hashlib
import json
from pathlib import Path
import struct
import zlib


def check_png(data, width, height):
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('Bad PNG signature')
    pos, compressed, header, ended = 8, bytearray(), False, False
    while pos < len(data):
        if pos+12 > len(data):
            raise ValueError('Truncated PNG')
        size = struct.unpack('>I', data[pos:pos+4])[0]
        if pos+12+size > len(data):
            raise ValueError('Truncated chunk')
        kind = data[pos+4:pos+8]
        payload = data[pos+8:pos+8+size]
        crc = struct.unpack('>I', data[pos+8+size:pos+12+size])[0]
        if zlib.crc32(kind+payload)&0xffffffff != crc:
            raise ValueError('PNG CRC mismatch')
        if kind == b'IHDR':
            if header or pos != 8 or struct.unpack('>IIBBBBB', payload) != (width,height,8,6,0,0,0):
                raise ValueError('Unexpected PNG dimensions/encoding')
            header = True
        elif kind == b'IDAT':
            compressed.extend(payload)
        elif kind == b'IEND':
            if size or pos+12 != len(data):
                raise ValueError('Unexpected PNG ending')
            ended = True
        pos += size+12
    if not header or not ended:
        raise ValueError('Missing PNG header/end')
    expected = height*(width*4+1)
    decoder = zlib.decompressobj()
    raw = decoder.decompress(compressed, expected+1)
    if len(raw) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError('Incorrect decompressed PNG size')
    if any(raw[y*(width*4+1)] > 4 for y in range(height)):
        raise ValueError('Unknown PNG filter')


def main():
    root = Path(__file__).resolve().parents[1]
    base = root / 'analysis/visual-2026'
    directory = base / 'ab-kit-atlases'
    manifest = json.loads((directory / 'manifest.json').read_text())
    inventory = json.loads((base / 'coverage/kit_slots.json').read_text())
    expected = {(c['division'], c['club'], s['slot']): s for c in inventory['clubs']
                for s in c['slots'] if s['slot'] in ('p1', 'p2')}
    if not manifest['complete'] or manifest['errors'] or manifest['installed']:
        raise ValueError('Incomplete or unexpected manifest')
    seen = set()
    map_hash = hashlib.sha256((base / 'kit-uv-map/pes2013-1024x512.json').read_bytes()).hexdigest()
    for r in manifest['atlases']:
        key = (r['division'], r['club'], r['slot'])
        if key not in expected or key in seen:
            raise ValueError('Missing/duplicate/unknown slot')
        seen.add(key)
        src = expected[key]
        if r['source'] != src['texture'] or r['source_sha256'] != src['sha256'] or r['map_sha256'] != map_hash:
            raise ValueError('Source/map mismatch')
        if hashlib.sha256((root / r['source']).read_bytes()).hexdigest() != r['source_sha256']:
            raise ValueError('Source changed')
        if Path(r['png']).name != r['png']:
            raise ValueError('Nonlocal PNG path')
        png = (directory / r['png']).read_bytes()
        if hashlib.sha256(png).hexdigest() != r['png_sha256']:
            raise ValueError('PNG hash mismatch')
        check_png(png, r['width'], r['height'])
        if r['installed'] or r['ps3_verified']:
            raise ValueError('Unexpected installation claim')
    if seen != set(expected):
        raise ValueError('Incomplete coverage')
    result = dict(atlases=len(seen), clubs=len({k[:2] for k in seen}),
                  source_and_png_hashes_valid=True, png_crc_and_payload_valid=True,
                  installed=False, game_validation_pending=True)
    (directory / 'validation.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
