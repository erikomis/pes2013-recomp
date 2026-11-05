#!/usr/bin/env python3
"""Read-only AFS/ADX catalogue; export selected original clips for comparison."""
import argparse
import json
import struct
from pathlib import Path


def catalogue(path):
    size = path.stat().st_size
    with path.open('rb') as stream:
        header = stream.read(8)
        if len(header) != 8 or header[:4] != b'AFS\0':
            raise ValueError('Not an AFS archive')
        count = struct.unpack('<I', header[4:])[0]
        if count > (size - 8) // 8:
            raise ValueError('Invalid AFS table size')
        table = [struct.unpack('<II', stream.read(8)) for _ in range(count)]
        rows = []
        for slot, (offset, length) in enumerate(table):
            if offset + length > size or (length and offset < 8 + count * 8):
                raise ValueError(f'Invalid bounds in slot {slot}')
            row = dict(slot=slot, offset=offset, size=length)
            if length:
                stream.seek(offset)
                data = stream.read(min(256, length))
                if len(data) >= 20 and data[:2] == b'\x80\0':
                    rate, samples = struct.unpack('>II', data[8:16])
                    row.update(codec='ADX', channels=data[7], sample_rate=rate,
                               samples=samples, seconds=samples / rate if rate else None)
                    marker = data.find(b'AINF')
                    if marker >= 0:
                        row['internal_name'] = data[marker + 8:marker + 24].split(b'\0')[0].decode('ascii', 'replace')
                else:
                    row['codec'] = 'unknown'
            rows.append(row)
    return dict(source=str(path.resolve()), archive_bytes=size, entries=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--output', type=Path, required=True,
                        help='New directory beneath project analysis/')
    parser.add_argument('--sample-slots', type=int, nargs='*', default=[])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / 'analysis'
    output = args.output.resolve()
    if not output.is_relative_to(root.resolve()) or output == root.resolve():
        parser.error('Output must be a new directory beneath project analysis/')
    result = catalogue(args.archive)
    selected = []
    for slot in args.sample_slots:
        if not 0 <= slot < len(result['entries']):
            parser.error(f'Invalid slot: {slot}')
        row = result['entries'][slot]
        if row.get('codec') != 'ADX':
            parser.error(f'Slot {slot} is not ADX')
        selected.append(row)
    output.mkdir(parents=True, exist_ok=False)
    with args.archive.open('rb') as stream:
        for row in selected:
            stream.seek(row['offset'])
            (output / f"slot-{row['slot']:05d}.adx").write_bytes(stream.read(row['size']))
    (output / 'inventory.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(entries=len(result['entries']),
                          adx=sum(r.get('codec') == 'ADX' for r in result['entries']),
                          exported=len(selected), output=str(output))))


if __name__ == '__main__':
    main()
