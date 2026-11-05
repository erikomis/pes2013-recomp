"""Convert Kitserver .ftex textures (PES 2019-2021 era) to PNG.

Pure stdlib (struct + zlib). Decodes the Fox Engine FTEX container:
64-byte header, then one 16-byte record per mipmap
    <offset:u32> <uncompressed:u32> <compressed:u32> <index:u8> <ftexs:u8> <chunks:u16>
Data offsets are relative to the end of the mipmap table. Mip payloads are
raw, one zlib blob, or an array of locally-zlib chunks described by
    <compressed:u16> <uncompressed:u16> <offset:u32>  (bit31 of offset = raw)

Pixel formats 0 RGBA8888 / 1 R8 / 2 BC1 / 3 BC2 / 4 BC3 / 8 BC4 / 9 BC5.
BC6H and BC7 (formats 10/11) are rejected explicitly.

Derived-data policy: outputs go to analysis/ (default) and are never
committed. Never writes inside the source kitpack tree.
"""

import argparse
import struct
import sys
import zlib
from pathlib import Path


class DecodeError(Exception):
    pass


FMT_NAMES = {
    0: "RGBA8888",
    1: "R8",
    2: "BC1/DXT1",
    3: "BC2/DXT3",
    4: "BC3/DXT5",
    8: "BC4",
    9: "BC5",
    10: "BC6H_UF16",
    11: "BC7",
    12: "RGBA16F",
    13: "RGBA32F",
    14: "R10G10B10A2",
    15: "R11G11B10F",
}

_HEADER = struct.Struct("< 4s f HHHH BB HIII BB 14x 8s 8s")
_MIP = struct.Struct("< I I I BB H")
_CHUNK = struct.Struct("< HH I")
_BLOCK_U32 = struct.Struct("< HHI")


# ---------------------------------------------------------------- container


def read_ftex(path):
    data = Path(path).read_bytes()
    if data[:4] != b"FTEX":
        raise DecodeError(f"{path}: not an FTEX file")
    (
        magic, version, pixel_format, width, height, depth,
        mipmap_count, nrt, flags, unk1, unk2, texture_type,
        ftexs_count, unk3, hash1, hash2,
    ) = _HEADER.unpack_from(data, 0)
    if magic != b"FTEX":
        raise DecodeError(f"{path}: bad magic")
    if not (2.025 <= version <= 2.045):
        raise DecodeError(f"{path}: unsupported FTEX version {version:.3f}")
    if ftexs_count != 0:
        raise DecodeError(f"{path}: sidecar .ftexs payload not supported")
    if mipmap_count == 0:
        raise DecodeError(f"{path}: no mipmaps")
    if pixel_format in (10, 11):
        raise DecodeError(f"{path}: BC6H/BC7 not supported (format {pixel_format})")

    mips = []
    for i in range(mipmap_count):
        offset, uncompressed_size, compressed_size, index, _ftexs, chunk_count = (
            _MIP.unpack_from(data, 64 + 16 * i))
        if index != i:
            raise DecodeError(f"{path}: mipmap index {index} != {i} at record {i}")
        mips.append((offset, uncompressed_size, compressed_size, chunk_count))
    base = 64 + 16 * mipmap_count

    return {
        "pixel_format": pixel_format,
        "width": width,
        "height": height,
        "depth": depth,
        "mips": mips,
        "base": base,
        "version": version,
        "flags": flags,
        "texture_type": texture_type,
    }


def _read_frame(info, mip_index):
    """Mip record `offset` is the ABSOLUTE file offset of the frame
    (the writer stores 64 + mips_table_size there directly). Chunk
    offsets already include the chunk array length; bit31 of the
    offset field marks a raw (uncompressed) chunk."""
    data = info["data"]
    offset, uncompressed_size, compressed_size, chunk_count = info["mips"][mip_index]
    pos = offset

    if chunk_count == 0:
        if compressed_size == 0:
            frame = data[pos:pos + uncompressed_size]
        else:
            frame = zlib.decompress(data[pos:pos + compressed_size])
        if len(frame) != uncompressed_size:
            raise DecodeError(f"frame size mismatch: got {len(frame)} want {uncompressed_size}")
        return frame

    chunk_array_len = 8 * chunk_count
    chunks = []
    for _ in range(chunk_count):
        c_comp, c_unc, c_off = _CHUNK.unpack_from(data, pos)
        chunks.append((c_off & ~(1 << 31), c_comp, c_unc, bool(c_off & (1 << 31))))
        pos += 8
    out = bytearray()
    for c_off, c_comp, c_unc, raw_chunk in chunks:
        start = offset + c_off
        take = c_unc if (raw_chunk or c_comp == c_unc) else c_comp
        blob = data[start:start + take]
        if raw_chunk or c_comp == c_unc:
            out += blob
        else:
            out += zlib.decompress(blob)
    if len(out) != uncompressed_size:
        raise DecodeError(f"chunked frame size mismatch: got {len(out)} want {uncompressed_size}")
    return bytes(out)


def _mip_dims(info, mip_index):
    return (max(1, info["width"] >> mip_index),
            max(1, info["height"] >> mip_index))


def decode_frame_rgba(info, mip_index):
    pf = info["pixel_format"]
    raw = _read_frame(info, mip_index)
    w, h = _mip_dims(info, mip_index)
    if pf == 0:
        return _rgba8888(raw, w, h), w, h
    if pf == 1:
        return _r8(raw, w, h), w, h
    if pf == 2:
        return _bc1(raw, w, h), w, h
    if pf == 3:
        return _bc2(raw, w, h), w, h
    if pf == 4:
        return _bc3(raw, w, h), w, h
    if pf == 8:
        return _bc45(raw, w, h, False), w, h
    if pf == 9:
        return _bc45(raw, w, h, True), w, h
    raise DecodeError(f"unsupported pixel format {pf}")


# ---------------------------------------------------------------- bit formats


def _rgb565(v):
    r = ((v >> 11) & 0x1F) << 3
    g = ((v >> 5) & 0x3F) << 2
    b = (v & 0x1F) << 3
    return ((r | (r >> 5)) << 0, (g | (g >> 6)) << 0, (b | (b >> 5)) << 0)


def _color_codes(c0, c1):
    """4 RGBA codes for a color pair (c0/c1 3-tuples)."""
    if c0 > c1:
        return (c0, c1,
                tuple((2 * a + b + 1) // 3 for a, b in zip(c0, c1)),
                tuple((a + 2 * b + 1) // 3 for a, b in zip(c0, c1)))
    # 4th colormap slot replaces black with opaque black when no alpha
    return (c0, c1,
            tuple((a + b) // 2 for a, b in zip(c0, c1)),
            (0, 0, 0, 0))


def _bc3_alpha_codes(a0, a1):
    if a0 > a1:
        return (a0, a1,
                (6 * a0 + 1 * a1) // 7, (5 * a0 + 2 * a1) // 7,
                (4 * a0 + 3 * a1) // 7, (3 * a0 + 4 * a1) // 7,
                (2 * a0 + 5 * a1) // 7, (1 * a0 + 6 * a1) // 7)
    return (a0, a1,
            (4 * a0 + 1 * a1) // 5, (3 * a0 + 2 * a1) // 5,
            (2 * a0 + 3 * a1) // 5, (1 * a0 + 4 * a1) // 5,
            0, 255)


def _bc1(raw, w, h):
    out = bytearray(w * h * 4)
    bw, bh = (w + 3) // 4, (h + 3) // 4
    for by in range(bh):
        for bx in range(bw):
            bo = (bx + by * bw) * 8
            if bo + 8 > len(raw):
                break
            c0v, c1v, bits = _BLOCK_U32.unpack_from(raw, bo)
            codes = _color_codes(_rgb565(c0v), _rgb565(c1v))
            opaque4 = c0v > c1v   # BC1 alpha mode: index 3 is transparent
            for py in range(4):
                yy = by * 4 + py
                if yy >= h:
                    break
                rowbase = (yy * w + bx * 4) * 4
                shift = (py % 4) * 8
                for px in range(4):
                    if bx * 4 + px >= w:
                        break
                    ci = (bits >> (shift + px * 2)) & 3
                    o = rowbase + px * 4
                    cv = codes[ci]
                    out[o:o + 3] = cv[0:3]
                    out[o + 3] = 255 if (opaque4 or ci != 3) else 0
    return out


def _bc3_alpha(raw, bo, is_bc2):
    if is_bc2:
        q = struct.unpack_from("< Q", raw, bo)[0]
        return None, q, "4bit"
    a0 = raw[bo]
    a1 = raw[bo + 1]
    if a0 == a1:
        return a0, None, "flat"
    codes = _bc3_alpha_codes(a0, a1)
    q = struct.unpack_from("< Q", raw, bo)[0] >> 16
    return codes, q, "3bit"


def _bc3(raw, w, h, is_bc2=False):
    out = bytearray(w * h * 4)
    bw, bh = (w + 3) // 4, (h + 3) // 4
    for by in range(bh):
        for bx in range(bw):
            bo = (bx + by * bw) * 16
            if bo + 16 > len(raw):
                break
            codes, q, mode = _bc3_alpha(raw, bo, is_bc2)
            c0v, c1v, bits = _BLOCK_U32.unpack_from(raw, bo + 8)
            ccodes = _color_codes(_rgb565(c0v), _rgb565(c1v))
            for py in range(4):
                yy = by * 4 + py
                if yy >= h:
                    break
                rowbase = (yy * w + bx * 4) * 4
                cshift = (py % 4) * 8
                for px in range(4):
                    if bx * 4 + px >= w:
                        break
                    n = py * 4 + px
                    if mode == "flat":
                        a = codes
                    elif mode == "4bit":
                        a = (q >> (n * 4)) & 0xF
                        a |= a << 4
                    else:
                        a = codes[(q >> (n * 3)) & 7]
                    o = rowbase + px * 4
                    cvv = ccodes[(bits >> (cshift + px * 2)) & 3]
                    out[o:o + 3] = cvv[0:3]
                    out[o + 3] = a
    return out


def _bc2(raw, w, h):
    return _bc3(raw, w, h, is_bc2=True)


def _bc45(raw, w, h, is_bc5):
    out = bytearray(w * h * 4)
    bw, bh = (w + 3) // 4, (h + 3) // 4
    for by in range(bh):
        for bx in range(bw):
            bo = (bx + by * bw) * 8
            if bo + 8 > len(raw):
                break
            a0, a1 = raw[bo], raw[bo + 1]
            if a0 == a1:
                codes, q, mode = a0, None, "flat"
            else:
                codes = _bc3_alpha_codes(a0, a1)
                q = struct.unpack_from("< Q", raw, bo)[0] >> 16
                mode = "3bit"
            for py in range(4):
                yy = by * 4 + py
                if yy >= h:
                    break
                rowbase = (yy * w + bx * 4) * 4
                for px in range(4):
                    if bx * 4 + px >= w:
                        break
                    n = py * 4 + px
                    if mode == "flat":
                        v = codes
                    else:
                        v = codes[(q >> (n * 3)) & 7]
                    o = rowbase + px * 4
                    if is_bc5:
                        out[o:o + 4] = bytes((v, 128, 128, 255))
                    else:
                        out[o:o + 4] = bytes((v, v, v, 255))
    return out


def _rgba8888(raw, w, h):
    if len(raw) < w * h * 4:
        raise DecodeError(f"RGBA frame too small: {len(raw)} < {w*h*4}")
    out = bytearray(w * h * 4)
    for o in range(0, w * h * 4, 4):
        out[o] = raw[o + 2]      # A8R8G8B8 -> bytes RGBA
        out[o + 1] = raw[o + 1]
        out[o + 2] = raw[o + 0]
        out[o + 3] = raw[o + 3]
    return out


def _r8(raw, w, h):
    need = w * h
    if len(raw) < need:
        raise DecodeError(f"R8 frame too small: {len(raw)} < {need}")
    out = bytearray(w * h * 4)
    for p, v in enumerate(raw[:need]):
        o = p * 4
        out[o:o + 4] = bytes((v, v, v, 255))
    return out


# ---------------------------------------------------------------- png


def _png_chunk(kind, payload):
    return (struct.pack(">I", len(payload)) + kind + payload +
            struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))


def encode_png_rgba(rgba, width, height):
    stride = width * 4
    rows = b"".join(b"\0" + rgba[y * stride:(y + 1) * stride]
                    for y in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + _png_chunk(b"IHDR", ihdr)
            + _png_chunk(b"IDAT", zlib.compress(rows, 6))
            + _png_chunk(b"IEND", b""))


# ---------------------------------------------------------------- resample


def box_downscale(rgba, width, height, target):
    if width % target or height % target:
        raise ValueError(
            f"{width}x{height} is not an integral multiple of {target}")
    sw, sh = width // target, height // target
    out = bytearray(target * target * 4)
    for ty in range(target):
        for tx in range(target):
            r = g = b = a = 0
            for yy in range(ty * sh, (ty + 1) * sh):
                row = yy * width * 4
                for xx in range(tx * sw, (tx + 1) * sw):
                    o = row + xx * 4
                    r += rgba[o]; g += rgba[o + 1]
                    b += rgba[o + 2]; a += rgba[o + 3]
            n = sw * sh
            o2 = (ty * target + tx) * 4
            accumulated = (r // n, g // n, b // n, a // n)
            out[o2:o2 + 4] = bytes(v & 0xFF for v in accumulated)
    return out


def pick_mip(info, target_size):
    """Prefer a mip that IS the target size (native pixels, no resample);
    else the largest mip still at least 2x the target (one clean 2x box
    pass); else the biggest available mip."""
    best = 0
    for i in range(len(info["mips"])):
        w, _h = _mip_dims(info, i)
        if w == target_size:
            return i
        if w >= target_size * 2:
            best = i
    return best


def convert(path, target_size=None, mip_index=None):
    """Return (png_bytes, width, height) for an .ftex file."""
    info = read_ftex(path)
    info["data"] = Path(path).read_bytes()
    if mip_index is None:
        if target_size is not None:
            mip_index = pick_mip(info, target_size)
        else:
            mip_index = 0
    rgba, w, h = decode_frame_rgba(info, mip_index)
    if target_size is not None and target_size != w:
        rgba = box_downscale(rgba, w, h, target_size)
        w = h = target_size
    return encode_png_rgba(rgba, w, h), w, h


# ---------------------------------------------------------------- cli


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ftex", type=Path, nargs="+")
    ap.add_argument("--output-dir", type=Path,
                    default=Path("analysis/visual-2026/ftex-png"))
    ap.add_argument("--target-size", type=int, default=None)
    ap.add_argument("--mip", type=int, default=None)
    ap.add_argument("--print-info", action="store_true")
    args = ap.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rc = 0
    for f in args.ftex:
        try:
            if args.print_info:
                info = read_ftex(f)
                fmt = FMT_NAMES.get(info["pixel_format"], info["pixel_format"])
                print(f"{f}: fmt={fmt} {info['width']}x{info['height']} "
                      f"mips={len(info['mips'])} ver={info['version']:.3f}")
            png, w, h = convert(f, target_size=args.target_size,
                                mip_index=args.mip)
            out = args.output_dir / (f.stem + ".png")
            out.write_bytes(png)
            print(f"{f} -> {out} ({w}x{h})")
        except (DecodeError, ValueError, OSError) as exc:
            print(f"{f}: ERROR {exc}", file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
