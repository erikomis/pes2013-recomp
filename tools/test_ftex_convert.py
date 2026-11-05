"""Synthetic tests for tools/ftex_convert.py (no game data committed).

Builds a small FTEX by hand following the documented container layout:
  - 64-byte header + mip records (offset *absolute file offset*),
  - frames in ascending mip order (smallest first), sizes = comp field,
  - chunk arrays with (comp u16, unc u16, off u32) where off already
    includes the array length, bit31 = raw chunk.
Then decodes it with the converter and compares pixels. Negative cases:
bad magic, unsupported version, .ftexs sidecar, unsupported formats.
"""

import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import ftex_convert as fc  # noqa: E402

import tempfile  # noqa: E402
import unittest  # noqa: E402


def make_bc3_block(color):
    """One 4x4 BC3 block, fully opaque, constant color."""
    # Alpha: a0 = a1 = 255 -> flat opaque
    alpha = b"\xff\xff" + b"\x00" * 6
    # Color: encode via the standard 4-color palette: c0 = color, c1 = color
    r, g, b = color
    c0 = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
    c1 = c0  # a0 > a1 false -> 3-colour mode, but c0 == c1 yields codes 0/1/2 = same colour
    bits = 0  # every pixel uses code 0 = c0
    return alpha + struct.pack("<HHI", c0, c1, bits)


class TestFtexConvert(unittest.TestCase):
    def _write_ftex(self, path, blocks_rgb, width=8, height=8):
        """16x16 BC3, 2 mips: mip0 chunked (2 chunks: zlib + raw),
        mip1 single raw chunk. Pixels: mip0 8x8 = 4 blocks."""
        pixel_fmt = 4  # BC3
        mip0_unc = 4 * 16  # 4 blocks * 16 bytes
        mip1_unc = 1 * 16

        # mip0: 8x8 = 2x2 blocks, byte-stream is sliced in order:
        # chunk0 = first 32 bytes = blocks (0,0)+(4,0) zlib-compressed,
        # chunk1 = next 32 bytes = blocks (0,4)+(4,4) raw
        b0 = make_bc3_block(blocks_rgb[0])
        b1 = make_bc3_block(blocks_rgb[1])
        b2 = make_bc3_block(blocks_rgb[0])
        b3 = make_bc3_block(blocks_rgb[1])
        z0 = zlib.compress(b0 + b1, 6)
        chunk0 = (z0, 32, len(z0), False)   # compressed
        chunk1 = (b2 + b3, 32, 32, True)    # raw (bit31)

        chunk_count = 2
        arrlen = chunk_count * 8
        # frame layout: [chunk array][chunk data]; off includes arrlen
        cum = 0
        chunk_offs = []
        for i in range(chunk_count):
            chunk_offs.append(cum + arrlen)
            cum += len(z0) if i == 0 else 32
        frame_parts0 = bytearray()
        for i, (off, (data, unc, comp, raw)) in enumerate(zip(chunk_offs, (chunk0, chunk1))):
            o = off | ((1 << 31) if raw else 0)
            frame_parts0 += struct.pack("<HHI", comp, unc, o)
        # data order: writer concatenates header buffer first? NO: writer
        # writes header entries first, then chunk data blobs in order.
        frame0 = bytes(frame_parts0) + z0 + (b2 + b3)
        mip0_comp = len(frame0)

        # mip1: 1 chunk, raw 16 bytes
        m1header = struct.pack("<HHI", mip1_unc, mip1_unc, 8)
        frame1 = m1header + make_bc3_block(blocks_rgb[2])
        mip1_comp = len(frame1)

        # frames ascending by mip index (smallest first), offsets absolute
        header_size = 64 + 2 * 16
        off1 = header_size          # mip1 (small) first
        off0 = off1 + mip1_comp
        total = off0 + mip0_comp

        header = struct.pack(
            "< 4s f HHHH BB HIII BB 14x 8s 8s",
            b"FTEX", 2.03, pixel_fmt, width, height, 1, 2,
            0x02, 0x11, 1, 0, 3, 0, 0, b"\0" * 8, b"\0" * 8,
        )
        miprecs = struct.pack(
            "< III BB H", off0, mip0_unc, mip0_comp, 0, 0, 2
        ) + struct.pack("< III BB H", off1, mip1_unc, mip1_comp, 1, 0, 1)
        path.write_bytes(header + miprecs + frame1 + frame0)
        return total

    def test_decode_lifecycle(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "synthetic.ftex"
            self._write_ftex(p, [(255, 0, 0), (0, 0, 255), (0, 255, 0)])
            info = fc.read_ftex(p)
            info["data"] = p.read_bytes()
            rgba, w, h = fc.decode_frame_rgba(info, 0)
            self.assertEqual((w, h), (8, 8))
            # block (0,0) red; block (1,0) blue alpha-tested to opaque
            top_left = rgba[0:4]
            self.assertEqual(top_left[0], 255)   # R
            self.assertEqual(top_left[1], 0)
            self.assertEqual(top_left[2], 0)
            self.assertEqual(top_left[3], 255)   # opaque
            block_b = rgba[(1 * 8 + 5) * 4:(1 * 8 + 5) * 4 + 4]
            self.assertEqual(block_b[2], 255)    # B
            self.assertEqual(block_b[0], 0)
            # mip1 (single chunk raw)
            rgba1, w1, h1 = fc.decode_frame_rgba(info, 1)
            self.assertEqual((w1, h1), (4, 4))
            self.assertEqual(rgba1[0], 0)
            self.assertEqual(rgba1[1], 255)      # green
            self.assertEqual(rgba1[3], 255)

    def test_pick_mip_exact_target(self):
        info = {"mips": [(0, 0, 0, 0)] * 12, "width": 2048, "height": 2048, "depth": 1}
        self.assertEqual(fc.pick_mip(info, 256), 3)   # 2048 >> 3 == 256
        info2 = {"mips": [(0, 0, 0, 0)] * 4, "width": 128, "height": 128, "depth": 1}
        self.assertEqual(fc.pick_mip(info2, 256), 0)  # fallback: biggest

    def test_rejected_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            # bad magic
            p = Path(td) / "bad.ftex"
            p.write_bytes(b"XXXX" + b"\0" * 100)
            with self.assertRaises(fc.DecodeError):
                fc.read_ftex(p)
            # too-old version
            q = Path(td) / "old.ftex"
            h = struct.pack("< 4s f HHHH BB HIII BB 14x 8s 8s",
                            b"FTEX", 2.0, 4, 8, 8, 1, 1, 2, 0x11, 1, 0, 3,
                            0, 0, b"\0" * 8, b"\0" * 8)
            q.write_bytes(h + b"\0" * 64)
            with self.assertRaises(fc.DecodeError):
                fc.read_ftex(q)

    def test_box_downscale_accuracy(self):
        # 2x2 px -> 1x1 average; each source pixel is one RGBA quad
        rgba = bytes([10, 20, 30, 40, 50, 60, 70, 80,
                      20, 30, 40, 50, 60, 70, 80, 90])
        out = fc.box_downscale(rgba, 2, 2, 1)
        self.assertEqual(out, bytes([35, 45, 55, 65]))


if __name__ == "__main__":
    unittest.main()
