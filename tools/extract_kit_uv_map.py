#!/usr/bin/env python3
"""Read numeric UV data from the downloaded converter without executing its code."""
import hashlib
import io
import json
import math
from pathlib import Path
import pickle
import struct
import zlib


class DType:
    def __init__(self, code, *args):
        if code != 'f8':
            raise ValueError('Only float64 UV coordinates supported')

    def __setstate__(self, state):
        if state != (3, '<', None, None, None, -1, -1, 0):
            raise ValueError('Unexpected dtype state')


class Array:
    def __setstate__(self, state):
        version, shape, dtype, fortran, raw = state
        if version != 1 or shape != (3, 2) or not isinstance(dtype, DType) or fortran or len(raw) != 48:
            raise ValueError('Unexpected triangle array')
        values = struct.unpack('<6d', raw)
        if not all(math.isfinite(x) for x in values):
            raise ValueError('Nonfinite UV')
        self.values = [list(values[i:i+2]) for i in range(0, 6, 2)]


def reconstruct(cls, shape, code):
    if cls is not Array or shape != (0,) or code != b'b':
        raise ValueError('Unexpected reconstruction')
    return Array()


class NumericOnly(pickle.Unpickler):
    def find_class(self, module, name):
        # Map to our local data-only objects; never import a class from the file.
        allowed = {('numpy._core.multiarray', '_reconstruct'): reconstruct,
                   ('numpy', 'ndarray'): Array, ('numpy', 'dtype'): DType}
        if (module, name) not in allowed:
            raise ValueError(f'Unsupported global {module}.{name}')
        return allowed[module, name]


def member(blob, wanted):
    cookie = blob.rfind(b'MEI\x0c\x0b\x0a\x0b\x0e')
    if cookie < 0:
        raise ValueError('Missing archive cookie')
    _, size, offset, length, _, _ = struct.unpack('!8sIIII64s', blob[cookie:cookie+88])
    base = cookie + 88 - size
    pos, end = base + offset, base + offset + length
    if not 0 <= base <= pos <= end <= cookie:
        raise ValueError('Invalid archive bounds')
    while pos < end:
        n, off, packed, unpacked, compressed, kind = struct.unpack('!IIIIBc', blob[pos:pos+18])
        if n < 18 or pos+n > end:
            raise ValueError('Invalid table entry')
        name = blob[pos+18:pos+n].rstrip(b'\0').decode()
        pos += n
        if name != wanted:
            continue
        if unpacked > 2_000_000 or base+off+packed > base+offset:
            raise ValueError('Invalid member bounds')
        raw = blob[base+off:base+off+packed]
        if compressed:
            decoder = zlib.decompressobj()
            raw = decoder.decompress(raw, unpacked+1)
            if not decoder.eof or decoder.unconsumed_tail or decoder.unused_data:
                raise ValueError('Invalid compressed data')
        if len(raw) != unpacked:
            raise ValueError('Size mismatch')
        return raw
    raise ValueError('Missing UV member')


def main():
    base = Path(__file__).resolve().parents[1] / 'analysis/visual-2026'
    exe = (base / 'pes21_kit_converter_v3.exe').read_bytes()
    expected = json.loads((base / 'converter_inventory.json').read_text())['sha256']
    if hashlib.sha256(exe).hexdigest() != expected:
        raise ValueError('Converter hash changed')
    name = 'triangles_pes2013_1024x512.pkl'
    data = member(exe, name)
    decoded = NumericOnly(io.BytesIO(data)).load()
    def plain(value):
        if isinstance(value, Array):
            return value.values
        if isinstance(value, dict):
            return {k: plain(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [plain(v) for v in value]
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        raise ValueError('Unexpected object')
    result = dict(source_exe_sha256=expected, member=name,
                  member_sha256=hashlib.sha256(data).hexdigest(),
                  executable_run=False, game_compatibility_verified=False, data=plain(decoded))
    out = base / 'kit-uv-map'
    out.mkdir(exist_ok=True)
    (out / 'pes2013-1024x512.json').write_text(json.dumps(result, separators=(',', ':'))+'\n')
    print('Extracted numeric map:', {k: len(v) if isinstance(v, list) else v for k,v in result['data'].items()})


if __name__ == '__main__':
    main()
